# 0004. A public, host-free deploy/base; everything network-specific lives in the overlay

Status: proposed
Issue: #19   Date: 2026-11-21

## Context
`deploy/` is mirrored publicly. The GitOps repo points an overlay at `deploy/base`. Host names, private addresses,
the namespace, the front end's address and secret values must not be published (threat model T7). The rate limit and
the daily budget live in memory, so two pods double the allowed model load (T13). The app handles hostile uploads with
native parsers (Tesseract, poppler), so the container must not be able to reach the node, the API or the network
beyond what it needs (T9, T12). "Nothing is stored" needs scratch space that disappears with the pod (T10).

## Decision
`deploy/base` holds a Deployment, a Service and a NetworkPolicy listed in `kustomization.yaml`, and nothing else: no
Ingress, no Secret, no namespace, no image tag, no `host`, no `ipBlock`, no peer in the NetworkPolicy. One replica with
`strategy: Recreate`; non-root uid/gid 10001, read-only root, no escalation, all capabilities dropped, seccomp
`RuntimeDefault`, no service account token; `/tmp` and `/data` are memory `emptyDir`s with size limits; CPU and memory
limits are set. The API key comes from `secretKeyRef` and the TLS files from a read-only `secret` volume with mode 0440,
both from the Secret `brevkoll-llm`. Egress allows only DNS (53) and TCP 8743; ingress allows only TCP 8000.

## Consequences
Base alone does not run: the overlay must add the image tag and digest, `LLM_BASE_URL`, `LLM_MODEL`,
`TRUSTED_PROXIES`, the Secret, the Ingress, the namespace and the NetworkPolicy peers. Until it adds the peers,
egress to 8743 and ingress to 8000 are open to any address (accepted risks R2, R3). Each rollout has a few seconds of
downtime. Do not add host names, addresses or a second replica to base; put them in the overlay or make a new decision.
