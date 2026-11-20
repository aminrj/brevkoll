import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_ocr import png_bytes, which

from app.main import create_app
from app.ocr import TesseractOcr


@pytest.mark.usefixtures("env")
def test_ocr_timeout_gives_generic_502(tmp_path: Path) -> None:
    def boom(args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(args, 30, output=b"secret letter text")

    ocr = TesseractOcr(run=boom, which=which, tmp_root=tmp_path)
    client = TestClient(create_app(ocr=ocr), raise_server_exceptions=False)
    r = client.post("/api/decode", files={"file": ("a.png", png_bytes(), "image/png")})
    assert r.status_code == 502
    assert r.json() == {"error": "Could not read the letter."}
    assert "secret" not in r.text
