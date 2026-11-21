from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from helpers import PNG

Make = Callable[..., TestClient]


def directives(policy: str) -> dict[str, list[str]]:
    parts = [p.strip().split() for p in policy.split(";") if p.strip()]
    return {p[0]: p[1:] for p in parts}


def test_index_has_csp_header(make_client: Make) -> None:
    assert "content-security-policy" in make_client().get("/").headers


def test_csp_has_no_unsafe_directives(make_client: Make) -> None:
    policy = make_client().get("/").headers["content-security-policy"]
    for bad in ("unsafe-inline", "unsafe-eval", "*", "http:", "data:"):
        assert bad not in policy
    parsed = directives(policy)
    assert parsed["script-src"] == ["'self'"]
    assert parsed["style-src"] == ["'self'"]
    assert parsed["default-src"] == ["'self'"]


def test_csp_on_error_and_static_responses(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    client = make_client()
    bad = client.post("/ui/decode", content=b"not multipart")
    assert bad.status_code == 422
    assert "content-security-policy" in bad.headers
    css = client.get("/static/style.css")
    assert "content-security-policy" in css.headers
    limited = client.post("/ui/decode", files={"file": ("a.png", PNG, "image/png")})
    assert limited.status_code == 429
    assert "content-security-policy" in limited.headers


def test_csp_does_not_set_cookies_or_cors(make_client: Make) -> None:
    r = make_client().get("/")
    assert "set-cookie" not in r.headers
    assert "access-control-allow-origin" not in r.headers
