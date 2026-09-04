import pytest
from charter.kernel.methodology import roster_for, UnknownMethodology
from charter.library import load_methodologies, load_roles


@pytest.fixture
def defs():
    return load_methodologies(), load_roles()


def test_scrum_roster_is_deterministic(defs):
    m, r = defs
    assert roster_for("scrum", m, r).role_ids() == roster_for("scrum", m, r).role_ids()


def test_roster_only_contains_roles_the_methodology_activates(defs):
    m, r = defs
    roster = roster_for("scrum", m, r)
    for role in roster.roles:
        assert "scrum" in role.activates_on


def test_roster_order_follows_the_methodology_declaration(defs):
    m, r = defs
    assert roster_for("scrum", m, r).role_ids() == m["scrum"].roles


def test_unknown_methodology_is_rejected_not_guessed(defs):
    m, r = defs
    with pytest.raises(UnknownMethodology, match="waterfall"):
        roster_for("waterfall", m, r)


def test_methodology_naming_a_missing_role_is_an_error(defs):
    m, r = defs
    del r["qa"]
    with pytest.raises(UnknownMethodology, match="qa"):
        roster_for("scrum", m, r)


def test_activates_on_filter_excludes_roles_that_dont_activate(tmp_path):
    """Prove the activates_on filter actually excludes roles that don't activate.

    This test creates a synthetic definitions tree where a methodology names
    multiple roles, but only some declare that methodology in their activates_on.
    The filter must exclude those that don't activate, or this test fails.
    """
    # Create directories
    roles_dir = tmp_path / "roles"
    roles_dir.mkdir()
    methodologies_dir = tmp_path / "methodologies"
    methodologies_dir.mkdir()

    # Create a role that activates on "test_method"
    (roles_dir / "active.yaml").write_text(
        "id: active\n"
        "name: Active Role\n"
        "brief: Activates on test_method.\n"
        "contract: change_summary\n"
        "activates_on: [test_method]\n"
    )

    # Create a role that does NOT activate on "test_method" (only on "scrum")
    (roles_dir / "inactive.yaml").write_text(
        "id: inactive\n"
        "name: Inactive Role\n"
        "brief: Does not activate on test_method.\n"
        "contract: failing_test\n"
        "activates_on: [scrum]\n"
    )

    # Create a methodology that names both roles
    (methodologies_dir / "test_method.yaml").write_text(
        "id: test_method\n"
        "name: Test Method\n"
        "phases: [testing]\n"
        "roles: [active, inactive]\n"
    )

    m = load_methodologies(tmp_path)
    r = load_roles(tmp_path)

    # The roster should only contain "active", not "inactive"
    roster = roster_for("test_method", m, r)
    assert roster.role_ids() == ["active"]
    assert "inactive" not in roster.role_ids()
