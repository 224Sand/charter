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


def test_the_mcp_dependency_is_bounded_to_the_api_charter_targets():
    """An unbounded lower bound on a fast-moving SDK is how charter shipped
    broken: `mcp>=1.2` resolved to 2.x, whose decorator API this code does not
    use, and the failure was masked by tests running under a different
    interpreter that happened to have 1.x installed."""
    import re
    pyproject = (ROOT / "pyproject.toml").read_text()
    # Scope to the dependencies array. Matching any "mcp..." string in the file
    # picked up the "mcp" keyword once keywords were added, and passed on a
    # value that was never the dependency.
    deps = re.search(r"^dependencies = \[(.*?)^\]", pyproject, re.S | re.M).group(1)
    spec = re.search(r'"mcp([^"]*)"', deps).group(1)
    assert "<" in spec, f"mcp dependency {spec!r} has no upper bound"


def test_the_declared_mcp_api_is_the_one_the_code_uses():
    """Fails loudly against an SDK where the decorators charter relies on are
    gone, rather than at a stranger's first install."""
    from mcp.server import Server

    for decorator in ("list_tools", "call_tool"):
        assert hasattr(Server, decorator), (
            f"installed mcp has no Server.{decorator}; charter's server code "
            f"targets the 1.x decorator API")


def test_the_server_reports_charters_version_not_the_sdks():
    """Server() defaults to the mcp package's version, so an inspecting client
    was told charter was 1.29.1 -- the SDK's number, not the product's."""
    import asyncio
    from charter import __version__
    from charter.mcp_server import build_server

    server = build_server(ROOT)
    opts = server.create_initialization_options()
    assert opts.server_version == __version__, (
        f"server reports {opts.server_version}, package is {__version__}")
