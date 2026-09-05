# Self-audit, second run — a completed governed build

The [first run](../2026-09-05-first-run/) did not finish. It found a shipping bug and a
flaw in charter's own loop ordering, both fixed. This run completed.

## The record

| role | connection | artifact | who |
|---|---|---|---|
| qa | `3353c690` | `failing_test` | separate agent context |
| developer | `39f7fa76` | `change_summary` | main session |
| appsec | `5c849420` | `threat_entry` | separate agent context |

Three distinct connection ids, zero rejections. `transcript.jsonl` is the full trace.

Charter re-ran QA's test before permitting the phase to close, and only then reported
`done`. That verification is the change this build was about.

## What it governed

**QA (red).** Charter recorded that a defect test *failed* and never re-ran it after the
fix, so a build could reach `done` with the defect still live — proof the bug existed,
none that it was fixed. QA submitted a test failing for exactly that reason, and confirmed
the gap by reading `role_coverage` rather than taking the brief on trust.

**Developer (green).** `role_coverage` now re-runs each defect-scoped sign-off's cited
test before a phase may close, and blocks when given no repository to verify in — *not
verified is not the same as passed.*

**AppSec (review).** Filed **CWE-94** against that implementation. Re-running cited tests
against the live tree turned a one-time reviewed check into a recurring execution surface:
`next()` is an unauthenticated poll, and a file accepted once as evidence could be edited
afterwards to carry code pytest executes on collection — every poll, indefinitely. Path
containment was enforced; content was not.

## The point about that last one

The build closed with AppSec's finding **accepted**. That is not a contradiction: the
contract requires the finding be *produced*, not that it be empty. An accepted
`threat_entry` is a recorded finding, not a clearance.

It was fixed rather than shipped — sign-offs now record the sha256 of their evidence file,
and charter refuses to execute a file whose content changed since it was reviewed.

## Two findings against the author

Both runs found real defects in charter, filed by roles the author did not control:
a dependency bug that would have broken every install, a flaw in the loop's own ordering,
and a code-execution regression introduced by the fix. That is the artifact — not a green
checkmark.
