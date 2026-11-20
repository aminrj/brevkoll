from datetime import datetime, timedelta

import pytest

from app.errors import BudgetExhausted, RateLimited
from app.limits import DailyBudget, SlidingWindowLimiter, client_ip


class Ticker:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_fourth_call_in_a_minute_raises() -> None:
    limiter = SlidingWindowLimiter(3, Ticker())
    for _ in range(3):
        limiter.check("a")
    with pytest.raises(RateLimited):
        limiter.check("a")


def test_keys_are_independent_and_window_slides() -> None:
    t = Ticker()
    limiter = SlidingWindowLimiter(1, t)
    limiter.check("a")
    limiter.check("b")
    with pytest.raises(RateLimited):
        limiter.check("a")
    t.now += 61
    limiter.check("a")


def test_old_keys_are_pruned() -> None:
    t = Ticker()
    limiter = SlidingWindowLimiter(1, t)
    for i in range(3000):
        limiter.check(f"ip{i}")
    t.now += 61
    limiter.check("fresh")
    assert limiter.size() < 2000


def test_budget_exhausts_and_resets_next_day() -> None:
    now = [datetime(2026, 12, 1, 10, 0)]
    budget = DailyBudget(2, lambda: now[0])
    budget.consume()
    budget.consume()
    with pytest.raises(BudgetExhausted):
        budget.consume()
    now[0] = now[0] + timedelta(days=1)
    budget.consume()


def test_client_ip_ignores_spoofed_header_from_untrusted_peer() -> None:
    assert client_ip("1.2.3.4", "9.9.9.9", ["10.0.0.1"]) == "1.2.3.4"
    assert client_ip("1.2.3.4", "9.9.9.9", []) == "1.2.3.4"


def test_client_ip_honors_trusted_peer_rightmost_untrusted() -> None:
    assert client_ip("10.0.0.1", "6.6.6.6, 5.5.5.5", ["10.0.0.1"]) == "5.5.5.5"
    trusted = ["10.0.0.1", "10.0.0.2"]
    assert client_ip("10.0.0.1", "6.6.6.6, 5.5.5.5, 10.0.0.2", trusted) == "5.5.5.5"


def test_client_ip_trusted_peer_without_header_and_missing_peer() -> None:
    assert client_ip("10.0.0.1", None, ["10.0.0.1"]) == "10.0.0.1"
    assert client_ip(None, None, []) == "unknown"
