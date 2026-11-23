from collections.abc import Callable

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import post

Make = Callable[..., TestClient]


# I8
def test_ac8_fourth_request_gets_429(make_client: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    client = make_client()
    assert [post(client).status_code for _ in range(3)] == [200, 200, 200]
    r = post(client)
    assert r.status_code == 429
    assert set(r.json()) == {"error"}


def test_fresh_app_has_fresh_limiter(make_client: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    assert post(make_client()).status_code == 200
    assert post(make_client()).status_code == 200


def test_rate_limit_applies_before_body_is_read(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    client = make_client()
    assert post(client).status_code == 200
    assert client.post("/api/decode", content=b"not multipart").status_code == 429


def test_spoofed_forwarded_for_does_not_bypass(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    client = make_client()
    assert post(client).status_code == 200
    r = client.post("/api/decode", headers={"X-Forwarded-For": "8.8.8.8"}, content=b"x")
    assert r.status_code == 429


# I8
def test_budget_exhausted_gives_503_and_model_not_called(
    make_client: Make, env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAILY_MODEL_CALL_BUDGET", "1")
    client = make_client()
    assert post(client).status_code == 200
    calls = len(env.payloads())
    assert post(client).status_code == 503
    assert len(env.payloads()) == calls
