from charter.contracts.models import ChangeSummary
from charter.gates.checks import (
    GateResult, no_self_signoff, role_coverage, staleness)
from charter.kernel.methodology import roster_for
from charter.library import load_methodologies, load_roles
from charter.record.models import Signoff

ART = ChangeSummary(kind="change_summary", files=["a.py"],
                    decision_ref="D-1", summary="x")


def _s(role, producer, sha="abc123"):
    return Signoff(role=role, producer_role=producer, artifact=ART, tree_sha=sha)


def test_a_role_may_not_sign_off_its_own_work():
    result = no_self_signoff(_s("developer", "developer"))
    assert not result.allowed
    assert "own work" in result.reason


def test_a_different_role_may_sign_off():
    assert no_self_signoff(_s("qa", "developer")).allowed


def test_a_signoff_against_a_changed_tree_is_stale():
    result = staleness(_s("qa", "developer", sha="old"), current_tree_sha="new")
    assert not result.allowed
    assert "stale" in result.reason


def test_a_signoff_against_the_current_tree_is_fresh():
    assert staleness(_s("qa", "developer", sha="same"), "same").allowed


def test_coverage_blocks_while_a_required_role_has_not_signed_off():
    roster = roster_for("scrum", load_methodologies(), load_roles())
    result = role_coverage(roster, [_s("qa", "developer")], "abc123")
    assert not result.allowed
    assert "appsec" in result.reason


def test_coverage_allows_once_every_role_has_signed_off_the_current_tree():
    roster = roster_for("scrum", load_methodologies(), load_roles())
    signoffs = [_s(r, "someone_else") for r in roster.role_ids()]
    assert role_coverage(roster, signoffs, "abc123").allowed


def test_coverage_ignores_signoffs_against_an_older_tree():
    roster = roster_for("scrum", load_methodologies(), load_roles())
    signoffs = [_s(r, "someone_else", sha="old") for r in roster.role_ids()]
    result = role_coverage(roster, signoffs, "new")
    assert not result.allowed
