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


def test_the_gate_no_longer_relies_on_the_v1_producer_role_label():
    """v1 compared role labels via a hardcoded convention whose values could
    never collide, so the gate passed everything. Identity replaced it; a
    sign-off carrying only the old label must not be treated as verified."""
    legacy = Signoff(role="qa", producer_role="developer", artifact=ART,
                     tree_sha="abc123")
    result = no_self_signoff(legacy, [_s2("developer", "conn-a")], ROSTER)
    assert not result.allowed, "a label-only sign-off must not pass as independent"


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


# ---- v2: identity-based independence -----------------------------------

ROSTER = roster_for("scrum", load_methodologies(), load_roles())


def _s2(role, conn, sha="abc123"):
    return Signoff(role=role, artifact=ART, tree_sha=sha, connection_id=conn)


def test_a_reviewer_from_the_same_process_as_the_developer_is_blocked():
    dev = _s2("developer", "conn-a")
    qa = _s2("qa", "conn-a")
    result = no_self_signoff(qa, [dev], ROSTER)
    assert not result.allowed
    assert "same process" in result.reason


def test_a_reviewer_from_a_different_process_is_allowed():
    dev = _s2("developer", "conn-a")
    assert no_self_signoff(_s2("qa", "conn-b"), [dev], ROSTER).allowed


def test_a_missing_id_reports_unavailable_and_blocks_rather_than_passing():
    dev = _s2("developer", None)
    result = no_self_signoff(_s2("qa", "conn-b"), [dev], ROSTER)
    assert not result.allowed
    assert "unavailable" in result.reason.lower()

    result = no_self_signoff(_s2("qa", None), [_s2("developer", "conn-a")], ROSTER)
    assert not result.allowed
    assert "unavailable" in result.reason.lower()


def test_the_developers_own_pass_has_nothing_to_be_independent_of():
    assert no_self_signoff(_s2("developer", "conn-a"), [], ROSTER).allowed


def test_a_stale_developer_signoff_does_not_constrain_a_new_tree():
    old_dev = _s2("developer", "conn-a", sha="old")
    assert no_self_signoff(_s2("qa", "conn-a", sha="new"), [old_dev], ROSTER).allowed
