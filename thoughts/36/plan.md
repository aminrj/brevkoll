# Plan: #36 Strip markdown code fences from model responses before parsing

Status: approved

## Phase 1: Strip markdown code fences in `parse_model_output`

- [x] **Files:**
  - `src/app/llm.py` — add `_strip_markdown_fence`, update `parse_model_output`
  - `tests/unit/test_llm_output.py` — add holdout tests for AC1–AC4 plus a backtracking safety test

- [x] **Types and signatures:**
  - `_strip_markdown_fence(raw: str) -> str` — pure function, no side effects
    - Regex: `^````?(?:json)?\s*\n(.*?)\s*````\s*$` with `re.DOTALL | re.UNICODE`
    - If no match, returns `raw` unchanged (backward compatible)
    - Group 1 is the trimmed inner content
  - `parse_model_output(raw: str) -> ModelOutput` — unchanged signature
    - Becomes: `return ModelOutput.model_validate_json(_strip_markdown_fence(raw))`
    - All existing error paths preserved (ValidationError → BadModelOutput)

- [x] **Tests to add (and why each fails today):**
  1. `test_fenced_with_json_tag_parses()` — AC1: response wrapped in ````json … ```` — currently raises `BadModelOutput`
  2. `test_fenced_without_language_tag_parses()` — AC2: response wrapped in ```` … ```` — currently raises `BadModelOutput`
  3. `test_plain_json_still_works()` — AC3: plain JSON with no fences — must still pass (regression guard)
  4. `test_fenced_with_invalid_inner_json_raises()` — AC4: fenced but invalid JSON inside — must still raise `BadModelOutput`
  5. `test_fenced_backticks_inside_json_preserved()` — threat model LLM05 control: backticks embedded in JSON content (not at boundaries) are preserved by the boundary-anchored regex; the full JSON is captured and parses correctly
  6. `test_no_closing_fence_rejected()` — threat model: truncated output with opening fence but no closing fence — should be rejected (validation fails on the raw string since regex doesn't match)
  7. `test_catastrophic_backtracking_does_not_hang()` — threat model LLM10 control: 10,000 backticks followed by valid JSON must not hang (timed test, 1 s cap)

- [x] **Automated verification:** `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest tests/unit/test_llm_output.py`

- [x] **Manual verification:**
  1. Run `uv run pytest` — all existing tests still pass
  2. Run `uv run fastapi dev src/app/main.py` with `FAKE_LLM_RESPONSE` set to a fenced JSON string — the decode pipeline completes successfully
  3. Upload a test PDF through the UI — confirm the decode succeeds with a fenced model response

- [x] **Threat-model controls implemented:**
  - LLM05 (improper output handling): regex anchored to string boundaries only; inner backticks left untouched → validation catches corruption
  - LLM05 (improper output handling): regex not too permissive → tested with AC1–AC4
  - LLM01 (prompt injection): text outside fences causes validation failure (Pydantic `extra="forbid"`); no injection reaches frontend
  - LLM10 (unbounded consumption): simple linear regex, no nested quantifiers → backtracking test

- [x] **Docs touched:** none — this is an internal bug fix; no user-facing behavior changes

## Phase 2: (none required)

All work fits in Phase 1. No architecture changes, no new endpoints, no new dependencies.

## Docs (the app's own, not the factory's)

`README.md` and `AGENTS.md` are not touched. This change fixes an internal parsing bug — the user sees a working decode instead of an error, but the app's documented behavior, limits, and configuration are unchanged.

## Architecture contracts

No new imports or structural changes. The existing `.importlinter` contracts remain valid.

```ini
[importlinter:contract:layers]
# Already exists: routes -> services -> adapters
[importlinter:contract:llm-adapter]
# Already exists: only app.adapters.llm imports a model client
[importlinter:contract:no-test-imports]
# Already exists: nothing in app/ imports tests/
```

## Decisions (ADRs)

None. This is a narrow bug fix with no significant design trade-offs. The regex pattern is already specified by the spec and threat model.

## Dependencies added (Python and system)

None. Only `re` (stdlib) and `json` (stdlib) are used.

## What I am unsure about

- Q1: The spec's sketch says the opening regex should be `^````?(?:json)?\s*\n`. Should the regex also handle the case where there is no newline after the fence (e.g., ````json{"summary":...}``)? The current spec says "an optional line starting with", implying a line break. I'll keep `\s*\n` as specified and let non-conforming output fail validation.
- Q2: Should the closing fence also require a preceding newline? E.g., `{...}``` vs `{...\n`````. I'll use `\s*````\s*$` which handles both cases (whitespace includes newlines).

## Notes from implementation

- The regex uses `$` anchor so the closing fence must be at the end of the string. This means inner backticks (e.g. `"use \`code\`"` in JSON) are correctly preserved — the non-greedy `(.*?)` expands past them until the actual closing fence at string end is found. The original plan test `test_fenced_backticks_inside_json_rejected` assumed the regex would match inner backticks as a fence, but the `$` anchor prevents that. Updated the test to `test_fenced_backticks_inside_json_preserved` which verifies the correct behavior.
- **Rework (issue #36 rework):** The original regex `\s*```\s*$` accepted only 3 backticks at the closing fence. Some LLM models output 4 backticks (````) at the closing fence, causing the regex to capture one extra backtick and produce invalid JSON — leading to the "json_invalid" error. Fixed by changing the closing pattern to `\s*````?\s*$` to accept both 3 and 4 closing backticks. Added `test_fenced_with_four_backticks_closing_parses` to cover this case.
- All 258 tests pass (1 skipped), ruff + pyright clean.
- No README changes needed — this is an internal parsing fix.
