# Research: #32 Show the app version on /healthz and in the page footer

## What exists

### Package metadata
- `pyproject.toml:1-2`: Project name is `"app"`, version `"0.1.0"`. `importlib.metadata.version("app")` will return `"0.1.0"` when the package is installed, and raise `PackageNotFoundError` when it is not.
- No dependency on `importlib.metadata` exists yet in the source code.

### Health endpoint
- `src/app/routes.py:42-44`: `GET /healthz` returns `{"status": "ok"}` as a plain dict (FastAPI auto-serialises to JSON). No version field.
- `tests/unit/test_health.py:6-10`: Single test asserts `{"status": "ok"}` exactly. This test will need updating to include `"version"`.

### Templates
- `src/app/templates/index.html:1-48`: Index page with `<main>` closing tag at line 46, `</body>` at line 47. No footer element.
- `src/app/templates/result.html:1-28`: Result page is an `<article>` fragment (injected via HTMX into `#result`). No footer.
- `src/app/templates/error.html:1`: Error template — also needs a footer for consistency.

### Route rendering
- `src/app/ui.py:58-60`: `render_index()` passes `{"languages": languages}` to `index.html`.
- `src/app/ui.py:63-70`: `render_result()` passes `{"result", "dates", "lang", "dir"}` to `result.html`.
- Neither function currently receives or passes a version string.

### Static assets
- `src/app/ui.py:14`: `STATIC_DIR = APP_DIR / "static"` — static files served at `/static`.

## Relevant code (file:line)

| Location | Role |
|---|---|
| `pyproject.toml:2-3` | Package name `"app"`, version `"0.1.0"` |
| `src/app/routes.py:42-44` | `/healthz` endpoint — returns `{"status": "ok"}` |
| `src/app/ui.py:58-60` | `render_index()` — builds index context |
| `src/app/ui.py:63-70` | `render_result()` — builds result context |
| `src/app/templates/index.html:46` | `</main>` tag — footer would go before this |
| `src/app/templates/result.html:28` | Last line — footer would go here |
| `tests/unit/test_health.py:6-10` | Existing healthz test |
| `tests/deploy/test_deploy_base.py:121` | Kustomize probe checks `/healthz` path |

## Where untrusted input enters

This issue does **not** introduce any new untrusted input paths. The version string comes from package metadata (`importlib.metadata`), which is a build-time constant, not user-controlled data. The only data flowing through the new code path is the version string itself, which is read from local filesystem metadata and passed to templates and a JSON response.

No existing untrusted input paths are affected:
- `POST /ui/decode` — user file upload + language choice (unchanged)
- `POST /api/decode` — user file upload + language choice (unchanged)
- `GET /healthz` — no input, only output changes

## Constraints found

1. **No new dependencies.** The spec explicitly forbids adding a dependency. `importlib.metadata` is in the Python standard library (3.8+), so `importlib.metadata.version("app")` is available with Python 3.12.
2. **No Dockerfile or CI changes.** The version must come from the installed package metadata, not from an env var baked into the image.
3. **`tests/unit/test_health.py:10`** asserts `{"status": "ok"}` exactly. Adding `"version"` will break this assertion unless the test is updated.
4. **Template rendering:** Jinja2Templates auto-escapes `.html` templates (`src/app/ui.py:50`). The version string is safe to interpolate directly.
5. **`result.html`** is an article fragment injected via HTMX, not a full page. The footer should be placed inside the article, before the closing `</article>`.
6. **`error.html`** should also receive the footer for consistency across all user-facing pages.

## Open questions for the human

1. Should the error page (`error.html`) also show the version footer, or only the index and result pages as stated in the spec?
2. The spec says the footer should contain `brevkoll <version>` — should this be a separate HTML element (e.g. `<footer class="footer">`) with existing CSS styling, or a new inline style? Is there an existing `.footer` class in `static/style.css`?
