"""The plugin bundle must not drift from the role library.

charter's whole claim is that the instructions an agent reads and the rules it
is held to cannot drift apart, because the skill is generated from the same
definitions the kernel enforces. That guarantee is worthless if the copy we
SHIP is a stale snapshot, so it is checked here rather than trusted.
"""
import json
from pathlib import Path

from charter.skillgen import render_skill

ROOT = Path(__file__).resolve().parent.parent
BUNDLED_SKILL = ROOT / "skills" / "charter" / "SKILL.md"


def test_the_bundled_skill_matches_the_role_library():
    assert BUNDLED_SKILL.is_file(), f"{BUNDLED_SKILL} is missing"
    assert BUNDLED_SKILL.read_text() == render_skill(), (
        "The shipped skill is stale: it no longer matches what the role library "
        "renders. Regenerate it with `charter gen-skill --dest skills/charter`."
    )


def test_plugin_manifest_version_matches_the_package():
    from charter import __version__

    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["version"] == __version__, (
        f"plugin.json says {manifest['version']}, package says {__version__}"
    )


def test_marketplace_entry_matches_the_plugin_manifest():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    entries = [p for p in market["plugins"] if p["name"] == plugin["name"]]
    assert entries, f"marketplace.json has no entry named {plugin['name']!r}"
    assert entries[0]["version"] == plugin["version"]


def test_mcp_config_registers_the_charter_server():
    cfg = json.loads((ROOT / ".mcp.json").read_text())
    server = cfg["mcpServers"]["charter"]
    assert server["type"] == "stdio", "charter governs local files; it cannot be remote"
    assert "serve" in server["args"]


def test_the_independence_statement_names_its_own_limits():
    """Charter's ethic is claiming exactly what is proven.

    A statement that only advertises the guarantee, with no mention of what
    defeats it, is the overclaim this project keeps catching in itself.
    """
    from charter.loop.machine import INDEPENDENCE_STATEMENT

    lowered = INDEPENDENCE_STATEMENT.lower()
    assert "separate process" in lowered, "must say what it does prove"
    assert "not proof" in lowered or "does not prove" in lowered, (
        "must say what it does NOT prove")
    for limit in ("restart", "clicking through"):
        assert limit in lowered, f"limit {limit!r} is not disclosed"
