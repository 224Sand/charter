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
    # What this role is reviewing. A reviewing role runs in its own session
    # with no context but the record, so the producer's artifact travels with
    # the assignment. Paths only -- the reviewer opens the files itself.
    reviewing: Artifact | None = None
    cited_paths: list[str] = Field(default_factory=list)


class Signoff(BaseModel):
    """A role's accepted approval, with the evidence that earned it."""

    role: str
    artifact: Artifact
    tree_sha: str
    # None means this sign-off predates v2 (or no id was supplied). The
    # independence gate reports that as UNAVAILABLE, never as a pass.
    connection_id: str | None = None
    # sha256 of the cited evidence file at the moment it was accepted. Green
    # verification re-runs that file against the LIVE tree, so without this a
    # file accepted once could be edited afterwards to carry arbitrary code
    # that pytest then executes on every later poll (CWE-94, found by charter's
    # own AppSec pass). None means pre-dating this check, or no file cited.
    evidence_digest: str | None = None
    # v1 field. Retained so v1 records still parse; no longer consulted --
    # the synthetic convention it encoded is what v2 replaced.
    producer_role: str | None = None
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
