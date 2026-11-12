import pytest
from pydantic import ValidationError

from app.config import Settings


def test_missing_api_key_stops_startup(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_empty_api_key_stops_startup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_defaults_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    s = Settings(_env_file=None)
    assert s.model == "claude-haiku-5-5"
    assert s.max_history == 6
    assert s.daily_budget_usd == 0.30


def test_openai_compatible_requires_key_and_base_url(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="openai_compatible", llm_api_key="k")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="openai_compatible", llm_base_url="http://x/v1")


def test_openai_compatible_does_not_need_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = Settings(
        _env_file=None,
        llm_provider="openai_compatible",
        llm_api_key="k",
        llm_base_url="http://x/v1",
    )
    assert s.llm_provider == "openai_compatible"


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="cos-innego")
