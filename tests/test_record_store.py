import pytest
from datetime import timezone
from charter.kernel.methodology import roster_for
from charter.library import load_methodologies, load_roles
from charter.record.models import Assignment, BuildState, Signoff, TranscriptEvent
from charter.record.store import RecordStore
from charter.contracts.models import ChangeSummary


@pytest.fixture
def roster():
    return roster_for("scrum", load_methodologies(), load_roles())


@pytest.fixture
def store(tmp_path, roster):
    s = RecordStore(tmp_path)
    s.init(roster, idea="a governed build", phase="requirements")
    return s


def _signoff(role="qa", producer="developer"):
    return Signoff(role=role, producer_role=producer, tree_sha="abc123",
                   artifact=ChangeSummary(kind="change_summary", files=["a.py"],
                                          decision_ref="D-1", summary="x"))


def test_init_creates_a_readable_charter(store, roster):
    assert store.exists()
    assert store.load_roster().role_ids() == roster.role_ids()


def test_state_round_trips(store):
    state = BuildState(phase="implementation", task_id="T-1",
                       current=Assignment(role="developer", phase="implementation",
                                          task_id="T-1", contract="change_summary",
                                          instruction="do the thing"))
    store.save_state(state)
    assert store.load_state().current.role == "developer"


def test_signoffs_are_append_only(store):
    store.append_signoff(_signoff())
    store.append_signoff(_signoff(role="appsec"))
    assert [s.role for s in store.signoffs()] == ["qa", "appsec"]


def test_transcript_is_append_only_and_ordered(store):
    for name in ["issued", "submitted", "rejected"]:
        store.append_event(TranscriptEvent(event=name, role="qa"))
    assert [e.event for e in store.events()] == ["issued", "submitted", "rejected"]


def test_a_cold_store_reconstructs_full_state_from_disk(tmp_path, roster):
    warm = RecordStore(tmp_path)
    warm.init(roster, idea="x", phase="requirements")
    warm.save_state(BuildState(phase="verification", task_id="T-7"))
    warm.append_signoff(_signoff())

    cold = RecordStore(tmp_path)          # no shared memory with `warm`
    assert cold.load_state().phase == "verification"
    assert cold.load_state().task_id == "T-7"

    # Verify discriminated-union round-trip: artifact must be ChangeSummary, not dict
    signoffs = cold.signoffs()
    assert len(signoffs) == 1
    s = signoffs[0]
    assert isinstance(s.artifact, ChangeSummary), \
        f"artifact should be ChangeSummary instance, got {type(s.artifact)}"
    assert s.artifact.files == ["a.py"], \
        "artifact fields must survive JSON round-trip"
    assert s.artifact.decision_ref == "D-1"
    assert s.artifact.summary == "x"

    # Verify timezone-aware timestamps survive
    assert s.at.tzinfo is not None, \
        "signoff timestamp must be timezone-aware after reload"
    assert s.at.tzinfo == timezone.utc, \
        "timestamp should be UTC after round-trip"

    assert cold.load_roster().methodology == "scrum"


def test_loading_an_uninitialised_store_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        RecordStore(tmp_path).load_state()


def test_load_idea(store):
    """Idea should persist and be retrievable."""
    idea = store.load_idea()
    assert idea == "a governed build"


def test_transcript_events_have_timezone_aware_timestamps(store):
    """Timestamps in transcript events must survive as timezone-aware."""
    store.append_event(TranscriptEvent(event="test_event", role="qa"))
    events = store.events()
    assert len(events) == 1
    assert events[0].at.tzinfo is not None, \
        "event timestamp must be timezone-aware after reload"
    assert events[0].at.tzinfo == timezone.utc
