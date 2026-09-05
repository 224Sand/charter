"""Cross-cutting rules the loop enforces.

`no_self_signoff` is the rule that stops multi-role collapsing into one voice
agreeing with itself. The independence it buys is structural, not model
independence -- see the design doc, section 7.4.
"""
from pydantic import BaseModel

from charter.kernel.models import Roster
from charter.record.models import Signoff


class GateResult(BaseModel):
    allowed: bool
    reason: str = ""

    @classmethod
    def allow(cls) -> "GateResult":
        return cls(allowed=True)

    @classmethod
    def block(cls, reason: str) -> "GateResult":
        return cls(allowed=False, reason=reason)


def no_self_signoff(signoff: Signoff) -> GateResult:
    """A role may not approve work it produced itself."""
    if signoff.role == signoff.producer_role:
        return GateResult.block(
            f"role {signoff.role!r} may not sign off its own work; "
            f"another role in the roster must approve it")
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
