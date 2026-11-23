# Architecture: <app name>

Status: template
<!-- Owned by the human, kept true by every change. A change that moves a box, a boundary or an invariant updates this
     file in the same pull request and says so in the plan. One page of text plus the diagram. -->

## The picture
One diagram a new reader can follow in a minute: the boxes (modules or services), what crosses each arrow, and where the
trust boundaries are (a trust boundary is any arrow where data leaves your control or comes in untrusted).

```text
<draw it: browser -> app -> OCR -> model, with the boundaries marked>
```

## Where the data goes
One row per kind of sensitive data: where it enters, where it may travel, where it must never be, how long it lives.

| Data | Enters at | May travel to | Must never reach | Lives for |
|---|---|---|---|---|

## Invariants
Promises the code keeps whatever a ticket says. Each row needs a test whose comment is `# I<n>` (or
`@pytest.mark.invariant("I<n>")`); `scripts/trace.py` fails the build otherwise. A new invariant is a decision: write an
ADR in `docs/decisions/`.

| ID | Invariant | Intent | Enforced by (test) |
|---|---|---|---|
| I1 | | N1 | |

## Decisions
The ADRs that shaped this picture, one line each (`docs/decisions/NNNN-title.md`).

## Known gaps
Where the code does not yet keep an invariant or the picture is not true yet. Honest gaps beat a tidy page.
