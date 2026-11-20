import httpx
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

LETTER = (
    "Hej föräldrar! Anmäl senast 2026-12-04. Museibesök 11 december.\n"
    "Personnummer 850101-1234, mejl anna.svensson@example.se, tel 070-123 45 67.\n"
)


class FakeOcr:
    def __init__(self, text: str = LETTER) -> None:
        self.text = text
        self.calls = 0

    def extract(self, data: bytes, kind: str) -> str:
        self.calls += 1
        return self.text


def post(
    client: TestClient,
    data: bytes = PNG,
    *,
    name: str = "letter.png",
    language: str | None = None,
) -> httpx.Response:
    form = {} if language is None else {"language": language}
    return client.post("/api/decode", files={"file": (name, data, "image/png")}, data=form)
