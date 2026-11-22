# Threat model: #29 Accept 256 KB PDFs without "File too large"

Status: DRAFT. Every decision is ACCEPTED; the human decides.

Scope: what this change adds, which is setting `max_file_size=MAX_BYTES` on the `File()` parameters in `routes.py` so FastAPI's internal upload limit matches the app's 10 MB cap. The letter-handling controls from `thoughts/1/threat-model.md` (redaction, output schema, prompt injection, rate limit, budget) do not change and are not repeated here. Where this change could weaken one of them, the row says so.

## Assets

- **The upload pipeline** (FastAPI `UploadFile`, the `read_limited()` reader, the middleware content-length check). If the pipeline rejects valid files or accepts over-sized ones, availability or resource exhaustion follows.
- **The 10 MB hard cap** (`MAX_BYTES`). It is the boundary between "accept and process" and "reject with 413."

## Entry points and trust boundaries

1. **POST `/api/decode` and `/ui/decode`** (multipart: `file`, `language`). Untrusted: file bytes, filename, declared content type, `language`. This boundary is unchanged; only the FastAPI-side size gate moves from 1 MB to 10 MB.
2. **FastAPI `UploadFile` internal limit** (new boundary). Before `read_limited()` ever runs, FastAPI enforces its own per-file size limit (default 1 MB). This is the gate that currently rejects the 256 KB file.
3. **Middleware content-length check** (in `main.py`). A lightweight pre-check that rejects requests whose `Content-Length` header exceeds `MAX_BYTES + _BODY_SLACK` (64 KB). This is a defense-in-depth layer, not the primary cap.

## Data flow to models

| Data | Model (local / cloud) | Why acceptable |
|---|---|---|
| Same as before | Unchanged | This change does not touch OCR, the prompt, or the model call. No new data reaches the model. |

## Threats and controls

| ID | Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|---|
| T1 | LLM10 Unbounded consumption / availability | FastAPI's default `UploadFile` rejects files over 1 MB. A 256 KB PDF hits this limit and returns 413/500 before `read_limited()` ever runs. The user sees "File too large." | Set `max_file_size=MAX_BYTES` on the `File()` parameters in `routes.py` so FastAPI accepts files up to 10 MB. The app's own `read_limited()` enforces the 10 MB cap in 64 KB chunks. | Holdout AC1: a 256 KB PDF returns 200 (not 413 or 500) on `/api/decode`. Holdout AC2: a file just under 10 MB returns 200. | ACCEPTED |
| T2 | Web: upload handling — limit bypass via missing Content-Length | The middleware's `content-length` check (`main.py:83-85`) only triggers when `Content-Length` is present and numeric. A client can omit it, letting FastAPI stream the body to `read_limited()`. Without the middleware pre-check, a 100 MB upload would consume memory before rejection. | The middleware check is *defense-in-depth*, not the primary cap. `read_limited()` always enforces `MAX_BYTES` regardless of headers. Removing or weakening the middleware check does not weaken the hard cap. Keep the middleware check as-is. | Holdout AC3: a file 1 byte over 10 MB returns 413 with `{"error": "File too large."}`. Unit: `read_limited()` rejects data exceeding `max_bytes` even when no `Content-Length` header is set. | ACCEPTED |
| T3 | Web: upload handling — multipart overhead | The middleware check uses `MAX_BYTES + _BODY_SLACK` (64 KB) to account for multipart form overhead. If `_BODY_SLACK` is too small, a valid 10 MB file could be rejected by the middleware before reaching `read_limited()`. | `_BODY_SLACK = 64 * 1024` is sufficient for typical multipart headers and boundary strings. A 10 MB file with reasonable metadata adds well under 64 KB. The spec does not change this value. | Holdout AC2: a file just under 10 MB returns 200 (the middleware does not reject it). | ACCEPTED |
| T4 | LLM01, LLM05, LLM06, LLM07 | Unchanged by this issue. No new prompt content, no new model output path, no new tools. The same letter goes through OCR, redaction, and the model exactly as before. | No new control. The existing #1 controls apply unchanged. | Existing #1 tests continue to pass. No new test needed. | ACCEPTED |
| T5 | Web: upload handling — existing controls not weakened | Raising FastAPI's limit from 1 MB to 10 MB does not weaken the magic-byte check (`sniff_kind`), the `read_limited()` cap, the rate limit, or the daily budget. | All existing upload controls (`upload.py`, `limits.py`, `routes.py`) remain in place. The only change is the `max_file_size` parameter on two `File()` calls. | All existing holdout tests (AC1–AC8 from #1) continue to pass. | ACCEPTED |

## Accepted risks

Proposed for the human to accept or reject:

- **R1: FastAPI still buffers the full file in memory.** `UploadFile` with `max_file_size` set still reads the entire body into memory before `read_limited()` processes it. For a single-user app on a private cluster this is acceptable; the 10 MB cap limits exposure. If the app ever scales, streaming to disk would be needed. ACCEPTED.
- **R2: No change to the middleware's content-length pre-check.** The middleware check remains as-is (defense-in-depth). It is not the primary enforcement mechanism — `read_limited()` is. ACCEPTED.

## Open questions for the human

- Q1: `_BODY_SLACK` is 64 KB. Is this sufficient if users upload PDFs with very large embedded metadata (e.g. XMP sidecar data) that inflates the multipart body beyond 64 KB over the raw file size? The spec says the limit is 10 MB on the *file*, not the multipart payload.
