/*!
 * faq-chatbot widget: jeden plik, bez zależności.
 *
 * Osadzenie:
 *   <script src="https://twoj-serwer/widget/chat.js" data-tenant="salon"></script>
 *
 * Atrybuty (opcjonalne): data-api (domyślnie origin skryptu), data-title,
 * data-greeting, data-placeholder, data-max-chars (domyślnie 500).
 */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) return;

  var tenant = script.getAttribute("data-tenant");
  if (!tenant) {
    console.error("faq-chatbot: brak atrybutu data-tenant");
    return;
  }

  var api = (script.getAttribute("data-api") || new URL(script.src, location.href).origin).replace(/\/+$/, "");
  var title = script.getAttribute("data-title") || "Zapytaj asystenta";
  var greeting = script.getAttribute("data-greeting") || "Cześć! W czym mogę pomóc?";
  var placeholder = script.getAttribute("data-placeholder") || "Napisz pytanie…";
  var maxChars = parseInt(script.getAttribute("data-max-chars") || "500", 10);
  var HISTORY_LIMIT = 12;
  var GENERIC_ERROR = "Coś poszło nie tak. Spróbuj ponownie za chwilę.";

  // Tylko jeden widget na stronie: nowy zastępuje poprzedni.
  var old = document.getElementById("faq-chatbot-host");
  if (old) old.remove();

  var host = document.createElement("div");
  host.id = "faq-chatbot-host";
  var root = host.attachShadow({ mode: "open" });

  var style = document.createElement("style");
  style.textContent = [
    ":host{all:initial}",
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}",
    ".fab{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;border:0;",
    "background:#2f5d50;color:#fff;font-size:26px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25);z-index:2147483000}",
    ".fab:focus-visible,button:focus-visible,textarea:focus-visible{outline:3px solid #f2b705;outline-offset:2px}",
    ".panel{position:fixed;right:20px;bottom:88px;width:340px;max-width:calc(100vw - 32px);height:480px;",
    "max-height:calc(100vh - 110px);background:#fff;color:#1d2521;border-radius:14px;display:none;flex-direction:column;",
    "box-shadow:0 10px 36px rgba(0,0,0,.28);overflow:hidden;z-index:2147483000}",
    ".panel.open{display:flex}",
    ".head{background:#2f5d50;color:#fff;padding:12px 14px;font-weight:600;display:flex;justify-content:space-between;align-items:center}",
    ".head button{background:none;border:0;color:#fff;font-size:20px;cursor:pointer;line-height:1}",
    ".log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f4f6f5}",
    ".msg{max-width:86%;padding:8px 11px;border-radius:12px;font-size:14px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word}",
    ".bot{background:#fff;border:1px solid #dfe5e2;align-self:flex-start}",
    ".user{background:#2f5d50;color:#fff;align-self:flex-end}",
    ".err{background:#fdecea;border:1px solid #f1b9b3;color:#7a1f16;align-self:flex-start}",
    ".form{display:flex;gap:8px;padding:10px;border-top:1px solid #dfe5e2;background:#fff}",
    "textarea{flex:1;resize:none;border:1px solid #c5cec9;border-radius:8px;padding:8px;font-size:14px;height:40px}",
    ".send{border:0;background:#2f5d50;color:#fff;border-radius:8px;padding:0 14px;font-size:14px;cursor:pointer}",
    ".send:disabled{opacity:.5;cursor:default}",
    ".note{font-size:11px;color:#5d6b64;text-align:center;padding:0 10px 8px;background:#fff}",
    "@media (prefers-color-scheme:dark){.panel,.form,.note{background:#1c2320;color:#e8eeeb;border-color:#33403a}",
    ".log{background:#141a17}.bot{background:#232d29;border-color:#33403a;color:#e8eeeb}",
    "textarea{background:#141a17;color:#e8eeeb;border-color:#3d4b44}.note{color:#9aaaa2}}"
  ].join("");

  var fab = el("button", "fab", "💬");
  fab.setAttribute("aria-label", "Otwórz czat");
  fab.setAttribute("aria-expanded", "false");

  var panel = el("div", "panel");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", title);

  var head = el("div", "head");
  head.appendChild(el("span", "", title));
  var close = el("button", "", "×");
  close.setAttribute("aria-label", "Zamknij czat");
  head.appendChild(close);

  var log = el("div", "log");
  log.setAttribute("role", "log");
  log.setAttribute("aria-live", "polite");

  var form = el("form", "form");
  var input = document.createElement("textarea");
  input.placeholder = placeholder;
  input.maxLength = maxChars;
  input.setAttribute("aria-label", "Twoja wiadomość");
  var send = el("button", "send", "Wyślij");
  send.type = "submit";
  form.appendChild(input);
  form.appendChild(send);

  var note = el("div", "note", "Asystent AI. Odpowiada na podstawie dokumentów firmy i może się mylić.");

  panel.appendChild(head);
  panel.appendChild(log);
  panel.appendChild(form);
  panel.appendChild(note);
  root.appendChild(style);
  root.appendChild(fab);
  root.appendChild(panel);
  document.body.appendChild(host);

  var history = [];
  var busy = false;

  addMessage("bot", greeting);

  fab.addEventListener("click", function () {
    toggle(!panel.classList.contains("open"));
  });
  close.addEventListener("click", function () {
    toggle(false);
  });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text || busy) return;
    input.value = "";
    ask(text);
  });

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text; // zawsze textContent, nigdy innerHTML
    return node;
  }

  function toggle(open) {
    panel.classList.toggle("open", open);
    fab.setAttribute("aria-expanded", String(open));
    if (open) input.focus();
  }

  function addMessage(kind, text) {
    var node = el("div", "msg " + kind, text);
    log.appendChild(node);
    log.scrollTop = log.scrollHeight;
    return node;
  }

  function setBusy(value) {
    busy = value;
    send.disabled = value;
  }

  function ask(text) {
    addMessage("user", text);
    var typing = addMessage("bot", "…");
    setBusy(true);

    fetch(api + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant: tenant,
        message: text,
        history: history.slice(-HISTORY_LIMIT)
      })
    })
      .then(function (res) {
        return res
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            return { ok: res.ok, data: data };
          });
      })
      .then(function (r) {
        typing.remove();
        if (r.ok && typeof r.data.reply === "string") {
          addMessage("bot", r.data.reply);
          history.push({ role: "user", content: text });
          history.push({ role: "assistant", content: r.data.reply });
        } else {
          // detail bywa tekstem (nasze błędy) albo listą (walidacja): listę pomijamy.
          var detail = typeof r.data.detail === "string" ? r.data.detail : GENERIC_ERROR;
          addMessage("err", detail);
        }
      })
      .catch(function () {
        typing.remove();
        addMessage("err", "Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.");
      })
      .then(function () {
        setBusy(false);
        input.focus();
      });
  }
})();
