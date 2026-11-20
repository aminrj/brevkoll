from datetime import date

import pytest

from app.dates import find_dates

TODAY = date(2026, 11, 20)


def found(text: str, today: date = TODAY) -> list[date]:
    return [f.date for f in find_dates(text, today)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Anmäl senast 2026-12-04.", date(2026, 12, 4)),
        ("Den 4 december 2026 är det möte", date(2026, 12, 4)),
        ("Den 4 december är det möte", date(2026, 12, 4)),
        ("Den 4:e december", date(2026, 12, 4)),
        ("Senast 4 dec.", date(2026, 12, 4)),
        ("Senast 4/12", date(2026, 12, 4)),
        ("Senast 4/12/2027", date(2027, 12, 4)),
        ("Utflykt 11 Mars", date(2027, 3, 11)),
        ("Utflykt 1 januari 2027", date(2027, 1, 1)),
    ],
)
def test_formats(text: str, expected: date) -> None:
    assert found(text) == [expected]


def test_invalid_calendar_date_rejected() -> None:
    assert found("Datum 2026-02-30 och 31 april och 31/11") == []


def test_yearless_resolves_to_next_occurrence_with_injected_clock() -> None:
    assert found("4 dec", date(2026, 12, 4)) == [date(2026, 12, 4)]
    assert found("4 dec", date(2026, 12, 5)) == [date(2027, 12, 4)]
    assert found("4 dec", date(2026, 1, 2)) == [date(2026, 12, 4)]


def test_yearless_leap_day_skips_to_leap_year() -> None:
    assert found("29 februari", date(2026, 11, 20)) == [date(2028, 2, 29)]


def test_sorted_and_deduplicated() -> None:
    text = "11 december och 2026-12-04 samt 4 december 2026"
    assert found(text) == [date(2026, 12, 4), date(2026, 12, 11)]


def test_phone_and_personnummer_produce_no_dates() -> None:
    text = "tel 070-123 45 67, 0701-23-45, 850101-1234, 19850101-1234, +46 70 123 45 67"
    assert found(text) == []


def test_context_is_letter_wording_collapsed_and_redacted() -> None:
    text = "Hej!\nAnmäl   senast 2026-12-04, pn 850101-1234 och  mejl a@b.se.\n"
    [item] = find_dates(text, TODAY)
    assert "Anmäl senast 2026-12-04" in item.context
    assert "850101-1234" not in item.context
    assert "a@b.se" not in item.context
    assert "  " not in item.context and "\n" not in item.context


def test_context_is_capped_and_keeps_the_date() -> None:
    text = "x" * 300 + " 2026-12-04 " + "y" * 300
    [item] = find_dates(text, TODAY)
    assert len(item.context) <= 120
    assert "2026-12-04" in item.context
