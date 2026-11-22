# Validation: #19

Branch `agent/issue-19` compared with `thoughts/19/plan.md` (approved), `thoughts/19/threat-model.md` and
`thoughts/19/spec.md`. Diff taken against the merge base (`git diff main...HEAD`). `main` has moved on since the branch
point (#15 theme switch merged); those UI changes are not part of this branch.

**Re-run 2026-11-22.** The only commit since the first validation (`32e7285`) changes `thoughts/19/issue.md`: it
adds the owner's rework request (see "Owner rework request" below). No code, test, manifest or doc changed, so every
finding below still holds. I re-ran the checks and re-verified the weakened-check scan, the env var table and the
`.importlinter` line.

## Owner rework request (not addressed)

The issue snapshot adds the owner's rework request: the staging link "to test it from my phone" does not work, and
the phone is on the tailnet. **No phase in the plan covers this, and no commit after the request changes code.**
The branch does not address it.

What I can tell from the repo, without running anything:

- Per `docs/deploy.md` "Staging (by the factory)", the staging link comes from the factory's sandbox on the owner's
  machine, not from brevkoll code. The image listens on `0.0.0.0:8000` (`Dockerfile`). Nothing in the app filters
  by Host header (no `TrustedHostMiddleware`, no `allowed_hosts`). So I see no cause for an unreachable link in this
  branch's app code.
- One cause the branch *could* produce (not verified, because I cannot see the staging configuration): if the staging
  sandbox sets any `LLM_TLS_*` variable (the last `/go` says `model=local`, which may mean the local model through its
  mTLS front end) while it keeps an `http://` `LLM_BASE_URL`, or points a `LLM_TLS_*` variable at a path that does not
  exist in the sandbox, then `load_settings` now raises `ConfigError` at import. uvicorn exits and the link is dead.
  That is the intended T1/T3 fail-fast behaviour, so the fix would be in the staging env, not in a looser check.
  Look at the sandbox container's log first.
- If the cause is reachability from the tailnet (port binding, firewall, the URL host the factory posts), the fix is
  in the factory, outside this repo.

Needs a decision: either the request is triaged as a factory/staging issue, or an amended plan adds a phase for it.
I did not improvise a fix (report only).

## Checks run

| Check | Result |
|---|---|
| `uv run ruff check .` | pass |
| `uv run ruff format --check .` | pass (95 files) |
| `uv run pyright` | 0 errors, 0 warnings |
| `uv run pytest` | 245 passed, 1 skipped, 1 warning |
| `bash scripts/quality.sh origin/main` | **not run**: permission denied in this session (also not run in any implement session) |
| `uv run lint-imports` | **not run**: outside this command's allowed tools |
| `kubectl kustomize deploy/base` | **not run**: tool not installed in the agent VM |

So the ratchet, changed-line coverage, import contracts, traceability and context-size guards have **never** been run
on this branch by an agent. The dispatcher runs them before pushing; see "Needs human attention" for the two that I
expect to fail.

## Phases complete

| Phase | Status |
|---|---|
| 1: TLS settings validated at startup | Complete. All boxes ticked. Code matches the signatures (`TLS_VARS`, three `Path \| None` fields, `_readable_file`, `_check_tls`, called first in `load_settings`). |
| 2: mTLS model client | Complete. `app.tls.model_ssl_context` / `_load_client_cert`, `app.llm.model_http_client`, `_build_llm` uses it, `import httpx` removed from `main.py`. Unit (6) and integration (5) tests present. |
| 3: hardened, host-free `deploy/base` | Complete except the manual box (`kubectl kustomize`), left unticked on purpose. Manifests match the data model field by field (replicas, `Recreate`, pod and container `securityContext`, probes, resources, env, three volumes, `defaultMode: 288`, Service, NetworkPolicy without peers). 12 tests in `tests/deploy/`. |

## Deviations from the plan

All are recorded in the plan's "Notes from implementation"; none changes intent.

1. Phase 1 manual check text: setting only `LLM_TLS_CERT_FILE` reports the pair rule, not "must name a readable file"
   (the plan's own ordering). Correct behaviour; plan text was wrong.
2. Phase 1 adds three extra tests (`test_tls_paths_default_to_none`, `test_http_base_url_refused_with_ca_alone`,
   `test_empty_tls_var_counts_as_unset`). Additive.
3. Phase 2 integration test uses its own fake OCR instead of `tests/unit/helpers.py`. Harmless.
4. Phase 3 `test_tmp_and_data_are_memory_emptydirs_with_limits` does not spell `/tmp` (ruff S108); it checks the two
   writable root-level mounts are `tmp` and `data` instead. Equivalent strength; no `noqa` added.
5. Phase 3 `test_image_has_no_latest_tag` is stricter than planned (also refuses an `@` digest).
6. A `kustomization.yaml` comment was reworded to pass the T7 scan; the allowlist is unchanged.
7. Dependency pins: `trustme>=1.2.1` and `pyyaml>=6.0.3` use `>=`, while every other dev dependency in
   `pyproject.toml` is pinned with `==`. `uv.lock` pins them anyway, but it breaks the file's convention.
8. `ruff format` was run on `thoughts/19/plan.md` (rewrapped one code block). Layout only.

No production code was added beyond what the plan names. No new runtime dependency.

## Threat-model controls without an enforcing test

Controls with a `@pytest.mark.control` test on this branch: T1, T2, T3, T4, T5, T7, T8, T9, T10, T11, T12, T13, T14.

- **T6** and **T15**: no test names them. The threat model says "existing #1 tests, no new test", but
  `scripts/trace.py` requires a test carrying the ID, so the traceability guard fails (`no test for 19/T6`,
  `no test for 19/T15`, reported in the Phase 3 notes). Not fixed, correctly: the plan does not cover it.
- **T3, CA half (gap)**: a garbage `LLM_TLS_CA_FILE` makes `ssl.create_default_context(cafile=...)` raise `ssl.SSLError`
  at startup, not a `ConfigError` naming the variable. The app still fails fast and the OpenSSL message holds no path or
  content, but it is a traceback. Neither the plan nor T3 asks for it; no test covers it.
- **T5, budget half (partial)**: the threat model's enforcing test says the mTLS client is wrapped in `BudgetedLLM`.
  `test_build_llm_with_tls_returns_openai_compat_client` proves `create_app` builds the client through
  `model_ssl_context`, but does not assert the `BudgetedLLM` wrapper. `create_app` is unchanged, so the risk is low.
- **T7, single-label names (limitation)**: the raw-text scan catches dotted names and dotted quads only. A bare
  single-label host name (for example a short cluster service name) or an IPv6 literal would not be caught. Matches the
  plan; worth knowing.

## Weakened checks

None found. In `src/`, the new tests and `pyproject.toml`: no `# type: ignore`, no `cast(`, no bare `except` or
`except Exception`, no `noqa`, no `skip`/`xfail`/`importorskip`, no `pragma: no cover`. The only `except` added is
`except (ssl.SSLError, OSError)` in `app/tls.py`, which re-raises `ConfigError ... from None`. No existing test was
deleted or loosened. `testpaths` only gained `tests/deploy`. No change under `.gitea/`, `quality/`, `.importlinter`
or `.claude/`. `tests/holdout/` files on the branch come from the orchestrator's gate-1 commit, not from an agent.

## Docs

- **README.md**: describes this app, no template text or placeholder. Every env var read in `src/app/config.py` is in
  the configuration table with the right default (`LLM_PROVIDER=fake`, `APP_ENV=dev`, `APP_DATA_DIR=data`,
  `RATE_LIMIT_PER_MINUTE=10`, `DAILY_MODEL_CALL_BUDGET=200`, `OCR_CONCURRENCY=2`, `MODEL_TIMEOUT_S=30`,
  `MODEL_MAX_TOKENS=600`, `TRUSTED_PROXIES` empty, the three `LLM_TLS_*` none, the rest none). Run command
  `uv run fastapi dev src/app/main.py` matches AGENTS.md. New "Deploy" pointer to `deploy/base` and `docs/deploy.md`.
  Minor: "How it was built" still points only at `thoughts/1/`.
- **AGENTS.md**: "What this repo is" is a real paragraph and now names `deploy/base`. Stack line is right and lists the
  dev-only `trustme` and `pyyaml`. Tests line now lists `tests/unit`, `tests/integration`, `tests/tooling`,
  `tests/deploy`, matching `testpaths`.
- **docs/deploy.md**: mTLS section replaces "Not supported yet"; Production section describes `deploy/base` and the
  overlay checklist. No host names, addresses or secrets (it is also outside the T7 scan, which covers `deploy/` only).

## Needs human attention

0. **Owner rework request (phone link on the tailnet)** is not addressed by any phase or commit. See the section near
   the top. Triage it as a staging/factory issue, or amend the plan.
1. **Traceability guard will fail** on T6 and T15 (see above). Decide: mark those rows so `trace.py` does not require a
   test, or approve a small phase that adds `@pytest.mark.control("T6")` / `("T15")` to the existing #1 tests.
2. **Import contracts, likely failure.** `.importlinter`'s `http-client` contract still lists
   `ignore_imports = app.main -> httpx`, and `main.py` no longer imports httpx. import-linter 2.1 reports unmatched
   ignored imports, and I believe its default is to treat that as an error, so `lint-imports` may now fail. I could not
   run it. The file is human-owned: drop that line, and consider the plan's proposed `app.tls` layer and `tls-context`
   contract. Without them, `app.tls` is not in any layer, so nothing stops it importing upward.
3. **`kubectl kustomize deploy/base`** (Phase 3 manual box) and optionally `kubeconform -strict` on the output.
4. **Phase 2 manual check** against the real front end with the borrowed identity, including that the name in
   `LLM_BASE_URL` is in the front end certificate's SAN (`check_hostname=True`, threat model Q2).
5. **ADRs 0003 to 0005** are still `proposed`; ADR 0005 (manifest tests in `tests/deploy/`, outside the fail-before-patch
   gate) needs an explicit yes or no.
6. **Garbage CA file** gives a traceback rather than a named `ConfigError` (T3 gap above). Follow-up issue if wanted.
7. **Cert and key without a CA** use the OS trust store, not certifi as before. `deploy/base` always sets the CA, so this
   only affects local use.
8. Resource numbers (T11) are guesses until first real use; tune in the overlay.
