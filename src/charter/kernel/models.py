"""Core kernel types.

No I/O and no LLM calls live in this package -- see Global Constraints.
Loading YAML from disk is the loader's job (charter.library), not the
model's, so the kernel stays a pure, exhaustively testable core.
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ArtifactKind(str, Enum):
    """What a role must produce before it may sign off."""

    CHANGE_SUMMARY = "change_summary"
    FAILING_TEST = "failing_test"
    THREAT_ENTRY = "threat_entry"


class EvidenceScope(str, Enum):
    """What a role's artifact is evidence ABOUT.

    TREE artifacts approve the code as it currently stands, so they go stale
    the moment it moves. DEFECT artifacts prove a problem existed -- a failing
    test is exactly that -- and must survive the fix they justified, or the
    evidence is destroyed by the very change it enabled.
    """

    TREE = "tree"
    DEFECT = "defect"


class RoleDef(BaseModel):
    """One role's lens and the contract it owes."""

    # A mistyped key in a hand-written YAML definition must fail loudly
    # rather than silently falling back to a default.
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    contract: ArtifactKind
    activates_on: list[str] = Field(min_length=1)
    evidence: EvidenceScope = EvidenceScope.TREE


class MethodologyDef(BaseModel):
    """A methodology: the phases it runs and the roles it activates."""

    # A mistyped key in a hand-written YAML definition must fail loudly
    # rather than silently falling back to a default.
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    phases: list[str] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    decision_points: list[str] = Field(default_factory=list)


class Roster(BaseModel):
    """The active role set for one build."""

    methodology: str = Field(min_length=1)
    roles: list[RoleDef] = Field(min_length=1)

    def role_ids(self) -> list[str]:
        return [r.id for r in self.roles]
