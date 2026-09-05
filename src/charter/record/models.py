"""Build-record types.

The record is the build's memory. A session with no prior context must be able
to reconstruct full state from these files alone -- that is what makes a
nine-sprint build survivable across sessions.
"""
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from charter.contracts.models import Artifact


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Assignment(BaseModel):
    """One role's outstanding instruction."""

    role: str
    phase: str
    task_id: str
    contract: str
    instruction: str
    attempt: int = 1


class Signoff(BaseModel):
    """A role's accepted approval, with the evidence that earned it."""

    role: str
    producer_role: str
    artifact: Artifact
    tree_sha: str
    at: datetime = Field(default_factory=_now)


class BuildState(BaseModel):
    """Where the build is right now."""

    phase: str
    task_id: str
    current: Assignment | None = None
    escalated: bool = False
    escalation_reason: str = ""


class TranscriptEvent(BaseModel):
    """One line of the append-only audit trail."""

    event: str
    role: str
    detail: str = ""
    at: datetime = Field(default_factory=_now)
