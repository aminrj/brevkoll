# Plan: #29 Accept 256 KB PDFs without "File too large"
Status: approved

## Phase 1: Raise Starlette `FormParser.max_part_size` to `MAX_BYTES`

> **Deviation from plan:** The original plan assumed `File(max_file_size=MAX_BYTES)` on the route parameters. FastAPI 0.165.0 does not expose `max_file_size` on `File()`. The actual bottleneck is Starlette's `FormParser.max_part_size` (default 1 MB), which is set in `Request.form()`. The fix patches `StarletteRequest._get_form` at module load time to default `max_part_size=MAX_BYTES`.

- [x] **Files:**
  - `src/app/upload.py` — added `MAX_PART_BYTES = 10 * 1024 * 1024` (mirrors `MAX_BYTES`).
  - `src/app/main.py` — `_patch_request()` monkey-patches `StarletteRequest._get_form` to use `max_part_size=MAX_PART_BYTES`.
  - `tests/unit/test_upload.py` — added `test_form_parser_allows_up_to_max_bytes` inspecting `_get_form`'s default.

- [x] **Types and signatures:**

  No new public types. One new constant `MAX_PART_BYTES` in `app.upload`. The `_patch_request()` function is private.

- [x] **Tests added (and why each fails today):**

  1. `test_form_parser_allows_up_to_max_bytes` — inspects `StarletteRequest._get_form`'s `max_part_size` default parameter. **Fails today** because the default is 1 MB. **Succeeds after** the patch sets it to `MAX_BYTES`.

  The existing tests (`test_one_byte_over_limit_is_413`, `test_exactly_at_limit_is_accepted`) already verify AC3 and the 10 MB cap. They use `TestClient` which bypasses the `FormParser` entirely and will continue to pass.

- [x] **Automated verification:** `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` — all green.

- [x] **Manual verification:**
  1. `uv run fastapi dev src/app/main.py`
  2. Upload a 256 KB PDF via the UI (`/`) or `/api/decode` endpoint — should return 200 with decoded result.
  3. Upload a 11 MB file — should return 413 "File too large."

- [x] **Threat-model controls implemented:**
  - T1: Starlette's `FormParser.max_part_size` no longer blocks files under 10 MB.
  - T5: All existing controls (magic-byte check, `read_limited()` cap, rate limit, budget, middleware `Content-Length` pre-check) remain unchanged.

- [x] **Docs touched:** none — this change does not modify any user-visible contract. The 10 MB limit was always the documented cap; it was just not reachable for files between 1 MB and 10 MB due to a bug.

## Phase 2: Deferred

## Deferred

- **Q1 from research:** Is `File(max_file_size=MAX_BYTES)` the correct FastAPI API? — **No.** FastAPI 0.165.0's `File()` does not accept `max_file_size`. The correct approach is patching `StarletteRequest._get_form` to raise `max_part_size`.

- **Q2 from research:** Is `_BODY_SLACK = 64 KB` sufficient? — Accepted by the threat model. The middleware's `Content-Length` pre-check is defense-in-depth; `read_limited()` is the hard enforcement. The spec does not change this value.

## Docs (the app's own, not the factory's)
`README.md` — no change needed. The documented limit was already 10 MB; the bug was that files 1–10 MB were incorrectly rejected. Once fixed, the docs already describe correct behavior.

`AGENTS.md` — no change. The stack and commands are unchanged.

## Architecture contracts
N/A — this change does not modify `routes.py` and does not introduce new cross-module dependencies.

## Decisions (ADRs)
- **Patch `StarletteRequest._get_form` instead of using a custom `Request` subclass.** FastAPI 0.165.0 does not support `request_class` on `FastAPI()` or `APIRouter()`. A monkey-patch at module import time is the simplest way to change the default `max_part_size` for all requests.

## Dependencies added (Python and system)
None.

## Notes from implementation
- The original plan assumed `File(max_file_size=MAX_BYTES)` works in FastAPI. It does not — `File()` in FastAPI 0.165.0 has no `max_file_size` parameter. The real limit is `FormParser.max_part_size` (1 MB default) in Starlette's `Request.form()`.
- `TestClient` bypasses the `FormParser` entirely (sends data directly to the ASGI app), so integration-style tests with large files would pass even without the fix. The test inspects `_get_form`'s signature default instead.
- The `_patch_request()` function runs at module import time (top-level call), so the patch is in place before any request is handled.

## What I am unsure about
None.
