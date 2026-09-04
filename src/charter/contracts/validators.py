"""Contract validators.

Each validator has a known-bad fixture in the tests that it must reject. A
validator that only ever passes is not a validator -- see Global Constraints.
"""
from pathlib import Path

from charter.contracts.models import ChangeSummary, ThreatEntry, ValidationResult


def _resolve_inside(repo: Path, name: str) -> Path | None:
    """Resolve `name` under `repo`, or None if it escapes the repository."""
    root = repo.resolve()
    candidate = (root / name).resolve()
    if root != candidate and root not in candidate.parents:
        return None
    return candidate


def _check_files(repo: Path, names: list[str]) -> ValidationResult:
    for name in names:
        resolved = _resolve_inside(repo, name)
        if resolved is None:
            return ValidationResult.reject(
                f"{name!r} resolves outside the repository")
        if not resolved.exists():
            return ValidationResult.reject(
                f"{name!r} does not exist in the repository")
    return ValidationResult.ok()


def validate_change_summary(a: ChangeSummary, repo: Path) -> ValidationResult:
    """A developer must cite files that actually exist and a decision."""
    return _check_files(repo, a.files)


def validate_threat_entry(a: ThreatEntry, repo: Path) -> ValidationResult:
    """AppSec must point at real files. The CWE and attack path are shape-checked
    by the model; this confirms the finding is anchored to the tree."""
    return _check_files(repo, a.affected_files)
