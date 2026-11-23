# Plan: #32 Show the app version on /healthz and in the page footer
Status: approved

## Phase 1: Read version from package metadata and surface it on /healthz and in page footers
- Files:
  - `src/app/ui.py` — add `get_version()` helper; pass `version` to `render_index()` and `render_result()` contexts
  - `src/app/routes.py` — update `/healthz` to return `{"status": "ok", "version": ...}`
  - `src/app/templates/index.html` — add `<footer>` before `</main>`
  - `src/app/templates/result.html` — add `<footer>` before `</article>`
  - `src/app/templates/error.html` — add `<footer>` for consistency (open question: spec only names index and result, but error pages should also show version so the owner can distinguish builds even on error)
  - `tests/unit/test_health.py` — update assertion to include `"version"`
  - `tests/holdout_test_issue_32.py` — acceptance tests for AC1, AC2, AC3
- Types and signatures:
  - `def get_version() -> str:` in `ui.py` — reads `importlib.metadata.version("app")`, returns `"unknown"` on `PackageNotFoundError`. Pure function, no side effects, fully testable via patching.
  - `def render_index(request: Request) -> HTMLResponse:` — new context key `"version": get_version()`
  - `def render_result(request: Request, result: DecodeResult, language: str) -> HTMLResponse:` — new context key `"version": get_version()`
  - `def healthz() -> dict[str, str]:` — returns `{"status": "ok", "version": get_version()}`
- Tests to add (and why each fails today):
  - `tests/unit/test_health.py:test_healthz()` — currently asserts `{"status": "ok"}` exactly; will fail because `"version"` key is missing. After the change it must assert `{"status": "ok", "version": "0.1.0"}` (or `"unknown"` in uninstalled env).
  - `tests/holdout_test_issue_32.py:test_healthz_returns_version` — AC1: GET /healthz returns JSON with `"status": "ok"` and a non-empty `"version"` string. Fails today because `/healthz` has no `"version"` key.
  - `tests/holdout_test_issue_32.py:test_index_contains_version_footer` — AC2: GET / returns HTML with a `<footer>` element containing the version string. Fails today because no footer exists.
  - `tests/holdout_test_issue_32.py:test_version_from_metadata_or_unknown` — AC3: when `importlib.metadata.version("app")` succeeds, returns that value; when it raises `PackageNotFoundError`, returns `"unknown"`. Fails today because `get_version()` does not exist.
- Automated verification: `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest tests/unit/test_health.py tests/holdout_test_issue_32.py`
- Manual verification:
  1. Run `uv run fastapi dev src/app/main.py`.
  2. Open `http://localhost:8000/healthz` — see `{"status": "ok", "version": "0.1.0"}`.
  3. Open `http://localhost:8000/` — scroll to bottom, see `brevkoll 0.1.0` in small muted text.
  4. Upload a letter, get a result — scroll to bottom, see the same footer.
  5. Trigger an error page — verify footer is present there too.
- Threat-model controls implemented:
  - LLM02 Sensitive information disclosure: version is read from package metadata only (non-sensitive, already available via `pip show`). No secrets or PII included.
  - Web: authn/z, IDOR, CSRF, SSRF, upload handling: no new vectors introduced. One extra JSON field and one HTML fragment.
- Docs touched: none — this phase changes no command, env var, route limit or user-facing behaviour that a user or operator needs to document. The README's "how to run" and env vars are unchanged.

## Phase 2: (none)

## Docs (the app's own, not the factory's)
`README.md` — no changes needed. The README describes how to run the app and env vars; version display is a visibility aid, not a configuration or runtime change.
`AGENTS.md` — no changes needed.

## Architecture contracts
No new import rules needed. `importlib.metadata` is stdlib; the existing `.importlinter` contracts are unaffected.

```ini
```

## Decisions (ADRs)
None. The decision to use `importlib.metadata.version("app")` with `"unknown"` fallback is prescribed by the spec. No alternative was considered significant enough for an ADR.

## Dependencies added (Python and system)
None. `importlib.metadata` is part of the Python standard library (3.8+); the project targets Python 3.12.

## What I am unsure about
1. **CSS for the footer:** The spec says "small, muted text" but there is no existing `.footer` class in `static/style.css`. I will add a minimal inline style block (or a small CSS rule) for `.footer` with `font-size: 0.8em; color: #888; text-align: center; padding: 1rem 0;`. The human should review the CSS choice.
2. **error.html footer:** The spec only names index and result pages. I am including error.html for consistency so the owner can distinguish builds even on error pages, but this is a slight spec extension.
3. **result.html is an HTMX fragment:** The result page is injected via HTMX into `#result`. Adding a `<footer>` inside the `<article>` means it will appear inline after the result content. This matches the spec's intent ("result pages include a `<footer>` element").

## Notes from implementation
- Phase 1 completed on 2026-11-22. All 247 tests pass (1 skipped). Lint, format, and pyright clean.
- CSS for `.footer` was added to `static/style.css` (not inline `<style>`) after `test_no_inline_style_or_emoji` rejected inline styles. Used `var(--muted)` instead of hardcoded `#888` to respect dark-mode theming.
- `render_error()` also receives `version` (not in original plan) so error pages show the footer for consistency.
- `get_version()` is a pure function — no dependency injection needed. Tests patch `importlib.metadata.version` directly.
