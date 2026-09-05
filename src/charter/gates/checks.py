"""Cross-cutting rules the loop enforces.

`no_self_signoff` is the rule that stops multi-role collapsing into one voice
agreeing with itself. The independence it buys is structural, not model
independence -- see the design doc, section 7.4.
"""
from pydantic import BaseModel

from charter.kernel.models import EvidenceScope, Roster
import hashlib
from pathlib import Path

from charter.contracts.models import FailingTest
from charter.contracts.validators import (_resolve_inside,
                                          validate_failing_test)
from charter.record.models import Signoff

# The role whose passes are 'the work' every reviewing role is checked
# against. Reviewers must not share its process; it is its own baseline.
_PRODUCER_ROLE = "developer"


class GateResult(BaseModel):
    allowed: bool
    reason: str = ""

    @classmethod
    def allow(cls) -> "GateResult":
        return cls(allowed=True)

    @classmethod
    def block(cls, reason: str) -> "GateResult":
        return cls(allowed=False, reason=reason)


def no_self_signoff(
    signoff: Signoff, signoffs: list[Signoff], roster: Roster
) -> GateResult:
    """A reviewing role may not be the process that produced the work.

    v1 compared role labels, which could never collide and so proved nothing.
    v2 compares the server-generated connection id recorded on each sign-off:
    two ids means two server processes, which the caller cannot fake because it
    never supplies the id.

    What this does NOT prove is independent reasoning -- a server restart, an
    adversarial agent, or a human clicking through two sessions all satisfy it.
    See the v2 design, section 6.
    """
    producer_role = _PRODUCER_ROLE
    if signoff.role == producer_role:
        # The producer's own pass is the baseline everything else is compared
        # against. It has nothing to be independent of.
        return GateResult.allow()

    producer = next(
        (s for s in signoffs
         if s.role == producer_role and s.tree_sha == signoff.tree_sha),
        None,
    )
    if producer is None:
        # Nothing has been produced for this tree yet, so there is no identity
        # to differ from.
        return GateResult.allow()

    if producer.connection_id is None or signoff.connection_id is None:
        missing = "the producing" if producer.connection_id is None else "this"
        return GateResult.block(
            f"independence is UNAVAILABLE for {signoff.role!r}: "
            f"{missing} sign-off carries no connection id, so charter cannot "
            f"show it came from a separate process. Re-run this role from its "
            f"own charter session rather than accepting it unverified.")

    if producer.connection_id == signoff.connection_id:
        return GateResult.block(
            f"role {signoff.role!r} was submitted by the same process that "
            f"produced the work (connection {signoff.connection_id[:8]}). Run "
            f"this review from a separate charter session so the sign-off is "
            f"not the author checking their own homework.")

    return GateResult.allow()


def staleness(signoff: Signoff, current_tree_sha: str) -> GateResult:
    """A sign-off against a tree that has since changed is void."""
    if signoff.tree_sha != current_tree_sha:
        return GateResult.block(
            f"sign-off by {signoff.role!r} is stale: it was made against tree "
            f"{signoff.tree_sha} but the tree is now {current_tree_sha}")
    return GateResult.allow()


def evidence_digest(artifact, repo: Path) -> str | None:
    """sha256 of the file an artifact cites as its evidence, or None.

    Green verification executes that file. Pinning its content at acceptance is
    what stops an accepted file being swapped for one that runs something else.
    """
    path = getattr(artifact, "test_path", None)
    if path is None:
        return None
    resolved = _resolve_inside(repo, path)
    if resolved is None or not resolved.is_file():
        return None
    return hashlib.sha256(resolved.read_bytes()).hexdigest()


def covered_roles(
    roster: Roster, signoffs: list[Signoff], current_tree_sha: str
) -> set[str]:
    """Which roles count as having signed off the current tree.

    The single definition of freshness. It was duplicated -- role_coverage
    applied evidence scope, the loop's role picker compared tree_sha directly --
    and the two disagreed the moment defect-scoped evidence existed: coverage
    counted QA as covered while the picker re-issued it forever. One rule, one
    place.
    """
    scopes = {r.id: r.evidence for r in roster.roles}
    return {
        s.role for s in signoffs
        if scopes.get(s.role) is EvidenceScope.DEFECT
        or s.tree_sha == current_tree_sha
    }


def role_coverage(
    roster: Roster, signoffs: list[Signoff], current_tree_sha: str,
    repo: Path | None = None,
) -> GateResult:
    """A phase cannot close while a required role has not signed off.

    Freshness depends on what the role's evidence is ABOUT. A tree-scoped
    sign-off approves the code as it stands and is void once it moves. A
    defect-scoped one -- a failing test proving the problem existed -- must
    survive the fix it justified, or the evidence is destroyed by the change
    it enabled.
    """
    fresh = covered_roles(roster, signoffs, current_tree_sha)
    missing = [r for r in roster.role_ids() if r not in fresh]
    if missing:
        return GateResult.block(
            f"these roles have not signed off the current tree: "
            f"{', '.join(missing)}")

    # Independence, checked over the whole set rather than per submission.
    # With a reviewing role running BEFORE the producer, there is no producer
    # sign-off to compare against at submit time, so the per-submission check
    # cannot fire. This is what closes that hole, whatever the order.
    producer = next(
        (s for s in signoffs if s.role == _PRODUCER_ROLE and s.role in fresh),
        None)
    if producer is not None and producer.connection_id is not None:
        shared = [
            s.role for s in signoffs
            if s.role in fresh
            and s.role != _PRODUCER_ROLE
            and s.connection_id == producer.connection_id
        ]
        if shared:
            return GateResult.block(
                f"cannot close: {', '.join(sorted(set(shared)))} signed off "
                f"from the same process as {_PRODUCER_ROLE!r} "
                f"(connection {producer.connection_id[:8]}). Re-run those "
                f"reviews from their own charter session.")

    # Green. Charter recorded that a defect test FAILED; nothing yet confirmed
    # the fix made it pass, so a build could close with the defect still live.
    # Re-run each defect test before letting the phase close.
    for s in signoffs:
        if s.role not in fresh or not isinstance(s.artifact, FailingTest):
            continue
        # Content, not just path. The file is about to be executed; if it is
        # not the one that was reviewed, nothing downstream is trustworthy.
        if s.evidence_digest is not None and repo is not None:
            current = evidence_digest(s.artifact, repo)
            if current != s.evidence_digest:
                return GateResult.block(
                    f"cannot close: {s.artifact.test_path} changed since it was "
                    f"accepted as evidence for {s.artifact.defect_id!r}. Charter "
                    f"re-runs that file, so it will not execute content nobody "
                    f"reviewed. Re-submit it through {s.role!r}.")
        if repo is None:
            return GateResult.block(
                f"cannot close: {s.role!r} recorded a failing test for defect "
                f"{s.artifact.defect_id!r} and charter was given no repository "
                f"to re-run it in, so it cannot show the defect is fixed. "
                f"Not verified is not the same as passed.")
        # validate_failing_test accepts when the test FAILS. Still accepted
        # here means the defect it proved is still reproducing.
        if validate_failing_test(s.artifact, repo).accepted:
            return GateResult.block(
                f"cannot close: {s.artifact.test_path}::"
                f"{s.artifact.test_name} still fails, so defect "
                f"{s.artifact.defect_id!r} is not fixed. Charter proved this "
                f"defect exists; it will not close until it stops.")
    return GateResult.allow()
