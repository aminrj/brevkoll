import io
import re
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.errors import OcrBusy, OcrFailed, TooLarge

MAX_PIXELS = 25_000_000
MAX_PDF_PAGES = 3
SUBPROCESS_TIMEOUT_S = 30
DEFAULT_CONCURRENCY = 2
SLOT_WAIT_S = 2.0

Image.MAX_IMAGE_PIXELS = MAX_PIXELS

Run = Callable[..., subprocess.CompletedProcess[bytes]]
Which = Callable[[str], str | None]


def check_image_size(data: bytes) -> None:
    """Read only the image header and reject oversized or unreadable images."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise OcrFailed() from None
    if width * height > MAX_PIXELS:
        raise TooLarge()


def pdf_page_count(path: Path, run: Run, pdfinfo: str) -> int:
    out = _run(run, [pdfinfo, str(path)]).stdout.decode("utf-8", errors="replace")
    match = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    if match is None:
        raise OcrFailed()
    return int(match.group(1))


def _run(run: Run, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return run(args, check=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT_S)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        raise OcrFailed() from None


class TesseractOcr:
    def __init__(
        self,
        run: Run = subprocess.run,
        which: Which = shutil.which,
        tmp_root: Path | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        wait_s: float = SLOT_WAIT_S,
    ) -> None:
        self._run = run
        self._which = which
        self._tmp_root = tmp_root
        self._wait_s = wait_s
        self.slots = threading.BoundedSemaphore(concurrency)

    def extract(self, data: bytes, kind: str) -> str:
        if not self.slots.acquire(timeout=self._wait_s):
            raise OcrBusy()
        try:
            return self._extract(data, kind)
        finally:
            self.slots.release()

    def _binary(self, name: str) -> str:
        path = self._which(name)
        if path is None:
            raise OcrFailed()
        return path

    def _extract(self, data: bytes, kind: str) -> str:
        if kind != "pdf":
            check_image_size(data)
        tess = self._binary("tesseract")
        root = str(self._tmp_root) if self._tmp_root else None
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            work = Path(tmp)
            if kind == "pdf":
                pages = self._render_pdf(data, work)
            else:
                source = work / "in.img"
                source.write_bytes(data)
                pages = [source]
            return "\n".join(self._ocr_page(tess, page) for page in pages)

    def _render_pdf(self, data: bytes, work: Path) -> list[Path]:
        pdfinfo = self._binary("pdfinfo")
        pdftoppm = self._binary("pdftoppm")
        source = work / "in.pdf"
        source.write_bytes(data)
        if pdf_page_count(source, self._run, pdfinfo) > MAX_PDF_PAGES:
            raise TooLarge()
        prefix = work / "page"
        _run(
            self._run,
            [pdftoppm, "-r", "200", "-l", str(MAX_PDF_PAGES), "-png", str(source), str(prefix)],
        )
        return sorted(work.glob("page*.png"))

    def _ocr_page(self, tess: str, page: Path) -> str:
        result = _run(self._run, [tess, str(page), "stdout", "-l", "swe"])
        return result.stdout.decode("utf-8", errors="replace")
