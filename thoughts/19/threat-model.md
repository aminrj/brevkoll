# Threat model: #19

Status: DRAFT. Every decision is ACCEPTED; the human decides. When a row is decided, change its
decision cell to ACCEPTED, CHANGED or REJECTED (`scripts/trace.py` then requires a test for the
first two).

Scope: what this change adds, which is (a) mutual TLS from the app to the model front end and (b) a
public, host-free `deploy/base`. The letter-handling controls from `thoughts/1/threat-model.md`
(redaction, output schema, upload caps, rate limit, budget) do not change and are not repeated
here. Where this change could weaken one of them, the row says so.

## Assets

- **The client private key** (`tls.key`), the client certificate and the CA bundle. With the key,
  anyone who reaches the front end can call the model as this identity. The spec allows the overlay
  to use a *borrowed* identity (the factory's), so a leak exposes more than brevkoll.
- **The model API key** (`LLM_API_KEY`, Secret key `api-key`).
- **The redacted letter text** in transit to the model. Today it travels over whatever
  `LLM_BASE_URL` says. On the cluster it crosses the network to the front end.
- **The public mirror of `deploy/`.** Anything committed there is published: host names, private
  addresses, namespace network details.
- **The "nothing is stored" promise.** On the cluster this depends on `/tmp` and `/data` being
  in-memory volumes that disappear with the pod.
- **The cluster** (node, other namespaces) if the container escapes or misuses its service account.
- **The model's capacity and budget**, now shared with other cluster users of the same front end.

## Entry points and trust boundaries

1. **Environment and mounted files** (`LLM_TLS_CERT_FILE`, `LLM_TLS_KEY_FILE`, `LLM_TLS_CA_FILE`,
   `LLM_BASE_URL`, `LLM_API_KEY`). Trusted origin (the overlay and the ExternalSecret), but the
   values can be wrong: missing file, only one of the pair, wrong CA, a plain `http://` URL.
2. **App to model front end** (new boundary: pod network to front end on 8743). The server is
   authenticated by the configured CA only; the app authenticates with its client certificate.
3. **Model response.** Still untrusted, parsed by `parse_model_output` (unchanged, #1).
4. **Ingress to the pod on 8000.** Comes from the ingress controller in the overlay (out of scope),
   but `deploy/base` decides whether anything else in the cluster can reach the pod.
5. **Kubernetes API and the node.** The pod's service account token and its security context.
6. **The public mirror.** Everything under `deploy/` crosses from private to public.

## Data flow to models

| Data | Model (local / cloud) | Why acceptable |
|---|---|---|
| Redacted OCR text and the target language (unchanged from #1) | Local model on the owner's hardware, reached through its mutual-TLS front end on the cluster network. | Same redaction as #1. New: the hop is now encrypted and both ends are authenticated (T1, T2, T3), so other workloads on the network cannot read or spoof it. ACCEPTED |
| Client certificate (public part) | Sent to the front end in the TLS handshake. | It is meant to be presented. It identifies the client to the front end, not to the model. |
| Client private key, CA bundle, API key | Never in a prompt. The key never leaves the pod; the API key goes only in the `Authorization` header. | AGENTS.md: no secrets in prompts. T4 keeps them out of logs and errors. |

## Threats and controls

| ID | Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|---|
| T1 | LLM02 Sensitive information disclosure (transport) | TLS settings are set but `LLM_BASE_URL` is `http://...`. httpx then sends the letter text and the API key in clear text and silently ignores the certificate, and the owner believes mTLS is on. | `load_settings` raises `ConfigError("LLM_BASE_URL must use https when LLM_TLS_* is set")` when any `LLM_TLS_*` variable is set and the URL scheme is not `https`. | Unit (`test_config.py`): cert, key and CA set with `LLM_BASE_URL=http://model:8743/v1` raises `ConfigError` naming `LLM_BASE_URL`; the same with `https://` loads. | ACCEPTED |
| T2 | LLM02 / spoofing of the model | The app trusts the system CA store as well as the configured CA, so any server with a public certificate (or a cluster workload that can redirect DNS) can impersonate the front end, read the letter text and return crafted output. AC1 says "trusts only that CA". | `_build_llm` builds an `ssl.SSLContext` with `ssl.create_default_context(cafile=ca)` (no `load_default_certs`), `check_hostname=True`, `verify_mode=CERT_REQUIRED`, minimum TLS 1.2, and passes it as `httpx.Client(verify=ctx)`. `trust_env=False` stays so `SSL_CERT_FILE` / `SSL_CERT_DIR` and proxy variables cannot widen trust. | Unit: build the client from settings with a test CA and assert the context's `get_ca_certs()` holds exactly that CA, `check_hostname` is true and `minimum_version >= TLSv1_2`. Integration (with AC3): a local TLS server signed by a *different* CA makes `complete()` raise `ModelUnavailable`. | ACCEPTED |
| T3 | LLM02 / spoofing of the client (misconfiguration) | Only the cert or only the key is set, or a path is wrong. Without a guard the app starts, calls the front end without a certificate, and every decode fails at request time with a generic 502 (or worse, a front end that does not require a certificate is called unauthenticated). | `load_settings` requires cert and key together and checks each set path exists and is a readable file; otherwise `ConfigError` names the variable and never the file content (AC2). The key and cert are loaded once at startup with `ctx.load_cert_chain(cert, key)`; an `ssl.SSLError` there (wrong format, key does not match cert, encrypted key) is converted to `ConfigError("LLM_TLS_CERT_FILE / LLM_TLS_KEY_FILE could not be loaded")`, so the pod fails fast and the readiness probe never passes. | Holdout AC2. Unit: cert without key, key without cert, a missing path, and a key that does not match the cert each raise `ConfigError`; the message contains the variable name and does not contain the PEM text or the `BEGIN` marker. | ACCEPTED |
| T4 | LLM02 Sensitive information disclosure (secrets in logs) | A TLS or HTTP error is logged with its full text, or a `ConfigError` echoes a value, putting key material or the API key in pod logs (which leave the pod via the cluster log pipeline). | Error messages for TLS settings name variables only. `OpenAICompatLLM.complete` keeps converting `httpx.HTTPError` (which includes `ConnectError` from TLS failures) to `ModelUnavailable` with `from None`, so no exception text is logged or returned. `Settings` keeps `llm_api_key` as `SecretStr`; the TLS paths are plain `Path`s (paths are not secret), file contents are never held in `Settings`. | Unit: a TLS handshake failure gives a 502 with the generic message, and a log capture during that request has no certificate subject, no PEM text and no API key. Unit: `repr(settings)` does not contain the API key. | ACCEPTED |
| T5 | LLM10 Unbounded consumption / availability | The front end refuses the certificate or is down. The app crashes, hangs, or retries in a loop and burns the shared model's capacity (AC3: "fails and the app does not crash"). | No change in behaviour: a TLS failure is an `httpx.HTTPError`, mapped to `ModelUnavailable` (502). The existing timeout and `max_tokens` cap apply to the mTLS client. No retries. The daily budget still counts the call (`BudgetedLLM` wraps the new client unchanged). | Holdout AC3. Unit: `_build_llm` with TLS settings still returns a client that `create_app` wraps in `BudgetedLLM` (the budget test from #1 passes with the mTLS client injected). | ACCEPTED |
| T6 | LLM01, LLM05, LLM06, LLM07 | Unchanged by this issue. The model gets the same prompt and the output goes through the same schema; mTLS adds no tools, no new output path and nothing to the prompt. | No new control. The existing #1 controls (data delimiters, `ModelOutput` with `extra="forbid"`, no tools, no secrets in the system prompt) apply to the new client because it implements the same `LLMClient.complete`. | Existing #1 tests, which run against `LLMClient` and do not depend on the transport. No new test. | ACCEPTED |
| T7 | Public mirror: information disclosure | A host name, an internal domain, a tailnet name, a private address, a namespace's CIDR or a secret value is committed under `deploy/` and published by the mirror (AC6). | `deploy/base` contains no `Ingress`, no `Secret` with `data`/`stringData`, no `host:`, no `ipBlock`. The NetworkPolicy egress to 8743 has no `to:` peer in base (the overlay adds it). The model key and TLS files come only from `secretKeyRef` / a `secret` volume naming `brevkoll-llm`. | Holdout AC6. Unit (`tests/unit/test_deploy_base.py`): parse every YAML document in `deploy/base`; fail on `kind: Secret` with data, `kind: Ingress`, any `ipBlock`, any `host` key; scan raw text with a regex for RFC 1918 / CGNAT / link-local addresses and for any dotted name that is not on a short allowlist of Kubernetes API groups (`apps/v1`, `networking.k8s.io/v1`, `kustomize.config.k8s.io/...`) and the image registry placeholder. The test file holds patterns, not the real names, so the test itself does not leak them. | ACCEPTED |
| T8 | Secret handling in the pod | The key is mounted world-readable, into a writable path, or as an environment variable (env leaks into `/proc`, crash dumps and `kubectl describe`). | TLS files are a `secret` volume (`brevkoll-llm`, items `tls.crt`, `tls.key`, `ca.crt`) mounted `readOnly: true` at a fixed path such as `/etc/brevkoll/tls`, with `defaultMode: 0440` and the pod `fsGroup: 10001` so uid 10001 can read it and others cannot. `LLM_TLS_*_FILE` point at that path. Only the API key uses `secretKeyRef` (it is a bearer token, and the app reads it from env today). | Unit (deploy test): the volume is of type `secret` with `secretName: brevkoll-llm`, the mount is `readOnly`, `defaultMode` is no wider than `0440`, and no env var takes `tls.key` via `secretKeyRef`. | ACCEPTED |
| T9 | Container escape / lateral movement | The container runs as root, can escalate, keeps capabilities, writes to its root filesystem, or uses the default service account token to talk to the Kubernetes API. A parser bug in Tesseract or poppler on a hostile upload then reaches the node or the API. | Deployment: `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile.type: RuntimeDefault` (AC4 plus seccomp), and `automountServiceAccountToken: false` on the pod. | Holdout AC4. Unit (deploy test): the seccomp profile is `RuntimeDefault` and `automountServiceAccountToken` is `false`. | ACCEPTED |
| T10 | LLM02 (storage): "nothing is stored" | `/tmp` or `/data` is backed by node disk (a plain `emptyDir`, a hostPath or a PVC), so a temp file left by a crash survives on the node after the pod is gone. | Both are `emptyDir: {medium: Memory}` with a `sizeLimit` (proposed 256Mi for `/tmp`, 64Mi for `/data`). No PVC, no hostPath in base. | Holdout AC4 (in-memory volumes). Unit (deploy test): no `hostPath` or `persistentVolumeClaim` volume, and both `emptyDir` volumes set `sizeLimit`. | ACCEPTED |
| T11 | LLM10 Unbounded consumption (pod resources) | A large PDF or a burst of uploads makes OCR use all the node's memory or CPU, affecting other workloads; memory-backed `emptyDir` counts against pod memory and can grow without bound. | Container `resources.requests` and `resources.limits` for CPU and memory (proposed: request 250m / 512Mi, limit 1 CPU / 1Gi, to tune on first real use). Together with the `sizeLimit` above and the existing upload, page and pixel caps and `OCR_CONCURRENCY`. | Unit (deploy test): the container sets memory and CPU limits, and the memory limit is greater than the sum of the `emptyDir` size limits. | ACCEPTED |
| T12 | Web: network exposure and SSRF egress | Egress: a compromised pod reaches the internet, the Kubernetes API or other services. Ingress: any pod in the cluster can call the decode API directly, bypassing the ingress controller and the rate limit's trusted-proxy logic. | NetworkPolicy selecting the brevkoll pods with `policyTypes: [Ingress, Egress]`. Egress: DNS on 53 UDP and TCP, and TCP 8743; nothing else (AC5). Ingress: TCP 8000 only, with the `from:` peer (the ingress controller's namespace) left to the overlay. Base ships ingress with no `from` peer and a comment that the overlay must narrow it. | Holdout AC5. Unit (deploy test): `policyTypes` includes both, egress ports are exactly {53/UDP, 53/TCP, 8743/TCP}, ingress ports are exactly {8000/TCP}. | ACCEPTED |
| T13 | Availability / single replica | Two replicas would each keep their own in-memory rate limit and budget, doubling the allowed load on the model (#1 R5). A rolling update can briefly run two pods. | `replicas: 1` and `strategy: Recreate`, so an update never runs two pods at once. No HorizontalPodAutoscaler in base. | Holdout AC4 (one replica). Unit (deploy test): the strategy is `Recreate` and there is no `HorizontalPodAutoscaler`. | ACCEPTED |
| T14 | Supply chain: image | Base references a mutable tag (`:latest`), so a pushed image changes what runs without a commit. | Base uses a placeholder image name with no tag; the overlay sets the tag and digest through kustomize `images:` (rollback is a revert of that commit, as `docs/deploy.md` says). | Unit (deploy test): the container image has no `:latest` tag. | ACCEPTED |
| T15 | Web: authn/z, IDOR, CSRF, upload handling | Unchanged by this issue. The service stays reachable only from the tailnet through the overlay's Ingress; still no accounts, no stored data. | No new control. #1 controls apply. Health probes hit `/healthz` only, which returns no data. | Existing #1 tests and `test_health.py`. | ACCEPTED |

## Accepted risks

Proposed for the human to accept or reject:

- **R1: borrowed client identity.** The spec allows the overlay to use the factory's client
  certificate. A leak of brevkoll's Secret then lets the holder call the model as the factory, and
  the front end cannot tell brevkoll's traffic from the factory's in its logs or limits. Mitigation
  is the separate identity in the owner's PKI work, out of scope here.
- **R2: base egress to 8743 is to any address.** Because the model's address must not be in the
  public repo, `deploy/base` allows TCP 8743 to every destination. Until the overlay adds the `to:`
  peer, a compromised pod can reach any service on that port. The overlay must narrow it.
- **R3: base ingress has no source restriction.** Same reason as R2: the ingress controller's
  namespace belongs in the overlay. Until then any pod in the cluster can reach port 8000.
- **R4: no certificate rotation without a restart.** The certificate is loaded once at startup.
  When the ExternalSecret updates the files, the pod keeps the old key until it restarts. Expiry
  shows up as 502s, not a crash.
- **R5: encrypted private keys are not supported.** `LLM_TLS_KEY_FILE` must be an unencrypted PEM
  key; protection is the Secret, the `0440` mode and the read-only mount.
- **R6: single replica.** One pod means downtime on restart or node drain. Accepted by the spec
  because the limits are in memory.

## Open questions for the human

- Q1: T1 refuses `http://` when TLS settings are set. Should it also refuse `http://` in general
  when `APP_ENV=prod`? That would break any staging setup that still uses plain HTTP with
  `APP_ENV=prod` (the image sets `prod`).
- Q2: T2 sets `check_hostname=True`. Does the front end's server certificate carry the name the
  overlay will put in `LLM_BASE_URL` in its SAN? If the overlay calls the front end by IP, hostname
  checking fails unless the certificate has an IP SAN.
- Q3: The deploy tests (T7 to T14) need a YAML parser. PyYAML is importable today only as a
  transitive dependency of `fastapi[standard]`. Should the plan name `pyyaml` as an explicit dev
  dependency, or should the tests parse with something else?
- Q4: T11 resource numbers are guesses. Do you have numbers from staging for a 3-page PDF?
- Q5: T12 makes the NetworkPolicy cover ingress as well as egress. The spec's AC5 mentions only
  egress. Is an ingress rule in base wanted, or should ingress live only in the overlay?
- Q6: T13 uses `strategy: Recreate`. Is a few seconds of downtime per rollout acceptable (I think
  yes, given one user)?
