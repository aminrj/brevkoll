import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from helpers import FakeOcr, post

Make = Callable[..., TestClient]


# I3
def test_dates_come_from_code_not_model(make_client: Make) -> None:
    body = post(make_client()).json()
    assert [d["date"] for d in body["dates"]][0] == "2026-12-04"
    assert "DTSTART;VALUE=DATE:20261204" in body["ics"]
    assert body["dates"][0]["description"].startswith("Hej föräldrar! Anmäl senast")
    assert "850101-1234" not in json.dumps(body)


# I3
def test_model_claiming_other_dates_is_ignored(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = json.dumps({"summary": "Deadline 2030-01-01 !", "actions": ["Pay by 2031-02-02"]})
    monkeypatch.setenv("FAKE_LLM_RESPONSE", fake)
    body = post(make_client(), language="en").json()
    assert all(not d["date"].startswith(("2030", "2031")) for d in body["dates"])
    assert "DTSTART;VALUE=DATE:2030" not in body["ics"]
    assert "DTSTART;VALUE=DATE:20261204" in body["ics"]


def test_letter_without_dates_gives_no_events(make_client: Make) -> None:
    body = post(make_client(FakeOcr("Hej, inget datum här."))).json()
    assert body["dates"] == []
    assert "BEGIN:VEVENT" not in body["ics"]
