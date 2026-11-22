# 0005. Manifest tests live in tests/deploy, outside the fail-before-patch gate

Status: proposed
Issue: #19   Date: 2026-11-21

## Context
Every new behaviour needs a test that fails without the change. `scripts/check-tests-fail-before-patch.sh` checks that
for `tests/unit` and `tests/integration` by resetting only `src/` to the base. Tests that read `deploy/base/*.yaml`
do not depend on `src/`, so under that gate they keep passing (the manifests are not reset) and the gate reports them
as useless, although they do fail without the change because `deploy/base` does not exist on the base. The gate is
human-owned. The tests also need a YAML parser; PyYAML is in the lock file only as a transitive dependency.

## Decision
Tests over `deploy/` go in `tests/deploy/`, which `pyproject.toml` adds to pytest's `testpaths`, so `uv run pytest`
and CI run them and `scripts/trace.py` sees their AC and T markers. `pyyaml` is a named dev dependency.

## Consequences
The gate does not measure these tests; reviewers check by hand that each one fails on a tree without `deploy/base`.
Do not put tests of `src/` behaviour in `tests/deploy/`. If the gate later learns to reset `deploy/` as well, move the
tests to `tests/unit` and supersede this decision.
