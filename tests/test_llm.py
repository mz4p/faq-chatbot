import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.config import Settings
from app.llm import AnthropicLLM, ChatError, OpenAICompatLLM, create_llm


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    return Settings(_env_file=None)


def compat_settings(model="anthropic/claude-haiku-5.5"):
    return Settings(
        _env_file=None,
        llm_provider="openai_compatible",
        llm_api_key="secret",
        llm_base_url="https://api.example/v1/",
        model=model,
    )


# ---------- Anthropic ----------

class FakeAnthropic:
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


def anthropic_reply(blocks, stop_reason="end_turn"):
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=20,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=5,
    )
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, usage=usage)


def test_anthropic_request_shape_and_usage(settings):
    client = FakeAnthropic(anthropic_reply([SimpleNamespace(type="text", text="Odp")]))

    out = AnthropicLLM(client, settings).complete("SYSTEM", [{"role": "user", "content": "?"}])

    call = client.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"] == {"effort": "low"}
    assert call["system"] == [
        {"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}
    ]
    assert "temperature" not in call
    assert out.text == "Odp" and out.refused is False
    assert (out.usage.input_tokens, out.usage.cache_read_input_tokens) == (100, 5)
    assert out.usage.cache_creation_input_tokens == 0


def test_anthropic_ignores_thinking_blocks_and_flags_refusal(settings):
    blocks = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="X")]
    out = AnthropicLLM(FakeAnthropic(anthropic_reply(blocks, "refusal")), settings).complete("s", [])
    assert out.text == "X" and out.refused is True


def test_anthropic_api_error_becomes_chat_error(settings):
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "http://x"))
    with pytest.raises(ChatError):
        AnthropicLLM(FakeAnthropic(error=error), settings).complete("s", [])


# ---------- OpenAI-compatible ----------

def compat_llm(handler, model="anthropic/claude-haiku-5.5"):
    s = compat_settings(model)
    http = httpx2.Client(
        base_url="https://api.example/v1",
        transport=httpx2.MockTransport(handler),
    )
    return OpenAICompatLLM(http, s)


def ok(content="Odp", usage=None, finish="stop", **message):
    return {
        "choices": [
            {"finish_reason": finish, "message": {"role": "assistant", "content": content, **message}}
        ],
        "usage": usage or {"prompt_tokens": 1000, "completion_tokens": 50},
    }


def test_compat_request_shape_for_anthropic_models():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=ok())

    out = compat_llm(handler).complete("SYSTEM", [{"role": "user", "content": "?"}])

    assert seen["url"] == "https://api.example/v1/chat/completions"
    body = seen["body"]
    assert body["model"] == "anthropic/claude-haiku-5.5"
    assert body["reasoning_effort"] == "low"
    assert body["messages"][0] == {
        "role": "system",
        "content": [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}],
    }
    assert body["messages"][1] == {"role": "user", "content": "?"}
    assert out.text == "Odp"


def test_compat_plain_system_string_for_other_models():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=ok())

    compat_llm(handler, model="deepseek/deepseek-v4-flash").complete("SYSTEM", [])
    assert seen["body"]["messages"][0] == {"role": "system", "content": "SYSTEM"}


def test_compat_usage_separates_cached_tokens():
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 40,
        "prompt_tokens_details": {"cached_tokens": 600, "cache_write_tokens": 100},
    }
    out = compat_llm(lambda r: httpx2.Response(200, json=ok(usage=usage))).complete("s", [])
    u = out.usage
    assert (u.input_tokens, u.cache_read_input_tokens, u.cache_creation_input_tokens) == (300, 600, 100)
    assert u.output_tokens == 40


def test_compat_flags_refusal():
    for payload in (ok("", refusal="odmowa"), ok("", finish="content_filter")):
        out = compat_llm(lambda r, p=payload: httpx2.Response(200, json=p)).complete("s", [])
        assert out.refused is True


def test_compat_accepts_list_content():
    payload = ok([{"type": "text", "text": "A"}, {"type": "text", "text": "B"}])
    out = compat_llm(lambda r: httpx2.Response(200, json=payload)).complete("s", [])
    assert out.text == "AB"


def test_compat_retries_once_on_5xx_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(503) if len(calls) == 1 else httpx2.Response(200, json=ok())

    assert compat_llm(handler).complete("s", []).text == "Odp"
    assert len(calls) == 2


def test_compat_gives_up_after_second_5xx():
    with pytest.raises(ChatError):
        compat_llm(lambda r: httpx2.Response(500)).complete("s", [])


def test_compat_4xx_is_not_retried_and_hides_nothing_secret():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(401, json={"error": "bad key"})

    with pytest.raises(ChatError) as exc:
        compat_llm(handler).complete("s", [])
    assert len(calls) == 1
    assert "secret" not in str(exc.value)


def test_compat_network_error_becomes_chat_error():
    def handler(request):
        raise httpx2.ConnectError("boom")

    with pytest.raises(ChatError):
        compat_llm(handler).complete("s", [])


def test_compat_malformed_response_becomes_chat_error():
    with pytest.raises(ChatError):
        compat_llm(lambda r: httpx2.Response(200, json={"choices": []})).complete("s", [])
    with pytest.raises(ChatError):
        compat_llm(lambda r: httpx2.Response(200, text="<html>")).complete("s", [])


# ---------- fabryka ----------

def test_create_llm_picks_provider(settings):
    assert isinstance(create_llm(settings), AnthropicLLM)
    assert isinstance(create_llm(compat_settings()), OpenAICompatLLM)
