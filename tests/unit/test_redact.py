import pytest

from app.redact import redact


@pytest.mark.parametrize(
    "text",
    [
        "850101-1234",
        "850101+1234",
        "8501011234",
        "19850101-1234",
        "19850101+1234",
        "198501011234",
        "850161-1234",  # samordningsnummer (day + 60)
        "19850161-1234",
    ],
)
def test_personnummer_forms(text: str) -> None:
    out = redact(f"Nr {text} slut")
    assert out == "Nr [PERSONNUMMER] slut"


@pytest.mark.parametrize(
    "text",
    ["070-123 45 67", "+46 70 123 45 67", "+46701234567", "08-123 456 78"],
)
def test_phone_forms(text: str) -> None:
    assert redact(f"Ring {text} nu") == "Ring [PHONE] nu"


def test_ten_digit_mobile_without_separators_is_redacted() -> None:
    # Indistinguishable from a personnummer, so either placeholder is fine. The digits go.
    out = redact("Ring 0701234567 nu")
    assert "0701234567" not in out
    assert out in ("Ring [PHONE] nu", "Ring [PERSONNUMMER] nu")


@pytest.mark.parametrize(
    "text", ["anna@example.se", "anna.svensson+skola@mail.example.com", "a_b-c@x.se"]
)
def test_email_forms(text: str) -> None:
    assert redact(f"Mejl {text}.") == "Mejl [EMAIL]."


def test_plain_text_and_dates_untouched() -> None:
    text = "Anmäl senast 2026-12-04 eller 4 december. Klass 2B."
    assert redact(text) == text
