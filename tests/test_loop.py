import pytest
from charter.kernel.methodology import roster_for
from charter.library import load_methodologies, load_roles
from charter.loop.machine import Council, MAX_ATTEMPTS
from charter.record.store import RecordStore
from charter.record.models import Signoff
from charter.contracts.models import ChangeSummary, FailingTest
from charter.gates.checks import role_coverage


def _seed_repo(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "t.py").write_text("def test_reproduces():\n    assert 1 == 2\n")


@pytest.fixture
def council(tmp_path):
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="a governed build", phase="implementation")
    _seed_repo(tmp_path)
    return Council(store, tmp_path, "conn-main")


# QA leads: red before green. Its contract is a test that genuinely fails.
GOOD = {"kind": "failing_test", "test_path": "t.py",
        "test_name": "test_reproduces", "defect_id": "D-1"}
BAD = {"kind": "failing_test", "test_path": "ghost.py",
       "test_name": "test_reproduces", "defect_id": "D-1"}
FIRST_ROLE = "qa"

GOOD_CHANGE = {"kind": "change_summary", "files": ["a.py"],
               "decision_ref": "D-1", "summary": "did the thing"}
BAD_CHANGE = {"kind": "change_summary", "files": ["ghost.py"],
              "decision_ref": "D-1", "summary": "did the thing"}


def test_next_issues_the_first_role_with_its_contract(council):
    r = council.next()
    assert r.kind == "assignment"
    assert r.assignment.role == FIRST_ROLE
    assert r.assignment.contract == "failing_test"
    assert r.assignment.instruction


def test_next_is_idempotent_until_something_is_submitted(council):
    assert council.next().assignment.role == council.next().assignment.role


def test_a_valid_submission_is_accepted_and_advances_the_role(council):
    council.next()
    assert council.submit(FIRST_ROLE, GOOD).accepted
    assert council.next().assignment.role == "developer"


def test_an_invalid_submission_is_rejected_and_reissues_the_same_role(council):
    council.next()
    result = council.submit(FIRST_ROLE, BAD)
    assert not result.accepted
    assert "ghost.py" in result.reason
    assert result.attempts_remaining == MAX_ATTEMPTS - 1
    assert council.next().assignment.role == FIRST_ROLE


def test_submitting_as_the_wrong_role_is_refused(council):
    council.next()
    result = council.submit("developer", GOOD_CHANGE)
    assert not result.accepted
    assert FIRST_ROLE in result.reason


def test_three_failures_escalate_to_a_human(council):
    council.next()
    for _ in range(MAX_ATTEMPTS):
        result = council.submit(FIRST_ROLE, BAD)
    assert result.escalated
    assert council.next().kind == "escalated"


def test_status_reports_outstanding_roles(council):
    council.next()
    council.submit(FIRST_ROLE, GOOD)
    s = council.status()
    assert s.signed_off == [FIRST_ROLE]
    assert "developer" in s.outstanding
    assert s.methodology == "scrum"


def test_every_transition_is_recorded_in_the_transcript(council):
    council.next()
    council.submit(FIRST_ROLE, BAD)
    council.submit(FIRST_ROLE, GOOD)
    events = [e.event for e in council.store.events()]
    assert "issued" in events and "rejected" in events and "accepted" in events


def test_a_cold_council_resumes_the_identical_assignment(council, tmp_path):
    council.next()
    council.submit(FIRST_ROLE, GOOD)
    expected = council.next().assignment

    cold = Council(RecordStore(tmp_path), tmp_path)
    assert cold.next().assignment.role == expected.role
    assert cold.next().assignment.task_id == expected.task_id


def test_status_discloses_the_independence_limitation(council):
    council.next()
    council.submit("developer", GOOD_CHANGE)
    s = council.status()
    assert isinstance(s.independence, str)
    assert s.independence.strip()


def test_a_wrong_role_submission_is_recorded_in_the_transcript(council):
    council.next()
    council.submit("qa", GOOD_CHANGE)
    events = [e.event for e in council.store.events()]
    assert "rejected" in events


def test_a_submission_with_no_outstanding_assignment_is_recorded(council):
    council.submit("developer", GOOD_CHANGE)
    events = [e.event for e in council.store.events()]
    assert "rejected" in events


# ---- v2: bounded handover ----------------------------------------------

MARKER = "SUPER_SECRET_FILE_BODY_MARKER"
ART_CHANGE = ChangeSummary(kind="change_summary", files=["a.py"],
                           decision_ref="D-1", summary="x")


def test_a_reviewer_is_told_what_it_is_reviewing(tmp_path):
    """A cold review session has no context but the record.

    Without the producer's artifact and its cited paths, a reviewing role in
    its own session is asked to review something it was never shown.
    """
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    _seed_repo(tmp_path)
    (tmp_path / "a.py").write_text(f"# {MARKER}\n")

    red = Council(store, tmp_path, "conn-qa")
    red.next(); red.submit("qa", GOOD)

    dev = Council(store, tmp_path, "conn-dev")
    dev.next(); dev.submit("developer", GOOD_CHANGE)

    review = Council(store, tmp_path, "conn-review")
    assignment = review.next().assignment
    assert assignment.role == "appsec"
    assert assignment.reviewing is not None, "reviewer was shown nothing"
    assert assignment.reviewing.kind == "change_summary"
    assert assignment.cited_paths == ["a.py"]


def test_the_handover_carries_paths_never_file_contents(tmp_path):
    """The reviewer opens the files itself. Charter hands over references."""
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    _seed_repo(tmp_path)
    (tmp_path / "a.py").write_text(f"# {MARKER}\n")

    red = Council(store, tmp_path, "conn-qa")
    red.next(); red.submit("qa", GOOD)
    dev = Council(store, tmp_path, "conn-dev")
    dev.next(); dev.submit("developer", GOOD_CHANGE)

    payload = Council(store, tmp_path, "conn-review").next().model_dump_json()
    assert MARKER not in payload, "file contents leaked into the handover"
    assert len(payload.encode()) < 8192, (
        f"handover is {len(payload.encode())} bytes, over the 8 KB ceiling")


def test_status_reports_what_the_handover_is_costing(tmp_path):
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    _seed_repo(tmp_path)

    red = Council(store, tmp_path, "conn-qa")
    red.next()
    red.submit("qa", BAD)                    # rejected
    red.submit("qa", GOOD)                   # accepted
    Council(store, tmp_path, "conn-review").next()

    s = Council(store, tmp_path, "conn-review").status()
    assert s.passes_issued >= 2
    assert s.passes_rejected == 1
    assert s.distinct_connections == 1       # only accepted sign-offs count
    assert s.bytes_handed_over > 0


# ---- v2.1: red-green ordering ------------------------------------------

def test_qa_is_issued_before_the_developer(tmp_path):
    """QA's contract is a test that fails NOW. Handed a tree where the fix is
    already applied, it can never honestly be satisfied -- charter's own
    self-audit found exactly this."""
    roster = roster_for("cicd", load_methodologies(), load_roles())
    assert roster.role_ids()[0] == "qa"


def test_defect_evidence_survives_the_fix_that_answers_it(tmp_path):
    """A failing test proves a defect existed. The developer's fix changes the
    tree, and must not invalidate the evidence that justified it."""
    roster = roster_for("cicd", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    (tmp_path / "a.py").write_text("x = 1\n")

    qa_signoff = Signoff(role="qa", tree_sha="before-the-fix",
                         connection_id="conn-qa",
                         artifact=FailingTest(kind="failing_test",
                                              test_path="t.py",
                                              test_name="test_x",
                                              defect_id="D-1"))
    store.append_signoff(qa_signoff)

    result = role_coverage(roster, store.signoffs(), "after-the-fix")
    assert "qa" not in result.reason, (
        "QA's defect evidence was invalidated by the fix it enabled")


def test_independence_is_enforced_even_when_the_reviewer_signs_first(tmp_path):
    """With QA first there is no developer sign-off to compare against at
    submit time, so the per-submission check cannot fire. The completion check
    is what closes that hole."""
    roster = roster_for("cicd", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    for role, conn in (("qa", "same"), ("developer", "same"), ("appsec", "other")):
        store.append_signoff(Signoff(role=role, tree_sha="t", connection_id=conn,
                                     artifact=ART_CHANGE))
    result = role_coverage(roster, store.signoffs(), "t")
    assert not result.allowed
    assert "same process" in result.reason


def test_a_still_reproducing_defect_blocks_instead_of_crashing(tmp_path):
    """Coverage can now refuse while EVERY role has signed -- the defect is
    still live. There is no role left to issue, and _issue's generator has no
    default, so this used to raise StopIteration out of next()."""
    roster = roster_for("cicd", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    _seed_repo(tmp_path)
    sha = None
    from charter.vcs import tree_sha
    sha = tree_sha(tmp_path)
    for role, conn, art in (
        ("qa", "c1", FailingTest(kind="failing_test", test_path="t.py",
                                 test_name="test_reproduces", defect_id="D-1")),
        ("developer", "c2", ART_CHANGE),
        ("appsec", "c3", ART_CHANGE),
    ):
        store.append_signoff(Signoff(role=role, artifact=art, tree_sha=sha,
                                     connection_id=conn))
    r = Council(store, tmp_path, "c4").next()      # must not raise
    assert r.kind == "blocked"
    assert "still fails" in r.reason
