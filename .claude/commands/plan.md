---
description: Turn spec, threat model and research into a phased plan. Stops for human review.
allowed-tools: Read, Grep, Glob, Write
---
Issue number: $ARGUMENTS

Read `docs/intent.md`, `docs/architecture.md`, then `thoughts/$ARGUMENTS/spec.md`, `threat-model.md` and `research.md`.
Write `thoughts/$ARGUMENTS/plan.md` using `.factory/templates/plan.md`:

- Phases are vertical slices: each ends with something runnable and testable end to end.
- For each phase: files to change, new types and real Python function signatures, data model changes, tests to add
  (and why each fails before the change), automated verification commands, manual verification steps, and which
  threat-model controls it implements.
- Respect every contract in the spec's "Contract" section exactly (endpoints, env vars, test seams).
  The human's acceptance tests depend on it.
- Name every new dependency and justify it. Note any system package (apt) the app needs; the human adds it to CI.
- Keep phases small enough for one session.
- Fill "Architecture contracts" with app-specific import rules in `.importlinter` syntax. Do not edit `.importlinter`.
- Write one ADR per significant decision in `docs/decisions/NNNN-title.md` using `docs/decisions/0000-template.md`,
  and list them in the plan. Later reviews audit the code against them.
- Fill the "Docs" section: which phase updates which part of `README.md` and `AGENTS.md`. The README must describe the app
  (what it does, how to run it, env vars, limits), never the template. If either file still has template text or the
  `<One paragraph written at Gate 1...>` placeholder, make the first phase replace it (start the README from `.factory/templates/readme-app.md`).
- Fill "Intent and architecture impact". If the change moves a box, a trust boundary, a data path or an invariant, say so,
  add an ADR, and make one phase update `docs/architecture.md`. Never edit `docs/intent.md`.
- Add "What I am unsure about".
- Leave `Status: draft` at the top. Only the human sets `Status: approved`.

Do not write code. Stop.
