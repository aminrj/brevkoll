from datetime import date, datetime

from app.dates import FoundDate
from app.ics import build_ics, escape_text

NOW = datetime(2026, 11, 20, 8, 0)


def one(context: str = "Anmäl senast 2026-12-04") -> list[FoundDate]:
    return [FoundDate(date=date(2026, 12, 4), context=context)]


def test_valid_calendar_with_all_day_event() -> None:
    ics = build_ics(one(), "Summary", ["Do it"], NOW)
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20261204\r\n" in ics
    assert "DTSTAMP:20261120T080000Z\r\n" in ics
    assert ics.count("BEGIN:VEVENT") == 1
    assert "\n" not in ics.replace("\r\n", "")


def test_uid_is_stable_hash() -> None:
    a = build_ics(one(), "s", [], NOW)
    assert a == build_ics(one(), "s", [], NOW)
    assert "UID:" in a and "@brevkoll" in a


def test_no_dates_gives_empty_valid_calendar() -> None:
    ics = build_ics([], "s", [], NOW)
    assert "BEGIN:VEVENT" not in ics and ics.endswith("END:VCALENDAR\r\n")


def logical_lines(ics: str) -> list[str]:
    return ics.replace("\r\n ", "").split("\r\n")


def test_injected_action_creates_no_second_event() -> None:
    evil = "x\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:pwn"
    lines = logical_lines(build_ics(one(), evil, [evil], NOW))
    assert lines.count("BEGIN:VEVENT") == 1
    assert lines.count("END:VEVENT") == 1
    assert "SUMMARY:pwn" not in lines


def test_injected_letter_wording_is_escaped() -> None:
    lines = logical_lines(build_ics(one("a\r\nBEGIN:VEVENT"), "s", [], NOW))
    assert lines.count("BEGIN:VEVENT") == 1


def test_escape_text() -> None:
    assert escape_text("a,b;c\\d\ne\r\x00f\x07") == "a\\,b\\;c\\\\d\\nef"


def test_lines_folded_at_75_octets_without_splitting_characters() -> None:
    ics = build_ics(one("å" * 200), "ö" * 200, [], NOW)
    for line in ics.split("\r\n"):
        assert len(line.encode()) <= 75
    assert "\r\n " in ics
