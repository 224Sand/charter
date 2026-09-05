import pytest
from charter.kernel.methodology import roster_for
from charter.library import load_methodologies, load_roles
from charter.loop.machine import Council, MAX_ATTEMPTS
from charter.record.store import RecordStore


@pytest.fixture
def council(tmp_path):
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="a governed build", phase="implementation")
    (tmp_path / "a.py").write_text("x = 1\n")
    return Council(store, tmp_path)


GOOD_CHANGE = {"kind": "change_summary", "files": ["a.py"],
               "decision_ref": "D-1", "summary": "did the thing"}
BAD_CHANGE = {"kind": "change_summary", "files": ["ghost.py"],
              "decision_ref": "D-1", "summary": "did the thing"}


def test_next_issues_the_first_role_with_its_contract(council):
    r = council.next()
    assert r.kind == "assignment"
    assert r.assignment.role == "developer"
    assert r.assignment.contract == "change_summary"
    assert r.assignment.instruction


def test_next_is_idempotent_until_something_is_submitted(council):
    assert council.next().assignment.role == council.next().assignment.role


def test_a_valid_submission_is_accepted_and_advances_the_role(council):
    council.next()
    assert council.submit("developer", GOOD_CHANGE).accepted
    assert council.next().assignment.role == "qa"


def test_an_invalid_submission_is_rejected_and_reissues_the_same_role(council):
    council.next()
    result = council.submit("developer", BAD_CHANGE)
    assert not result.accepted
    assert "ghost.py" in result.reason
    assert result.attempts_remaining == MAX_ATTEMPTS - 1
    assert council.next().assignment.role == "developer"


def test_submitting_as_the_wrong_role_is_refused(council):
    council.next()
    result = council.submit("qa", GOOD_CHANGE)
    assert not result.accepted
    assert "developer" in result.reason


def test_three_failures_escalate_to_a_human(council):
    council.next()
    for _ in range(MAX_ATTEMPTS):
        result = council.submit("developer", BAD_CHANGE)
    assert result.escalated
    assert council.next().kind == "escalated"


def test_status_reports_outstanding_roles(council):
    council.next()
    council.submit("developer", GOOD_CHANGE)
    s = council.status()
    assert s.signed_off == ["developer"]
    assert "qa" in s.outstanding
    assert s.methodology == "scrum"


def test_every_transition_is_recorded_in_the_transcript(council):
    council.next()
    council.submit("developer", BAD_CHANGE)
    council.submit("developer", GOOD_CHANGE)
    events = [e.event for e in council.store.events()]
    assert "issued" in events and "rejected" in events and "accepted" in events


def test_a_cold_council_resumes_the_identical_assignment(council, tmp_path):
    council.next()
    council.submit("developer", GOOD_CHANGE)
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


def test_a_reviewer_is_told_what_it_is_reviewing(tmp_path):
    """A cold review session has no context but the record.

    Without the producer's artifact and its cited paths, a reviewing role in
    its own session is asked to review something it was never shown.
    """
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    (tmp_path / "a.py").write_text(f"# {MARKER}\n")

    dev = Council(store, tmp_path, "conn-dev")
    dev.next()
    dev.submit("developer", GOOD_CHANGE)

    review = Council(store, tmp_path, "conn-review")
    assignment = review.next().assignment
    assert assignment.role == "qa"
    assert assignment.reviewing is not None, "reviewer was shown nothing"
    assert assignment.reviewing.kind == "change_summary"
    assert assignment.cited_paths == ["a.py"]


def test_the_handover_carries_paths_never_file_contents(tmp_path):
    """The reviewer opens the files itself. Charter hands over references."""
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    (tmp_path / "a.py").write_text(f"# {MARKER}\n")

    dev = Council(store, tmp_path, "conn-dev")
    dev.next()
    dev.submit("developer", GOOD_CHANGE)

    payload = Council(store, tmp_path, "conn-review").next().model_dump_json()
    assert MARKER not in payload, "file contents leaked into the handover"
    assert len(payload.encode()) < 8192, (
        f"handover is {len(payload.encode())} bytes, over the 8 KB ceiling")


def test_status_reports_what_the_handover_is_costing(tmp_path):
    roster = roster_for("scrum", load_methodologies(), load_roles())
    store = RecordStore(tmp_path)
    store.init(roster, idea="x", phase="implementation")
    (tmp_path / "a.py").write_text("x = 1\n")

    dev = Council(store, tmp_path, "conn-dev")
    dev.next()
    dev.submit("developer", BAD_CHANGE)      # rejected
    dev.submit("developer", GOOD_CHANGE)     # accepted
    Council(store, tmp_path, "conn-review").next()

    s = Council(store, tmp_path, "conn-review").status()
    assert s.passes_issued >= 2
    assert s.passes_rejected == 1
    assert s.distinct_connections == 1       # only accepted sign-offs count
    assert s.bytes_handed_over > 0
