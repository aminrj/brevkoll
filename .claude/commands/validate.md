---
description: Check the implementation against the plan and threat model. Report only.
allowed-tools: Read, Grep, Glob, Write, Bash(uv run pytest:*), Bash(uv run ruff:*), Bash(uv run pyright:*), Bash(git diff:*), Bash(git log:*)
---
Issue number: $ARGUMENTS

Compare the branch with `thoughts/$ARGUMENTS/plan.md` and `threat-model.md`. Run all checks.
Write `thoughts/$ARGUMENTS/validation.md` with:

- phases complete
- deviations from the plan
- threat-model controls without an enforcing test
- weakened checks (ignores, casts, broad excepts, skipped tests)
- docs: does `README.md` describe this app (no template text, no placeholder), list every env var read in the code with the
  right default, and match the real run command? Does `AGENTS.md` "What this repo is" hold a real paragraph and the right stack?
- anything that needs human attention

Do not fix anything.
