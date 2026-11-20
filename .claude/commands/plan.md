---
description: Turn spec, threat model and research into a phased plan. Stops for human review.
allowed-tools: Read, Grep, Glob, Write
---
Issue number: $ARGUMENTS

Read `thoughts/$ARGUMENTS/spec.md`, `threat-model.md` and `research.md`.
Write `thoughts/$ARGUMENTS/plan.md` using `.factory/templates/plan.md`:

- Phases are vertical slices: each ends with something runnable and testable end to end.
- For each phase: files to change, new types and real Python function signatures, data model changes, tests to add
  (and why each fails before the change), automated verification commands, manual verification steps, and which
  threat-model controls it implements.
- Respect every contract in the spec's "Contract" section exactly (endpoints, env vars, test seams).
  The human's acceptance tests depend on it.
- Name every new dependency and justify it. Note any system package (apt) the app needs; the human adds it to CI.
- Keep phases small enough for one session.
- Add "What I am unsure about".
- Leave `Status: draft` at the top. Only the human sets `Status: approved`.

Do not write code. Stop.
