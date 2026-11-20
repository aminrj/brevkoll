import asyncio
import io
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from helpers import PNG, post

from app.errors import TooLarge, UnsupportedMedia
from app.upload import MAX_BYTES, read_limited, sniff_kind


def test_sniff_kinds() -> None:
    assert sniff_kind(PNG) == "png"
    assert sniff_kind(b"\xff\xd8\xff\xe0abc") == "jpeg"
    assert sniff_kind(b"%PDF-1.7 abc") == "pdf"


def test_sniff_rejects_other() -> None:
    with pytest.raises(UnsupportedMedia):
        sniff_kind(b"hello, I am text")
    with pytest.raises(UnsupportedMedia):
        sniff_kind(b"")


def test_read_limited_rejects_over_limit() -> None:
    f = UploadFile(io.BytesIO(b"a" * 11), size=11)
    with pytest.raises(TooLarge):
        asyncio.run(read_limited(f, max_bytes=10))
    ok = UploadFile(io.BytesIO(b"a" * 10), size=10)
    assert asyncio.run(read_limited(ok, max_bytes=10)) == b"a" * 10


def test_png_bytes_with_pdf_name_is_accepted_by_content_not_name(
    make_client: Callable[..., TestClient],
) -> None:
    assert post(make_client(), PNG, name="letter.pdf").status_code == 200


def test_pdf_name_with_text_content_is_415(make_client: Callable[..., TestClient]) -> None:
    r = post(make_client(), b"just some text", name="letter.pdf")
    assert r.status_code == 415
    assert "error" in r.json()


def test_one_byte_over_limit_is_413(make_client: Callable[..., TestClient]) -> None:
    r = post(make_client(), PNG + b"\x00" * (MAX_BYTES + 1 - len(PNG)))
    assert r.status_code == 413
    assert r.json() == {"error": "File too large."}


def test_exactly_at_limit_is_accepted(make_client: Callable[..., TestClient]) -> None:
    assert post(make_client(), PNG + b"\x00" * (MAX_BYTES - len(PNG))).status_code == 200


def test_traversal_filename_creates_nothing(
    make_client: Callable[..., TestClient], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    before = {p for p in tmp_path.rglob("*")}
    r = post(make_client(), PNG, name="../../x.png")
    assert r.status_code == 200
    created = {p for p in tmp_path.rglob("*")} - before
    assert {p.name for p in created} <= {"fake_llm.jsonl"}
    assert not (tmp_path / "x.png").exists()
