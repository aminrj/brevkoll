---
description: Check the implementation against the plan and threat model. Report only.
allowed-tools: Read, Grep, Glob, Write, Bash(uv run pytest:*), Bash(uv run ruff:*), Bash(uv run pyright:*), Bash(git diff:*), Bash(git log:*)
---
Issue number: $ARGUMENTS

Compare the branch with `thoughts/$ARGUMENTS/plan.md` and `threat-model.md`. Run all checks.
Also read `docs/intent.md` and `docs/architecture.md`. The foreman writes `thoughts/$ARGUMENTS/drift.md` after you (a script
compares the diff with the plan, the criteria with their tests and the diff with the invariants): do not write it, and do
not claim "no deviations" in your report; name the deviations you can see, or say you found none by reading.
Write `thoughts/$ARGUMENTS/validation.md` with:

- phases complete
- does the change keep every invariant in `docs/architecture.md` it touches, and does the picture there still match the code?
- deviations from the plan
- threat-model controls without an enforcing test
- weakened checks (ignores, casts, broad excepts, skipped tests)
- docs: does `README.md` describe this app (no template text, no placeholder), list every env var read in the code with the
  right default, and match the real run command? Does `AGENTS.md` "What this repo is" hold a real paragraph and the right stack?
- `docs/deploy.md`: is it filled in for this app (internal port, `/healthz`, every env var, the paths written to), with no template text?
- anything that needs human attention

Also write `thoughts/$ARGUMENTS/acceptance.md`, the checklist the owner follows on their phone against the staged build
(use `.factory/templates/acceptance.md`). Four to eight items taken from the acceptance criteria in `spec.md` and from what a
person can feel: the wrong-file message, the "model busy" state. No hostnames, URLs, commands or secrets; the factory adds the link.

Do not fix anything else.
