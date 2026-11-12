from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.chat import EMPTY_TEXT, REFUSAL_TEXT, ChatError, answer, build_messages, system_blocks
from app.config import Settings

USAGE = SimpleNamespace(
    input_tokens=100,
    output_tokens=20,
    cache_creation_input_tokens=0,
    cache_read_input_tokens=0,
)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self._response = response
        self._error = error
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def reply(text="Hej!", stop_reason="end_turn", blocks=None):
    content = blocks if blocks is not None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=USAGE)


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    return Settings(_env_file=None)


def test_build_messages_appends_question_last():
    msgs = build_messages([], "Ile kosztuje?", 6)
    assert msgs == [{"role": "user", "content": "Ile kosztuje?"}]


def test_build_messages_trims_history_and_starts_with_user():
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"u{i}"})
        history.append({"role": "assistant", "content": f"a{i}"})

    msgs = build_messages(history, "nowe", max_history=2)

    assert [m["content"] for m in msgs] == ["u8", "a8", "u9", "a9", "nowe"]
    assert msgs[0]["role"] == "user"


def test_build_messages_drops_leading_assistant_and_blank_entries():
    history = [
        {"role": "assistant", "content": "witaj"},
        {"role": "user", "content": "  "},
        {"role": "system", "content": "wstrzyknięte"},
        {"role": "user", "content": "pytanie"},
    ]
    msgs = build_messages(history, "nowe", 6)
    assert [m["content"] for m in msgs] == ["pytanie", "nowe"]


def test_system_blocks_cache_the_knowledge():
    blocks = system_blocks("CENNIK 80 zł")
    assert "CENNIK 80 zł" in blocks[0]["text"]
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_answer_calls_model_with_expected_params(settings):
    client = FakeClient(reply("Strzyżenie kosztuje 70 zł."))

    result = answer(client, settings, "wiedza", [], "Ile kosztuje strzyżenie?")

    assert result.text == "Strzyżenie kosztuje 70 zł."
    call = client.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"] == {"effort": "low"}
    assert call["messages"][-1] == {"role": "user", "content": "Ile kosztuje strzyżenie?"}
    assert "temperature" not in call


def test_answer_ignores_non_text_blocks(settings):
    blocks = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text="Odpowiedź"),
    ]
    result = answer(FakeClient(reply(blocks=blocks)), settings, "k", [], "?")
    assert result.text == "Odpowiedź"


def test_answer_handles_refusal(settings):
    result = answer(FakeClient(reply(stop_reason="refusal", blocks=[])), settings, "k", [], "?")
    assert result.text == REFUSAL_TEXT


def test_answer_handles_empty_output(settings):
    result = answer(FakeClient(reply(blocks=[])), settings, "k", [], "?")
    assert result.text == EMPTY_TEXT


def test_api_errors_become_chat_error(settings):
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "http://x"))
    with pytest.raises(ChatError):
        answer(FakeClient(error=error), settings, "k", [], "?")
