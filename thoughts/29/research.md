# Research: #29 Accept 256 KB PDFs without "File too large"

## What exists

**`src/app/upload.py`** — The upload module owns the file-size contract.
- `MAX_BYTES = 10 * 1024 * 1024` (10 MB) at line 7 — the hard upper bound.
- `read_limited(file, max_bytes=MAX_BYTES)` at line 13 — reads an `UploadFile` in 64 KB chunks (`_CHUNK`), raises `TooLarge` when total exceeds `max_bytes`.
- `sniff_kind(data)` at line 24 — magic-byte check for PNG, JPEG, PDF. Filename and declared content-type are ignored.

**`src/app/routes.py`** — The FastAPI router.
- `build_router()` at line 17 creates the router.
- `decode()` POST `/api/decode` at line 50 — accepts `file: Annotated[UploadFile, File()]` and `language: Annotated[str, Form()]`.
- `decode_ui()` POST `/ui/decode` at line 57 — same parameters, returns HTML.
- Both call `run(file, language)` which calls `await read_limited(file)` at line 30.

**`src/app/main.py`** — App factory and middleware.
- `limit_body` middleware at line 72 — defense-in-depth: rejects POST requests to decode paths where `Content-Length` header exceeds `MAX_BYTES + _BODY_SLACK` (10 MB + 64 KB). Only fires when header is present and numeric.
- `security_headers` middleware at line 88 — adds CSP.
- Exception handlers at lines 96–106 — `AppError` → status/message, `RequestValidationError` → 422.

**`src/app/errors.py`** — Error classes.
- `TooLarge` at line 16 — `status_code = 413`, `message = "File too large."`.

**`src/app/decode.py`** — Decode pipeline (OCR → redact → LLM → dates → ICS). Not touched by this issue.

**`tests/unit/test_upload.py`** — Upload module tests.
- `test_read_limited_rejects_over_limit` (line 28) — verifies `read_limited()` raises `TooLarge`.
- `test_one_byte_over_limit_is_413` (line 48) — end-to-end via TestClient.
- `test_exactly_at_limit_is_accepted` (line 54) — end-to-end at exactly 10 MB.

**`tests/unit/test_decode_api.py`** — API-level tests (payload shape, language, redaction, model output validation, route allowlist).

## Relevant code (file:line)

| Location | Role |
|---|---|
| `src/app/upload.py:7` | `MAX_BYTES = 10 * 1024 * 1024` |
| `src/app/upload.py:8` | `_CHUNK = 64 * 1024` |
| `src/app/upload.py:13-21` | `read_limited()` — the app's enforcement of `MAX_BYTES` |
| `src/app/routes.py:50-55` | `/api/decode` — `File()` parameter, no `max_file_size` |
| `src/app/routes.py:57-63` | `/ui/decode` — same |
| `src/app/main.py:21` | `_BODY_SLACK = 64 * 1024` |
| `src/app/main.py:83-85` | Middleware `Content-Length` pre-check |
| `src/app/errors.py:16-18` | `TooLarge` → 413 |
| `tests/unit/test_upload.py:48-51` | Holdout AC3 (1 byte over → 413) |
| `tests/unit/test_upload.py:54-55` | Holdout AC2 (at limit → 200) |

## Where untrusted input enters

1. **`src/app/routes.py:52`** — `file: Annotated[UploadFile, File()]` on `/api/decode`. FastAPI's `File()` has a **default `max_file_size=1_000_000` (1 MB)**. A 256 KB file exceeds this default and is rejected by FastAPI before `read_limited()` ever runs. This is the root cause.
2. **`src/app/routes.py:60`** — `file: Annotated[UploadFile, File()]` on `/ui/decode`. Same issue.
3. **`src/app/main.py:83-85`** — Middleware checks `Content-Length` header against `MAX_BYTES + _BODY_SLACK`. This is secondary; it only triggers when the header is present and numeric.
4. **`src/app/upload.py:24-32`** — `sniff_kind()` validates magic bytes. Filename and declared content-type are ignored (safe).

## Constraints found (CI, system packages, data, deployment)

- **No database.** The app is stateless; the upload pipeline is the only stateful path.
- **Single-user, private cluster.** Memory is not a concern; the 10 MB cap is sufficient.
- **TestClient** in tests bypasses the HTTP layer, so `raise_server_exceptions=False` is needed to see 4xx/5xx responses. The existing tests at `test_upload.py:48-55` already use this pattern.
- **Holdout tests** live in `tests/holdout/` (not read per hard rules). AC1 (256 KB PDF → 200) and AC2 (near 10 MB → 200) are not yet implemented.
- **Pyright, ruff, quality.sh** — all checks must pass. The plan calls for a single-line change per `File()` call plus a test.

## Open questions for the human

1. The spec sketch says to set `max_file_size=MAX_BYTES` on the `File()` parameters. FastAPI's `File()` type accepts a `max_file_size` keyword argument — is this the correct API, or should we use `UploadFile` directly with a size parameter?
2. `_BODY_SLACK` is 64 KB. For a 10 MB file with multipart boundaries and metadata, the overhead is typically under 1 KB. Is 64 KB sufficient, or should it be larger? (The threat model accepted this as-is.)
