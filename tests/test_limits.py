from datetime import date
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.limits import DailyBudget, RateLimiter, cost_usd


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


def test_rate_limiter_blocks_after_limit():
    clock = FakeClock()
    rl = RateLimiter(max_per_minute=3, clock=clock)

    assert [rl.allow("1.1.1.1") for _ in range(4)] == [True, True, True, False]


def test_rate_limiter_window_slides():
    clock = FakeClock()
    rl = RateLimiter(max_per_minute=2, clock=clock)
    rl.allow("a")
    rl.allow("a")
    assert rl.allow("a") is False

    clock.now = 61
    assert rl.allow("a") is True


def test_rate_limiter_keys_are_independent():
    rl = RateLimiter(max_per_minute=1, clock=FakeClock())
    assert rl.allow("a") is True
    assert rl.allow("b") is True
    assert rl.allow("a") is False


def test_rate_limiter_forgets_idle_keys():
    clock = FakeClock()
    rl = RateLimiter(max_per_minute=1, clock=clock)
    rl.allow("a")
    clock.now = 120
    rl.allow("b")
    assert "a" not in rl._hits


def test_daily_budget_blocks_when_exhausted():
    budget = DailyBudget(limit_usd=0.10, today=lambda: date(2026, 11, 12))
    assert budget.can_spend() is True
    budget.record(0.06)
    assert budget.can_spend() is True
    budget.record(0.05)
    assert budget.can_spend() is False


def test_daily_budget_resets_next_day():
    day = {"d": date(2026, 11, 12)}
    budget = DailyBudget(limit_usd=0.10, today=lambda: day["d"])
    budget.record(0.20)
    assert budget.can_spend() is False

    day["d"] = date(2026, 11, 13)
    assert budget.can_spend() is True
    assert budget.spent == 0


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    return Settings(_env_file=None)


def test_cost_usd_counts_all_token_kinds(settings):
    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    # 0.10 + 0.50 + 0.10*1.25 + 0.10*0.10
    assert cost_usd(usage, settings) == pytest.approx(0.735)


def test_cost_usd_handles_missing_cache_fields(settings):
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=100,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )
    assert cost_usd(usage, settings) == pytest.approx(0.0001 + 0.00005)
