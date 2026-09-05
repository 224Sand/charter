import json
import pytest
from charter.mcp_server import Handlers


@pytest.fixture
def handlers(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    return Handlers(tmp_path)


def test_init_creates_the_charter_and_reports_the_roster(handlers):
    out = json.loads(handlers.init(idea="build a thing", methodology="scrum"))
    assert out["methodology"] == "scrum"
    assert out["roles"] == ["developer", "qa", "appsec"]


def test_next_before_init_returns_a_clear_error(handlers):
    out = json.loads(handlers.next())
    assert out["error"]
    assert "charter_init" in out["error"]


def test_full_round_trip_through_the_handlers(handlers):
    handlers.init(idea="build a thing", methodology="scrum")
    assignment = json.loads(handlers.next())
    assert assignment["assignment"]["role"] == "developer"

    accepted = json.loads(handlers.submit(role="developer", artifact={
        "kind": "change_summary", "files": ["a.py"],
        "decision_ref": "D-1", "summary": "did the thing"}))
    assert accepted["accepted"] is True

    status = json.loads(handlers.status())
    assert status["signed_off"] == ["developer"]


def test_an_unknown_methodology_is_reported_not_raised(handlers):
    out = json.loads(handlers.init(idea="x", methodology="waterfall"))
    assert "waterfall" in out["error"]
