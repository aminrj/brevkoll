#!/usr/bin/env bash
# All quality guards, in the order CI runs them. Usage: scripts/quality.sh [base-ref]
# Local runs and the `quality` CI job use the same commands. Mutation testing is separate
# (scripts/mutation.py) because it is slow and starts in warn mode.
set -euo pipefail
BASE="${1:-origin/main}"
rc=0
step() { echo; echo "== $1"; shift; "$@" || rc=1; }

policy() { python3 -c "import tomllib,sys;d=tomllib.load(open('quality/policy.toml','rb'));print(eval(sys.argv[1]))" "$1"; }

step "health metrics" uv run python scripts/health.py --out health.current.json
step "ratchet vs quality/health.json" uv run python scripts/ratchet.py check
uv run coverage xml -q -o coverage.xml || true
FLOOR="$(policy "d['diff_coverage']['floor_percent']")"
MODE="$(policy "d['diff_coverage']['mode']")"
echo; echo "== coverage on changed lines (floor ${FLOOR}%, mode ${MODE})"
if uv run diff-cover coverage.xml --compare-branch="$BASE" --fail-under="$FLOOR"; then :; else
  [ "$MODE" = enforce ] && rc=1 || echo "warn only"
fi
step "architecture contracts" env PYTHONPATH=src uv run lint-imports
step "traceability" uv run python scripts/trace.py
step "context hygiene" bash scripts/check-context.sh
exit $rc
