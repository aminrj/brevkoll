import re
import urllib.parse
from collections.abc import Callable

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import PNG, FakeOcr

from app.config import SUPPORTED_LANGUAGES
from app.main import create_app
from app.ui import WEEKDAYS, weekday_name

Make = Callable[..., TestClient]


def ui_post(client: TestClient, language: str = "en") -> httpx.Response:
    return client.post(
        "/ui/decode",
        files={"file": ("letter.png", PNG, "image/png")},
        data={"language": language},
    )


def dates_block(html: str) -> str:
    m = re.search(r'<ul class="dates">(.*?)</ul>', html, re.S)
    assert m, "no ul.dates"
    return m.group(1)


def test_weekday_table() -> None:
    for lang, friday in (("en", "Friday"), ("sv", "fredag")):
        assert weekday_name("2026-12-04", lang) == friday
        assert weekday_name("2027-01-01", lang) == friday
    assert weekday_name("2028-02-29", "en") == "Tuesday"
    assert weekday_name("2026-12-31", "en") == "Thursday"
    for lang in ("ar", "uk"):
        assert weekday_name("2026-12-04", lang)


def test_every_supported_language_has_weekday_row() -> None:
    assert set(WEEKDAYS) == SUPPORTED_LANGUAGES
    assert all(len(row) == 7 and all(row) for row in WEEKDAYS.values())


def test_unknown_language_falls_back_to_english() -> None:
    assert weekday_name("2026-12-04", "xx") == "Friday"


def test_what_to_do_before_dates_and_summary_last(make_client: Make) -> None:
    t = ui_post(make_client()).text
    assert t.index("What to do") < t.index("Dates") < t.index("Summary")


def test_date_item_shows_full_iso_weekday_and_wording(make_client: Make) -> None:
    t = ui_post(make_client()).text
    assert re.search(r'<time datetime="2026-12-04"[^>]*>2026-12-04</time>', t)
    assert "Friday" in t
    assert "Anmäl senast" in t


def test_large_date_markup_holds_only_code_dates(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FAKE_LLM_RESPONSE",
        '{"summary": "deadline cancelled 2026-01-01", "actions": ["Deadline: 1 jan"]}',
    )
    t = ui_post(TestClient(create_app(ocr=FakeOcr()))).text
    block = dates_block(t)
    assert block.count("<time ") == block.count("<li")
    assert "2026-12-04" in block
    assert "2026-01-01" not in block
    assert "1 jan" not in block


def test_notice_summary_actions_dates_and_ics_present(make_client: Make) -> None:
    t = ui_post(make_client()).text
    m = re.search(r'<p class="notice"([^>]*)>(.*?)</p>', t, re.S)
    assert m and "Machine generated" in m.group(2)
    assert "hidden" not in m.group(1) and "alert" not in m.group(1)
    assert "Fake summary." in t and "Fake action." in t
    assert 'href="data:text/calendar' in t


def test_result_escapes_model_and_letter_text(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FAKE_LLM_RESPONSE",
        '{"summary": "<script>alert(1)</script>", "actions": ["x><img onerror=y>"]}',
    )
    ocr = FakeOcr("<b onmouseover=z> deadline 2026-12-04")
    t = ui_post(TestClient(create_app(ocr=ocr))).text
    assert "<script>alert(1)" not in t
    assert "<img onerror" not in t
    assert "<b onmouseover" not in t


def test_ics_link_unchanged(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FAKE_LLM_RESPONSE",
        '{"summary": "s", "actions": ["x\\r\\nBEGIN:VEVENT"]}',
    )
    client = TestClient(create_app(ocr=FakeOcr()))
    ics = client.post("/api/decode", files={"file": ("a.png", PNG, "image/png")}).json()["ics"]
    t = ui_post(client).text
    m = re.search(r'href="(data:text/calendar;charset=utf-8,[^"]*)"', t)
    assert m
    decoded = urllib.parse.unquote(m.group(1).split(",", 1)[1])
    assert decoded == ics
    assert decoded.count("BEGIN:VEVENT") == ics.count("BEGIN:VEVENT")


def test_result_language_and_direction(make_client: Make) -> None:
    ar = ui_post(make_client(), "ar").text
    assert '<article lang="ar" dir="rtl"' in ar
    en = ui_post(make_client(), "en").text
    assert '<article lang="en" dir="ltr"' in en


def test_api_decode_json_unchanged(make_client: Make) -> None:
    r = make_client().post("/api/decode", files={"file": ("a.png", PNG, "image/png")})
    body = r.json()
    assert set(body) == {"summary", "actions", "dates", "ics"}
    assert all(set(d) == {"date", "description"} for d in body["dates"])


def test_no_dates_message_kept(env: Env) -> None:
    t = ui_post(TestClient(create_app(ocr=FakeOcr("Hej utan datum.")))).text
    assert "No dates found in the letter." in t
    assert "data:text/calendar" not in t
