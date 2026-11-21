# Deploy

How brevkoll runs, written for someone who has never seen it. No hostnames, addresses or secrets in this file; it is mirrored publicly.

## The contract with the factory

- The image listens on **8000** inside the container (`uvicorn app.main:app --host 0.0.0.0 --port 8000`).
- `GET /healthz` answers 200.
- It runs as user `app` (uid 10001) with a read-only root filesystem. It writes only to `/tmp` and `/data`, and `/data` must be empty after every request.
- **One replica only.** The rate limit and the daily model-call budget live in memory.
- All settings are environment variables, see the table in `README.md`.

## Model

brevkoll needs an OpenAI-compatible chat endpoint and uses it for the summary and the action list only. Dates come from code.

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `openai_compat`. `fake` is for tests and is refused when `APP_ENV=prod` (the image sets `prod`). |
| `LLM_BASE_URL`, `LLM_MODEL` | Endpoint including `/v1`, and the model name. |
| `LLM_API_KEY` | Optional bearer key. |
| `MODEL_TIMEOUT_S`, `MODEL_MAX_TOKENS` | A model that thinks before answering needs 120 s or more and a higher token cap. |

Not supported yet: an endpoint that requires a client certificate (mutual TLS). That blocks the cluster, not staging on the owner's machine.
The model can be busy or off. The app answers 502 then; it does not crash.

## Staging (by the factory)

At the review checkpoint the factory builds the PR head, runs it in a sandbox on the owner's machine and posts the link on the Gitea PR.
The owner opens it on a phone that is on the tailnet. Nothing to run by hand.

## Production

Not deployed. Planned: the cluster, reachable only from the tailnet, one replica, the model through its mutual-TLS front end. The manifests will live in `deploy/` in this repo.

## Rollback

Staging: merge, `/stop`, or remove the container `stage-brevkoll`. Production: revert the commit that bumped the image tag.
