#!/usr/bin/env bash
# Gate: tests added or changed in this PR must fail against the base code.
# If they pass on the old code, they do not detect the change.
set -euo pipefail
BASE="${1:-origin/main}"

CHANGED_TESTS=$(git diff --name-only --diff-filter=AM "$BASE"...HEAD -- tests/unit tests/integration \
  | grep -E '/test_[^/]+\.py$' || true)
if [ -z "$CHANGED_TESTS" ]; then
  echo "No new or changed tests. Fine for docs or refactors; feat and fix PRs should add one."
  exit 0
fi

if ! git cat-file -e "$BASE:src" 2>/dev/null; then
  echo "No src/ on base. Skipping."
  exit 0
fi

ADDED_SRC=$(git diff --name-only --diff-filter=A "$BASE"...HEAD -- src || true)
restore() { git checkout -q HEAD -- src; }
trap restore EXIT

git checkout -q "$BASE" -- src
if [ -n "$ADDED_SRC" ]; then echo "$ADDED_SRC" | xargs rm -f; fi

# shellcheck disable=SC2086
if uv run pytest -q $CHANGED_TESTS; then
  echo "::error::Changed tests pass against the base code, so they do not detect this change."
  exit 1
fi
echo "OK: changed tests fail against the base code."
