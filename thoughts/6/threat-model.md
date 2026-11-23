# Threat model: #6

Status: DRAFT. Every decision is ACCEPTED (provisional, shown at Checkpoint 3); the human decides.

## Assets

- Letter content: photos and PDFs of Swedish letters. These contain personnummer, names, addresses, phone numbers, emails and sometimes health or school information about children.
- The result page HTML rendered in the user's browser.
- The "Machine generated" notice (existing) and the new OCR-specific notice (proposed).

## Entry points and trust boundaries

1. `POST /ui/decode` (multipart: `file`, `language`) — renders `result.html`. The result page is the only place the new notice appears.
2. Browser → server: the result page is a server-rendered Jinja2 template with autoescape. No client-side script touches the notice text.

## Data flow to models

| Data | Model (local / cloud) | Why acceptable |
|---|---|---|
| New notice text ("Email addresses, phone numbers and special characters may contain OCR errors — check the original letter.") | Never sent to any model. | It is a static string in the Jinja2 template, never derived from user input or model output. |
| OCR text | Already flows to the model (unchanged from #1). | The notice does not change what the model sees; the redaction pipeline is untouched. |

## Threats and controls

| Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|
| LLM01 Prompt injection | Not applicable. The new notice is static HTML in a template; it does not touch the prompt or model input. | No code changes to `prompt.py`, `redact.py`, or the LLM client. | No new test needed. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM02 Sensitive information disclosure | Not applicable. The notice contains no user data and is not derived from OCR text. | The notice text is a hardcoded string in `result.html`. | No new test needed. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM05 Improper output handling | Not applicable. The notice is rendered by Jinja2 with autoescape enabled (per `ui.py` comment on line 64). No user-controlled data flows into the notice element. | Jinja2 autoescape on `.html` templates; no `|safe` filter on the notice line. | Holdout AC1: result page HTML contains a notice element mentioning "email" and "OCR". | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM06 Excessive agency | Not applicable. No new write actions, tools, or model calls are introduced. | No changes to the LLM client protocol or route handlers. | No new test needed. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM07 System prompt leakage | Not applicable. The notice is not part of the system prompt. | No changes to `prompt.py`. | No new test needed. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM10 Unbounded consumption | Not applicable. No new processing, parsing, or model calls. | No code changes to limits, upload handling, or OCR. | No new test needed. | ACCEPTED (provisional, shown at Checkpoint 3) |
| Web: XSS | The notice text is static, but all template content must remain static. A future change could accidentally inject user data into the notice. | Jinja2 autoescape; the notice line contains no variable interpolation. Code review is the control. | Holdout AC1: the notice text is exactly the expected string (no variable interpolation in the template). | ACCEPTED (provisional, shown at Checkpoint 3) |
| Web: API contract regression | Adding the notice to the HTML page accidentally adds a field to the JSON API response. | The notice lives only in `result.html`; `render_result()` passes the same `DecodeResult` to the template. The API route (`/api/decode`) returns `DecodeResult` unchanged. | Holdout AC2: `POST /api/decode` JSON response has no `ocr_warning` field. | ACCEPTED (provisional, shown at Checkpoint 3) |

## Accepted risks

- **R1:** The notice is English-only. Swedish users will read it (they are learning Swedish and the existing notice is also in English), but a Swedish version would be preferable in a future iteration.
- **R2:** The notice text is hardcoded. If the wording needs to change, a deploy is required. This is acceptable for v1 given the small user base and stable message.

## Open questions for the human

- Q1: Is the English-only notice text acceptable for Swedish-speaking parents who are still learning the language, or should it be bilingual (SV + EN)?
