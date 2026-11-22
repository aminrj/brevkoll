# Research: #19

Scope: what exists today that the two halves of this issue touch. (a) The model client, which needs
mutual TLS. (b) A `deploy/base` that does not exist yet. Sources: `thoughts/19/spec.md` (approved),
`thoughts/19/threat-model.md` (T1 to T15 marked ACCEPTED), and the code on `agent/issue-19` at
`5d13fde`. `tests/holdout/` and `.gitea/workflows/` were not read (AGENTS.md hard rule).

## What exists

- **Settings.** `app.config.load_settings(env)` builds a frozen Pydantic `Settings` from a mapping
  and raises `ConfigError(ValueError)` with messages that name the variable and never the value.
  There are no TLS fields and no file-existence checks. The only `Path` fields are `app_data_dir`
  and `fake_llm_log`, and neither is checked on disk.
- **Model client.** `app.main._build_llm(settings)` builds one `httpx.Client(follow_redirects=False,
  trust_env=False)` with default verification (the system CA store through httpx's default
  `SSLContext`, certifi-backed) and no client certificate. It passes that client to
  `OpenAICompatLLM`, which posts to `<base>/chat/completions` and maps every `httpx.HTTPError` or
  `ValueError` to `ModelUnavailable` (502) `from None`. Nothing checks the URL scheme:
  `http://` and `https://` are both accepted.
- **Wrapping.** `create_app` always wraps the client in `BudgetedLLM` (daily budget). Rate limiting
  is per IP, in middleware, in memory.
- **Health.** `GET /healthz` returns `{"status": "ok"}`. It does not touch the model.
- **Container.** `Dockerfile` creates uid 10001 (`useradd ... app`, no explicit group id; Debian
  `useradd` normally creates a matching group with the same id when it is free), creates `/data`
  owned by `app`, sets `APP_ENV=prod` and `APP_DATA_DIR=/data`, exposes 8000, and runs uvicorn on
  `0.0.0.0:8000`. No `HEALTHCHECK`. The README `docker run` line already uses `--read-only`,
  tmpfs for `/tmp` and `/data`, `--cap-drop ALL` and `no-new-privileges`.
- **Deploy.** No `deploy/` directory and no Kubernetes YAML anywhere in the repo.
  `docs/deploy.md` describes the container contract (port 8000, `/healthz`, uid 10001, read-only
  root, `/tmp` and `/data` writable, one replica) and says mutual TLS is "Not supported yet" and
  that manifests "will live in `deploy/`".
- **Docs on TLS variables.** `LLM_TLS_CERT_FILE`, `LLM_TLS_KEY_FILE` and `LLM_TLS_CA_FILE` appear
  nowhere outside `thoughts/19/`. The spec's contract says "Same names as `docs/deploy.md` already
  lists for staging", but `docs/deploy.md` and `README.md` do not list them today.
- **Tests that touch this area.** `tests/unit/test_model_settings.py` (timeouts, token cap, API key
  as `SecretStr`, key not in logs or responses), `tests/unit/test_llm_openai_compat.py` (request
  shape, errors become 502, provider selection, `openai_compat` needs URL and model),
  `tests/unit/test_config.py` (defaults, bad ints, fake provider refused in prod),
  `tests/unit/test_health.py`. All model tests use `httpx.MockTransport`. None of them do a
  real TLS handshake. `tests/integration/test_tesseract.py` is the only integration test.

## Relevant code (file:line)

Model client and settings
- `src/app/config.py:9-10` `ConfigError(ValueError)`.
- `src/app/config.py:13-29` `Settings` (frozen). `llm_api_key: SecretStr | None` at `:27`.
- `src/app/config.py:32-61` helpers `_int`, `_bounded_float`, `_bounded_int`. Pattern: the
  message names the key and the range, and uses `from None`.
- `src/app/config.py:64-82` `load_settings`. `llm_base_url` is read raw at `:77` with no scheme
  check.
- `src/app/main.py:36-47` `_build_llm`. `httpx.Client(follow_redirects=False, trust_env=False)` at
  `:44`. API key unwrapped at `:45`.
- `src/app/main.py:50-58` `create_app` reads `os.environ` once and wraps the client in
  `BudgetedLLM`. `:112` module-level `app = create_app()`, so a `ConfigError` happens at import
  time, which means at uvicorn startup.
- `src/app/main.py:105-107` catch-all `Exception` handler returns 500 "Internal error".
- `src/app/llm.py:13-14` `LLMClient` protocol, `complete(prompt, *, max_tokens, timeout)`.
- `src/app/llm.py:29-52` `OpenAICompatLLM`. The error mapping at `:51-52` catches
  `httpx.HTTPError`, which includes `httpx.ConnectError`, which is what a TLS handshake failure
  raises.
- `src/app/limits.py:59-68` `BudgetedLLM`.
- `src/app/errors.py:36-38` `ModelUnavailable` (502, fixed message).
- `src/app/routes.py:42-44` `/healthz`.

Container and docs
- `Dockerfile:16-24` user, `/data`, env, port, CMD.
- `docs/deploy.md:5-11` container contract. `:17-24` model variables and the "mTLS not supported"
  line. `:32-34` production "not deployed".
- `README.md:44-59` config table (no TLS rows). `README.md:32,40` examples use `http://`.

Architecture and quality guards (human-owned)
- `.importlinter:8-20` layers. `app.config` is in the bottom layer, with `app.errors`. Any new
  module under `app` that is not listed in `layers` is not constrained by that contract.
- `.importlinter:46-57` only `app.llm` and `app.main` may import `httpx`. `ssl` (stdlib) is not
  restricted.
- `.importlinter:22-44` `app.config` and `app.llm` must not import fastapi, starlette or jinja2.
- `quality/health.json:7-14` baseline: longest file 94 lines (enforce, tolerance 0), longest
  function 52, max complexity 9, mean 2.44 (tolerance 0.5), test/source ratio 1.42 (tolerance
  0.05), line coverage 99.48 (tolerance 1.0), runtime deps 3 (warn). `src/app/main.py` is 112
  lines today. I did not check whether `scripts/health.py` measures only `src/` or what counts
  as a "file"; that decides whether `main.py` is already the 94-line maximum or above it.
- `quality/policy.toml:65-67` 80% coverage on changed lines (enforce).
- `scripts/trace.py:6-7,53` a threat-model row needs a test when its *last* cell starts with
  `ACCEPTED` or `CHANGED`. All of T1 to T15 in `thoughts/19/threat-model.md` match today.
- `scripts/trace.py:84,107` IDs are matched by bare name across issues (`AC1` in #19 is
  satisfied by any test tagged `AC1`, including #1's holdout tests). `thoughts/1/threat-model.md`
  uses `LLM01`-style first cells, not `T<n>`, and `thoughts/15/threat-model.md` has no `T<n>`
  rows, so #19's T1 to T15 are the first `T<n>` controls in the repo. No test in
  `tests/unit`, `tests/integration` or `tests/tooling` carries a `T<n>` marker or comment today
  (only fixture strings in `tests/tooling/test_quality_scripts.py`).
- `scripts/check-tests-fail-before-patch.sh:7-30` changed tests in `tests/unit` and
  `tests/integration` must fail when only `src/` is reset to the base. Files outside `src/`
  (such as `deploy/base/*.yaml`) are **not** reset.
- `scripts/check-holdout-guard.sh:7` guarded paths: `tests/holdout/`, `.gitea/workflows/`,
  `.claude/settings.json`, `quality/`, `.importlinter`. `deploy/` is not guarded.
- `pyproject.toml:25` `testpaths` includes `tests/tooling` (AGENTS.md says unit and integration
  only).
- `pyproject.toml:43-46` pyright checks `src` only.

Dependencies (`uv.lock`)
- `httpx 0.28.1` (`uv.lock:777-778`), `pydantic 2.14.4`.
- `pyyaml 6.0.3` (`uv.lock:1495`) is present only as a dependency of `uvicorn[standard]`
  (`uv.lock:1849`), pulled in by `fastapi[standard]`. It is not a direct dependency.
- No `cryptography` and no `trustme` in the lock. Nothing in the dependency set can generate an
  X.509 certificate at test time.

## Where untrusted input enters

Existing paths that do not change with this issue (all from #1):
1. Uploaded file bytes at `POST /api/decode` and `POST /ui/decode` (`src/app/routes.py`,
   `src/app/upload.py`), then parsed by Pillow and poppler and read by Tesseract (`src/app/ocr.py`).
2. The `language` form field.
3. `X-Forwarded-For` (`src/app/main.py:79`, `src/app/limits.py:71-80`), trusted only from
   `TRUSTED_PROXIES`.
4. OCR text, which is letter content. It is redacted, then wrapped as data in the prompt
   (`src/app/redact.py`, `src/app/prompt.py`).
5. The model response: the HTTP envelope (`src/app/llm.py:55-62`) and the JSON body
   (`src/app/llm.py:74-78`, `ModelOutput` with `extra="forbid"`).

New or changed with this issue:
6. **Environment variables** `LLM_TLS_CERT_FILE`, `LLM_TLS_KEY_FILE`, `LLM_TLS_CA_FILE` (and the
   existing `LLM_BASE_URL`, `LLM_API_KEY`). The operator sets them, so their origin is trusted,
   but they enter at `src/app/config.py:64` and can be wrong.
7. **Mounted file contents** (PEM certificate, key and CA) read at startup by whatever loads
   them. Today nothing reads them.
8. **The TLS handshake from the model front end**: the server certificate chain and the
   negotiated parameters, at `src/app/main.py:44` / `src/app/llm.py:48`. Today they are verified
   against the system store, not a pinned CA.
9. **The public mirror direction (outbound):** everything committed under `deploy/` leaves the
   private repo. It is not an input to the app, but it is a trust boundary the tests must guard
   (T7).

## Constraints found (CI, system packages, data, deployment)

- **CI definition not read.** `.gitea/workflows/` is off-limits. From `tests/tooling/test_workflow.py:6,38`
  the file is `gates.yml` with required jobs `checks`, `gates`, `security`, `holdout`,
  `quality`. Commit `24035ac` says "OCR in CI". I cannot see whether CI has the `openssl`
  binary, network access for a local TLS server, or which Python packages the holdout job
  installs.
- **Holdout tests for AC4 to AC6 exist but I have not read them.** Whatever YAML parser and file
  layout they assume is a contract I cannot see. The spec fixes `deploy/base/kustomization.yaml`,
  the Secret name `brevkoll-llm` and the keys `api-key`, `tls.crt`, `tls.key`, `ca.crt`.
- **"Tests must fail before the patch" vs deploy tests.** Unit tests that only read
  `deploy/base/*.yaml` would still pass when the gate resets `src/` to base, because `deploy/`
  is not reset (`scripts/check-tests-fail-before-patch.sh:23`). The gate would then report
  "Changed tests pass against the base code".
- **No certificate tooling in the dependency set.** A real-handshake test (AC3, T2's
  "different CA" case, T3's mismatched key) needs certificates from one of: the `openssl` CLI at
  test time, PEM fixtures committed to the repo, or a new dev dependency. Committed private keys
  will likely trip the `security` job's secret scanning (`test_model_settings.py:15` notes that
  gitleaks scans history).
- **httpx 0.28.1 API.** In 0.28, the `cert=` argument and string or path values for `verify=` are
  deprecated in favour of passing an `ssl.SSLContext` as `verify=`. The spec sketch
  (`httpx.Client(cert=(cert, key), verify=ca)`) uses the deprecated forms. T2 describes the
  `SSLContext` form. `pyproject.toml` has no `filterwarnings`, so deprecation warnings do not
  fail tests today.
- **`trust_env=False` is already set** (`src/app/main.py:44`), so `SSL_CERT_FILE`, `SSL_CERT_DIR`
  and proxy variables are ignored by httpx today.
- **Startup failure mode.** `create_app()` runs at import (`src/app/main.py:112`). A
  `ConfigError` makes uvicorn exit, and in Kubernetes the pod then goes into CrashLoopBackOff.
  It does not just fail its readiness probe, which is what T3's text says.
- **Container user and group.** The image fixes uid 10001 but does not pin a gid. The threat model
  (T8, T9) assumes `runAsGroup: 10001` and `fsGroup: 10001`. `/data` is owned by `app:app` in the
  image, but the manifests replace it with an `emptyDir`.
- **Read-only root filesystem.** The app writes only to `/tmp` (Python `tempfile`, Tesseract and
  poppler temp files) and `APP_DATA_DIR`. uvicorn and Python need no other writable path that I
  found. `PYTHONDONTWRITEBYTECODE` is not set, so Python tries to write `.pyc` files and fails
  silently on a read-only `/app`.
- **Size ratchet.** `src/app/main.py` is 112 lines and `src/app/config.py` 83. The longest-file
  baseline is 94 with tolerance 0, so growth in the largest measured file fails `quality`
  (see the caveat above on what `health.py` measures).
- **Public mirror.** `docs/deploy.md:3` already applies the no-hostnames rule to docs. The spec
  extends it to `deploy/`. The repo has no existing scanner for addresses or host names.
- **Dependencies.** AGENTS.md: add a dependency only if the approved plan names it. Runtime deps
  are at 3 (warn-only ratchet).

## Open questions for the human

1. **Spec vs docs.** The spec says the TLS names are ones "`docs/deploy.md` already lists for
   staging", but no doc lists them. Is that sentence wrong, or is there a doc change (perhaps in
   the factory repo) I cannot see? Should this issue add them to `docs/deploy.md` and the README
   table?
2. **Test certificates.** How should tests get certificates for a real handshake (AC3, T2, T3):
   the `openssl` CLI in CI, committed throwaway PEM fixtures (and a gitleaks allowlist, which
   touches CI config I may not edit), or a dev dependency such as `trustme` or `cryptography`
   that the plan would name? What do the holdout tests for AC3 use? The implementation must not
   contradict them.
3. **YAML parser for deploy tests** (same as threat-model Q3): make `pyyaml` an explicit dev
   dependency, or rely on the transitive copy?
4. **Fail-before-patch gate vs deploy tests.** Unit tests over `deploy/base` pass even when `src/`
   is reset, so the gate would flag them. Is that acceptable for this issue (manifest-only tests),
   should they live outside `tests/unit` and `tests/integration` (e.g. `tests/tooling`, which the
   gate does not scan), or should the gate be adjusted by a human?
5. **Trace collisions.** `scripts/trace.py` matches IDs across issues by bare name, so #19's
   AC1 to AC6 count as covered by #1's holdout tests whatever #19 adds. Is that known and accepted,
   or should #19's tests use a qualified form (which `trace.py` does not support today)?
6. **Group id.** The Dockerfile does not pin gid 10001. Should the plan change the Dockerfile to
   create the group explicitly, or should the manifests rely on `runAsGroup` alone?
7. **Startup failure on bad TLS config** is a crash loop, not a pod that stays unready. Is
   fail-fast at import what you want (it matches today's `ConfigError` behaviour), or should
   T3's wording be corrected?
8. **Size ratchet.** Adding TLS settings and context building to `config.py` and `main.py` grows
   files that are already near or above the 94-line baseline. Is a new module (for example a
   small TLS helper) acceptable? It would need a place in `.importlinter`'s layers, which is
   human-owned.
9. **httpx form.** Is the `SSLContext` form in T2 the intended one over the spec sketch's
   deprecated `cert=`/`verify=path` form? (I read T2 as overriding the sketch.)
