"""Artifact shapes.

These enforce SHAPE and the presence of evidence -- never content. A role must
be free to say "nothing to weigh in on here"; what it may not do is approve
without producing the thing its contract owes.
"""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

# "CWE-89", not "SQL injection". A weakness class or nothing.
CWE_PATTERN = r"^CWE-\d{1,4}$"

# Long enough that "validate input" cannot pass as an attack path.
MIN_ATTACK_PATH = 30


class ChangeSummary(BaseModel):
    kind: Literal["change_summary"]
    files: list[str] = Field(min_length=1)
    decision_ref: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class FailingTest(BaseModel):
    kind: Literal["failing_test"]
    test_path: str = Field(min_length=1)
    test_name: str = Field(min_length=1)
    defect_id: str = Field(min_length=1)


class ThreatEntry(BaseModel):
    kind: Literal["threat_entry"]
    cwe_id: str = Field(pattern=CWE_PATTERN)
    attack_path: str = Field(min_length=MIN_ATTACK_PATH)
    affected_files: list[str] = Field(min_length=1)


Artifact = Annotated[
    Union[ChangeSummary, FailingTest, ThreatEntry],
    Field(discriminator="kind"),
]

_ADAPTER: TypeAdapter = TypeAdapter(Artifact)


def parse_artifact(data: dict) -> Artifact:
    """Parse a submitted artifact, dispatching on its `kind`."""
    return _ADAPTER.validate_python(data)


class ValidationResult(BaseModel):
    accepted: bool
    reason: str = ""

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(accepted=True)

    @classmethod
    def reject(cls, reason: str) -> "ValidationResult":
        return cls(accepted=False, reason=reason)
