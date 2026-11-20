# Plan: #<n>
Status: draft

## Phase 1: <slice name>
- [ ] Files:
- [ ] Types and signatures:
- [ ] Tests to add (and why each fails today):
- [ ] Automated verification: `uv run ruff check . && uv run pyright && uv run pytest`
- [ ] Manual verification:
- [ ] Threat-model controls implemented:
- [ ] Docs touched (README.md, AGENTS.md; write `none` only if this phase changes no command, env var, route, limit or behaviour a user or operator sees):

## Phase 2: ...

## Docs (the app's own, not the factory's)
`README.md` says what the app is, who it is for, how to run it, every env var with its default, the limits, and what is not done yet.
`AGENTS.md` "What this repo is" has the one paragraph, and its stack and commands match reality. List here which phase writes which part.

## Architecture contracts
Proposed import rules specific to this app (the skeleton's `.importlinter` already has: layers routes -> services -> adapters,
only `app.adapters.llm` imports a model client, nothing imports `tests`). Write each as a contract in `.importlinter` syntax,
with one line on what mistake it prevents. Do not edit `.importlinter`: the human commits it after approving the plan.
```ini
[importlinter:contract:<name>]
```

## Decisions (ADRs)
One file per significant decision in `docs/decisions/NNNN-title.md`, from `docs/decisions/0000-template.md`
(new dependency, data model, trust boundary, anything a reader in 14 days would ask "why?" about). List them here.

## Dependencies added (Python and system)
## What I am unsure about
## Notes from implementation
