# Research: #6 Warn about OCR character errors on the result page

## What exists

Tesseract (via poppler for PDFs) reads uploaded Swedish letters and returns raw text. That text is redacted (personnummer, email, phone replaced with placeholders) and sent to a local LLM, which returns JSON with `summary` and `actions`. Code extracts dates from the OCR text and builds an `.ics` file. The result page (`result.html`) renders the model output with Jinja2 autoescape and shows a single "Machine generated" notice at the top.

This issue adds a second notice — specifically about OCR character errors in emails and phone numbers — placed after the existing notice and before the first `<h2>` heading. The API response shape is unchanged.

## Relevant code (file:line)

**Templates**
- `src/app/templates/result.html:1-29` — Result page template (fragment, no `<html>` wrapper)
- `src/app/templates/result.html:2` — Existing notice: `<p class="notice">Machine generated. Check the original letter before you rely on this.</p>`
- `src/app/templates/result.html:4` — First `<h2>`: "What to do"

**UI rendering**
- `src/app/ui.py:64` — `Jinja2Templates` autoescapes `.html` templates
- `src/app/ui.py:77-85` — `render_result(request, result, language)` builds context dict and calls `_render()`
- `src/app/ui.py:68-69` — `_render()` calls `TemplateResponse()` with the context

**Routes**
- `src/app/routes.py:50-55` — `POST /api/decode` returns `DecodeResult` (JSON, Pydantic model)
- `src/app/routes.py:57-63` — `POST /ui/decode` returns HTML via `render_result()`

**Data models**
- `src/app/decode.py:26-30` — `DecodeResult`: `summary: str`, `actions: list[str]`, `dates: list[DateItem]`, `ics: str`
- `src/app/decode.py:21-23` — `DateItem`: `date: str`, `description: str`

**CSS**
- `src/app/static/style.css:166-173` — `.notice` class: `--panel` background, muted left border, `0.9375rem` font
- `src/app/static/style.css:72` — `.card > .notice + h2 { margin-top: 1rem; }` (spacing rule)

**Tests**
- `tests/unit/test_ui_result.py:76-80` — `test_notice_summary_actions_dates_and_ics_present`: checks existing notice text
- `tests/unit/test_ui_result.py:119-123` — `test_api_decode_json_unchanged`: asserts `{"summary", "actions", "dates", "ics"}` keys
- `tests/unit/test_ui_result.py:51-53` — `test_what_to_do_before_dates_and_summary_last`: asserts heading order
- `tests/unit/test_ui.py:41-48` — `test_fragment_shows_result_and_labels_it_machine_generated`
- `tests/holdout_test_issue_32.py` — pattern for holdout acceptance tests (each AC is a test function)

**Pipeline**
- `src/app/decode.py:47-55` — `decode_letter()`: OCR → redact → prompt → LLM → parse → find_dates → build_ics → DecodeResult
- `src/app/redact.py` — replaces personnummer, email, phone with placeholders before the model sees them

## Where untrusted input enters

| # | Entry point | Data | Where it lands |
|---|---|---|---|
| 1 | `POST /ui/decode` (multipart `file`) | Uploaded photo/PDF bytes | `ocr.extract()` → raw text |
| 2 | Tesseract output | OCR text (may contain garbled `@`, `Q`, etc.) | Redacted → prompt → LLM → `summary`/`actions` |
| 3 | LLM JSON output | `summary: str`, `actions: list[str]` | Rendered into `result.html` via Jinja2 autoescape |
| 4 | OCR text (unredacted parts) | Dates, wording like "Anmäl senast" | Rendered into `<blockquote>` in `result.html:18` via Jinja2 autoescape |

The new OCR notice text is a **static string in the template** — it does not derive from any untrusted input.

## Constraints found (CI, system packages, data, deployment)

- **Jinja2 autoescape** is enabled for `.html` templates (`ui.py:64`). No template uses `|safe`.
- **No `|safe` anywhere** in templates or static files (`test_ui.py:124-135` holds this constraint).
- **API contract**: `DecodeResult` is a Pydantic model with exactly 4 fields. Adding a 5th field would break the contract. The notice lives only in the template, not in the model.
- **CSS**: The existing `.notice` class provides adequate styling. No new CSS is needed.
- **Holdout tests**: Each acceptance criterion (AC1, AC2, AC3) maps to a test function in `tests/holdout_test_issue_6.py`.
- **Quality guard**: `scripts/quality.sh` enforces complexity ratchet, changed-line coverage, import contracts, traceability, and context size.

## Open questions for the human

1. **Q1 (from threat model):** The notice is English-only. Is this acceptable for Swedish-speaking parents who are still learning the language, or should it be bilingual (SV + EN)?
2. **Q2:** The spec hardcodes the notice text. If the wording needs to change, a deploy is required. Is this acceptable for v1 given the small user base?
