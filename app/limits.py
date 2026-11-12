"""Limity chroniące publiczne demo przed nadużyciem i niekontrolowanym kosztem.

Stan jest trzymany w pamięci procesu, więc limity działają poprawnie przy jednej instancji.
Przy wielu instancjach trzeba by je przenieść do wspólnego magazynu (np. Redis).
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import date

from .config import Settings

WINDOW_SECONDS = 60.0


class RateLimiter:
    """Okno przesuwne: maksymalnie `max_per_minute` zapytań na klucz (np. adres IP)."""

    def __init__(self, max_per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.max = max_per_minute
        self.clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        self._forget_idle(now)
        hits = self._hits[key]
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= self.max:
            return False
        hits.append(now)
        return True

    def _forget_idle(self, now: float) -> None:
        idle = [k for k, h in self._hits.items() if not h or now - h[-1] >= WINDOW_SECONDS]
        for k in idle:
            del self._hits[k]


class DailyBudget:
    """Dzienny twardy limit wydatków (USD), zerowany po zmianie daty."""

    def __init__(self, limit_usd: float, today: Callable[[], date] = date.today):
        self.limit = limit_usd
        self.today = today
        self.spent = 0.0
        self._day = today()

    def _roll(self) -> None:
        current = self.today()
        if current != self._day:
            self._day = current
            self.spent = 0.0

    def can_spend(self) -> bool:
        self._roll()
        return self.spent < self.limit

    def record(self, cost: float) -> None:
        self._roll()
        self.spent += cost


def cost_usd(usage, settings: Settings) -> float:
    """Koszt jednego wywołania na podstawie `response.usage`."""
    per_token_in = settings.price_input_per_mtok / 1_000_000
    per_token_out = settings.price_output_per_mtok / 1_000_000
    cache_write = usage.cache_creation_input_tokens or 0
    cache_read = usage.cache_read_input_tokens or 0
    return (
        (usage.input_tokens or 0) * per_token_in
        + (usage.output_tokens or 0) * per_token_out
        + cache_write * per_token_in * settings.cache_write_multiplier
        + cache_read * per_token_in * settings.cache_read_multiplier
    )
