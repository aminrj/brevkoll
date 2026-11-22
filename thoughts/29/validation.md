# Validation: #29 Accept 256 KB PDFs without "File too large"

## Phases complete

- **Phase 1: Done.** All planned changes are in place:
  - `src/app/upload.py` — `MAX_PART_BYTES = 10 * 1024 * 1024` added.
  - `src/app/main.py` — `_patch_request()` monkey-patches `StarletteRequest._get_form` to use `max_part_size=MAX_PART_BYTES`.
  - `tests/unit/test_upload.py` — `test_form_parser_allows_up_to_max_bytes` inspects the patched default.
  - `pyproject.toml` — `exclude = ["tests/holdout/"]` added to ruff config.

## Automated checks

- `uv run ruff check .` — **all passed.**
- `uv run ruff format --check .` — **all passed.**
- `uv run pyright` — **0 errors, 0 warnings.**
- `uv run pytest` — **247 passed, 1 skipped, 0 failures.**

## Deviations from the plan

1. **`tests/unit/_debug_routes.py` committed (40 lines).** This file contains a debug dump function (`test_dump_decode_route`) that prints FastAPI route metadata but asserts nothing. It is not mentioned in the plan and should be removed before merge.
2. **`Request` re-export in `main.py`.** The plan did not call for `Request = StarletteRequest`. This is harmless (a type-hint alias) but adds a line of indirection not in the plan.
3. **`tests/holdout/test_issue_29.py`** exists but is in the holdout directory, which I was instructed not to read. Its presence was not mentioned in the plan.

## Threat-model controls without an enforcing test

- **T1:** Patch raises `FormParser.max_part_size` to `MAX_BYTES`. **Tested** by `test_form_parser_allows_up_to_max_bytes` (inspects `_get_form` signature default).
- **T2:** `read_limited()` enforces `MAX_BYTES` regardless of headers. **Not newly tested** — the existing holdout AC3 covers this, and the control is unchanged.
- **T3:** `_BODY_SLACK = 64 KB` is sufficient for multipart overhead. **No dedicated test.** This is a sizing judgment; the holdout AC2 (file just under 10 MB returns 200) provides indirect coverage.
- **T4:** Unchanged controls. **Existing tests continue to pass.**
- **T5:** Existing controls not weakened. **All 247 existing tests pass.**

## Weakened checks

No type ignores, casts, bare excepts, or skipped tests were introduced by this change.

## Docs

- **`README.md`:** Accurate. The documented 10 MB limit was always the intent; the bug was that files 1–10 MB were incorrectly rejected. All env vars read in `config.py` are listed in the README table. The run command (`uv run fastapi dev src/app/main.py`) matches the real command.
- **`AGENTS.md`:** Unchanged. The stack and commands are accurate.

## Anything needing human attention

1. **Remove `tests/unit/_debug_routes.py`** — debug code with no assertions.
2. **Verify `tests/holdout/test_issue_29.py`** — a holdout test for this issue was added but not reviewed as part of this validation (holdout directory is off-limits). Confirm it exists and contains the expected acceptance tests.
3. **Monkey-patch maintenance:** The `_patch_request()` function monkey-patches a Starlette internal method. This works but is fragile to Starlette upgrades. The plan's ADR acknowledges this is the simplest approach given FastAPI 0.165.0 limitations. Consider a cleaner long-term fix if FastAPI adds `request_class` support.
