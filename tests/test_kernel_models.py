import pytest
from pydantic import ValidationError
from charter.kernel.models import ArtifactKind, RoleDef, MethodologyDef, Roster


def _role(rid="qa", contract=ArtifactKind.FAILING_TEST):
    return RoleDef(id=rid, name="QA Lead", brief="Demands evidence.",
                   contract=contract, activates_on=["scrum"])


def test_artifact_kinds_are_the_three_v1_contracts():
    assert {k.value for k in ArtifactKind} == {
        "change_summary", "failing_test", "threat_entry"}


def test_role_def_round_trips():
    r = _role()
    assert r.id == "qa"
    assert r.contract is ArtifactKind.FAILING_TEST


def test_role_id_must_be_non_empty():
    with pytest.raises(ValidationError):
        RoleDef(id="", name="X", brief="b", contract=ArtifactKind.FAILING_TEST,
                activates_on=["scrum"])


def test_methodology_requires_at_least_one_phase():
    with pytest.raises(ValidationError):
        MethodologyDef(id="scrum", name="Scrum", phases=[], roles=["qa"],
                       decision_points=["sprint_review"])


def test_roster_exposes_role_ids_in_order():
    roster = Roster(methodology="scrum", roles=[
        _role("developer", ArtifactKind.CHANGE_SUMMARY), _role("qa")])
    assert roster.role_ids() == ["developer", "qa"]
