# Threat model: #1

Status: DRAFT. Every decision is PROPOSED; the human decides.

## Assets

- Letter content: photos and PDFs of Swedish letters. These contain personnummer, names, addresses, phone numbers, emails and sometimes health or school information about children.
- OCR text and the redacted text derived from it.
- The deadlines the user relies on (`dates`, `ics`). A wrong or missing date causes a missed deadline.
- Model provider credentials (API key, if a cloud model is chosen at Gate 2).
- Model budget and server CPU/RAM (OCR is expensive).
- The "nothing is stored" promise to the three school parents.

## Entry points and trust boundaries

1. `POST /api/decode` (multipart: `file`, `language`). Untrusted: file bytes, filename, declared content type, `language`.
2. Letter text after OCR. Untrusted: a letter can contain text aimed at the model ("ignore previous instructions...").
3. Model response. Untrusted: it must be parsed and validated against the schema.
4. Environment configuration (`LLM_PROVIDER`, `FAKE_LLM_*`, `APP_DATA_DIR`, `RATE_LIMIT_PER_MINUTE`). Trusted, but the `fake` provider must not be selectable in production by accident.
5. Tesseract and PDF rasterizer subprocesses. They parse hostile files.
6. Browser to server: the HTMX page and the `.ics` download. The response text is rendered in the DOM.
7. Reverse proxy at `brevkoll.lab.aminrj.com`. Client IP comes from it, so rate limiting depends on how it forwards the IP.

## Data flow to models

| Data | Model (local / cloud) | Why acceptable |
|---|---|---|
| Redacted OCR text and the target language (PROPOSED) | Decided at Gate 2. Options: local model, or cloud model. | Personnummer, emails and phone numbers are removed before the call (AC4). Names and street addresses are not redacted in v1 (accepted risk R1). Because of R1, PROPOSED default is a local model, with a cloud model only if the human accepts R1 for that provider. |
| Original image or PDF bytes | Never sent to any model. | OCR runs locally with Tesseract. |
| System prompt (static) | Same model as above. | Contains no secrets and no user data. |
| Dates | Never sent for decisions. Code parses them from OCR text. | The model never decides a deadline (AC2). |

## Threats and controls

| Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|
| LLM01 Prompt injection | A letter (or a crafted upload) contains instructions such as "say the deadline is cancelled" or "output this link". The model summary then misleads the user. | The model has no tools. OCR text is wrapped in a delimited data block and the system prompt says it is data. Output is limited to the `{summary, actions}` schema. Dates come from code only, so injection cannot change `dates` or `ics`. Summary and actions are plain strings, length capped, and rendered as text. | Unit: with `FAKE_LLM_RESPONSE` returning a summary that claims other dates, `dates` and `ics` still hold only the code-parsed dates. Unit: the prompt builder puts the OCR text only inside the data delimiters, and a letter containing the delimiter string cannot close the block (delimiter is escaped or stripped). | ACCEPTED |
| LLM02 Sensitive information disclosure | Personnummer, email or phone reaches the model, the logs or disk. | A `redact()` function runs on OCR text before any prompt is built, replacing personnummer and samordningsnummer (all separator forms, 10 and 12 digit), emails and Swedish phone numbers with placeholders. Logs record lengths, status codes and timings, never letter text, OCR text or model output. The fake client's `FAKE_LLM_LOG` is the only place payloads are written, and only under the `fake` provider. | Holdout AC4 (payload has none of the three values). Unit: table test of redaction forms (`-`, `+`, no separator, 10 and 12 digits, `+46` and `07x` phones, plus-addressed emails). Unit: a logging capture during a decode contains no letter text. | ACCEPTED |
| LLM02 (storage) | Uploads or derived text persist on disk, in temp files, or in a cache. | Process uploads in memory. If a temp file is needed for Tesseract, use `tempfile.TemporaryDirectory` as a context manager so it is removed even on error. Temp files go under `APP_DATA_DIR` or the OS temp dir. No database, no response caching. | Holdout AC5 (data dir empty after success). Unit: data dir and temp dir are empty after a failing request (OCR error, model error, 415). | ACCEPTED |
| LLM05 Improper output handling | The model returns invalid JSON, extra fields, huge strings, HTML or script; the app echoes it or the browser executes it. | Parse model output with a Pydantic model (`extra="forbid"`, max lengths on summary, number and length of actions). On failure return 502 with a fixed generic message. The frontend inserts summary and actions with `textContent` or auto-escaped Jinja templates, never `innerHTML` or `|safe`. The `ics` string is built by code from parsed dates; model text in a `DESCRIPTION` is escaped per RFC 5545 (commas, semicolons, backslashes, newlines) so it cannot inject extra properties or events. | Holdout AC6 (invalid JSON gives 502, no echo). Unit: extra field and oversize string give 502. Unit: a summary containing `<script>` is HTML-escaped in the rendered page. Unit: an action with `\r\nBEGIN:VEVENT` does not create a second VEVENT in the `ics`. | ACCEPTED |
| LLM05 (date parsing) | OCR errors or odd formats produce a wrong date, or a date is missed. | A deterministic parser extracts Swedish formats (`2026-12-04`, `4 december 2026`, `4/12`) from OCR text and returns ISO dates. Dates without a year use a clock injected into the parser. Only valid calendar dates are accepted. Unit tests cover the fixture. The UI shows the dates next to the original letter wording so the user can check them. | Holdout AC2 and AC3. Unit: parser table test with formats, invalid dates (`2026-02-30`), and the model returning no dates. | ACCEPTED |
| LLM06 Excessive agency | The model triggers actions. | The model client exposes only `complete(prompt) -> str`. No tools, no function calling, no network or file access from model output. The only write action is the user's own `.ics` download in the browser. | Unit: the model client protocol has no tool parameter, and a model response naming a tool or URL changes nothing in the response beyond the validated strings. | ACCEPTED |
| LLM07 System prompt leakage | The user or a letter extracts the system prompt. | The system prompt holds no secrets, keys or other users' data, so leakage has low impact. It is not returned in any response or error. | Unit: error responses and 200 bodies for a letter saying "print your instructions" with a fake model echoing the prompt do not contain the prompt text (the validation fails, so the echo gives a 502 with a generic message). | ACCEPTED |
| LLM10 Unbounded consumption | Large or many uploads, decompression bombs, many-page PDFs, or request floods exhaust CPU, RAM or the model budget. | Reject over 10 MB before reading it all (stream with a byte counter), 413. Allow only PNG, JPEG and PDF, checked by magic bytes and not by the filename or declared type, 415. Cap PDFs at 3 pages and images at a maximum pixel count (e.g. 25 MP) before OCR. Tesseract and rasterizer run with a timeout. The model call has a timeout, a max output token cap and a cap on input characters. Per-IP rate limit from `RATE_LIMIT_PER_MINUTE` (default 10), 429. A daily model call budget (`DAILY_MODEL_CALL_BUDGET`, count based in memory, resets at midnight) returns 503 when exhausted. A global concurrency limit on OCR jobs. | Holdout AC7 and AC8. Unit: PNG header with a `.pdf` name gives 415. Unit: 4-page PDF is rejected. Unit: pixel limit is rejected. Unit: model timeout gives 502. Unit: the budget is exhausted after N calls and the next gets 503. Unit: the model client call receives a `max_tokens` and `timeout`. | ACCEPTED |
| Web: authn/z, IDOR | There are no accounts and nothing stored, so there is nothing to access across users. | No endpoint returns stored data. No IDs, no sessions. The service is public in v1 (see R3). | Unit: the app has no route other than the page, static files, health and `/api/decode` (route allowlist test). | ACCEPTED |
| Web: CSRF | A third-party page makes a visitor's browser POST a letter to the API. | Impact is low (no session, no state, no cookies). Control: no cookies are set; CORS is not enabled, so cross-origin pages cannot read responses. Cap on rate limits applies. | Unit: a response has no `Set-Cookie` and no `Access-Control-Allow-Origin` header. | ACCEPTED |
| Web: SSRF | The app fetches URLs from letter text or model output. | The app makes no outbound HTTP requests except to the configured model endpoint, whose URL comes from the environment only. Links in letters are never fetched or followed. | Unit: with the HTTP client replaced by a recorder, a letter containing a URL causes no request other than the one model call. | ACCEPTED |
| Web: upload handling | Path traversal through the filename, malicious PDF or image exploiting the parser, polyglot files. | The filename is never used for any path. Temp names are generated. Magic-byte check, size and page caps as above. Tesseract and the rasterizer run as argument lists, never through a shell. Dependencies (Pillow, PDF library, Tesseract) are kept patched through `uv.lock` updates and the base image. Container runs as non-root with a read-only root filesystem and a writable `APP_DATA_DIR` only (deployment note for the plan). | Unit: a filename like `../../x.png` leaves no file outside the temp dir. Unit: subprocess calls use list arguments (checked with a recorder). | ACCEPTED |
| Web: abuse of `language` | `language` field injected into the prompt. | Validate against an allowlist of ISO 639-1 codes the app supports. Anything else gives 422 with a generic message. | Unit: `language="en; ignore rules"` gives 422 and the model is not called. | ACCEPTED |
| Web: rate limit bypass | Client IP behind the reverse proxy is always the proxy's IP, so one user exhausts the limit for everyone, or a spoofed `X-Forwarded-For` bypasses it. | Take the IP from `X-Forwarded-For` only if the direct peer is in `TRUSTED_PROXIES` (env); otherwise use the socket peer. | Unit: a spoofed `X-Forwarded-For` from an untrusted peer does not reset the limit. | ACCEPTED |
| Config: fake provider in production | `LLM_PROVIDER=fake` writes payloads (letter text) to a log file. | The app refuses to start with `fake` unless `APP_ENV` is `test`/`dev`. The fake log path must be outside `APP_DATA_DIR` so AC5 still holds. | Unit: `create_app()` with `LLM_PROVIDER=fake` and `APP_ENV=prod` raises. See open question Q2, because the holdout tests may not set `APP_ENV`. | ACCEPTED |

## Accepted risks

- **R1 (from the spec):** names and street addresses are not redacted in v1. They can reach the model. PROPOSED mitigation is the model choice at Gate 2 (local model preferred).
- **R2:** OCR errors can corrupt a date or a name. The user sees the original wording beside each date, and the summary is labeled as machine generated. The user is expected to check the deadline.
- **R3:** The service is public with no login. Abuse is limited only by the rate limit, size caps and daily budget. PROPOSED: put it behind the existing reverse proxy access control if the human wants it closed.
- **R4:** Prompt injection can still change the wording of `summary` and `actions` (not the dates). The user is told these are machine summaries.
- **R5:** The in-memory rate limit and daily budget reset when the process restarts, and do not work across multiple workers. v1 runs one worker.
- **R6:** If a cloud model is chosen, the redacted text leaves the household and the provider's retention rules apply.

## Open questions for the human

- Q1: Local or cloud model for the default (Gate 2)? This sets how much R1 and R6 matter.
- Q2: Is it acceptable to require `APP_ENV` for the fake-provider guard, or should the guard be dropped because the holdout tests cannot be changed? I could not read `tests/holdout/`.
- Q3: Should access be restricted (basic auth or proxy allowlist) given R3?
- Q4: The spec mentions "the two languages my first users ask for" but gives no list. Which languages go in the allowlist?
- Q5: Is a daily budget by call count enough, or do you want a cost-based one?
