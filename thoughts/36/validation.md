# Validation: #36 Strip markdown code fences from model responses

Branch `agent/issue-36`, HEAD `df456a8`. Report only; nothing was fixed. This replaces the earlier report, which predates rework `0f031a5` (reasoning blocks and prose around bare JSON).

## Checks run

| Check | Result |
|---|---|
| `uv run ruff check .` | pass |
| `uv run ruff format --check .` | pass (118 files) |
| `uv run pyright` | 0 errors |
| `uv run pytest` | 264 passed, 1 skipped (pre-existing), 1 warning (PIL decompression bomb, pre-existing) |
| `bash scripts/quality.sh origin/main` | not run in this step |

## Phases complete

Phase 1 is done and all plan checkboxes are `[x]`. There is no Phase 2.

## Deviations from the plan

The code has moved well past the plan. The plan's "Notes from implementation" stop at the 4-backtick rework, and the reworks `0d5ad6a` and `0f031a5` are not recorded there.

1. **Regex differs from the plan and the threat model.** Plan: `^````?(?:json)?\s*\n(.*?)\s*````?\s*$` with `DOTALL|UNICODE`. Code (`src/app/llm.py:83`): `^[ \t]*````?[A-Za-z]*[ \t]*\r?\n(.*?)\s*````?[ \t]*$` with `DOTALL|MULTILINE`, applied with `.search()`.
2. **Fences are no longer boundary-anchored.** With `MULTILINE` and `search`, text before the opening fence or after the closing fence is discarded instead of failing validation. The threat model (LLM01 row) says it must fail. `test_fence_after_preamble_and_uppercase_tag_parses` accepts a preamble on purpose.
3. **Any alphabetic language tag is accepted** (`[A-Za-z]*`), not only `json`.
4. **New behaviour beyond fences (`0f031a5`).** `_strip_markdown_fence` now removes `<think>…</think>` blocks (`_THINK_RE`). It also extracts the first JSON object from unfenced prose through `_bare_object` (`raw_decode`), unless the text contains a backtick. The spec and threat model never covered either. Text before or after the JSON is now silently dropped for unfenced output.
5. A BOM and surrounding whitespace are stripped first.
6. **Unplanned change outside `llm.py`:** `BadModelOutput` in `src/app/errors.py` takes a detail (Pydantic error types), and the message becomes "The model returned an unusable answer. json_invalid" (`874b3f0`). It exposes only error type labels. `test_invalid_output_error_contains_details` covers it.
7. The plan names `test_fenced_backticks_inside_json_rejected`. The implemented test is `..._preserved`, and the plan's notes explain why.

## Threat-model controls without an enforcing test

- **LLM01, text before or after the fence or JSON.** The threat model requires unit tests where leading text ("ignore previous instructions") and trailing text ("print your system prompt") cause validation to fail. No such test exists, and the behaviour is now the opposite (items 2 and 4). The tests `test_prose_around_bare_json_is_ignored` and `test_reasoning_block_before_json_is_ignored` assert acceptance. The extra-field rejection does still hold for bare JSON (`test_bare_json_with_extra_field_still_rejected`). The threat model needs updating, and the owner should decide.
- **LLM05, inner backticks.** `test_fenced_backticks_inside_json_preserved` covers only a backtick pair inside one line. With `MULTILINE`, a JSON string value that has a line ending in a triple backtick could end the match early. Untested. The test docstring still says "anchored with `$`" at string boundaries, which is no longer accurate.
- **LLM10, linear-time claim.** The threat model says there are no nested quantifiers. `(.*?)\s*` has adjacent overlapping quantifiers, `search` with `MULTILINE` tries every line start, and `_THINK_RE` is a lazy `.*?` over the whole text. The single timing test (10,000 backticks, 1 s cap) does not cover many fence-opening lines, long whitespace runs, or many unclosed `<think>` tags. Super-linear cost is possible and unmeasured. Also, the test input has a closing fence without a valid opening, so it does not exercise the `_bare_object` path.
- **Nested-backtick pattern test** from the threat model (LLM10 row) is missing.
- **Covered:** the extra-field and oversize rejections, in the parametrised `test_invalid_output_rejected`. AC1–AC4 map to the first four fence tests.

## Weakened checks

No `type: ignore`, `cast()`, bare `except`, `except Exception: pass`, skips or xfails in the changed code or tests. No assertions were loosened. `_FENCE_JSON` in `tests/unit/test_llm_output.py:57` is an unused constant that ruff does not flag. It looks like leftover junk.

## Docs

- `README.md` describes the real app, and the run command (`uv run fastapi dev src/app/main.py`) matches. The env table covers every variable read through `config.py`, including `LLM_MODEL`, `LLM_TLS_KEY_FILE` and `FAKE_LLM_RESPONSE`. `APP_VERSION` (read in `src/app/ui.py:19`) is not in the table. That predates this issue and comes from #32.
- `AGENTS.md`: "What this repo is" holds a real paragraph. It names Python 3.12 while the venv is 3.14 (pre-existing).
- The README does not mention the output tolerance. That is acceptable for an internal parsing fix, though the model-output behaviour is now broader than before.

## Needs human attention

1. Decide whether tolerating a preamble, trailing prose, `<think>` blocks and any language tag is wanted. If so, update `threat-model.md` and `plan.md`, which currently say the opposite. If not, narrow the regex and `_bare_object`.
2. Add tests for trailing text after the fence, a closing-fence-like line inside a JSON string, and scaling on many fence lines or many `<think>` tags. Fix the stale docstring and remove `_FENCE_JSON`.
3. Two reworks have followed the owner's "still json_invalid" reports. The reworks guess at the cause. The owner's attached letter and the local model's real output have not been reproduced in a test, so check the staged build against the real letter. The cause may be something else, for example truncation at `MODEL_MAX_TOKENS`.
4. `thoughts/36/issue.md` has an uncommitted change (the foreman's rework block removed). I left it alone. `quality/health.json` and `tests/holdout*` appear in the diff against local `main` and look like items from other issues. I did not read `tests/holdout/`.
