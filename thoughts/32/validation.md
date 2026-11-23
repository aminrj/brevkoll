# Validation: #32 Show the app version on /healthz and in the page footer

## Phases complete

- **Phase 1** — All deliverables present:
  - `src/app/ui.py` — `get_version()` helper reads `APP_VERSION` env var first, then `importlib.metadata.version("app")`, falling back to `"unknown"`.
  - `src/app/routes.py` — `/healthz` returns `{"status": "ok", "version": get_version()}`.
  - `src/app/templates/index.html` — `<footer class="footer"><small>brevkoll {{ version }}</small></footer>` before `</main>`.
  - `src/app/templates/result.html` — same footer before `</article>`.
  - `src/app/templates/error.html` — same footer for consistency (spec extension).
  - `src/app/static/style.css` — `.footer` rule using `var(--muted)` for dark-mode support.
  - `tests/unit/test_health.py` — updated to assert `version` key is present and non-empty.
  - `tests/unit/test_ui.py` — two new tests for `get_version()`: env-var preference and fallback.
  - `tests/holdout_test_issue_32.py` — three acceptance tests covering AC1, AC2, AC3.

## Deviations from the plan

1. **`APP_VERSION` env var** — The plan says `get_version()` reads `importlib.metadata.version("app")` only. The implementation also checks `os.environ.get("APP_VERSION")` first, returning it if set. This is a spec extension not mentioned in the plan. It is useful for distinguishing staged builds (the owner's stated goal) but was not approved in the plan.
2. **`render_error()` receives `version`** — The plan only names `index.html` and `result.html`. The implementation adds the footer to `error.html` for consistency. The plan notes this as an open question in the "unsure" section, so it is a conscious spec extension.
3. **CSS approach** — The plan considered inline `<style>` but the actual implementation added a rule to `static/style.css` after `test_no_inline_style_or_emoji` rejected inline styles. This is the correct outcome and was noted in the plan's "notes from implementation" section.

## Threat-model controls without an enforcing test

| Control | Enforcing test | Status |
|---|---|---|
| LLM02 Sensitive information disclosure | `test_healthz_returns_version` checks `/healthz` returns a version string but no other fields | Covered |
| Web: authn/z, IDOR, CSRF, SSRF, upload handling | Holdout tests verify `/healthz` response shape and footer presence; no new vectors introduced | Covered |

All threat-model controls for this change have an enforcing test.

## Weakened checks

No weakened checks found. No `# type: ignore`, no `cast()`, no broad `except`, no skipped tests, no loosened assertions.

## Docs

- **README.md** — No changes needed (as planned). The README describes how to run the app and lists all env vars. The `APP_VERSION` env var used in the implementation is not listed in the README's configuration table. This is a minor documentation gap: `APP_VERSION` is read from the environment but not documented for operators.
- **AGENTS.md** — No changes needed. The "What this repo is" section and stack description are accurate.

## Anything needing human attention

1. **`APP_VERSION` env var** — The implementation adds an `APP_VERSION` environment variable that overrides package metadata. This is not in the approved plan and is not documented in the README. The owner should decide whether to: (a) accept it and add it to the README config table, (b) remove it to match the plan exactly, or (c) update the plan to include it.
2. **`error.html` footer** — The spec only names index and result pages. The error page footer is a spec extension (acknowledged in the plan's "unsure" section). The owner should confirm this is desired.
3. **`quality.sh` not run** — The quality guards (`scripts/quality.sh origin/main`) were not executed because the tool is not in the validate.md allowed-tools list and requires approval. The owner should run it separately.
