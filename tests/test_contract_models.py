import pytest
from pydantic import ValidationError
from charter.contracts.models import (
    ChangeSummary, FailingTest, ThreatEntry, ValidationResult, parse_artifact)


def test_change_summary_requires_at_least_one_file():
    with pytest.raises(ValidationError):
        ChangeSummary(kind="change_summary", files=[], decision_ref="D-1",
                      summary="x")


def test_threat_entry_rejects_a_non_cwe_identifier():
    with pytest.raises(ValidationError):
        ThreatEntry(kind="threat_entry", cwe_id="SQL injection",
                    attack_path="a" * 40, affected_files=["a.py"])


def test_threat_entry_accepts_a_real_cwe_id():
    t = ThreatEntry(kind="threat_entry", cwe_id="CWE-89",
                    attack_path="a" * 40, affected_files=["a.py"])
    assert t.cwe_id == "CWE-89"


def test_threat_entry_rejects_a_hand_wave_attack_path():
    with pytest.raises(ValidationError):
        ThreatEntry(kind="threat_entry", cwe_id="CWE-89",
                    attack_path="validate input", affected_files=["a.py"])


def test_parse_artifact_dispatches_on_kind():
    art = parse_artifact({"kind": "failing_test", "test_path": "tests/t.py",
                          "test_name": "test_x", "defect_id": "D-004"})
    assert isinstance(art, FailingTest)


def test_parse_artifact_rejects_an_unknown_kind():
    with pytest.raises(ValidationError):
        parse_artifact({"kind": "vibes"})


def test_validation_result_constructors():
    assert ValidationResult.ok().accepted is True
    r = ValidationResult.reject("no test attached")
    assert (r.accepted, r.reason) == (False, "no test attached")
