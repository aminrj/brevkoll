from collections import deque
from collections.abc import Callable, Sequence
from datetime import date, datetime
from threading import Lock

from app.errors import BudgetExhausted, RateLimited
from app.llm import LLMClient

_WINDOW_S = 60.0
_SWEEP_ABOVE = 1024  # sweep expired keys once the table grows past this


class SlidingWindowLimiter:
    def __init__(self, per_minute: int, clock: Callable[[], float]) -> None:
        self._limit = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            if len(self._hits) > _SWEEP_ABOVE:
                self._sweep(now)
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - _WINDOW_S:
                hits.popleft()
            if len(hits) >= self._limit:
                raise RateLimited()
            hits.append(now)

    def size(self) -> int:
        return len(self._hits)

    def _sweep(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or h[-1] <= now - _WINDOW_S]:
            del self._hits[key]


class DailyBudget:
    def __init__(self, limit: int, clock: Callable[[], datetime]) -> None:
        self._limit = limit
        self._clock = clock
        self._day: date | None = None
        self._used = 0
        self._lock = Lock()

    def consume(self) -> None:
        with self._lock:
            today = self._clock().date()
            if today != self._day:
                self._day = today
                self._used = 0
            if self._used >= self._limit:
                raise BudgetExhausted()
            self._used += 1


class BudgetedLLM:
    """Spends one unit of the daily budget before each model call."""

    def __init__(self, inner: LLMClient, budget: DailyBudget) -> None:
        self._inner = inner
        self._budget = budget

    def complete(self, prompt: str, *, max_tokens: int, timeout: float) -> str:
        self._budget.consume()
        return self._inner.complete(prompt, max_tokens=max_tokens, timeout=timeout)


def client_ip(peer: str | None, forwarded_for: str | None, trusted: Sequence[str]) -> str:
    """The peer, unless it is a trusted proxy; then the right-most untrusted forwarded entry."""
    if peer is None:
        return "unknown"
    if peer not in trusted or not forwarded_for:
        return peer
    for entry in reversed([e.strip() for e in forwarded_for.split(",")]):
        if entry and entry not in trusted:
            return entry
    return peer
