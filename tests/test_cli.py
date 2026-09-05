from typer.testing import CliRunner
from charter.cli import app

runner = CliRunner()


def test_init_reports_the_roster(tmp_path):
    result = runner.invoke(app, ["init", "an idea", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "developer" in result.stdout


def test_status_before_init_fails_clearly(tmp_path):
    result = runner.invoke(app, ["status", "--repo", str(tmp_path)])
    assert result.exit_code == 1
    assert "charter_init" in result.stdout


def test_gen_skill_writes_a_file(tmp_path):
    result = runner.invoke(app, ["gen-skill", "--dest", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "SKILL.md").is_file()
