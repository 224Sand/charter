import textwrap

from charter.contracts.models import ChangeSummary, FailingTest, ThreatEntry
from charter.contracts.validators import validate_failing_test
from charter.gates.checks import (GateResult, evidence_digest,
                                  no_self_signoff, role_coverage, staleness)
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


# ---- red/green: a defect sign-off's test is never re-verified -----------

def test_coverage_must_not_close_while_the_qas_recorded_defect_still_fails(tmp_path):
    """role_coverage treats a defect-scoped (qa) sign-off as permanently
    'fresh' the instant it is recorded -- it never re-runs the failing test
    the sign-off is evidence for. So a build can reach coverage, and charter
    can let the phase close, while the very defect QA flagged is still
    reproducibly broken in the tree.

    This sets up a tree where the QA-recorded test genuinely still fails
    (confirmed independently below via the same runner charter's own
    validator uses), records full role coverage for the current tree with
    distinct connection ids so no other gate has anything to block on, and
    asserts role_coverage refuses to close. It currently does not refuse --
    proving the missing verification, not a typo or a bad import.
    """
    _write(tmp_path, "tests/test_bug.py", """
        def test_reproduces():
            assert 1 == 2
    """)
    defect_art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                             test_name="test_reproduces", defect_id="T-1")

    # Independently confirm -- via charter's own evidence runner -- that the
    # defect this sign-off cites is still live in the tree right now.
    check = validate_failing_test(defect_art, tmp_path)
    assert check.accepted, (
        "fixture is broken: the test this case depends on is not actually "
        "failing, so it cannot demonstrate the gap")

    sha = "abc123"
    signoffs = [
        Signoff(role="developer", artifact=ChangeSummary(
            kind="change_summary", files=["a.py"], decision_ref="D-1",
            summary="x"), tree_sha=sha, connection_id="conn-dev"),
        Signoff(role="qa", artifact=defect_art, tree_sha=sha,
               connection_id="conn-qa"),
        Signoff(role="appsec", artifact=ThreatEntry(
            kind="threat_entry", cwe_id="CWE-89",
            attack_path="attacker-controlled input reaches a raw SQL query",
            affected_files=["a.py"]), tree_sha=sha,
               connection_id="conn-appsec"),
    ]

    roster = roster_for("scrum", load_methodologies(), load_roles())
    result = role_coverage(roster, signoffs, sha)

    assert not result.allowed, (
        "role_coverage allowed the phase to close with every role "
        "signed off, even though QA's own recorded failing test still "
        "fails against the current tree -- charter never re-ran it")


def _write(repo, name, body):
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body))
    return p


def test_evidence_that_changed_after_acceptance_is_refused(tmp_path):
    """AppSec finding, CWE-94, from charter's own governed build.

    Green verification re-runs the cited test against the LIVE tree on every
    poll. A file accepted once as evidence could then be edited to carry
    arbitrary code, which pytest executes on collection -- turning a one-time
    reviewed check into a recurring execution surface. Charter must refuse
    evidence whose content changed since it was accepted.
    """
    _write(tmp_path, "tests/test_bug.py", """
        def test_reproduces():
            assert 1 == 2
    """)
    art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                      test_name="test_reproduces", defect_id="T-1")
    digest = evidence_digest(art, tmp_path)
    assert digest, "a cited, existing test file must produce a digest"

    # The fix lands: the test now passes, so green verification is satisfied.
    _write(tmp_path, "tests/test_bug.py", """
        def test_reproduces():
            assert 1 == 1
    """)
    sha = "abc123"
    signoffs = [
        Signoff(role="qa", artifact=art, tree_sha=sha, connection_id="c1",
                evidence_digest=digest),
        Signoff(role="developer", artifact=ART, tree_sha=sha, connection_id="c2"),
        Signoff(role="appsec", artifact=ART, tree_sha=sha, connection_id="c3"),
    ]
    roster = roster_for("scrum", load_methodologies(), load_roles())
    # Content changed since acceptance -> refuse, whatever the test now returns.
    result = role_coverage(roster, signoffs, sha, tmp_path)
    assert not result.allowed
    assert "changed since" in result.reason
