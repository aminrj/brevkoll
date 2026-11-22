# 0003. Call the model over mutual TLS with a pinned CA, built in app.tls

Status: proposed
Issue: #19   Date: 2026-11-21

## Context
On the cluster the model is reachable only through a front end that requires a client certificate. The app must
present one, and it must trust only the CA that signs the front end (threat model T2), not the system store. A wrong
configuration (only the cert, a missing file, a key that does not match, `http://` with TLS settings) must not start
an app that silently sends letter text unauthenticated or in clear text (T1, T3). The spec sketch uses httpx's
`cert=` and `verify=<path>` arguments, which httpx 0.28 deprecates. `src/app/main.py` is at the size ratchet's
maximum and cannot grow. Tests need real certificates, and committed private keys would trip secret scanning.

## Decision
`app.tls.model_ssl_context(settings)` is the only place that builds an `ssl.SSLContext` for the model: CA from
`LLM_TLS_CA_FILE` only (no default certs), `check_hostname=True`, `CERT_REQUIRED`, TLS 1.2 minimum, and the client
cert and key loaded once with `load_cert_chain`. `app.llm.model_http_client` passes it as `httpx.Client(verify=ctx)`
with `trust_env=False`. `load_settings` refuses cert without key (and the reverse), unreadable paths and a non-`https`
`LLM_BASE_URL` when any `LLM_TLS_*` is set; a load failure is a `ConfigError` at startup. Error messages name
variables, never paths or content. Test certificates come from `trustme` at test time.

## Consequences
A bad TLS configuration stops the pod at startup (crash loop), which is visible at once. Certificate rotation needs a
pod restart. Encrypted private keys are not supported. With no `LLM_TLS_*` set, behaviour is exactly as before
(plain `http://` staging keeps working). Do not add the system store next to the pinned CA, do not set
`check_hostname=False` to work around a SAN mismatch (fix the name in `LLM_BASE_URL` or the front end's certificate),
and do not build a second SSL context elsewhere.
