import io
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.errors import OcrBusy, OcrFailed, TooLarge
from app.ocr import MAX_PDF_PAGES, TesseractOcr, check_image_size


def png_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return buf.getvalue()


class Recorder:
    """Stands in for subprocess.run; records every call."""

    def __init__(self, pages: int = 1, fail: Exception | None = None) -> None:
        self.calls: list[tuple[Sequence[str], dict[str, Any]]] = []
        self.pages = pages
        self.fail = fail

    def __call__(self, args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((args, kwargs))
        if self.fail is not None:
            raise self.fail
        name = Path(args[0]).name
        if name == "pdfinfo":
            out = ("Pages: " + str(self.pages) + "\n").encode()
            return subprocess.CompletedProcess(args, 0, out, b"")
        if name == "pdftoppm":
            prefix = Path(args[-1])
            (prefix.parent / (prefix.name + "-1.png")).write_bytes(png_bytes())
            return subprocess.CompletedProcess(args, 0, b"", b"")
        return subprocess.CompletedProcess(args, 0, "Hej värld".encode(), b"")


def which(name: str) -> str | None:
    return "/usr/bin/" + name


def make(rec: Recorder, tmp_root: Path, concurrency: int = 2) -> TesseractOcr:
    return TesseractOcr(run=rec, which=which, tmp_root=tmp_root, concurrency=concurrency)


def test_image_uses_list_args_timeout_no_shell(tmp_path: Path) -> None:
    rec = Recorder()
    text = make(rec, tmp_path).extract(png_bytes(), "png")
    assert text == "Hej värld"
    args, kwargs = rec.calls[0]
    assert isinstance(args, list) and args[0] == "/usr/bin/tesseract"
    assert "swe" in args
    assert kwargs.get("timeout")
    assert not kwargs.get("shell")


def test_tmp_dir_removed_after_success(tmp_path: Path) -> None:
    make(Recorder(), tmp_path).extract(png_bytes(), "png")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "err",
    [
        subprocess.CalledProcessError(1, "tesseract"),
        subprocess.TimeoutExpired("tesseract", 30),
    ],
)
def test_tmp_dir_removed_and_generic_error_on_failure(tmp_path: Path, err: Exception) -> None:
    with pytest.raises(OcrFailed):
        make(Recorder(fail=err), tmp_path).extract(png_bytes(), "png")
    assert list(tmp_path.iterdir()) == []


def test_missing_binary_is_generic_error(tmp_path: Path) -> None:
    ocr = TesseractOcr(run=Recorder(), which=lambda name: None, tmp_root=tmp_path)
    with pytest.raises(OcrFailed):
        ocr.extract(png_bytes(), "png")


def test_pdf_pipeline(tmp_path: Path) -> None:
    rec = Recorder(pages=MAX_PDF_PAGES)
    text = make(rec, tmp_path).extract(b"%PDF-1.7 x", "pdf")
    assert text == "Hej värld"
    names = [Path(a[0]).name for a, _ in rec.calls]
    assert names == ["pdfinfo", "pdftoppm", "tesseract"]
    assert all(isinstance(a, list) and k.get("timeout") for a, k in rec.calls)
    assert list(tmp_path.iterdir()) == []


def test_pdf_with_too_many_pages_rejected_before_rendering(tmp_path: Path) -> None:
    rec = Recorder(pages=MAX_PDF_PAGES + 1)
    with pytest.raises(TooLarge):
        make(rec, tmp_path).extract(b"%PDF-1.7 x", "pdf")
    assert [Path(a[0]).name for a, _ in rec.calls] == ["pdfinfo"]
    assert list(tmp_path.iterdir()) == []


def test_large_image_header_rejected_before_ocr(tmp_path: Path) -> None:
    rec = Recorder()
    with pytest.raises(TooLarge):
        make(rec, tmp_path).extract(png_bytes((6000, 5000)), "png")  # 30 MP
    assert rec.calls == []


def test_check_image_size_accepts_small() -> None:
    check_image_size(png_bytes())


def test_corrupt_image_is_generic_error(tmp_path: Path) -> None:
    with pytest.raises(OcrFailed):
        make(Recorder(), tmp_path).extract(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "png")


def test_busy_when_concurrency_exhausted(tmp_path: Path) -> None:
    ocr = TesseractOcr(run=Recorder(), which=which, tmp_root=tmp_path, concurrency=1, wait_s=0.01)
    assert ocr.slots.acquire(blocking=False)
    with pytest.raises(OcrBusy):
        ocr.extract(png_bytes(), "png")
    ocr.slots.release()
    assert ocr.extract(png_bytes(), "png") == "Hej värld"
