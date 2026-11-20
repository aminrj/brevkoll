import json
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FakeOcr

from app.main import create_app


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.data_dir = tmp_path / "data"
        self.data_dir.mkdir()
        self.tmp_dir = tmp_path / "tmp"
        self.tmp_dir.mkdir()
        self.log = tmp_path / "fake_llm.jsonl"

    def payloads(self) -> list[str]:
        if not self.log.exists():
            return []
        return [json.loads(line)["payload"] for line in self.log.read_text().splitlines()]


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    e = Env(tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", str(e.tmp_dir))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("APP_DATA_DIR", str(e.data_dir))
    monkeypatch.setenv("FAKE_LLM_LOG", str(e.log))
    monkeypatch.delenv("FAKE_LLM_RESPONSE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    return e


@pytest.fixture
def make_client(env: Env) -> Callable[..., TestClient]:
    def make(ocr: FakeOcr | None = None) -> TestClient:
        app = create_app(ocr=ocr if ocr is not None else FakeOcr())
        return TestClient(app, raise_server_exceptions=False)

    return make
