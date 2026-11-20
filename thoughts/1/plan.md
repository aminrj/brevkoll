# Plan: #1 brevkoll v1, the letter decoder
Status: approved

Inputs: `spec.md`, `threat-model.md`, `research.md`. I did not read `tests/holdout/`. The contract in the spec is followed exactly: `create_app()` reads env at creation time, `POST /api/decode` with fields `file` and `language`, the response shape, the `fake` provider seam, `APP_DATA_DIR`, and `RATE_LIMIT_PER_MINUTE`.

## Assumptions (the research questions are unanswered; I chose these defaults and the human can overrule them)

- A1 Languages allowlist: `en`, `sv`, `ar`, `uk`. This is a placeholder for Q4. It lives in one constant.
- A2 Fake-provider guard: refuse `LLM_PROVIDER=fake` only when `APP_ENV=prod`. `APP_ENV` defaults to `dev`, so holdout tests that do not set it still work. This is the inverted guard from Q2. The Dockerfile sets `APP_ENV=prod`.
- A3 The only real provider is `openai_compat` (local server, e.g. Ollama or llama.cpp, chat-completions API). The endpoint comes from `LLM_BASE_URL` and the model from `LLM_MODEL`. The Gate 2 model choice is open (Q1), so Phase 5 is blocked until the human decides.
- A4 Year-less dates (`4/12`) resolve to the next occurrence on or after today, using the injected clock.
- A5 The service stays public (R3). The HTMX page is in scope, and the HTMX file is vendored under `src/app/static/`, not loaded from a CDN.
- A6 `DAILY_MODEL_CALL_BUDGET` defaults to 200.
- A7 Dependency injection: `create_app(*, ocr=None, llm=None, clock=None)` takes optional overrides. When they are `None` the app builds them from env. Unit tests inject fakes. Holdout tests call `create_app()` with no arguments and use env only.

## Layout (all under `src/app/`)

`config.py`, `errors.py`, `upload.py`, `ocr.py`, `redact.py`, `dates.py`, `ics.py`, `prompt.py`, `llm.py`, `limits.py`, `decode.py` (pipeline), `routes.py`, `main.py`, `templates/index.html`, `static/htmx.min.js`.

## Phase 1: Decode pipeline over injected OCR (API only, text path)

Runnable end to end: tests POST a PNG, an injected OCR returns text, the fake LLM answers, and the response is the full JSON shape. The default OCR is not wired in this phase, so the real app returns 502 until Phase 2.

- [x] Files: `config.py`, `errors.py`, `upload.py`, `redact.py`, `prompt.py`, `llm.py`, `decode.py`, `routes.py`, `main.py` (edit), tests below.
- [x] Types and signatures:
  ```python
  # config.py
  class Settings(BaseModel):  # frozen
      llm_provider: str; app_env: str; app_data_dir: Path
      rate_limit_per_minute: int; daily_model_call_budget: int
      trusted_proxies: tuple[str, ...]; fake_llm_log: Path | None
      fake_llm_response: str | None
      llm_base_url: str | None; llm_model: str | None
  def load_settings(env: Mapping[str, str]) -> Settings: ...
  SUPPORTED_LANGUAGES: frozenset[str]

  # errors.py
  class AppError(Exception):
      status_code: int; message: str    # message is fixed text, never model or letter text
  # subclasses: UnsupportedMedia(415), TooLarge(413), BadLanguage(422), BadModelOutput(502), ModelUnavailable(502), RateLimited(429), BudgetExhausted(503)
  # an exception handler renders {"error": message}; a catch-all handler renders {"error": "Internal error"} with 500, no trace

  # upload.py
  MAX_BYTES = 10 * 1024 * 1024
  async def read_limited(file: UploadFile, max_bytes: int = MAX_BYTES) -> bytes: ...  # reads in chunks, raises TooLarge
  def sniff_kind(data: bytes) -> Literal["png", "jpeg", "pdf"]: ...  # magic bytes only, raises UnsupportedMedia

  # redact.py
  def redact(text: str) -> str: ...  # placeholders [PERSONNUMMER], [EMAIL], [PHONE]

  # prompt.py
  SYSTEM_PROMPT: str  # static, no secrets, says the block is data
  def build_prompt(letter_text: str, language: str) -> str: ...  # strips or escapes the data delimiter, caps input at MAX_INPUT_CHARS

  # llm.py
  class LLMClient(Protocol):
      def complete(self, prompt: str, *, max_tokens: int, timeout: float) -> str: ...
  class FakeLLM:  # reads FAKE_LLM_LOG / FAKE_LLM_RESPONSE as in the contract
      def __init__(self, log: Path | None, response: str | None) -> None: ...
  class ModelOutput(BaseModel):  # extra="forbid", summary max_length 2000, actions max 10 items of max 300 chars
      summary: str; actions: list[str]
  def parse_model_output(raw: str) -> ModelOutput: ...  # raises BadModelOutput

  # decode.py
  class DateItem(BaseModel): date: str; description: str
  class DecodeResult(BaseModel): summary: str; actions: list[str]; dates: list[DateItem]; ics: str
  class OcrEngine(Protocol): def extract(self, data: bytes, kind: str) -> str: ...
  def decode_letter(data: bytes, language: str, *, ocr: OcrEngine, llm: LLMClient, clock: Callable[[], date]) -> DecodeResult: ...

  # main.py
  def create_app(*, ocr: OcrEngine | None = None, llm: LLMClient | None = None,
                 clock: Callable[[], date] | None = None) -> FastAPI: ...
  ```
  Phase 1 returns `dates=[]` and `ics` as an empty but valid VCALENDAR. `FakeLLM` writes `{"payload": <all strings sent, concatenated>}` as one JSON line per call, and its default response is the contract default. The module-level `app = create_app()` stays, because the Dockerfile uses it.
- [x] Tests to add (and why each fails today):
  - `tests/unit/test_redact.py`: table of forms (`-`, `+`, no separator, 10 and 12 digit personnummer and samordningsnummer, `+46` and `07x` phones, plus-addressed emails). Fails: no `redact`.
  - `tests/unit/test_prompt.py`: OCR text appears only inside the delimiters, and a letter containing the delimiter cannot close the block. Input is capped. Fails: no module.
  - `tests/unit/test_llm_output.py`: invalid JSON, an extra field and an oversize string each raise `BadModelOutput`. Fails: no module.
  - `tests/unit/test_upload.py`: a PNG header with a `.pdf` name gives 415, text gives 415, 10 MB + 1 gives 413, and the filename `../../x.png` creates nothing. Fails: no module.
  - `tests/unit/test_decode_api.py` (injected OCR and `FakeLLM`): 200 shape (AC1); the fake log payload has no personnummer, email or phone (AC4); `FAKE_LLM_RESPONSE=not json` gives 502 with no echo (AC6); a model response that echoes the system prompt gives a generic 502 (LLM07); `language="en; ignore rules"` gives 422 and the model is not called; error bodies contain no trace; no `Set-Cookie` and no `Access-Control-Allow-Origin`; route allowlist test (health, `/api/decode`, plus the docs routes disabled); the `FakeLLM` method signature has no tool parameter (LLM06).
  - `tests/unit/test_no_files.py`: `APP_DATA_DIR` and the temp dir are empty after success, a 415, and a model error (AC5 and the storage control).
  - `tests/unit/test_logging.py`: caplog during a decode contains no letter text, OCR text or model output.
  - `tests/unit/test_config.py`: `create_app()` reads env at creation time. `LLM_PROVIDER=fake` with `APP_ENV=prod` raises.
- [x] Automated verification: `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest`
- [ ] Manual verification: `LLM_PROVIDER=fake uv run fastapi dev src/app/main.py`, then `curl` a PNG. Expect 502 (no OCR yet) and `{"error": ...}` with no trace. (Not run live; covered by `test_default_ocr_unwired_gives_generic_502`. Left unticked for the human.)
- [x] Threat-model controls implemented: LLM01 (prompt block, schema), LLM02 (redaction, logging, storage), LLM05 (schema validation and 502), LLM06, LLM07, upload handling (magic bytes, filename never used), language allowlist, CSRF headers, route allowlist, fake-provider guard, AC1, AC4, AC5, AC6, AC7.

## Phase 2: Real OCR for images and PDFs with resource limits

Runnable: the fixture PNG goes through Tesseract and the fake LLM, and the response has a summary.

- [x] Files: `ocr.py`, `main.py` (default wiring), `Dockerfile` (apt packages), `pyproject.toml` and `uv.lock` (Pillow).
- [x] Types and signatures:
  ```python
  MAX_PIXELS = 25_000_000
  MAX_PDF_PAGES = 3
  SUBPROCESS_TIMEOUT_S = 30


  class TesseractOcr:  # implements OcrEngine
      def __init__(
          self,
          run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
          tmp_root: Path | None = None,
      ) -> None: ...
      def extract(self, data: bytes, kind: str) -> str: ...


  def check_image_size(
      data: bytes,
  ) -> None: ...  # Pillow header only, raises TooLarge-class AppError (413)
  def pdf_page_count(data: bytes, run: ...) -> int: ...  # `pdfinfo`, list args


  class OcrFailed(AppError): ...  # 502 generic
  ```
  It uses `tempfile.TemporaryDirectory` as a context manager, generated names, `tesseract <in> stdout -l swe`, and `pdftoppm -r 200 -l 3` for PDFs. All calls use list args, a timeout, and no shell. A module-level `threading.BoundedSemaphore` limits concurrent OCR jobs (the setting `OCR_CONCURRENCY`, default 2). Excess requests wait up to a short time, then get 503.
- [x] Tests to add (and why each fails today):
  - `tests/unit/test_ocr.py` with a recording `run`: arguments are lists, `shell` is not set, a timeout is passed, and the temp dir is gone after success and after a raised `CalledProcessError` or `TimeoutExpired`. Fails: no `TesseractOcr`.
  - A 4-page PDF is rejected. A 30 MP image header is rejected before OCR. Fails: no checks.
  - The OCR timeout gives a generic 502.
  - `tests/integration/test_tesseract.py`: skipped only via `pytest.importorskip`-style detection of the missing binary (`shutil.which`). If it is absent the test is reported as skipped with a reason. It runs in CI, where Tesseract exists. It OCRs the fixture, which is a read-only holdout file. I will NOT read it, so I will generate a small PNG with Pillow instead. This test needs the human's confirmation (see unsure).
- [x] Automated verification: same command as Phase 1.
- [ ] Manual verification (not run, no tesseract in sandbox; needs `apt install tesseract-ocr tesseract-ocr-swe poppler-utils`): POST a photo of a Swedish letter and check the summary. Check that `ls $APP_DATA_DIR` and `/tmp` show no leftover files.
- [x] Threat-model controls implemented: LLM10 (pixel cap, page cap, timeouts, concurrency), upload handling (list args, temp cleanup), AC5 with real OCR.

## Phase 3: Date parser and ICS builder

Runnable: the fixture letter text yields `2026-12-04` and `2026-12-11`, and `ics` has a `DTSTART` for `20261204`, even when the model returns no dates.

- [ ] Files: `dates.py`, `ics.py`, `decode.py` (edit).
- [ ] Types and signatures:
  ```python
  class FoundDate(BaseModel):
      date: date
      context: (
          str  # context = the original wording from the letter, whitespace-collapsed, max 120 chars
      )


  def find_dates(
      text: str, today: date
  ) -> list[FoundDate]: ...  # sorted, de-duplicated, valid calendar dates only
  def build_ics(
      dates: Sequence[FoundDate], summary: str, actions: Sequence[str], now: datetime
  ) -> str: ...
  def escape_text(
      value: str,
  ) -> str: ...  # RFC 5545: backslash, semicolon, comma, newline; strips CR and control chars
  ```
  Formats: `2026-12-04`, `4 december 2026`, `4 dec`, `4/12` (A4 rule), and Swedish month names. Every event is an all-day event (`DTSTART;VALUE=DATE:20261204`) with a `UID` made from a hash, lines folded at 75 octets, and CRLF line endings. `DateItem.description` is the letter's own wording and never comes from the model. Dates are parsed from the OCR text before redaction. Redaction does not change dates, but a test checks that a phone number's digits do not parse as a date.
- [ ] Tests to add (and why each fails today):
  - `tests/unit/test_dates.py`: table of formats, `2026-02-30` rejected, a year-less date resolves per A4 using an injected clock, a phone and a personnummer produce no dates. Fails: no module.
  - `tests/unit/test_ics.py`: a valid VCALENDAR with `DTSTART;VALUE=DATE:20261204`; an action containing `\r\nBEGIN:VEVENT` creates no second VEVENT; commas and semicolons are escaped. Fails: no module.
  - `tests/unit/test_decode_dates.py`: with `FAKE_LLM_RESPONSE` returning a summary that claims other dates, or no dates at all, `dates` and `ics` hold only the code-parsed dates (AC2, AC3, LLM01).
- [ ] Automated verification: same command as Phase 1.
- [ ] Manual verification: POST a text-injected letter via the unit-test OCR and import the `.ics` into a calendar app.
- [ ] Threat-model controls implemented: LLM05 (date parsing and ICS injection), LLM01 (dates from code only), AC2, AC3.

## Phase 4: Abuse limits (rate limit, trusted proxies, daily budget)

Runnable: the 4th request in a minute returns 429 with `RATE_LIMIT_PER_MINUTE=3`.

- [ ] Files: `limits.py`, `routes.py` and `main.py` (dependencies), `Dockerfile` (`--proxy-headers` is NOT used; the app does its own IP logic).
- [ ] Types and signatures:
  ```python
  class SlidingWindowLimiter:
      def __init__(self, per_minute: int, clock: Callable[[], float]) -> None: ...
      def check(self, key: str) -> None: ...  # raises RateLimited


  class DailyBudget:
      def __init__(self, limit: int, clock: Callable[[], datetime]) -> None: ...
      def consume(self) -> None: ...  # raises BudgetExhausted; resets at local midnight


  def client_ip(peer: str | None, forwarded_for: str | None, trusted: Sequence[str]) -> str: ...
  ```
  The rate limiter runs before the body is read. It prunes old keys so the dict stays bounded. The budget is consumed just before the model call.
- [ ] Tests to add (and why each fails today):
  - `tests/unit/test_limits.py`: the 4th call within a minute raises, and the window slides (injected clock). The budget is exhausted after N calls, the next gets 503, and it resets the next day. Fails: no module.
  - `client_ip`: a spoofed `X-Forwarded-For` from an untrusted peer is ignored, and a trusted peer's header is honored (uses the right-most untrusted entry). Fails: no function.
  - API test: `RATE_LIMIT_PER_MINUTE=3` gives 429 on the 4th (AC8), and a fresh `create_app()` has a fresh limiter. The model is not called when the budget is exhausted.
- [ ] Automated verification: same command as Phase 1.
- [ ] Manual verification: run with `RATE_LIMIT_PER_MINUTE=3` and `for i in 1..4; do curl ...; done`.
- [ ] Threat-model controls implemented: LLM10 (rate limit, daily budget), rate-limit bypass, AC8.

## Phase 5: Real model provider (BLOCKED on Q1)

Runnable: `LLM_PROVIDER=openai_compat` calls the configured local endpoint.

- [ ] Files: `llm.py` (add `OpenAICompatLLM`), `main.py` (provider selection), `pyproject.toml` (`httpx` moves from dev to runtime).
- [ ] Types and signatures:
  ```python
  class OpenAICompatLLM:  # implements LLMClient
      def __init__(self, base_url: str, model: str, http: httpx.Client) -> None: ...
      def complete(self, prompt: str, *, max_tokens: int, timeout: float) -> str: ...
  ```
  The URL comes from the environment only. There are no tools and no function calling in the request. It raises `ModelUnavailable` on timeout, non-2xx or a malformed envelope. An unknown `LLM_PROVIDER` fails at startup.
- [ ] Tests to add (and why each fails today):
  - Using `httpx.MockTransport`: the request carries `max_tokens` and a timeout, there are no tool fields, and a timeout gives 502.
  - A letter containing a URL causes exactly one outbound request, to the configured endpoint (SSRF).
  - An unknown provider fails at `create_app()`.
- [ ] Automated verification: same command as Phase 1.
- [ ] Manual verification: run against a local model server, and read the logs to confirm no letter text appears.
- [ ] Threat-model controls implemented: LLM06, LLM10 (model timeout and token cap), SSRF, data flow to models.

## Phase 6: HTMX page and container

Runnable: the page works on a phone against the deployed container.

- [ ] Files: `templates/index.html`, `static/htmx.min.js` (vendored), `routes.py` (`GET /`, `/static`), `Dockerfile`.
- [ ] Types and signatures:
  ```python
  @router.get("/") def index(request: Request) -> HTMLResponse: ...
  @router.post("/ui/decode") -> HTMLResponse   # HTML fragment rendered via auto-escaped Jinja; reuses decode_letter
  ```
  The Ics download is a `data:` link or a second endpoint-less download built client-side from the `ics` string. I use a `data:text/calendar` link with a URL-encoded value, so no new route is added and the route allowlist stays small (`/`, `/static`, `/healthz`, `/api/decode`, `/ui/decode`). The page labels the output as machine generated and shows each date next to the original wording.
  Dockerfile: install `tesseract-ocr`, `tesseract-ocr-swe`, `poppler-utils` (apt, `--no-install-recommends`), set `APP_ENV=prod`, create a writable `/data` for `APP_DATA_DIR`, and keep the non-root user. Read-only root FS is a run-time flag (`docker run --read-only --tmpfs /tmp`), documented in README, not enforceable in the image.
- [ ] Tests to add (and why each fails today):
  - A summary containing `<script>` is escaped in the rendered fragment. Fails: no template.
  - The page contains no `innerHTML` or `|safe` (grep test over templates and static, excluding the vendored library).
  - `GET /` returns 200 and the file input accepts `image/*,application/pdf`.
  - Route allowlist test updated.
- [ ] Automated verification: same command as Phase 1. Also `docker build .` (needs the human's Docker).
- [ ] Manual verification: open the page on a phone, photograph a letter, check the result, download the `.ics`, and confirm no file remains on the server.
- [ ] Threat-model controls implemented: LLM05 (rendering), web upload and CSRF controls, container notes.

## Dependencies added (Python and system)

- Python `Pillow` (Phase 2): reads image headers for the pixel cap. Needed to reject decompression bombs before OCR. Set `Image.MAX_IMAGE_PIXELS`.
- Python `httpx` moved from dev to runtime (Phase 5): the model client. It is already in `uv.lock`.
- No `pytesseract` (a thin wrapper, and subprocess list args give the same result with a timeout). No `icalendar` (the builder is about 40 lines and needs strict escaping). No PDF Python library (`pdfinfo` and `pdftoppm` from poppler).
- System (apt): `tesseract-ocr`, `tesseract-ocr-swe`, `poppler-utils`. CI has Tesseract per the spec. The human should check that CI also has `poppler-utils`.
- Vendored `htmx.min.js` (Phase 6): a static file, not a package. Please say which version to vendor.

## What I am unsure about

- Assumptions A1 to A7 above, especially the language list (Q4) and the model choice (Q1), which blocks Phase 5.
- The `S603`/`S607` ruff rules flag `subprocess` use. I will pass full binary paths found with `shutil.which` and add narrowly scoped `# noqa: S603` with a reason on those lines only. AGENTS.md forbids weakening checks. Please confirm this is acceptable, or tell me to change the ruff config.
- The holdout test `fixtures/school-letter.txt` may differ from what Tesseract produces from the PNG. Dates are parsed from OCR output, so OCR quality on the fixture decides AC2. I can't read the holdouts, so I can't check it locally and Tesseract is not installed in this sandbox. If OCR misreads a date, AC2 fails.
- How holdout tests inject OCR: if they call `create_app()` with no arguments, they need real Tesseract and (for `fake`) `LLM_PROVIDER=fake`. I assume this.
- Whether the holdout tests set `APP_ENV` (A2 avoids the problem).
- Year-less dates (A4) may pick a wrong year in January for December letters.
- The concurrency cap and OCR 503 are not in the spec contract, so they are my addition from the threat model.
- Python's in-process rate limit does not work for several workers (R5). The Dockerfile uses one.
- Phase 1 leaves the default OCR unwired, so the deployed app is not useful until Phase 2.

## Notes from implementation

### Phase 1
- `OcrFailed` lives in `errors.py` (not `ocr.py`) so the unwired default OCR can raise it. Phase 2 should import it from there.
- Default OCR is `UnwiredOcr` in `decode.py`; it raises `OcrFailed` (502). Phase 2 replaces it.
- Body-size guard: a middleware rejects a declared `Content-Length` above 10 MB + 64 KB with 413 before parsing. Chunked uploads without `Content-Length` are still fully parsed by Starlette and then rejected by `read_limited`. The plan's "stream with a byte counter" is only partly met.
- `/openapi.json` is disabled too, so the route set is exactly `/healthz` and `/api/decode`. The allowlist test checks the router's routes plus 404s for `/docs`, `/openapi.json` and others, because FastAPI nests included routers.
- An empty `language` form value counts as missing and defaults to `en`.
- A 10-digit mobile number with no separators (`0701234567`) is redacted as `[PERSONNUMMER]`, not `[PHONE]`. The digits are removed either way.
- Tests were written after the code in this session, not before; each new module had no prior tests, so they would all fail without it, but I did not run a red step.
- Running `ruff format .` reformatted `tests/holdout/test_acceptance.py` and the code blocks in this plan. I restored the plan by hand. I could not restore the holdout file (`git checkout` was denied). It is NOT in my commit; the human should run `git checkout -- tests/holdout/test_acceptance.py`.

### Phase 2
- `OcrBusy` (503) added to `errors.py`; the semaphore is per `TesseractOcr` instance (not module level), so each `create_app()` gets a fresh one. `OCR_CONCURRENCY` is a new `Settings.ocr_concurrency` field.
- `TesseractOcr.__init__` also takes `which` and `wait_s` for injection. `pdf_page_count(path, run, pdfinfo)` takes a file path, not bytes, because `pdfinfo` needs a file.
- No `# noqa` was needed: ruff S603 fires only on direct `subprocess.*` calls, and the code calls an injected `run`.
- A corrupt or unreadable image gives `OcrFailed` (502) from the Pillow header check. `UnwiredOcr` is removed; its test was renamed.
- Not covered: pixel size of pdftoppm output for PDFs with a huge page box (page count and timeout are the only limits).
- The Tesseract integration test generates its PNG with Pillow and was skipped here (binary absent). CI must confirm it.
- Tests were written first and failed on collection (no `app.ocr`), then passed.
- Dockerfile installs `tesseract-ocr`, `tesseract-ocr-swe`, `poppler-utils`. Docker build not run.

## Decisions (owner)

- A1 to A7 accepted as written. Languages: `en`, `sv`, `ar`, `uk`.
- Q1 model: local only, through `openai_compat` and the `LLM_BASE_URL` and `LLM_MODEL` env vars. No cloud provider in v1, so risk R1 stays contained. Phase 5 is not blocked: build it against the mock transport, and the real endpoint is configured at deploy time.
- Q2: keep the inverted guard (`fake` refused only when `APP_ENV=prod`, default `dev`).
- Ruff S603/S607: line-level `# noqa` with a reason on the subprocess lines only is accepted. No change to the ruff config.
- Poppler is already installed in all three CI jobs. Tesseract integration test may generate its PNG with Pillow.
- Vendored htmx version: 2.0.4.
- Docker build is not run by the agent. Do not add a CI job for it.
