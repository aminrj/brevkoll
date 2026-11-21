# Research: #1

Scope: brevkoll v1 letter decoder (`thoughts/1/spec.md`, `thoughts/1/threat-model.md`). I did not read `tests/holdout/` (forbidden by AGENTS.md) or `.gitea/workflows/`; I only know the holdout file names from `git ls-files`.

## What exists

The repo is the factory template with almost no app code. Nothing from the spec is implemented.

- A FastAPI app factory `create_app()` with a single `GET /healthz` route and a module-level `app = create_app()`.
- One unit test for `/healthz`.
- A Dockerfile, a `pyproject.toml` and `uv.lock`.
- Guard scripts and templates (`scripts/`, `.factory/`).
- Gate 1 artifacts: the spec, the threat model (all decisions ACCEPTED) and holdout tests, which are listed but unread.
- No OCR, redaction, date parser, LLM client, ICS builder, rate limiter, upload handling, HTML page or static files.
- No config module.

## Relevant code (file:line)

- `src/app/main.py:4-11`: `create_app()` builds `FastAPI(title="app", docs_url=None, redoc_url=None)`. It takes no arguments and reads no environment variables yet. The spec requires reading config from the environment at creation time.
- `src/app/main.py:7-9`: `/healthz`, the only route.
- `src/app/main.py:14`: `app = create_app()` runs at import time. The Dockerfile CMD uses `app.main:app`. Any env validation done inside `create_app()` (for example the fake-provider guard) will also run at import.
- `src/app/__init__.py`: empty.
- `tests/unit/test_health.py:1-10`: the only test. It uses `TestClient(create_app())`.
- `tests/integration/.gitkeep`: no integration tests.
- `tests/holdout/`: contains `test_acceptance.py`, `fixtures/school-letter.png` and `fixtures/school-letter.txt`. Contents not read.
- `pyproject.toml:4-6`: the only runtime dependency is `fastapi[standard]>=0.115`.
- `pyproject.toml:9-14`: dev dependencies are pytest, httpx, ruff, pyright.
- `pyproject.toml:18-19`: pytest `testpaths` are `tests/unit` and `tests/integration`, with `pythonpath = ["src"]`. Holdout runs only in CI.
- `pyproject.toml:25-31`: ruff selects `E,F,I,B,UP,S,BLE`. `S` (bandit) flags `subprocess` use, and `BLE` flags blind excepts. Pyright runs in standard mode on `src` only.
- `uv.lock` already contains these packages, pulled in by `fastapi[standard]`: `python-multipart`, `jinja2`, `pydantic`, `pydantic-settings`, `httpx`, `uvicorn`. It has no Pillow, no PDF library (pdf2image, pypdf, PyMuPDF), no pytesseract, no `icalendar` and no rate-limit library.
- `Dockerfile:1-12`:
  - Base is `python:3.12-slim`, built with `uv sync --frozen --no-dev`. It does not install tesseract or poppler.
  - It runs as non-root uid 10001.
  - It sets no read-only filesystem and creates no data directory.
  - The CMD runs a single uvicorn worker with no `--proxy-headers` or `--forwarded-allow-ips` flags.
- `.gitignore`: `.env*` and `secrets/` are ignored.
- `AGENTS.md`: adding a dependency requires the approved plan to name it. The "What this repo is" paragraph is still a placeholder.

## Where untrusted input enters

No code exists for these paths yet, so each is a future entry point taken from the spec and threat model.

1. `POST /api/decode` multipart:
   - `file`: bytes, filename and declared content type.
   - `language`: free text.
2. OCR text derived from the file. A letter can contain prompt injection text, URLs, and strings that look like prompt delimiters or ICS syntax.
3. Model response (`FAKE_LLM_RESPONSE` under the fake provider, a real provider otherwise). This is the `summary` and `actions` content that goes into JSON, HTML and possibly ICS `DESCRIPTION`.
4. Subprocess and library parsers: Tesseract, a PDF rasterizer and an image decoder, all of which parse hostile files.
5. HTTP headers: `X-Forwarded-For` for the rate limit, and the reverse proxy's forwarding behavior.
6. Environment: `LLM_PROVIDER`, `FAKE_LLM_LOG`, `FAKE_LLM_RESPONSE`, `APP_DATA_DIR`, `RATE_LIMIT_PER_MINUTE`, `APP_ENV`, `TRUSTED_PROXIES`, `DAILY_MODEL_CALL_BUDGET`. These are trusted, but they select the provider and paths.
7. The browser page: the response text is rendered in the DOM, and the `.ics` is downloaded.

## Constraints found (CI, system packages, data, deployment)

- Tesseract is not installed in this sandbox (`which tesseract pdftoppm` returned nothing). Local OCR tests cannot run here without an injected OCR function. The spec says CI already has `tesseract-ocr-swe`. I could not check, because workflows are off limits.
- The Dockerfile has no tesseract, `tesseract-ocr-swe` or poppler. The spec says they "must be added".
- Python dependencies for OCR, image and PDF handling and ICS output are not in the lock. Per AGENTS.md they need explicit naming in the approved plan.
- `httpx` is a dev-only dependency in `pyproject.toml`. Its presence in `uv.lock` comes from `fastapi[standard]`, so I did not verify whether the image (`--no-dev`) installs it.
- The contract says `create_app()` reads env at creation time. Today the module-level `app = create_app()` freezes config at import, so tests that set env must call `create_app()` themselves.
- State required by the threat model (rate limiter, daily budget, OCR concurrency limit) is in memory, so it only works for one worker. The Dockerfile starts one worker.
- The threat model requires the rate limit to read the client IP via `TRUSTED_PROXIES`. Under `TestClient` the peer host is `testclient`, which is not an IP.
- AGENTS.md requires injected dependencies (clock, HTTP client, LLM client). The current app has no dependency-injection structure.
- No real LLM provider is defined yet. Only `fake` is specified. The Gate 2 model choice (local or cloud) is not recorded in any file.
- Limits from the spec: 3 pages and 10 MB maximum.
- The spec refers to "the two" languages the first users ask for, but gives no list.
- The HTML page and static files are net new. The threat model's route allowlist test expects only the page, static files, health and `/api/decode`.

## Open questions for the human

1. **Model provider:** Local or cloud model for the default, and which one (endpoint, model name)? Only `fake` is specified, so what does `LLM_PROVIDER` accept besides `fake`?
2. **Fake-provider guard vs holdout tests:** the threat model proposes refusing `fake` unless `APP_ENV` is `test` or `dev`. I can't read the holdout tests, so I don't know whether they set `APP_ENV`. Do they, or should the guard be dropped or inverted (for example, refuse only when `APP_ENV=prod`)?
3. **OCR in tests:** The holdout fixture is a PNG with a `.txt` beside it. Is Tesseract expected to be present when holdout tests run (CI only), and should unit tests run locally without it through an injected OCR function?
4. **Dependencies:** May the plan add Pillow, a PDF rasterizer or reader (which one: `pdf2image` plus poppler, PyMuPDF, or `pypdf`), `pytesseract` (or direct `subprocess`), and `httpx` as a runtime dependency? Is a hand-written ICS builder acceptable instead of `icalendar`?
5. **Languages:** Which ISO 639-1 codes go in the allowlist? The spec only says "the two".
6. **Access control:** Should the service stay public (R3), or sit behind proxy auth? This changes the rate-limit design.
7. **Proxy IP:** What IP or CIDR does the reverse proxy for the app's lab address use, and does it set `X-Forwarded-For`? This sets `TRUSTED_PROXIES`.
8. **Budget:** Is a call-count daily budget enough, and what default for `DAILY_MODEL_CALL_BUDGET`?
9. **Dates without a year:** The threat model injects a clock for `4/12`. Should a year-less date resolve to the next occurrence, or the current year?
10. **Frontend:** Is the HTMX page in scope for this issue, or only the API? The spec's user flow and sketch include a page. How should the HTMX asset be delivered (vendored file or CDN)?
