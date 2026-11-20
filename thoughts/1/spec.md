# Spec: #1 brevkoll v1, the letter decoder

**Real user:** my household first, then three international parents from the kids' school
**Size:** S   **Timebox:** 8h   **Kill date:** 14 days after ship

> Gate 1 draft. I review and edit this before any agent label is applied.

## Problem

Swedish letters from school, preschool and authorities arrive on paper or as PDFs. For parents still learning Swedish, each one costs 15 to 30 minutes of translating, guessing what is required, and copying dates by hand. Deadlines get missed.

## What v1 does (one sentence)

I photograph a Swedish letter and get a plain-language summary in my language, a list of what I must do, and the dates as a calendar file, while nothing about the letter is kept.

## User flow

1. Open `brevkoll.aminrj.com` on my phone.
2. Take a photo or pick a file (PNG, JPEG or PDF up to 10 MB). Choose the output language.
3. Within about 20 seconds I see: summary, actions, dates, and an "Add to calendar" button that downloads an `.ics` file.
4. I close the page. Nothing is stored on the server.

## Acceptance criteria (each one becomes a holdout test)

- [ ] **AC1** Given the fixture letter, when I POST it to `/api/decode`, then I get 200 with `summary` (string), `actions` (list of strings), `dates` (list of `{date, description}`) and `ics` (string).
- [ ] **AC2** Given the fixture letter, then `dates` contains `2026-12-04` and `2026-12-11`, **even when the model returns no dates**. Dates are parsed from the OCR text by code; the model never decides a deadline.
- [ ] **AC3** Given the fixture letter, then `ics` is a valid VCALENDAR with a `DTSTART` for `20261204`.
- [ ] **AC4** Given the fixture letter, then no payload sent to the model contains the personnummer, the email address or the phone number.
- [ ] **AC5** After any request, the app data directory contains no files.
- [ ] **AC6** Given the model returns text that is not valid JSON for the schema, then the API answers 502 with a generic error and does not echo the model's text.
- [ ] **AC7** Given an upload that is not PNG, JPEG or PDF, then 415. Given more than 10 MB, then 413.
- [ ] **AC8** Given `RATE_LIMIT_PER_MINUTE=3`, the 4th request from the same client within a minute gets 429.

## Contract (agents must respect this exactly; holdout tests depend on it)

- **App factory:** `from app.main import create_app` returns the FastAPI app and reads configuration from the environment at creation time.
- **Endpoint:** `POST /api/decode`, multipart form, file field `file`, text field `language` (ISO 639-1, default `en`).
- **Response 200:** JSON `{"summary": str, "actions": [str], "dates": [{"date": "YYYY-MM-DD", "description": str}], "ics": str}`.
- **Errors:** JSON `{"error": str}` with the status codes in AC6 to AC8. Never include stack traces or model output.
- **Model seam:** env `LLM_PROVIDER` selects the client. `fake` must:
  - append one JSON line per call to the file in env `FAKE_LLM_LOG`, with key `payload` holding every string sent to the model concatenated;
  - return the content of env `FAKE_LLM_RESPONSE` if set, otherwise `{"summary": "Fake summary.", "actions": ["Fake action."]}`.
- **Model output schema:** `{"summary": str, "actions": [str]}`. The model does not produce dates.
- **Storage:** env `APP_DATA_DIR` is the only directory the app may write to. Uploads are processed in memory or in a temp file that is deleted before the response returns.
- **Rate limit:** env `RATE_LIMIT_PER_MINUTE` (default 10), per client IP.
- **OCR:** Tesseract with Swedish (`tesseract-ocr-swe`), run locally. Already added to CI and must be added to the Dockerfile.

## Redaction (v1 scope)

Before any model call, replace with placeholders:

- personnummer and samordningsnummer (`YYMMDD-XXXX`, `YYYYMMDD-XXXX`, with `-`, `+` or no separator)
- email addresses
- Swedish phone numbers

Names and street addresses are **not** redacted in v1. That is an accepted risk, recorded in the threat model, and the reason the default model choice is decided at Gate 2.

## Out of scope

Accounts, history, storing letters, push reminders, handwriting, multi-page letters beyond 3 pages, languages other than the two my first users ask for.

## Sketch

```text
+----------------------------------+
|  brevkoll                        |
|  [ Take photo / choose file ]    |
|  Language: [English v]           |
|  [ Decode ]                      |
+----------------------------------+
|  Summary                         |
|  Class 2B goes to the museum...  |
|  To do                           |
|  - Sign up by 4 Dec              |
|  - Packed lunch on 11 Dec        |
|  Dates                           |
|  4 Dec  Sign-up deadline         |
|  11 Dec Museum trip              |
|  [ Add to calendar ]             |
+----------------------------------+
```
