# Validation: #1 brevkoll v1

Result: no blocking defects found. Nothing was fixed (report only).

## Checks run

- `ruff check .`: passed.
- `ruff format --check .`: passed (56 files).
- `pyright`: 0 errors, 0 warnings.
- `pytest`: 155 passed, 1 skipped. The skip is `tests/integration/test_tesseract.py`, which skips when the `tesseract` binary is absent. CI must show it running.
- `tests/holdout/` was not read or run. I also could not run `git diff` against it (the command was denied), so I did not confirm it is unmodified. The Phase 1 notes say it was reformatted by accident. Please confirm with `git diff main -- tests/holdout`.

## Phases complete

Phases 1 to 6 are implemented and their code, test and automated-check boxes are ticked. The `Manual verification` box is unticked in every phase (1 to 6). None of those manual checks were run: no live curl, no real Tesseract, no local model server, no phone, no docker build (docker build is excluded by owner decision).

## Deviations from the plan

- Body size (LLM10): a middleware rejects an oversize `Content-Length`. A chunked upload without `Content-Length` is fully parsed by Starlette before `read_limited` rejects it. This only partly meets "stream with a byte counter".
- Rate-limit key table is not hard-capped. Under many distinct IPs within one minute it can grow.
- `DTSTAMP` is midnight of the injected date, not the current time.
- The OCR semaphore is per `TesseractOcr` instance, not module level.
- The rate limiter lives in middleware rather than a dependency, for the reason in the plan notes.
- PDF page boxes are not size-capped: only the page count and timeout limit pdftoppm output.
- Each of these deviations is recorded in the plan's implementation notes.

## Threat-model controls without an enforcing test

- Config: fake provider. The control says the fake log path must be outside `APP_DATA_DIR`. `config.py` only reads `FAKE_LLM_LOG` and does not check the path. No test covers it. The prod refusal itself is tested (`test_fake_provider_refused_in_prod`).
- LLM10: a chunked upload with no `Content-Length` is not enforced early (see above). The tests cover only the post-parse 413 and the declared-length case.
- The threat model says the fake guard allows only `test`/`dev`. The plan's A2 changed it to refuse only `prod`. The owner accepted this (Q2), so this is a recorded change, not a gap.
- Controls that depend on real subprocess or real model behavior (Tesseract and poppler parsing, the model endpoint) are tested only with injected fakes. The real Tesseract test is skipped here.
- All other table rows have a matching unit test (redaction, prompt block, schema validation, ICS escaping, dates from code, language allowlist, no cookie/CORS, route allowlist, SSRF, rate limit and spoofed XFF, budget, storage cleanup, logging, UI escaping, model client has no tool parameter).

## Weakened checks

- No `type: ignore`, `cast()`, bare `except`, `except Exception: pass` or `noqa` in `src` or `tests/unit` or `tests/integration` (searched with grep).
- The only skip is the conditional `skipif` on the missing tesseract binary, with a reason.
- Ruff config is unchanged from the owner-approved set (S, BLE enabled; only S101 ignored for tests).
- No assertion loosening was visible, but I did not diff test history against earlier commits.

## Needs human attention

1. Run `git diff main -- tests/holdout` and confirm the holdout file is untouched (Phase 1 note).
2. Check that CI runs the Tesseract integration test and the holdout suite. AC2 depends on how Tesseract reads the fixture, which I could not check.
3. Run the manual checks in all six phases (curl, real OCR, local model, phone, `.ics` import via `data:` link, `docker run --read-only`).
4. Decide on the two gaps: validate `FAKE_LLM_LOG` against `APP_DATA_DIR`, and bound chunked uploads.
5. Operational limits: one worker only (R5, in-memory limits). `APP_ENV=prod` is set only in the Dockerfile, so other deployments default to `dev` and would allow the fake provider.
6. Year-less dates resolve to the next occurrence (A4) and may pick the wrong year for letters read in January.
