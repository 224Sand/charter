import pytest
from charter.kernel.models import ArtifactKind
from charter.library import load_roles, LibraryError


def test_v1_ships_exactly_three_roles():
    roles = load_roles()
    assert set(roles) == {"developer", "qa", "appsec"}


def test_each_role_has_a_real_brief_and_contract():
    for rid, role in load_roles().items():
        assert role.id == rid
        assert len(role.brief) > 80, f"{rid} brief is too thin to be a lens"
        assert isinstance(role.contract, ArtifactKind)


def test_qa_owes_a_failing_test():
    assert load_roles()["qa"].contract is ArtifactKind.FAILING_TEST


def test_malformed_role_yaml_is_rejected(tmp_path):
    (tmp_path / "roles").mkdir()
    (tmp_path / "roles" / "broken.yaml").write_text("id: broken\nname: Broken\n")
    with pytest.raises(LibraryError, match="broken.yaml"):
        load_roles(tmp_path)
