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
