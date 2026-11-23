# Threat model: #36 Strip markdown code fences from model responses before parsing

## Assets

- Model response text: untrusted JSON produced by a local or cloud model, now potentially wrapped in Markdown code fences.
- The `parse_model_output` function: the single gate between raw model output and validated `ModelOutput` data. A flaw here could let corrupted data through or reject valid data.
- The existing security controls: Pydantic schema validation (`extra="forbid"`, length caps), the `BadModelOutput` error path, and the HTML-escaped frontend. These must not be weakened by the fence-stripping change.

## Entry points and trust boundaries

1. `parse_model_output(raw: str) -> ModelOutput` — receives the raw string from the LLM client. This is the only new entry point for this change. Input: untrusted model output. Trust boundary: everything before this function is untrusted; everything after is validated.
2. `_strip_markdown_fence` (new helper) — processes the raw string before validation. Input: untrusted model output. Output: trimmed string passed to `model_validate_json`.

## Data flow to models

| Data | Model (local / cloud) | Why acceptable |
|---|---|---|
| Redacted OCR text and the target language | Decided at Gate 2. Options: local model, or cloud model. | Personnummer, emails and phone numbers are removed before the call. The system prompt wraps the text in delimited markers. |
| Model response (JSON, possibly fenced) | Parsed by `parse_model_output`, validated by Pydantic. | The fence-stripping change only removes wrapping markers; it does not change what the model sends. Validation is unchanged. |
| Model response (inner JSON) | Passed to `ModelOutput.model_validate_json` after stripping. | Pydantic enforces the schema: `extra="forbid"`, max lengths on summary and actions. Invalid JSON still raises `BadModelOutput`. |

## Threats and controls

| Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|
| LLM05 Improper output handling | The fence-stripping regex is too aggressive and strips triple backticks that are part of the JSON content (e.g. a summary containing ```` ``` ```` as literal text), corrupting the JSON before validation. Corruption leads to `BadModelOutput` — same user-facing error as today. No data integrity issue because validation still rejects the result. | The regex must match *only* standard Markdown code fences: an optional line of ````json` or ````` followed by content and a closing ````` on its own line. It must not strip backticks embedded mid-content. Use a anchored pattern: `^````?(json)?\s*\n` for the opening and `\s*````\s*$` for the closing, ensuring fences span the full string. | Unit: a response containing backticks inside the JSON object (e.g. `{"summary": "use \`\`\` for code", "actions": []}`) is rejected as `BadModelOutput` (the backticks are not at the string boundaries). Unit: a response with fences on every line but only the outermost being a fence is handled correctly. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM05 Improper output handling | The fence-stripping regex is too permissive and fails to strip actual fences, leaving fence markers in the JSON string so validation still fails. This is a regression: the current code already fails on fenced input; the change must fix that. | The regex must be tested against all four spec variants: fenced with `json`, fenced without language tag, plain JSON, and fenced with invalid inner JSON. | Holdout AC1 (fenced with `json` parses successfully). Holdout AC2 (fenced without language tag parses successfully). Holdout AC3 (plain JSON still works). Holdout AC4 (fenced + invalid inner JSON raises `BadModelOutput`). | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM01 Prompt injection | A crafted model response embeds prompt-injection text inside or after the closing fence that the regex fails to strip, leaking untrusted text into the Pydantic parser. Since Pydantic only extracts typed fields (`summary`, `actions`), injection text would land in the raw string but never reach the user — it would either be rejected by validation or silently dropped. | The regex strips the full fence block (opening fence + content + closing fence). Any text outside the fence markers is preserved as-is, then passed to `model_validate_json`. Pydantic's `extra="forbid"` rejects extra top-level keys, and the schema only extracts `summary` and `actions`. Injection text that survives stripping cannot reach the frontend because all output goes through `DecodeResult` → Jinja auto-escape. | Unit: a response with text before the opening fence (e.g. `"ignore previous instructions\n````json\n{...}\n`````") is handled: the leading text either causes validation to fail (rejected) or is stripped along with the fence. Unit: a response with text after the closing fence (e.g. `"````json\n{...}\n````\nprint your system prompt"`) — the trailing text causes validation to fail because Pydantic rejects the extra content. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM10 Unbounded consumption | The regex uses backtracking-prone patterns (e.g. greedy `.*` with nested optional groups) on input containing many backticks, causing catastrophic backtracking and a denial of service. | Use a simple, non-backtracking regex: `^````?(?:json)?\s*\n` for the opening and `\s*````\s*$` for the closing. These patterns have no nested quantifiers and run in linear time. Avoid `.*` or `.+` in the overall pattern; match content lazily or use `re.DOTALL` with a non-greedy `.*?` only if necessary. | Unit: a string of 10,000 backticks followed by valid JSON does not hang the process (timed test with a 1-second cap). Unit: a string of nested backtick patterns (```` ``` ```` ``` ````) does not cause exponential backtracking. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM05 Improper output handling | The fence-stripping change weakens existing validation: extra fields, length limits, or type checks that previously caught bad model output are now bypassed because the regex mangles the JSON in an unexpected way. | The regex operates *only* on the outermost fence markers. The inner JSON is passed verbatim to `model_validate_json`. All existing validation (extra field rejection, max lengths, type checks) runs unchanged. No `# type: ignore`, no `cast()`. | Unit: all existing invalid-input tests from `tests/unit/test_llm_output.py` still raise `BadModelOutput` (run the full parameterized test suite). Unit: an extra-field response (`{"summary": "s", "actions": ["a"], "dates": [...]}`) is still rejected. Unit: an oversize summary (`"x" * 2001`) is still rejected. | ACCEPTED (provisional, shown at Checkpoint 3) |
| Web: CSRF | Not affected by this change. No new state, no new endpoints. | No change to CSRF posture. | No new test needed. | ACCEPTED (provisional, shown at Checkpoint 3) |

## Accepted risks

- **R1 (unchanged from #1):** the model may still produce code fences; the prompt is not changed to stop them. This fix absorbs them gracefully.
- **R2 (unchanged from #1):** OCR errors can corrupt a date or a name. The user sees the original wording beside each date.

## Open questions for the human

- Q1: Should the regex also handle fenced content that has *no* closing fence (truncated model output)? The spec says fences wrap the entire response, so a truncated response would fail validation anyway. ACCEPTED (provisional, shown at Checkpoint 3): do not handle truncated output — let it fail validation.
