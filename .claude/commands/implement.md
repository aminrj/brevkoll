---
description: Implement exactly one approved phase of the plan, then stop.
---
Issue number: $ARGUMENTS

1. Read `thoughts/$ARGUMENTS/plan.md`. If the header does not say `Status: approved`, stop and say so.
2. Pick the first phase with unchecked boxes. Implement only that phase.
   If reality differs from the plan, stop and explain. Do not improvise.
3. Write the tests listed for the phase first, run them, confirm they fail.
4. Implement until all checks pass: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run pytest`.
5. If the phase adds or changes a command, env var, route, limit or visible behaviour, update `README.md` (and `AGENTS.md` if
   the stack or commands changed) in the same commit. A README line for an env var must match its default in the code.
6. Tick the phase checkboxes in plan.md and add an entry under "Notes from implementation".
7. Commit with message `#$ARGUMENTS phase <k>: <summary>`.
8. Print a short review guide: what changed, what to look at closely, anything you are unsure about. Stop.
