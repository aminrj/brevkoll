# Plan: #19
Status: approved

Goal: the app calls the model over mutual TLS (client certificate, server checked against one pinned CA), and the repo
carries a hardened, host-free `deploy/base` that a GitOps overlay can point at. Nothing in the decode pipeline changes
(OCR, redaction, prompt, output schema, dates, `.ics`, routes).

Inputs: `thoughts/19/spec.md` (approved), `thoughts/19/threat-model.md` (T1 to T15 ACCEPTED), `thoughts/19/research.md`.

How this plan settles the open questions so no phase waits on an answer (each can be changed at review; the phases
do not depend on a later approval):

- Threat model Q1 (refuse `http://` in prod in general): **not done.** Only T1 (refuse `http://` when any
  `LLM_TLS_*` is set). A general rule would break staging.
- Q2 (hostname check): `check_hostname=True` as T2 says. The overlay must call the front end by a name (or IP) that is in
  its certificate's SAN. Written in `docs/deploy.md`.
- Q3 / research Q3 (YAML parser): `pyyaml` becomes an explicit **dev** dependency (it is already in `uv.lock`).
- Q4 (resources): the T11 numbers (request 250m / 512Mi, limit 1 CPU / 1Gi). Tuned on first real use, in the overlay.
- Q5 (ingress in the NetworkPolicy): T12 is ACCEPTED, so base has an ingress rule on 8000 with no `from:` peer.
- Q6 (`Recreate`): T13 is ACCEPTED, so `strategy: Recreate`.
- Research Q1 (TLS names not in docs): this issue adds them to `README.md` and `docs/deploy.md`.
- Research Q2 (test certificates): `trustme` as a dev dependency. No committed PEM files (gitleaks), no `openssl` CLI
  needed in CI.
- Research Q4 (fail-before-patch gate vs manifest tests): manifest tests live in a new `tests/deploy/` folder, added to
  pytest `testpaths`. They fail without the change because `deploy/base/` does not exist; the gate, which resets only
  `src/`, cannot measure that. ADR 0005 records this. If the human rejects it, the tests move to `tests/unit` and the
  gate needs a human change; the manifests themselves do not change.
- Research Q6 (gid): no Dockerfile change. `runAsGroup: 10001` and `fsGroup: 10001` in the manifest set the gid at run
  time whatever `/etc/group` says.
- Research Q7 (bad TLS config): fail fast. `create_app()` runs at import, so a `ConfigError` exits uvicorn and the pod
  crash-loops (it does not sit unready). That is the existing `ConfigError` behaviour.
- Research Q8 (size ratchet): `src/app/main.py` is 94 non-blank lines, which is the baseline maximum with tolerance 0.
  It must not grow. The SSL context goes into a new module `app.tls`, and the HTTP client builder into `app.llm`, so
  `main.py` loses a line (`import httpx` goes away).
- Research Q9 (httpx form): the `ssl.SSLContext` passed as `verify=` (T2), not the deprecated `cert=` / `verify=<path>`.

## Phase 1: TLS settings are validated at startup
A wrong TLS configuration stops the app at startup with a `ConfigError` that names the variable. No network change yet.

- [x] Files:
  - `src/app/config.py` (three new fields, two helpers; stays at or under 90 non-blank lines)
  - `tests/unit/test_tls_settings.py` (new)
  - `README.md`, `docs/deploy.md` (see Docs)
- [x] Types and signatures:
  ```python
  # src/app/config.py
  TLS_VARS: tuple[str, str, str] = ("LLM_TLS_CERT_FILE", "LLM_TLS_KEY_FILE", "LLM_TLS_CA_FILE")


  class Settings(BaseModel):  # frozen, as today; three new fields at the end
      ...
      llm_tls_cert_file: Path | None
      llm_tls_key_file: Path | None
      llm_tls_ca_file: Path | None


  def _readable_file(env: Mapping[str, str], key: str) -> Path | None:
      """None when unset or empty. ConfigError(f"{key} must name a readable file") when the path is missing,
      is not a regular file, or os.access(path, os.R_OK) is false. Never reads the file. Never puts the path or
      the content in the message."""


  def _check_tls(env: Mapping[str, str], base_url: str | None) -> None:
      """ConfigError("LLM_TLS_CERT_FILE and LLM_TLS_KEY_FILE must be set together") when exactly one is set.
      ConfigError("LLM_BASE_URL must use https when LLM_TLS_* is set") when any TLS var is set, base_url is set,
      and urlsplit(base_url).scheme != "https"."""


  def load_settings(
      env: Mapping[str, str],
  ) -> Settings: ...  # same signature; calls _check_tls, then _readable_file x3
  ```
  The pair check runs before the file checks, so "only the key" reports the pair rule, not a path. `CA` alone is allowed
  (server authentication with a pinned CA, no client certificate). Cert and key without CA are allowed (system trust
  store plus client certificate; see Phase 2).
- [x] Tests to add, in `tests/unit/test_tls_settings.py` (all use `tmp_path` files with dummy text; Phase 1 never parses
  PEM). Markers `@pytest.mark.ac(...)` / `@pytest.mark.control(...)` as listed.
  - `test_tls_paths_load_when_all_three_exist` (AC1): the three paths come back as `Path` on `Settings`. Fails today:
    the fields do not exist.
  - `test_cert_without_key_names_the_pair` and `test_key_without_cert_names_the_pair` (AC2, T3): `ConfigError` whose
    message contains `LLM_TLS_CERT_FILE` and `LLM_TLS_KEY_FILE`. Fails today: no error.
  - `test_missing_path_names_the_variable` (AC2, T3): parametrised over the three variables, a nonexistent path gives a
    `ConfigError` naming that variable and not containing the path. Fails today.
  - `test_directory_is_not_a_readable_file` (T3): a directory path is refused. Fails today.
  - `test_error_never_contains_file_content` (T3, T4): a cert file whose text is `-----BEGIN PRIVATE KEY-----secret`
    with the key unset: the message has neither `BEGIN` nor `secret`. Fails today (no error is raised at all).
  - `test_http_base_url_refused_with_tls` (T1): cert, key and CA set with `LLM_BASE_URL=http://model:8743/v1` raises
    naming `LLM_BASE_URL`; the same with `https://` loads. Fails today.
  - `test_http_base_url_still_allowed_without_tls` (T1 boundary): no TLS vars and `http://` loads. Guard (keeps staging
    working); passes today.
  - `test_ca_alone_is_allowed` (T3 boundary): only `LLM_TLS_CA_FILE` set loads. Fails today (field missing).
  - `test_settings_repr_hides_api_key` (T4): `repr(load_settings(...))` with TLS vars and `LLM_API_KEY=sk-test` does not
    contain `sk-test`. Guard.
- [x] Automated verification: `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest && bash scripts/quality.sh origin/main`
- [x] Manual verification: `LLM_PROVIDER=fake LLM_TLS_CERT_FILE=/nonexistent uv run fastapi dev src/app/main.py`
  exits at startup with `LLM_TLS_CERT_FILE must name a readable file` and no traceback text containing a path.
- [x] Threat-model controls implemented: T1, T3 (pair and path half), T4 (message half).
- [x] Docs touched: `README.md` configuration table gets the three TLS rows; `docs/deploy.md` model table gets the
  same three rows (the "Not supported yet" line stays until Phase 2).

## Phase 2: the model client presents the client certificate and trusts only the configured CA
The real handshake works end to end against a local mutual-TLS server.

- [x] Files:
  - `src/app/tls.py` (new, about 25 lines; imports `ssl`, `app.config` only)
  - `src/app/llm.py` (`model_http_client`)
  - `src/app/main.py` (`_build_llm` uses `model_http_client(settings)`; `import httpx` removed; net one line shorter)
  - `tests/unit/test_model_tls.py` (new)
  - `tests/integration/test_mtls_handshake.py` (new)
  - `pyproject.toml`, `uv.lock` (dev dependencies `trustme`, `pyyaml`; see Dependencies)
  - `README.md`, `docs/deploy.md`, `AGENTS.md` (see Docs)
  - `docs/decisions/0003-model-mtls-with-pinned-ca.md` (already written with this plan; status stays proposed)
- [x] Types and signatures:
  ```python
  # src/app/tls.py
  import ssl

  from app.config import ConfigError, Settings


  def model_ssl_context(settings: Settings) -> ssl.SSLContext | None:
      """None when no LLM_TLS_* var is set (httpx keeps its default verification, unchanged behaviour).
      Otherwise ssl.create_default_context(cafile=ca) when a CA is set (only that CA, no load_default_certs),
      or ssl.create_default_context() when it is not. Always check_hostname=True, verify_mode=CERT_REQUIRED,
      minimum_version=TLSv1_2. Loads the client cert and key when both are set."""


  def _load_client_cert(ctx: ssl.SSLContext, cert: Path, key: Path) -> None:
      """ctx.load_cert_chain(cert, key). ssl.SSLError or OSError becomes
      ConfigError("LLM_TLS_CERT_FILE / LLM_TLS_KEY_FILE could not be loaded") from None."""
  ```
  ```python
  # src/app/llm.py
  def model_http_client(settings: Settings) -> httpx.Client:
      """httpx.Client(follow_redirects=False, trust_env=False, verify=ctx or True) with ctx from model_ssl_context."""
  ```
  ```python
  # src/app/main.py, inside _build_llm, openai_compat branch (signature unchanged: _build_llm(settings) -> LLMClient)
  http = model_http_client(settings)
  ```
  `OpenAICompatLLM` does not change: every `httpx.HTTPError` (TLS failures arrive as `ConnectError` / `ReadError`)
  still becomes `ModelUnavailable` (502) `from None`. No retries. `create_app` still wraps the client in `BudgetedLLM`.
  The certificate is loaded once, when `_build_llm` runs at startup (R4: rotation needs a restart).
- [x] Tests to add. Certificates come from `trustme` fixtures in the test files (a CA, a server cert for `127.0.0.1`,
  a client cert, and a second CA). Nothing is written to the repo.
  - `tests/unit/test_model_tls.py`
    - `test_context_trusts_only_the_configured_ca` (AC1, T2): `model_ssl_context(settings).get_ca_certs()` has exactly
      one entry, the test CA's subject; `check_hostname` is true; `verify_mode == CERT_REQUIRED`;
      `minimum_version >= TLSVersion.TLSv1_2`. Fails today: `app.tls` does not exist.
    - `test_no_tls_settings_gives_no_context` (T5): returns `None`. Fails today (module missing).
    - `test_key_that_does_not_match_cert_is_config_error` (T3): client cert from one issue, key from another:
      `_build_llm` raises `ConfigError`; message names both variables, contains no `BEGIN`. Fails today (no load).
    - `test_garbage_cert_file_is_config_error` (T3): a cert file with non-PEM text gives `ConfigError`. Fails today.
    - `test_build_llm_with_tls_returns_openai_compat_client` (T5): `_build_llm` with full TLS settings returns an
      `OpenAICompatLLM`, `create_app()` with that env starts, and `app.llm.model_ssl_context` (wrapped with
      `monkeypatch` to record calls) was called once with those settings. Fails today: `app.llm.model_ssl_context`
      does not exist, so the `monkeypatch` fails.
    - `test_tls_failure_is_502_and_logs_no_secrets` (T4, T5): `create_app(llm=OpenAICompatLLM(..., httpx.Client(transport=MockTransport(raise httpx.ConnectError("certificate verify failed: CN=front-end -----BEGIN"))), "sk-test"))`
      and the fake OCR from `tests/unit/helpers.py`; `/api/decode` gives 502 with the fixed message, and `caplog`
      text contains none of `CN=front-end`, `BEGIN`, `sk-test`. Guard (existing mapping); kept so the new transport
      cannot regress it.
  - `tests/integration/test_mtls_handshake.py` (a `ThreadingHTTPServer` on `127.0.0.1:0` wrapped in an
    `ssl.SSLContext(PROTOCOL_TLS_SERVER)` with `verify_mode=CERT_REQUIRED`, trusting only the test CA, answering
    `POST /v1/chat/completions` with a valid chat envelope whose content is `{"summary": "ok", "actions": []}`)
    - `test_call_succeeds_with_client_certificate` (AC1, AC3): `_build_llm(load_settings(env)).complete("hi", max_tokens=50, timeout=5)`
      returns the content; the server recorded the client certificate's subject. Fails today: settings ignore the TLS
      vars, the system store does not trust the test CA, so `complete` raises `ModelUnavailable`.
    - `test_call_without_tls_settings_fails_without_crash` (AC3, T5): same URL, no TLS vars: `ModelUnavailable`, no
      other exception. Guard for "does not crash" (passes today); the file fails as a whole without the change.
    - `test_ca_only_is_rejected_by_server_requiring_client_cert` (AC3): CA set, no cert: `ModelUnavailable`.
    - `test_server_signed_by_other_ca_is_refused` (T2): server cert from a second CA, client trusts the first:
      `ModelUnavailable`.
    - `test_decode_through_the_app_over_mtls` (AC3): `create_app(ocr=<fake OCR>)` with the TLS env, `POST /api/decode`
      returns 200 with summary `ok`.
- [x] Automated verification: same command as Phase 1, plus `uv run lint-imports`.
- [x] Manual verification (for the human, at the owner session): point `LLM_BASE_URL` at the model front end over
  `https://`, set the three `LLM_TLS_*` paths to the borrowed identity, decode a letter, then unset the cert and see a
  502 page and a running app.
- [x] Threat-model controls implemented: AC1, AC3, T2, T3 (load half), T4, T5. T6 unchanged (existing #1 tests).
- [x] Docs touched: `docs/deploy.md` replaces "Not supported yet" with how mTLS works (cert and key together, CA pinned,
  `https://` required, loaded once at startup so rotation needs a restart, unencrypted PEM key only, the name in
  `LLM_BASE_URL` must be in the front end's certificate SAN). `README.md` table rows gain those notes in one line.
  `AGENTS.md` stack line names `trustme` and `pyyaml` as dev-only.

## Phase 3: a hardened, host-free `deploy/base`
`kubectl kustomize deploy/base` renders a Deployment, a Service and a NetworkPolicy that an overlay can extend.

- [x] Files:
  - `deploy/base/kustomization.yaml`, `deploy/base/deployment.yaml`, `deploy/base/service.yaml`,
    `deploy/base/networkpolicy.yaml` (new)
  - `tests/deploy/test_deploy_base.py` (new), `tests/deploy/__init__.py` only if the other test folders have one
  - `pyproject.toml` (`testpaths` gains `tests/deploy`)
  - `README.md`, `docs/deploy.md`, `AGENTS.md` (see Docs)
  - `docs/decisions/0004-host-free-deploy-base.md`, `docs/decisions/0005-manifest-tests-outside-the-src-gate.md`
    (already written with this plan)
- [x] Data model (manifests). Label everywhere: `app: brevkoll` (no dotted label keys, so the T7 scan stays simple).
  No `namespace:`, no `Ingress`, no `Secret`, no `HorizontalPodAutoscaler`, no `ipBlock`, no `host`.
  - `kustomization.yaml`: `apiVersion: kustomize.config.k8s.io/v1beta1`, `kind: Kustomization`,
    `resources: [deployment.yaml, service.yaml, networkpolicy.yaml]`. No `images:` (the overlay sets tag and digest).
  - `deployment.yaml` (`apps/v1`): `replicas: 1`, `strategy: {type: Recreate}`, selector and template label
    `app: brevkoll`. Pod: `automountServiceAccountToken: false`, `securityContext: {runAsNonRoot: true, runAsUser: 10001,
    runAsGroup: 10001, fsGroup: 10001, seccompProfile: {type: RuntimeDefault}}`. Container `app`: `image: brevkoll`
    (no tag), `ports: [{name: http, containerPort: 8000}]`, container `securityContext` repeating `runAsNonRoot`,
    `runAsUser`, `runAsGroup`, `seccompProfile` and adding `readOnlyRootFilesystem: true`,
    `allowPrivilegeEscalation: false`, `capabilities: {drop: [ALL]}`. Probes: `livenessProbe` and `readinessProbe`
    `httpGet {path: /healthz, port: 8000}`. Resources: requests `cpu: 250m, memory: 512Mi`, limits `cpu: "1",
    memory: 1Gi`. Env: `APP_ENV=prod`, `APP_DATA_DIR=/data`, `LLM_PROVIDER=openai_compat`,
    `LLM_TLS_CERT_FILE=/etc/brevkoll/tls/tls.crt`, `LLM_TLS_KEY_FILE=/etc/brevkoll/tls/tls.key`,
    `LLM_TLS_CA_FILE=/etc/brevkoll/tls/ca.crt`, `LLM_API_KEY` from `secretKeyRef {name: brevkoll-llm, key: api-key}`.
    `LLM_BASE_URL`, `LLM_MODEL` and `TRUSTED_PROXIES` are left to the overlay (a comment says so); base alone exits
    with the existing `ConfigError`, which is intended. Volumes: `tmp` `emptyDir {medium: Memory, sizeLimit: 256Mi}` at
    `/tmp`; `data` `emptyDir {medium: Memory, sizeLimit: 64Mi}` at `/data`; `llm-tls` `secret {secretName: brevkoll-llm,
    defaultMode: 288 (# 0440), items: [tls.crt, tls.key, ca.crt]}` at `/etc/brevkoll/tls`, `readOnly: true`.
    `defaultMode` is written in decimal so no YAML parser reads it differently.
  - `service.yaml` (`v1`): `ClusterIP`, selector `app: brevkoll`, `port: 8000, targetPort: 8000, name: http`.
  - `networkpolicy.yaml` (`networking.k8s.io/v1`): `podSelector {matchLabels: {app: brevkoll}}`,
    `policyTypes: [Ingress, Egress]`; ingress one rule `ports: [{protocol: TCP, port: 8000}]`, no `from` (comment: the
    overlay must add the ingress controller's namespace, R3); egress rule 1 `ports: [UDP 53, TCP 53]`, rule 2
    `ports: [TCP 8743]`, no `to` (comment: the overlay must add the front end's peer, R2).
- [x] Tests to add, in `tests/deploy/test_deploy_base.py`. A module helper loads every `*.yaml` under `deploy/base`
  with `yaml.safe_load_all`. All fail today because `deploy/base/` does not exist.
  - `test_kustomization_lists_every_manifest` (AC4): `resources` equals the set of other YAML files in the folder.
  - `test_deployment_single_replica_recreate_no_hpa` (AC4, T13): `replicas == 1`, strategy `Recreate`, no HPA kind.
  - `test_container_is_locked_down` (AC4, T9): non-root, uid 10001, read-only root, no escalation, drop `ALL`,
    seccomp `RuntimeDefault`, `automountServiceAccountToken` false.
  - `test_tmp_and_data_are_memory_emptydirs_with_limits` (AC4, T10): mounts at `/tmp` and `/data` come from
    `emptyDir` with `medium: Memory` and a `sizeLimit`; no `hostPath` or `persistentVolumeClaim` volume.
  - `test_port_and_probes` (AC4): container port 8000; liveness and readiness `httpGet` on `/healthz` port 8000.
  - `test_resources_cover_memory_volumes` (T11): CPU and memory limits set; memory limit (parsed from `Mi`/`Gi`) is
    greater than the sum of the `emptyDir` size limits.
  - `test_service_targets_8000` (AC5).
  - `test_network_policy_ports` (AC5, T12): both policy types; egress ports exactly {UDP 53, TCP 53, TCP 8743};
    ingress ports exactly {TCP 8000}.
  - `test_secrets_by_reference_only` (AC6, T8): `LLM_API_KEY` uses `secretKeyRef` `brevkoll-llm`/`api-key`; the TLS
    volume is a `secret` named `brevkoll-llm` with items `tls.crt`, `tls.key`, `ca.crt`, mounted `readOnly`,
    `defaultMode & ~0o440 == 0`; no env var reads `tls.key` via `secretKeyRef`; the `LLM_TLS_*` env values point
    inside the mount path.
  - `test_no_secret_ingress_or_network_specifics` (AC6, T7): no `kind: Secret` with `data`/`stringData`, no
    `Ingress`, no `ipBlock`, no `host` key at any depth, no `namespace` key.
  - `test_no_addresses_or_host_names_in_raw_text` (AC6, T7): over the raw text of every file under `deploy/`, no IPv4
    literal in 10/8, 172.16/12, 192.168/16, 100.64/10 or 169.254/16 (any dotted quad fails, to be simple); every
    dotted token matching `[a-z0-9-]+(\.[a-z0-9-]+)+` is on the allowlist `{networking.k8s.io,
    kustomize.config.k8s.io}` or ends in `.yaml`, `.crt` or `.key`. The test holds patterns only, no real names.
  - `test_image_has_no_latest_tag` (T14): image has no `:` tag at all in base.
- [x] Automated verification: same command as Phase 1.
- [ ] Manual verification: `kubectl kustomize deploy/base` (or `kustomize build deploy/base`) renders without error;
  optionally `kubeconform -strict` on the output. Neither tool is needed by CI.
- [x] Threat-model controls implemented: AC4, AC5, AC6, T7, T8, T9, T10, T11, T12, T13, T14. T15 unchanged.
- [x] Docs touched: `docs/deploy.md` "Production" describes `deploy/base` and the list of what the overlay must add
  (image tag and digest, `LLM_BASE_URL`, `LLM_MODEL`, `TRUSTED_PROXIES`, the `brevkoll-llm` Secret via an
  ExternalSecret, the Ingress with the host name, the NetworkPolicy `to:` and `from:` peers, the namespace).
  `README.md` gets a "Deploy" line pointing at `deploy/base` and `docs/deploy.md`. `AGENTS.md` tests line lists
  `tests/deploy` (and the existing `tests/tooling`), and "What this repo is" names `deploy/base`.

## Docs (the app's own, not the factory's)
`README.md` and `AGENTS.md` already describe the app; neither has template text or the Gate 1 placeholder, so no
replacement phase is needed.
- Phase 1: `README.md` configuration table, three TLS rows. `docs/deploy.md` model table, same rows.
- Phase 2: `docs/deploy.md` mTLS section replaces "Not supported yet". `AGENTS.md` stack line (dev deps).
- Phase 3: `docs/deploy.md` "Production" and the overlay checklist. `README.md` deploy pointer. `AGENTS.md` "What this
  repo is" (one clause on `deploy/base`) and the tests command line.
- Every doc under `deploy/` and `docs/deploy.md` stays free of host names, addresses and secrets (it is mirrored).

## Architecture contracts
Proposed for `.importlinter` (the human commits it; the code passes with or without these).

Place the new module in the layers, next to the other leaf helpers it may use:
```ini
[importlinter:contract:layers]
# ... unchanged layers, except the bottom two lines become:
    app.redact | app.tls
    app.errors | app.config
```
Prevents `app.tls` from importing the pipeline or the web layer; it needs only `app.config`.

Add `app.tls` to `source_modules` of `[importlinter:contract:pipeline-without-web]` (it must not import fastapi,
starlette or jinja2).

One new contract:
```ini
[importlinter:contract:tls-context]
name = Only app.tls builds TLS contexts
# Prevents a second place from creating an ssl context with weaker settings (CERT_NONE, system store next to the
# pinned CA, no hostname check). app.llm passes the context from app.tls to httpx and does not touch ssl itself.
type = forbidden
source_modules =
    app
forbidden_modules =
    ssl
allow_indirect_imports = True
ignore_imports =
    app.tls -> ssl
```

## Decisions (ADRs)
Written with this plan, status `proposed`; the human flips them to `accepted`.
- `docs/decisions/0003-model-mtls-with-pinned-ca.md` (Phase 1, 2): `ssl.SSLContext` in `app.tls`, CA pinned without the
  system store, `https` required with TLS, cert loaded once at startup and fail-fast, test certificates from `trustme`.
- `docs/decisions/0004-host-free-deploy-base.md` (Phase 3): public base without hosts, peers, namespace or image tag;
  NetworkPolicy without peers; `Recreate` with one replica; secrets by reference, TLS as a `0440` volume.
- `docs/decisions/0005-manifest-tests-outside-the-src-gate.md` (Phase 3): manifest tests in `tests/deploy/`, why the
  fail-before-patch gate cannot measure them, `pyyaml` as an explicit dev dependency.

## Dependencies added (Python and system)
- `trustme` (dev group only). Generates a throwaway CA, server and client certificates in memory for the handshake
  tests (AC1, AC3, T2, T3). Alternatives rejected: committed PEM keys (trip gitleaks and need a CI allowlist I may not
  edit), the `openssl` CLI (unknown in CI, slower, shell-out). Pulls in `cryptography` (dev only).
- `pyyaml` (dev group only), already in `uv.lock` 6.0.3 as a transitive dependency of `uvicorn[standard]`. Named
  explicitly so the manifest tests do not depend on a transitive pin.
- No runtime dependency (`ssl` is stdlib). No apt package.

## What I am unsure about
- **Holdout tests.** I cannot read them. AC1 says the client "presents that client certificate and trusts only that
  CA"; if the holdout inspects httpx internals (for example the pool's SSL context) rather than doing a handshake, the
  exact place the context lives matters. I keep `OpenAICompatLLM`'s constructor and `_build_llm(settings)` unchanged
  and pass the context through `httpx.Client(verify=ctx)`, which is the documented httpx 0.28 way.
- **Where `securityContext` fields sit.** AC4 does not say pod or container level. I set `runAsNonRoot`, uid, gid and
  seccomp at both levels and the container-only fields on the container, so either reading passes. `fsGroup` is
  pod-only.
- **Cert and key without a CA** fall back to `ssl.create_default_context()` (the OS store), not httpx's certifi
  bundle, so the trust set differs slightly from today's default. `deploy/base` always sets the CA, so this only
  matters for local use.
- **`trustme` client certificates** must carry the clientAuth extended key usage for a strict server. I believe
  `trustme` issues certificates with both serverAuth and clientAuth; Phase 2's first test proves it either way.
- **TLS 1.3 client-cert rejection** shows up after the handshake, as a read error, not a connect error. Both are
  `httpx.HTTPError`, so they still map to 502; the integration test covers it.
- **The `ssl` import contract.** `ssl` is stdlib; I am not sure import-linter 2.1 with `include_external_packages`
  can forbid a stdlib module. If it cannot, drop that contract; the T2 unit test still pins the context's settings.
- **`tests/deploy/` and the gate** (ADR 0005). It is honest about what the gate measures, but it is a new test folder
  that the gate does not scan. The human may prefer another arrangement.
- **Trace collisions.** `scripts/trace.py` matches `AC1`..`AC6` by bare name, so #1's holdout tests already satisfy
  them. I still mark every #19 test with its AC and T IDs.
- **`main.py` size.** Removing `import httpx` and replacing the client line keeps it at 93 non-blank lines. Any further
  change to `main.py` in this issue would hit the ratchet.
- **Resource numbers** (T11) are guesses until first real use.

## Notes from implementation

### Phase 1
- `src/app/config.py`: `TLS_VARS`, three `Path | None` fields, `_readable_file`, `_check_tls`; 90 non-blank lines
  (the cap). `_check_tls` runs first in `load_settings`, so the pair rule wins over a path error.
- `tests/unit/test_tls_settings.py`: the listed tests, plus `test_tls_paths_default_to_none`,
  `test_http_base_url_refused_with_ca_alone` (T1 with only the CA) and `test_empty_tls_var_counts_as_unset`. Confirmed
  failing before the change (import error on `TLS_VARS`).
- Deviation (plan text): the manual check sets only `LLM_TLS_CERT_FILE`, so by the plan's own ordering it reports
  `LLM_TLS_CERT_FILE and LLM_TLS_KEY_FILE must be set together`, not "must name a readable file". To see the path
  message, set both cert and key to nonexistent paths. Covered by `test_missing_path_names_the_variable`.
- Not run in the agent session (permission denied): the `fastapi dev` manual check and `bash scripts/quality.sh
  origin/main` (the dispatcher runs it before pushing). ruff, ruff format, pyright and pytest pass (222 passed, 1 skipped).
- `uv run ruff format --check .` failed on a Python block in this plan (`load_settings` signature line too long);
  `ruff format thoughts/19/plan.md` rewrapped it. Layout only, no content change.

### Phase 2
- `src/app/tls.py`: `model_ssl_context` and `_load_client_cert` as specified. `src/app/llm.py`: `model_http_client`,
  which calls `model_ssl_context` by its module-level name, so the test can wrap it. `src/app/main.py`: `import httpx`
  gone, `_build_llm` uses `model_http_client(settings)`. Now 93 non-blank lines (was 94).
- Dev dependencies added with `uv add --dev trustme pyyaml` (trustme 1.2.1, pulls cryptography 50.0.2, cffi, pycparser).
- Tests: `tests/unit/test_model_tls.py` (6 tests) and `tests/integration/test_mtls_handshake.py` (5 tests), as listed.
  Before the change the unit file failed to import (`app.tls` missing) and two integration tests failed
  (`test_call_succeeds_with_client_certificate`, `test_decode_through_the_app_over_mtls`, both 502). The other three
  integration tests are guards that pass without the change, as the plan says. trustme certificates are accepted by a
  `CERT_REQUIRED` server, so the clientAuth EKU worry in "What I am unsure about" is settled.
- The integration file has its own tiny fake OCR instead of importing `tests/unit/helpers.py`, so it does not depend
  on `tests/unit` being on `sys.path`.
- Gap, not improvised: a garbage `LLM_TLS_CA_FILE` makes `ssl.create_default_context(cafile=...)` raise `ssl.SSLError`
  at startup, not `ConfigError`. The app still stops at startup (fail fast), and the OpenSSL message carries no path
  or content, but it is a traceback rather than a named variable. The plan and T3 cover only the cert/key load. A
  follow-up could wrap the CA load the same way.
- Not run in the agent session (permission denied): `lint-imports` (as `env PYTHONPATH=src uv run lint-imports`, which
  is how `scripts/quality.sh` runs it), `bash scripts/quality.sh origin/main` and the manual check, which is for the
  human at the owner session. ruff, ruff format, pyright and pytest pass (233 passed, 1 skipped).
- The proposed `.importlinter` changes (layers, `tls-context`) are not applied; that file is human-owned. The
  existing `http-client` contract still lists `app.main -> httpx`, which is now unused and can be dropped.

### Phase 3
- `deploy/base/{kustomization,deployment,service,networkpolicy}.yaml` as in the data model. `tests/deploy/test_deploy_base.py`
  (12 tests, all listed ones); no `__init__.py` (the other test folders have none). `pyproject.toml` `testpaths` gains
  `tests/deploy`. Before the manifests existed all 12 failed (`deploy/base has no manifests`).
- Deviation (test form, not intent): `test_tmp_and_data_are_memory_emptydirs_with_limits` does not spell the `/tmp`
  path, because ruff S108 flags that string as insecure temp-file use. Instead of a `noqa` or a config ignore, it
  checks that the writable (not `readOnly`) mounts are exactly two root-level directories named `tmp` and `data`,
  that `/data` equals `APP_DATA_DIR`, and that each is a `Memory` `emptyDir` with a `sizeLimit`.
- `test_image_has_no_latest_tag` also refuses an `@` digest in base (the overlay sets tag and digest).
- The T7 raw-text scan caught my own comment pointing at `docs/deploy.md` in `kustomization.yaml` (`deploy.md` is a
  dotted token not on the allowlist). The comment now says "the deploy doc"; the allowlist is unchanged.
- Manual verification not done: `kubectl` and `kustomize` are not installed in the agent VM. Box left unticked for
  the human.
- Checks run: ruff, ruff format, pyright, pytest (245 passed, 1 skipped), `scripts/health.py` + `scripts/ratchet.py
  check` (OK). Not run (permission denied): `bash scripts/quality.sh`, `lint-imports`, `check-context.sh`
  (AGENTS.md is 59 lines, limit 150).
- **Traceability guard fails, and not because of this phase:** `scripts/trace.py` reports `no test for 19/T6` and
  `no test for 19/T15`. Both rows are ACCEPTED with "existing #1 tests, no new test", but `trace.py` needs a test that
  names the ID, and no test does (IDs match by name across issues). The plan does not cover this, so it is not fixed
  here. Options for the human: mark the threat-model rows so they do not need a test, or allow a phase that adds
  `@pytest.mark.control("T6")` / `("T15")` to the existing #1 tests the rows point at (for example `test_llm_output.py`
  and `test_health.py`).
