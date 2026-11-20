from collections.abc import Callable

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import PNG, post

Make = Callable[..., TestClient]


def _assert_clean(env: Env) -> None:
    assert list(env.data_dir.iterdir()) == []
    assert list(env.tmp_dir.iterdir()) == []


def test_empty_after_success(make_client: Make, env: Env) -> None:
    assert post(make_client()).status_code == 200
    _assert_clean(env)


def test_empty_after_415(make_client: Make, env: Env) -> None:
    assert post(make_client(), b"plain text").status_code == 415
    _assert_clean(env)


def test_empty_after_model_error(
    make_client: Make, env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_LLM_RESPONSE", "garbage")
    assert post(make_client()).status_code == 502
    _assert_clean(env)


def test_empty_after_large_upload(make_client: Make, env: Env) -> None:
    # Big enough that the multipart parser spools to a temp file.
    assert post(make_client(), PNG + b"\x00" * (2 * 1024 * 1024)).status_code == 200
    _assert_clean(env)
