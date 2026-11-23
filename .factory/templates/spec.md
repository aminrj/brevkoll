# Spec: #<n> <feature name>

Status: draft

**Real user:** <name>   **Size:** S/M   **Timebox:** <h>   **Kill date:** <date>

## Intent (from docs/intent.md and docs/architecture.md)

- Serves: G<n>   <!-- the goal in docs/intent.md this change moves; `none` means ask whether it belongs -->
- Touches: N<n>, I<n>, or `none`   <!-- the "must never" lines and invariants this change comes near -->
- Decision needed from the owner before any code: no   <!-- `yes` when the issue itself says a choice is open: list the
  options under Problem and stop; the foreman holds the item at Checkpoint 1 -->

## Problem

## What v1 does (one sentence)

## User flow
1.
2.

## Acceptance criteria (each one becomes a holdout test)
- [ ] AC1: Given ..., when ..., then ...
- [ ] AC2: ...

Number every criterion `AC<n>`. The holdout test for each carries a `# AC<n>` comment (checked by `scripts/trace.py`).

## Contract (agents must respect this exactly; holdout tests depend on it)

## Out of scope

## Sketch
