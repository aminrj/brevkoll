# Spec: #19 Ready for the cluster: the model over mutual TLS, and a hardened deploy/ base

Status: approved

**Real user:** the owner (first real use of brevkoll outside a staged build)   **Size:** M   **Timebox:** 4 h   **Kill date:** 2026-12-05

## Problem

brevkoll runs only as a staged build on the GPU workstation. To use it for real it has to run on the cluster, where the model is reached only through its mutual-TLS front end, and the app cannot present a client certificate today (#14). There are also no Kubernetes manifests.

## What v1 does (one sentence)

The app can call the model with a client certificate, and the repo carries a hardened, host-free `deploy/base` that the GitOps repo can point at.

## User flow
1. The owner merges this change.
2. A session with the owner publishes the image, adds the overlay with the host name, the secrets and the Argo CD Application in the GitOps repo, and adds the DNS name (out of scope here, see below).
3. The owner opens brevkoll on the phone from the tailnet and decodes a letter.

## Acceptance criteria (each one becomes a holdout test)
- [ ] AC1: Given `LLM_TLS_CERT_FILE`, `LLM_TLS_KEY_FILE` and `LLM_TLS_CA_FILE` pointing at readable files, when the settings load, then they load without error and the model client presents that client certificate and trusts only that CA.
- [ ] AC2: Given only one of `LLM_TLS_CERT_FILE` / `LLM_TLS_KEY_FILE`, or a path that does not exist, when the settings load, then a `ConfigError` names the variable (no secret value in the message).
- [ ] AC3: Given a model endpoint that requires a client certificate, when the app calls it with the configured certificate, then the call succeeds; without the certificate settings the same call fails and the app does not crash.
- [ ] AC4: `deploy/base` is a kustomization with a Deployment of exactly one replica that runs the image as non-root with a read-only root filesystem, no privilege escalation, all capabilities dropped, in-memory `emptyDir` volumes for `/tmp` and `/data`, container port 8000, and liveness and readiness probes on `/healthz`.
- [ ] AC5: `deploy/base` has a Service to port 8000 and a NetworkPolicy whose egress allows only DNS (53) and the model front end (8743).
- [ ] AC6: `deploy/base` holds no secret values and no host names: the model key and the TLS files come from a Secret by reference (`secretKeyRef` and a secret volume), there is no `Secret` with data, no `Ingress`, and no internal name or private address in any file.

## Contract (agents must respect this exactly; holdout tests depend on it)
- Environment: `LLM_TLS_CERT_FILE`, `LLM_TLS_KEY_FILE`, `LLM_TLS_CA_FILE` (all optional; cert and key together). Same names as `docs/deploy.md` already lists for staging.
- `app.config.load_settings(env)` raises `app.config.ConfigError` for AC2.
- `app.main._build_llm(settings)` returns the model client; its `complete(prompt, max_tokens=..., timeout=...)` is what AC3 calls.
- Manifests live in `deploy/base/` with a `kustomization.yaml` listing them. The Secret the manifests reference is named `brevkoll-llm` with keys `api-key`, `tls.crt`, `tls.key`, `ca.crt`.
- `deploy/` is mirrored publicly: host names, addresses and the namespace's network specifics go in the GitOps overlay, not here.

## Out of scope
- Publishing the image, the GitOps overlay (Ingress with the host name, the model's address in the NetworkPolicy), the ExternalSecret, the Argo CD Application, DNS and the certificate for the name: a session with the owner, later factory#27.
- A new client identity for the model (PKI rotation, owner only). The overlay may use the borrowed identity as the factory does.
- More than one replica (the rate limit and the budget are in memory).

## Sketch
`httpx.Client(cert=(cert, key), verify=ca)` when the TLS settings are set. `deploy/base`: Deployment, Service, NetworkPolicy, kustomization.
