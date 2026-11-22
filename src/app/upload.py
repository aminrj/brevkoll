from typing import Literal

from fastapi import UploadFile

from app.errors import TooLarge, UnsupportedMedia

MAX_BYTES = 10 * 1024 * 1024
MAX_PART_BYTES = 10 * 1024 * 1024
_CHUNK = 64 * 1024

Kind = Literal["png", "jpeg", "pdf"]


async def read_limited(file: UploadFile, max_bytes: int = MAX_BYTES) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise TooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


def sniff_kind(data: bytes) -> Kind:
    """Decide the type from magic bytes only. The filename and content type are ignored."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"%PDF-"):
        return "pdf"
    raise UnsupportedMedia()
