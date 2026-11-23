# Architecture: brevkoll

Status: accepted
<!-- Owned by the human, kept true by every change. A change that moves a box, a boundary or an invariant updates this
     file in the same pull request and says so in the plan. -->

## The picture

```text
 phone browser ──(1) photo/PDF, language──▶ ┌───────────────────────── brevkoll (one process, one worker) ──────────────────────────┐
   ▲  page (HTML, one CSS file,             │ routes/ui ─▶ limits ─▶ upload (type, 10 MB) ─▶ ocr ─▶ redact ─▶ prompt ─▶ llm client │
   │  no external requests, strict CSP)     │   (rate limit, daily budget)      │ in memory        │ Tesseract     [EMAIL] [PHONE]   │
   │                                        │                                   ▼                  (local)         [PERSONNUMMER]    │
   │                                        │                           dates (code) ─▶ ics                          │               │
   └──(5) summary, actions, dates, .ics ◀───┴────────────────────────────────────────────────────────────────────────┼───────────────┘
                                                                                                                      │ (3) redacted text
                                                                                       ═══ trust boundary ═══════════╪════════════════
                                                                                   the owner's model server (local) ◀┘
                                                                                   (4) JSON {summary, actions}, parsed into a schema
                                                                                   plain HTTP, or TLS with a client certificate (mTLS)
```

Two trust boundaries matter: the **upload** (everything in it is hostile: file type, size, text) and the **model call**
(the only data that leaves the process, and its answer is untrusted). Nothing else crosses the process edge.

## Where the data goes

| Data | Enters at | May travel to | Must never reach | Lives for |
|---|---|---|---|---|
| The letter file | `POST /api/decode`, `POST /ui/decode` | memory, Tesseract (local), a temp file deleted before the response | disk afterwards, logs, the model (never the image) | one request |
| OCR text | `app.ocr` | `app.redact`, then the prompt; the date finder (code) | logs, a model before redaction, the response beyond the dates' own wording | one request |
| Redacted text | `app.redact` | the configured model endpoint | any other host | one request |
| Model answer | `app.llm` | a Pydantic schema, then the response | dates, URLs, paths or any decision in code (it is data) | one request |
| Settings and keys | environment | `app.config`, the model client | logs, responses | process |

## Invariants

Each row has a test whose comment is `# I<n>`; `scripts/trace.py` fails CI otherwise.

| ID | Invariant | Intent | Enforced by (test) |
|---|---|---|---|
| I1 | After any request, successful or not, the data directory is empty. | N1 | `tests/unit/test_no_files.py` |
| I2 | Personnummer, email addresses and phone numbers are replaced by placeholders before the model sees the text. | N2 | `tests/unit/test_redact.py` |
| I3 | Every date in the answer was found in the letter by code; what the model says about dates is ignored. | N3 | `tests/unit/test_decode_dates.py` |
| I4 | Model output is parsed into a schema; anything else is rejected with a generic error that never echoes the model. | N5 | `tests/unit/test_llm_output.py` |
| I5 | The only outbound request is one call to the configured model endpoint: no redirects, no proxy, no tools. | N4 | `tests/unit/test_llm_openai_compat.py` |
| I6 | Logs contain no letter text, OCR text or model text. | N1 | `tests/unit/test_logging.py` |
| I7 | Pages load only same-origin resources under a strict Content-Security-Policy, and set no cookies. | N4 | `tests/unit/test_csp.py`, `tests/unit/test_ui_static.py` |
| I8 | Every model call has a timeout and a token cap; requests are rate limited per client and capped per day. | N2 | `tests/unit/test_llm_openai_compat.py`, `tests/unit/test_limits_api.py` |
| I9 | The fake model is refused when `APP_ENV=prod`. | N5 | `tests/unit/test_config.py` |
| I10 | A file is accepted by its content, not its name, and only as PNG, JPEG or PDF up to 10 MB. | N1 | `tests/unit/test_upload.py` |

## Decisions
- [0001](decisions/0001-weekday-in-the-view-layer.md) the weekday is computed in the UI layer, not in the result.
- [0002](decisions/0002-content-security-policy-header.md) a strict Content-Security-Policy on every response.
- [0003](decisions/0003-model-mtls-with-pinned-ca.md) the model is called over mutual TLS with a pinned CA.
- [0004](decisions/0004-host-free-deploy-base.md) a public, host-free `deploy/base`; the overlay holds everything network-specific.
- [0005](decisions/0005-manifest-tests-outside-the-src-gate.md) manifest tests live in `tests/deploy`.

## Known gaps
Where the code does not yet keep what the intent says. Each is a candidate issue, not a footnote.
- **I2 has a hole (N2): OCR garbles the characters redaction looks for.** Tesseract read `@` as `Q`, so
  `mentorQexempelskola.se` was not recognised as an email and reached the model (brevkoll#6). Redaction matches the
  regex on OCR output; it does not know the text may be wrong. The page warning added for #6 does not close this.
- **Names and street addresses are not redacted** (accepted risk in the v1 threat model; the reason the model must be local, N2).
- **N5 is only a notice.** Dates, emails and phone numbers read by OCR are shown without a per-item confidence.
- The rate limit and the daily budget live in process memory: run one worker only.
- Chunked uploads are size-checked after parsing; PDF page boxes are not capped by pixels.
- Year-less dates (`4/12`) resolve to the next occurrence and can pick the wrong year in January.
