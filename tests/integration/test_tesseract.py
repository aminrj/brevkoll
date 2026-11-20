import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ocr import TesseractOcr

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract binary not installed"
)


def test_tesseract_reads_generated_png() -> None:
    img = Image.new("RGB", (900, 200), "white")
    font = ImageFont.load_default(size=48)
    ImageDraw.Draw(img).text((20, 60), "Anmal senast 2026-12-04", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    text = TesseractOcr().extract(buf.getvalue(), "png")
    assert "2026" in text
