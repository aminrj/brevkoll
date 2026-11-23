# Research: #36 Strip markdown code fences from model responses

## What exists

### The problem in practice
The LLM client (`src/app/llm.py:48-60`, `OpenAICompatLLM.complete`) calls a local model server and extracts the response text via `_extract_content` (line 63-70). The model returns JSON wrapped in Markdown code fences (````json … ````). The `parse_model_output` function (line 82-86) passes this raw string directly to `ModelOutput.model_validate_json(raw)`, which fails because the fence markers are not valid JSON, raising `BadModelOutput` with the message "The model returned an unusable answer."

### Key files

| File | Role |
|---|---|
| `src/app/llm.py:73-86` | `ModelOutput` Pydantic model (`extra="forbid"`, length caps) and `parse_model_output` — **the only function to change** |
| `src/app/llm.py:37-60` | `OpenAICompatLLM.complete` — fetches raw text from the model server |
| `src/app/llm.py:25-34` | `FakeLLM` — test double used across the test suite |
| `src/app/decode.py:51` | `decode_letter` calls `parse_model_output(raw)` in the decode pipeline |
| `src/app/errors.py:31-33` | `BadModelOutput` — HTTP 502, message "The model returned an unusable answer." |
| `tests/unit/test_llm_output.py` | Existing unit tests: valid JSON parses (line 10-13), invalid JSON rejected (line 16-32), LLMClient protocol check (line 35-38) |
| `tests/unit/conftest.py` | Fixtures: `env` (temp dirs, `FAKE_LLM_LOG`), `make_client` (TestClient with `FakeOcr`) |
| `tests/integration/test_tesseract.py` | Integration test for OCR (not affected) |
| `tests/integration/test_mtls_handshake.py` | Integration test for mTLS (not affected) |

### Data flow

```
User uploads PDF → routes.py → decode.py:decode_letter()
  → OCR extracts text → redact() removes PII → build_prompt()
  → LLMClient.complete() returns raw string (possibly fenced)
  → parse_model_output() ← **this is the bottleneck**
  → find_dates() (code-based, never model) → build_ics() → DecodeResult
```

## Where untrusted input enters

1. **`parse_model_output(raw: str)`** (`src/app/llm.py:82`) — receives raw LLM output. This is the sole entry point for the fenced-JSON problem. Input: untrusted model response (possibly wrapped in ````json … ````). Trust boundary: everything before is untrusted; everything after `model_validate_json` is validated by Pydantic.

2. **`_extract_content(envelope)`** (`src/app/llm.py:63`) — extracts string from HTTP response envelope. Already validated that it's a dict with nested structure. The extracted string is then passed to `parse_model_output`.

3. **`FakeLLM.complete`** (`src/app/llm.py:30`) — test double; returns whatever response string is set. Tests can simulate fenced output by setting `FAKE_LLM_RESPONSE` to a fenced string.

## Constraints found

### CI / quality guards (from `scripts/quality.sh`)
- `ruff check . && ruff format --check .` — lint and format
- `pyright` — static type checking
- `pytest` — runs `tests/unit`, `tests/integration`, `tests/tooling`, `tests/deploy`
- `scripts/quality.sh` — health metrics ratchet, diff-coverage floor, architecture contracts (`lint-imports`), traceability, context hygiene
- `scripts/mutation.py` — mutation testing (separate, slow)

### Hard rules (AGENTS.md)
- No `# type: ignore`, no `cast()` to silence pyright
- No weakened assertions
- Every new behavior gets a test that fails without the change
- Never edit `tests/holdout/`
- Keep functions short and call stacks shallow

### Contract (spec)
- `parse_model_output(raw: str) -> ModelOutput` — signature unchanged
- Regex pattern: optional line starting with ````json` or ``````, content, closing `````
- Strip fences → call `model_validate_json` on inner content
- Invalid inner JSON still raises `BadModelOutput`
- All existing validation (extra field rejection, length limits) unchanged

### Holdout tests (from spec, not yet written)
- AC1: fenced with `json` tag → parses successfully
- AC2: fenced without language tag → parses successfully
- AC3: plain JSON (no fences) → backward compatible
- AC4: fenced + invalid inner JSON → raises `BadModelOutput`

## Open questions for the human

- Q1: The spec says the regex should use `^````?(?:json)?\s*\n` for opening and `\s*````\s*$` for closing. Should the regex also handle Windows-style line endings (`\r\n`)? The threat model doesn't mention this.
- Q2: Should holdout tests be written as part of this research phase, or left for the plan phase? The AGENTS.md workflow says research describes what exists (no solutions), but the spec says "each one becomes a holdout test."
