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


def test_write_skill_creates_the_file(tmp_path):
    path = write_skill(tmp_path)
    assert path.is_file()
    assert path.name == "SKILL.md"
    assert path.read_text() == render_skill()
