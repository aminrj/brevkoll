# Plan: #6 Warn about OCR character errors on the result page
Status: approved

## Phase 1: Add OCR warning notice to result page
- [x] **Files:**
  - `src/app/templates/result.html` — insert a second `<p class="notice">` after the existing "Machine generated" notice and before the first `<h2>` ("What to do").
- [x] **Types and signatures:** None. The notice text is a static string in the template.
- [x] **Tests to add (and why each fails today):**
  - `tests/holdout_test_issue_6.py`:
    - `test_ac1_notice_mentions_email_and_ocr` — asserts the result page HTML contains a `<p class="notice">` whose text mentions both "email" and "OCR" (case-insensitive). Fails today because only the "Machine generated" notice exists.
    - `test_ac2_api_unchanged` — asserts `POST /api/decode` JSON response has no `ocr_warning` field. Fails today (passes trivially because nothing is added to the API).
    - `test_ac3_notice_before_what_to_do_heading` — asserts the new notice element appears before the first `<h2>` on the result page. Fails today because the notice does not exist.
  - `tests/unit/test_ui_result.py`: add a line to `test_notice_summary_actions_dates_and_ics_present` to assert the second notice text is present.
- [x] **Automated verification:** `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest`
- [ ] **Manual verification:** Upload a letter in the browser; confirm the result page shows two notices — first "Machine generated…", then "Email addresses, phone numbers and special characters may contain OCR errors — check the original letter." — before "What to do".
- [x] **Threat-model controls implemented:**
  - Web: XSS — notice is static HTML, no variable interpolation, Jinja2 autoescape applies.
  - Web: API contract regression — notice lives only in the template; `/api/decode` returns `DecodeResult` unchanged.
- [x] **Docs touched:** None. This phase changes no command, env var, route, limit or behaviour a user or operator sees.

## Docs (the app's own, not the factory's)
`README.md` — no changes needed. The existing "Machine generated" disclaimer already covers the app's limits.
`AGENTS.md` — no changes needed.

## Architecture contracts
No new import rules needed. This phase touches only a Jinja2 template.

## Decisions (ADRs)
None. This is a one-line template addition with no trade-offs worth documenting.

## Dependencies added (Python and system)
None.

## What I am unsure about
- The spec hardcodes the notice text. If the wording needs to change later, a deploy is required (acknowledged as Risk R2 in the threat model).
- The notice is English-only. The threat model accepts this (Risk R1), but the research flagged it as an open question (Q1).

## Notes from implementation

- Phase 1 implemented on 2026-11-22. All 249 tests pass, pyright clean, ruff clean.
- The holdout test file `tests/holdout_test_issue_6.py` was created with 3 acceptance tests; all 3 pass.
- `test_ac2_api_unchanged` passes trivially — the API response JSON still has exactly the four original keys.
- Manual verification not yet done (browser upload).
