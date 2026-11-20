#!/usr/bin/env bash
# Tripwire: guarded paths may only change in commits made by a human.
# Agent commits are recognised by the factory-agent identity or a Claude co-author trailer.
# Defense in depth with local deny rules and human review. Not a hard boundary.
set -euo pipefail
BASE="${1:-origin/main}"
GUARDED='^(tests/holdout/|\.gitea/workflows/|\.claude/settings\.json)'
fail=0
for c in $(git rev-list "$BASE"..HEAD); do
  if git diff-tree --no-commit-id --name-only -r "$c" | grep -qE "$GUARDED"; then
    author="$(git log -1 --format='%an <%ae>' "$c")"
    body="$(git log -1 --format=%B "$c")"
    if echo "$author" | grep -qi 'factory-agent\|claude' || echo "$body" | grep -qi 'co-authored-by: claude'; then
      echo "::error::Commit $c by $author touches guarded paths."
      fail=1
    fi
  fi
done
[ $fail -eq 0 ] && echo "OK: guarded paths untouched by agents."
exit $fail
