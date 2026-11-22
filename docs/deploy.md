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
| `LLM_TLS_CERT_FILE`, `LLM_TLS_KEY_FILE` | Client certificate and key files (PEM). Set both or neither. |
| `LLM_TLS_CA_FILE` | CA certificate file (PEM) for the model endpoint. Any `LLM_TLS_*` requires `https://` in `LLM_BASE_URL`. |
| `MODEL_TIMEOUT_S`, `MODEL_MAX_TOKENS` | A model that thinks before answering needs 120 s or more and a higher token cap. |

### Mutual TLS

When the endpoint requires a client certificate, set the three `LLM_TLS_*` files:

- Cert and key go together; the key must be an unencrypted PEM key.
- With `LLM_TLS_CA_FILE` set, the endpoint's certificate must chain to that CA only; the system trust store is not used.
- Any `LLM_TLS_*` requires `https://` in `LLM_BASE_URL`, and the host name is checked: the name (or IP) in `LLM_BASE_URL` must be in the front end's certificate SAN.
- The files are loaded once at startup. A file that cannot be loaded (wrong format, key that does not match the cert) stops the app with a `ConfigError`. Rotating the certificate needs a restart.
- If the front end refuses the certificate at request time, the app answers 502 and keeps running.

The model can be busy or off. The app answers 502 then; it does not crash.

## Staging (by the factory)

At the review checkpoint the factory builds the PR head, runs it in a sandbox on the owner's machine and posts the link on the Gitea PR.
The owner opens it on a phone that is on the tailnet. Nothing to run by hand.

## Production

Not deployed yet. Planned: the cluster, reachable only from the tailnet, one replica, the model through its mutual-TLS front end.

`deploy/base` is a public, host-free Kustomize base (`kubectl kustomize deploy/base`). It holds:

- a Deployment: one replica, `Recreate`, uid/gid 10001, non-root, read-only root filesystem, no privilege escalation, all capabilities dropped, seccomp `RuntimeDefault`, no service account token. `/tmp` (256Mi) and `/data` (64Mi) are in-memory `emptyDir` volumes. Requests 250m / 512Mi, limits 1 CPU / 1Gi. Liveness and readiness on `GET /healthz` port 8000. It sets `APP_ENV=prod`, `LLM_PROVIDER=openai_compat` and the three `LLM_TLS_*` paths under `/etc/brevkoll/tls`;
- a ClusterIP Service on port 8000;
- a NetworkPolicy: ingress on TCP 8000, egress on DNS (UDP and TCP 53) and TCP 8743, all without peers.

Secrets come by reference only: `LLM_API_KEY` from key `api-key` of the Secret `brevkoll-llm`, and that same Secret's `tls.crt`, `tls.key` and `ca.crt` mounted read-only with mode 0440.

On its own the base does not start: the app stops with a `ConfigError` until the overlay sets the model. The overlay (in the GitOps repo, not here) must add:

- the image tag and digest;
- `LLM_BASE_URL` (an `https://` URL whose host name is in the front end's certificate SAN), `LLM_MODEL` and `TRUSTED_PROXIES`;
- the `brevkoll-llm` Secret, through an ExternalSecret, with keys `api-key`, `tls.crt`, `tls.key` and `ca.crt`;
- the Ingress with the host name;
- the NetworkPolicy peers: a `from:` for the ingress controller's namespace and a `to:` for the model front end;
- the namespace.

`tests/deploy` checks the base: the controls above, and that no file under `deploy/` holds an address, a host name or a secret.

## Rollback

Staging: merge, `/stop`, or remove the container `stage-brevkoll`. Production: revert the commit that bumped the image tag.
