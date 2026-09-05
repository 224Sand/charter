"""Cross-cutting rules the loop enforces.

`no_self_signoff` is the rule that stops multi-role collapsing into one voice
agreeing with itself. The independence it buys is structural, not model
independence -- see the design doc, section 7.4.
"""
from pydantic import BaseModel

from charter.kernel.models import Roster
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


def role_coverage(
    roster: Roster, signoffs: list[Signoff], current_tree_sha: str
) -> GateResult:
    """A phase cannot close while a required role has not signed off the
    current tree."""
    fresh = {s.role for s in signoffs if s.tree_sha == current_tree_sha}
    missing = [r for r in roster.role_ids() if r not in fresh]
    if missing:
        return GateResult.block(
            f"these roles have not signed off the current tree: "
            f"{', '.join(missing)}")
    return GateResult.allow()
