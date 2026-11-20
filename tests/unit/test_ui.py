from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import PNG, FakeOcr

from app.main import create_app

Make = Callable[..., TestClient]

SRC = Path(__file__).resolve().parents[2] / "src" / "app"


def ui_post(client: TestClient, data: bytes = PNG, language: str = "en") -> httpx.Response:
    return client.post(
        "/ui/decode",
        files={"file": ("letter.png", data, "image/png")},
        data={"language": language},
    )


def test_index_page_accepts_images_and_pdf(make_client: Make) -> None:
    r = make_client().get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert 'accept="image/*,application/pdf"' in r.text
    assert 'hx-post="/ui/decode"' in r.text
    assert "set-cookie" not in r.headers


def test_index_lists_every_language(make_client: Make) -> None:
    text = make_client().get("/").text
    for code in ("en", "sv", "ar", "uk"):
        assert f'value="{code}"' in text


def test_fragment_shows_result_and_labels_it_machine_generated(make_client: Make) -> None:
    r = ui_post(make_client())
    assert r.status_code == 200
    assert "Fake summary." in r.text
    assert "Fake action." in r.text
    assert "2026-12-04" in r.text
    assert "machine" in r.text.lower()
    assert "<html" not in r.text.lower()  # a fragment, not a page


def test_fragment_has_ics_data_link_without_new_route(make_client: Make) -> None:
    r = ui_post(make_client())
    assert 'href="data:text/calendar' in r.text
    assert "BEGIN%3AVCALENDAR" in r.text
    assert "download=" in r.text


def test_fragment_shows_original_wording_next_to_date(make_client: Make) -> None:
    r = ui_post(make_client())
    assert "Anmäl senast" in r.text


def test_script_in_model_summary_is_escaped(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "FAKE_LLM_RESPONSE",
        '{"summary": "<script>alert(1)</script>", "actions": ["<img src=x onerror=y>"]}',
    )
    r = ui_post(make_client())
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text
    assert "<img src=x" not in r.text


def test_script_in_letter_wording_is_escaped(env: Env) -> None:
    ocr = FakeOcr("<script>alert(2)</script> deadline 2026-12-04")
    r = ui_post(TestClient(create_app(ocr=ocr)))
    assert "<script>alert(2)" not in r.text


def test_ui_errors_render_escaped_fragment_with_status(make_client: Make) -> None:
    r = ui_post(make_client(), language="xx")
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("text/html")
    assert "Unsupported language." in r.text
    r = ui_post(make_client(), data=b"plain text")
    assert r.status_code == 415
    assert "<html" not in r.text.lower()


def test_ui_model_failure_is_generic(make_client: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_LLM_RESPONSE", "not json SECRET-MODEL-TEXT")
    r = ui_post(make_client())
    assert r.status_code == 502
    assert "SECRET-MODEL-TEXT" not in r.text


def test_ui_decode_is_rate_limited(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    client = TestClient(create_app(ocr=FakeOcr()))
    assert ui_post(client).status_code == 200
    assert ui_post(client).status_code == 200
    r = ui_post(client)
    assert r.status_code == 429
    assert r.headers["content-type"].startswith("text/html")


def test_ui_and_api_share_one_rate_limit(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    client = TestClient(create_app(ocr=FakeOcr()))
    assert ui_post(client).status_code == 200
    r = client.post("/api/decode", files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 429


def test_ui_leaves_no_files(make_client: Make, env: Env) -> None:
    ui_post(make_client())
    assert list(env.data_dir.iterdir()) == []
    assert list(env.tmp_dir.iterdir()) == []


def test_no_unsafe_rendering_in_templates_or_own_static_files() -> None:
    files = [
        p
        for folder in ("templates", "static")
        for p in (SRC / folder).rglob("*")
        if p.is_file() and p.name != "htmx.min.js"
    ]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        for bad in ("innerHTML", "outerHTML", "|safe", "| safe", "autoescape false", "eval("):
            assert bad not in text, f"{bad} in {path.name}"


def test_page_loads_only_own_scripts_no_cdn() -> None:
    text = (SRC / "templates" / "index.html").read_text(encoding="utf-8")
    assert "http://" not in text and "https://" not in text
    assert 'src="/static/htmx.min.js"' in text
