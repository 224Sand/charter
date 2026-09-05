import yaml
from pathlib import Path

from charter.library import load_roles
from charter.skillgen import render_skill, write_skill


def test_skill_has_frontmatter_with_a_name():
    assert render_skill().startswith("---\nname: charter\n")


def test_skill_names_every_role_in_the_library():
    text = render_skill()
    for role in load_roles().values():
        assert role.name in text


def test_skill_states_the_loop_contract():
    text = render_skill()
    assert "charter_next" in text and "charter_submit" in text
    assert "keep calling" in text.lower()


def test_skill_includes_charter_init():
    text = render_skill()
    assert "charter_init" in text
    assert "idea" in text


def test_write_skill_creates_the_file(tmp_path):
    path = write_skill(tmp_path)
    assert path.is_file()
    assert path.name == "SKILL.md"
    assert path.read_text() == render_skill()


def test_render_skill_reads_from_custom_definitions_root(tmp_path):
    """Verify that render_skill generates from the provided definitions root,
    not a hardcoded list. Creates synthetic definitions with a unique role name
    and verifies that name appears in the output."""
    # Create definitions directory structure
    defs_root = tmp_path / "defs"
    roles_dir = defs_root / "roles"
    methods_dir = defs_root / "methodologies"
    roles_dir.mkdir(parents=True)
    methods_dir.mkdir(parents=True)

    # Write a custom role with a unique name
    unique_role_name = "UniqueTestRoleForVerification"
    role_def = {
        "id": "unique_test",
        "name": unique_role_name,
        "brief": "A test role to verify library-driven generation",
        "contract": "change_summary",
        "activates_on": ["all"]
    }
    (roles_dir / "unique_test.yaml").write_text(yaml.dump(role_def))

    # Write a custom methodology
    method_def = {
        "id": "test_method",
        "name": "Test Methodology",
        "phases": ["test_phase"],
        "roles": ["unique_test"]
    }
    (methods_dir / "test_method.yaml").write_text(yaml.dump(method_def))

    # Render with custom definitions
    output = render_skill(definitions_root=defs_root)

    # Verify the unique role name appears in the output
    assert unique_role_name in output, \
        f"Expected '{unique_role_name}' in rendered skill from custom definitions"

    # Verify the unique methodology ID appears in the initialization instructions
    assert "test_method" in output, \
        "Expected 'test_method' in rendered skill's methodology list"
