"""Contract validators.

Each validator has a known-bad fixture in the tests that it must reject. A
validator that only ever passes is not a validator -- see Global Constraints.
"""
import subprocess
import sys
from pathlib import Path

from charter.contracts.models import (
    Artifact,
    ChangeSummary,
    FailingTest,
    ThreatEntry,
    ValidationResult,
)
from charter.kernel.models import ArtifactKind


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


# A test run should be quick. A hang is a rejection, not a wait.
TEST_TIMEOUT_SECONDS = 120

# pytest's documented exit codes (pytest._pytest.main.ExitCode).
_PYTEST_TESTS_FAILED = 1
_PYTEST_USAGE_ERROR = 4
_PYTEST_NO_TESTS_COLLECTED = 5
# Both 4 and 5 mean "nothing ran that matches the selector" for this
# validator's purposes. Verified empirically (pytest 7.4.0) rather than
# assumed from the exit-code table: invoking `path::name` with a `name`
# that does not exist in an otherwise-valid, importable `path` returns 4
# (USAGE_ERROR -- pytest treats an unresolved explicit node id as a bad
# invocation, not as "collected zero tests"). 5 (NO_TESTS_COLLECTED) is
# pytest's code for a collection that legitimately yields zero items (an
# empty file/dir, or a `-k` filter matching nothing) -- this validator
# never constructs a selector that can hit that path today, since it
# always passes an explicit `path::name`, but 5 is kept as a documented,
# spec-true fallback rather than dropped.
_PYTEST_SELECTOR_NOT_FOUND = (_PYTEST_USAGE_ERROR, _PYTEST_NO_TESTS_COLLECTED)

# Exit 4 is ALSO what pytest returns when the targeted file exists but fails
# to collect at all -- a SyntaxError or an ImportError in the module. That is
# a different problem from "the test name is wrong", and telling a submitter
# whose file doesn't even import to "check the test name" is false. Verified
# empirically (pytest 7.4.0) that pytest's own stdout tells the two apart: a
# plain unresolved node id prints only "ERROR: not found: ...", while a file
# that raises on import additionally prints an "ERROR collecting <path>"
# section (present whether the underlying cause is a SyntaxError or an
# ImportError/ModuleNotFoundError) ahead of the traceback. Use that marker,
# not the exit code alone, to choose the accurate reason.
_PYTEST_COLLECTION_ERROR_MARKER = "ERROR collecting"


def validate_failing_test(a: FailingTest, repo: Path) -> ValidationResult:
    """The named test must genuinely fail against the tree as it stands.

    A test that passes is not evidence of a defect, and a test written after a
    fix tends to encode the fix rather than the requirement. Running it is the
    only way to know which one we were handed.
    """
    resolved = _resolve_inside(repo, a.test_path)
    if resolved is None:
        return ValidationResult.reject(
            f"{a.test_path!r} resolves outside the repository")
    if not resolved.exists():
        return ValidationResult.reject(
            f"{a.test_path!r} does not exist in the repository")

    selector = f"{a.test_path}::{a.test_name}"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", selector, "-x", "-q",
             "-p", "no:cacheprovider"],
            cwd=repo, capture_output=True, text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult.reject(
            f"{selector} did not finish within {TEST_TIMEOUT_SECONDS}s")

    if proc.returncode in _PYTEST_SELECTOR_NOT_FOUND:
        if _PYTEST_COLLECTION_ERROR_MARKER in proc.stdout:
            return ValidationResult.reject(
                f"{selector} failed to collect -- the test file did not "
                f"import cleanly, so this is not evidence about "
                f"{a.defect_id} one way or the other:\n"
                f"{proc.stdout[-800:]}")
        return ValidationResult.reject(
            f"{selector} collected no test -- check the test name")
    if proc.returncode == 0:
        return ValidationResult.reject(
            f"{selector} passes against the current tree, so it is not "
            f"evidence of defect {a.defect_id}. A test that reproduces the "
            f"defect must fail before the fix.")
    if proc.returncode != _PYTEST_TESTS_FAILED:
        return ValidationResult.reject(
            f"{selector} errored (pytest exit {proc.returncode}):\n"
            f"{proc.stdout[-800:]}")
    return ValidationResult.ok()


_VALIDATORS = {
    ArtifactKind.CHANGE_SUMMARY: validate_change_summary,
    ArtifactKind.FAILING_TEST: validate_failing_test,
    ArtifactKind.THREAT_ENTRY: validate_threat_entry,
}


def validate(
    role_contract: ArtifactKind, artifact: Artifact, repo: Path
) -> ValidationResult:
    """Validate a submitted artifact against the contract its role owes."""
    if artifact.kind != role_contract.value:
        return ValidationResult.reject(
            f"this role expects a {role_contract.value}, "
            f"got a {artifact.kind}")
    return _VALIDATORS[role_contract](artifact, repo)
