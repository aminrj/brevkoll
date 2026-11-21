#!/usr/bin/env bash
# Context hygiene: AGENTS.md is loaded into every agent session; keep it short.
set -euo pipefail
MAX="$(python3 -c "import tomllib;print(tomllib.load(open('quality/policy.toml','rb'))['context']['agents_md_max_lines'])")"
LINES="$(wc -l < AGENTS.md)"
if [ "$LINES" -gt "$MAX" ]; then
  echo "::error::AGENTS.md has $LINES lines, the limit is $MAX. Move detail into docs/ or a command file."
  exit 1
fi
echo "OK: AGENTS.md has $LINES lines (limit $MAX)."
