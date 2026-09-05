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


def _defs(tmp_path, *, roles: dict, methodologies: dict | None = None):
    """Write a synthetic definitions tree in the layout _load_dir expects."""
    for kind, items in (("roles", roles), ("methodologies", methodologies or {})):
        d = tmp_path / kind
        d.mkdir(exist_ok=True)
        for filename, body in items.items():
            (d / filename).write_text(body)
    return tmp_path


_ROLE = """
id: {id}
name: {name}
contract: change_summary
activates_on: [scrum]
brief: >-
  A brief long enough to read as a real lens rather than a label, describing what
  this role instinctively looks for and the question it always asks of an artifact.
"""


def test_a_yml_extension_is_loaded_not_silently_skipped(tmp_path):
    _defs(tmp_path, roles={"extra.yml": _ROLE.format(id="extra", name="Extra")})
    assert "extra" in load_roles(tmp_path)


def test_two_files_claiming_one_id_is_an_error_not_a_silent_overwrite(tmp_path):
    _defs(tmp_path, roles={
        "a_first.yaml": _ROLE.format(id="clash", name="First"),
        "b_second.yaml": _ROLE.format(id="clash", name="Second"),
    })
    with pytest.raises(LibraryError, match="duplicate id"):
        load_roles(tmp_path)


def test_an_unknown_key_in_a_definition_is_rejected(tmp_path):
    _defs(tmp_path, roles={
        "typo.yaml": _ROLE.format(id="typo", name="Typo") + "\nactivatesOn: [cicd]\n"})
    with pytest.raises(LibraryError, match="typo.yaml"):
        load_roles(tmp_path)
