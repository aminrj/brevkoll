"""Gate 1 acceptance tests for the UI refresh.

Drafted by the factory from the spec, approved by the human. Agents must not read or edit this file.
They run in CI only: `uv run pytest tests/holdout`.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "app" / "static"
TEMPLATES = ROOT / "src" / "app" / "templates"
LETTER = Path(__file__).parent / "fixtures" / "school-letter.png"
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐⬆✅]")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("FAKE_LLM_LOG", str(tmp_path / "llm_calls.jsonl"))
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.delenv("FAKE_LLM_RESPONSE", raising=False)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "100")
    from app.main import create_app

    return TestClient(create_app())


def css_text() -> str:
    return "\n".join(p.read_text() for p in sorted(STATIC.glob("*.css")))


def decode(client: TestClient) -> str:
    resp = client.post(
        "/ui/decode",
        files={"file": ("letter.png", LETTER.read_bytes(), "image/png")},
        data={"language": "en"},
    )
    assert resp.status_code == 200
    return resp.text


def test_only_same_origin_resources(client: TestClient) -> None:
    html = client.get("/").text + decode(client)
    for attr in re.findall(r"""(?:src|href|action)=["']([^"']+)["']""", html):
        assert attr.startswith(("/", "#", "data:")) and not attr.startswith("//"), attr
    css = css_text()
    assert not re.search(r"url\(\s*[\"']?(https?:)?//", css)


def test_weight_budget(client: TestClient) -> None:
    assert sum(p.stat().st_size for p in STATIC.glob("*.css")) <= 12 * 1024
    assert len(client.get("/").content) <= 8 * 1024


def test_no_script_but_the_bundled_htmx(client: TestClient) -> None:
    assert sorted(p.name for p in STATIC.glob("*.js")) == ["htmx.min.js"]
    for html in (client.get("/").text, decode(client)):
        for tag in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S):
            assert tag.strip() == ""
        for src in re.findall(r"<script\b[^>]*\bsrc=[\"']([^\"']+)", html):
            assert src.startswith("/static/htmx.min.js")


def test_no_decorative_effects_or_emoji() -> None:
    css = css_text().lower()
    for banned in ("gradient(", "backdrop-filter", "blur(", "@font-face", "@import"):
        assert banned not in css, banned
    for template in TEMPLATES.glob("*.html"):
        assert not EMOJI.search(template.read_text()), template.name


def test_page_basics_and_labels(client: TestClient) -> None:
    html = client.get("/").text
    assert re.search(r"<html[^>]*\blang=", html)
    assert re.search(r"<meta[^>]*name=[\"']viewport[\"'][^>]*width=device-width", html)
    assert re.search(r"<title>\s*\S+", html)
    controls = re.findall(r"<(?:input|select)\b[^>]*>", html)
    assert controls
    for control in controls:
        ident = re.search(r"\bid=[\"']([^\"']+)", control)
        assert ident, control
        assert re.search(rf"<label[^>]*\bfor=[\"']{re.escape(ident.group(1))}[\"']", html), control


def test_stylesheet_rules() -> None:
    css = css_text()
    assert "prefers-color-scheme: dark" in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_button_is_disabled_while_a_request_runs(client: TestClient) -> None:
    form = re.search(r"<form\b[^>]*>", client.get("/").text, re.S)
    assert form and "hx-disabled-elt" in form.group(0)


def test_dates_use_tabular_figures() -> None:
    assert "tabular-nums" in css_text()


def test_result_keeps_its_contract(client: TestClient) -> None:
    html = decode(client)
    assert re.search(r"machine generated", html, re.I)
    assert "download=" in html and "text/calendar" in html
    assert html.index("What to do") < html.index("Dates")
    bad = client.post(
        "/ui/decode", files={"file": ("x.txt", b"hello", "text/plain")}, data={"language": "en"}
    )
    assert 'role="alert"' in bad.text
