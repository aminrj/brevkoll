---
description: Draft a threat model from the spec. The human makes the decisions.
allowed-tools: Read, Grep, Glob, Write
---
Issue number: $ARGUMENTS

Read `thoughts/$ARGUMENTS/spec.md`. Draft `thoughts/$ARGUMENTS/threat-model.md` from
`.factory/templates/threat-model.md`. For each threat, propose a control in code and the test that would enforce it.
Mark every decision as `PROPOSED`. Stop.
