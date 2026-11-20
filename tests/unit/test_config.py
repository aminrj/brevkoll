from pathlib import Path

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import FakeOcr, post

from app.config import ConfigError, load_settings
from app.main import create_app


def test_defaults() -> None:
    s = load_settings({})
    assert s.llm_provider == "fake"
    assert s.app_env == "dev"
    assert s.rate_limit_per_minute == 10
    assert s.daily_model_call_budget == 200
    assert s.trusted_proxies == ()
    assert s.fake_llm_log is None


def test_values_are_read() -> None:
    s = load_settings(
        {
            "RATE_LIMIT_PER_MINUTE": "3",
            "TRUSTED_PROXIES": "10.0.0.1, 10.0.0.2",
            "FAKE_LLM_LOG": "/x/log",
            "APP_DATA_DIR": "/d",
        }
    )
    assert s.rate_limit_per_minute == 3
    assert s.trusted_proxies == ("10.0.0.1", "10.0.0.2")
    assert s.fake_llm_log == Path("/x/log")
    assert s.app_data_dir == Path("/d")


def test_bad_integer_is_config_error() -> None:
    with pytest.raises(ConfigError):
        load_settings({"RATE_LIMIT_PER_MINUTE": "many"})


def test_fake_provider_refused_in_prod(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(ConfigError):
        create_app()


def test_fake_provider_allowed_in_dev_and_test(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("dev", "test"):
        monkeypatch.setenv("APP_ENV", name)
        create_app()


def test_unknown_provider_fails_at_creation(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ConfigError):
        create_app()


def test_env_is_read_at_creation_time(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_LLM_RESPONSE", '{"summary": "first", "actions": []}')
    first = TestClient(create_app(ocr=FakeOcr()))
    monkeypatch.setenv("FAKE_LLM_RESPONSE", '{"summary": "second", "actions": []}')
    second = TestClient(create_app(ocr=FakeOcr()))
    assert post(first).json()["summary"] == "first"
    assert post(second).json()["summary"] == "second"
