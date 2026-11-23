# brevkoll

Decode a Swedish letter. Photograph or upload a letter from school, preschool or an authority and get a plain-language
summary in your language, a list of what you must do, and the dates as a calendar file. Built for parents who are still
learning Swedish. Nothing about the letter is kept.

## What it does

1. You send a PNG, JPEG or PDF (up to 10 MB) and pick an output language (`en`, `sv`, `ar`, `uk`).
2. Tesseract reads the text (Swedish). Personnummer, email addresses and phone numbers are replaced by placeholders
   before anything is sent to the model.
3. A local language model returns a summary and a list of actions as validated JSON.
4. Dates are found in the letter text by code, never by the model. They are returned with the letter's own wording, and
   as an `.ics` file with one all-day event per date. The page shows the weekday beside each date, computed in code, in
   the answer language (`/api/decode` is unchanged). The page lists "What to do" first, then the dates, then the summary.

The page works on a phone, starts in the system light or dark setting, and makes no external requests. A "Switch dark /
light" control flips it, in CSS only: the choice is not remembered after a reload. The button
disables and a wait message shows while the letter is read. Every response carries a strict
Content-Security-Policy, and the page loads nothing off-origin.

Endpoints: `GET /` (page), `POST /ui/decode` (page form), `POST /api/decode` (multipart fields `file` and `language`),
`GET /healthz`. There are no accounts, cookies, sessions or stored data.

## Run it

    uv sync
    LLM_PROVIDER=fake uv run fastapi dev src/app/main.py      # no model needed, fixed answer

Real OCR needs `tesseract-ocr`, `tesseract-ocr-swe` and `poppler-utils` on the machine. With a model server that speaks the
OpenAI chat-completions API (for example Ollama or llama.cpp):

    LLM_PROVIDER=openai_compat LLM_BASE_URL=http://127.0.0.1:11434/v1 LLM_MODEL=<model> \
      uv run fastapi dev src/app/main.py

Container (the image sets `APP_ENV=prod` and `APP_DATA_DIR=/data`; use a read-only root filesystem):

    docker build -t brevkoll .
    docker run --read-only --tmpfs /tmp --tmpfs /data:uid=10001,gid=10001 --cap-drop ALL \
      --security-opt no-new-privileges --memory 1g -p 127.0.0.1:8000:8000 \
      -e LLM_PROVIDER=openai_compat -e LLM_BASE_URL=http://host:11434/v1 -e LLM_MODEL=<model> brevkoll

Run one worker only: the rate limit and the daily budget live in memory.

Deploy: `deploy/base` is a hardened, host-free Kustomize base for one replica; a GitOps overlay adds the image tag, the
model settings, the Secret, the Ingress and the network peers. See `docs/deploy.md`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `fake` | `fake` (tests, dev) or `openai_compat`. `fake` is refused when `APP_ENV=prod`. |
| `LLM_BASE_URL`, `LLM_MODEL` | none | Model endpoint and model name, required for `openai_compat`. |
| `LLM_API_KEY` | none | Optional bearer key for the model endpoint. Read from the environment only, never logged or returned. |
| `LLM_TLS_CERT_FILE`, `LLM_TLS_KEY_FILE` | none | Client certificate and key (PEM) for a model endpoint that requires mutual TLS. Set both or neither; each must be a readable file. Unencrypted PEM key only; loaded once at startup, so rotation needs a restart. |
| `LLM_TLS_CA_FILE` | none | CA certificate (PEM) the model endpoint's certificate must chain to. Can be set alone. When set, only this CA is trusted (not the system store). Any `LLM_TLS_*` requires an `https://` `LLM_BASE_URL` whose host name is in the endpoint certificate's SAN. |
| `MODEL_TIMEOUT_S` | `120` | Seconds to wait for the model (1 to 600). A model that thinks before answering needs 120 or more. |
| `MODEL_MAX_TOKENS` | `3000` | Token cap for one answer (50 to 8000). Thinking models count their reasoning against it: at 600 one such model used the whole cap thinking and returned nothing (brevkoll#36). If the model is cut off at the cap the page says so (502, "ran out of room") instead of "unusable answer". |
| `APP_ENV` | `dev` | Set `prod` in deployments. |
| `APP_DATA_DIR` | `data` | Scratch directory. It must be empty after every request. |
| `RATE_LIMIT_PER_MINUTE` | `10` | Requests per minute per client IP. |
| `DAILY_MODEL_CALL_BUDGET` | `200` | Model calls per day, then 503. |
| `OCR_CONCURRENCY` | `2` | Parallel OCR jobs. |
| `TRUSTED_PROXIES` | empty | Proxy IPs whose `X-Forwarded-For` is trusted. |
| `FAKE_LLM_LOG`, `FAKE_LLM_RESPONSE` | none | Test seams for the `fake` provider. |

## Limits and what is not done

- OCR can misread characters in photos, for example an `@` in an email address. Check dates and addresses against the letter.
- Names and street addresses are not redacted and can reach the model, so use a local model.
- Year-less dates (`4/12`) resolve to the next occurrence and can pick the wrong year for letters read in January.
- PDF page boxes are not capped by pixels, and chunked uploads are checked only after parsing.

## How it was built

Built through the software factory. The spec, threat model, research, plan and validation report for v1 are in `thoughts/1/`,
and each later change has its own folder (`thoughts/15/`: the page refresh and the theme switch).
Acceptance tests are in `tests/holdout/`. Rules for coding agents are in `AGENTS.md`.

## Quality guards

The `quality` CI job and `bash scripts/quality.sh origin/main` check what a green test run misses: a complexity and size ratchet
against `quality/health.json` (it only moves toward better; a nightly job on the factory host opens a PR to tighten it),
80% coverage on changed lines, import contracts in `.importlinter`, acceptance-criterion traceability, and the size of
`AGENTS.md`. Mutation testing on changed files runs in warn mode. Policy: `quality/policy.toml`.
