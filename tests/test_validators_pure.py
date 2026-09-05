from charter.contracts.models import ChangeSummary, ThreatEntry
from charter.contracts.validators import (
    validate_change_summary, validate_threat_entry)


def _repo(tmp_path, *names):
    for n in names:
        (tmp_path / n).write_text("x = 1\n")
    return tmp_path


def test_change_summary_accepts_files_that_exist(tmp_path):
    repo = _repo(tmp_path, "a.py")
    art = ChangeSummary(kind="change_summary", files=["a.py"],
                        decision_ref="D-1", summary="did a thing")
    assert validate_change_summary(art, repo).accepted


def test_change_summary_rejects_a_file_that_does_not_exist(tmp_path):
    art = ChangeSummary(kind="change_summary", files=["ghost.py"],
                        decision_ref="D-1", summary="did a thing")
    result = validate_change_summary(art, tmp_path)
    assert not result.accepted
    assert "ghost.py" in result.reason


def test_threat_entry_accepts_a_cited_weakness(tmp_path):
    repo = _repo(tmp_path, "auth.py")
    art = ThreatEntry(kind="threat_entry", cwe_id="CWE-89",
                      attack_path="Unparameterised query in login builds SQL "
                                  "from the raw username field.",
                      affected_files=["auth.py"])
    assert validate_threat_entry(art, repo).accepted


def test_threat_entry_rejects_files_outside_the_repo(tmp_path):
    art = ThreatEntry(kind="threat_entry", cwe_id="CWE-89",
                      attack_path="a" * 40, affected_files=["../../etc/passwd"])
    result = validate_threat_entry(art, tmp_path)
    assert not result.accepted
    assert "outside the repository" in result.reason
