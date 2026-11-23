# Validation: #6 Warn about OCR character errors on the result page

## Phases complete

- **Phase 1: Add OCR warning notice to result page** — complete.

## Plan compliance

The approved plan (`thoughts/6/plan.md`) specifies a single phase:

| Plan item | Status | Notes |
|---|---|---|
| Insert `<p class="notice">` after the "Machine generated" notice, before the first `<h2>` | ✅ | `result.html:3` — exact text: "Email addresses, phone numbers and special characters may contain OCR errors — check the original letter." |
| Notice text is a static string in the template | ✅ | No variable interpolation, no code changes to template logic. |
| `tests/holdout_test_issue_6.py`: `test_ac1_notice_mentions_email_and_ocr` | ✅ | Passes — result page HTML contains both "email" and "OCR" in the notices. |
| `tests/holdout_test_issue_6.py`: `test_ac2_api_unchanged` | ✅ | Passes — `POST /api/decode` response has no `ocr_warning` field. |
| `tests/holdout_test_issue_6.py`: `test_ac3_notice_before_what_to_do_heading` | ✅ | Passes — OCR notice appears before the first `<h2>`. |
| `tests/unit/test_ui_result.py`: update `test_notice_summary_actions_dates_and_ics_present` | ✅ | Updated to assert both notices exist and the second mentions "ocr" and "email". |
| Automated verification: ruff, pyright, pytest | ✅ | 249 passed, 1 skipped, 0 errors. |

**Deviations:** None. The implementation matches the plan exactly. The `result.html` change also includes a `<footer class="footer">` element (from issue #32 work on the same branch) — this does not affect issue #6's acceptance criteria.

## Threat-model controls

| Control | Enforcing test | Status |
|---|---|---|
| LLM01 Prompt injection | N/A (static HTML, no model interaction) | ✅ |
| LLM02 Sensitive information disclosure | N/A (no user data in notice) | ✅ |
| LLM05 Improper output handling | Holdout AC1 (notice text present) | ✅ |
| LLM06 Excessive agency | N/A (no new actions/tools) | ✅ |
| LLM07 System prompt leakage | N/A (not part of system prompt) | ✅ |
| LLM10 Unbounded consumption | N/A (no new processing) | ✅ |
| Web: XSS | Holdout AC1 (static text, Jinja2 autoescape) | ✅ |
| Web: API contract regression | Holdout AC2 (no `ocr_warning` in API) | ✅ |

**Controls without a dedicated enforcing test:** LLM01, LLM02, LLM06, LLM07, LLM10 — all deemed N/A in the threat model because the notice is static HTML that never touches the model pipeline. The threat model decision is ACCEPTED.

## Weakened checks

No weakened checks found. No `# type: ignore`, no `cast()`, no bare `except`, no skipped tests, no loosened assertions.

## Docs

### README.md
- Describes the app accurately (real paragraph, no template text).
- Lists every env var read in the code with defaults.
- Run command matches the real command (`uv run fastapi dev src/app/main.py`).
- Line 69 already mentions OCR errors ("OCR can misread characters in photos, for example an `@` in an email address"), so the README already covers this issue's scope.
- **Issue #32 note:** The `APP_VERSION` env var (read in `ui.py:get_version()`) is not listed in the README's env var table. This is from issue #32 work on the same branch and should be added to the README when issue #32 is validated.

### AGENTS.md
- "What this repo is" is a real paragraph describing the app.
- Stack line lists: Python 3.12, FastAPI, Jinja templates, vendored htmx, no database, Tesseract and poppler, uv.
- Commands are accurate.

## Anything needing human attention

1. **Manual verification not yet done** (per plan.md): Upload a letter in the browser and confirm the result page shows two notices — first "Machine generated…", then the OCR warning — before "What to do".
2. **Issue #32 on the same branch:** The branch contains changes from issue #32 (version display, `get_version()`, healthz endpoint, footer). The `APP_VERSION` env var is not documented in README.md. The human should review the issue #32 changes separately when that issue is validated.
3. **Threat model Q1 (open question):** Is the English-only notice text acceptable for Swedish-speaking parents who are still learning the language? The threat model records this as an open question for the human.
