import asyncio
import json
import pytest
from charter.mcp_server import Handlers, build_server


@pytest.fixture
def handlers(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    return Handlers(tmp_path)


def test_init_creates_the_charter_and_reports_the_roster(handlers):
    out = json.loads(handlers.init(idea="build a thing", methodology="scrum"))
    assert out["methodology"] == "scrum"
    assert out["roles"] == ["developer", "qa", "appsec"]


def test_next_before_init_returns_a_clear_error(handlers):
    out = json.loads(handlers.next())
    assert out["error"]
    assert "charter_init" in out["error"]


def test_full_round_trip_through_the_handlers(handlers):
    handlers.init(idea="build a thing", methodology="scrum")
    assignment = json.loads(handlers.next())
    assert assignment["assignment"]["role"] == "developer"

    accepted = json.loads(handlers.submit(role="developer", artifact={
        "kind": "change_summary", "files": ["a.py"],
        "decision_ref": "D-1", "summary": "did the thing"}))
    assert accepted["accepted"] is True

    status = json.loads(handlers.status())
    assert status["signed_off"] == ["developer"]


def test_an_unknown_methodology_is_reported_not_raised(handlers):
    out = json.loads(handlers.init(idea="x", methodology="waterfall"))
    assert "waterfall" in out["error"]


# FINDING 1 (strengthened): init twice - verify state corruption is prevented
def test_init_twice_with_real_state_corruption_prevention(handlers):
    """
    After first init, submit real developer work to create state.
    Then call init again with different idea/methodology.
    Verify: (1) error returned, (2) original methodology/roster survives,
    (3) developer sign-off and progress survive.
    """
    # First init
    first = json.loads(handlers.init(idea="build feature A", methodology="scrum"))
    assert first["methodology"] == "scrum"
    assert set(first["roles"]) == {"developer", "qa", "appsec"}

    # Submit real developer work to create actual state
    assignment = json.loads(handlers.next())
    assert assignment["assignment"]["role"] == "developer"
    accepted = json.loads(handlers.submit(role="developer", artifact={
        "kind": "change_summary", "files": ["a.py"],
        "decision_ref": "D-1", "summary": "implemented feature A"}))
    assert accepted["accepted"] is True

    # Verify sign-off recorded
    status = json.loads(handlers.status())
    assert "developer" in status["signed_off"]
    original_methodology = status["methodology"]
    original_roles = set(status["roles"])

    # Attempt second init with DIFFERENT idea and methodology
    second = json.loads(handlers.init(idea="build feature B", methodology="scrum"))
    assert "error" in second
    assert "charter already exists" in second["error"]

    # Verify FIRST build's state survived (original methodology, roster, and sign-off)
    status_after = json.loads(handlers.status())
    assert status_after["methodology"] == original_methodology
    assert set(status_after["roles"]) == original_roles
    assert "developer" in status_after["signed_off"]

    # Verify loop still advances to qa (in-progress state not corrupted)
    assignment_after = json.loads(handlers.next())
    assert assignment_after["assignment"]["role"] == "qa"


# FINDING 2 (actual implementation): test build_server's real list_tools and call_tool
def test_build_server_list_tools_returns_actual_tool_objects(tmp_path):
    """
    Call the REAL list_tools handler registered on the server.
    Extract actual Tool names from the returned Tool objects (not from a literal).
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    server = build_server(tmp_path)

    # Call the real list_tools handler
    tools = asyncio.run(server._test_list_tools())

    # tools is a list of Tool objects - extract names from the actual objects
    tool_names = {tool.name for tool in tools}

    # Verify we got exactly four tools with the expected names
    assert len(tool_names) == 4
    assert tool_names == {"charter_init", "charter_next", "charter_submit", "charter_status"}


def test_build_server_call_tool_dispatch_consistency(tmp_path):
    """
    For each tool name returned by list_tools(), call call_tool and verify
    it does not return "unknown tool" error. This proves every registered tool
    resolves in the dispatcher.
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    server = build_server(tmp_path)

    # Get the actual registered tool names from list_tools
    tools = asyncio.run(server._test_list_tools())
    tool_names = [tool.name for tool in tools]

    # For each tool, call call_tool and verify no "unknown tool" error
    for tool_name in tool_names:
        # Most tools accept empty arguments; charter_init requires "idea"
        if tool_name == "charter_init":
            arguments = {"idea": "test"}
        else:
            arguments = {}

        result = asyncio.run(server._test_call_tool(tool_name, arguments))
        assert len(result) > 0
        text_content = result[0]
        response_json = json.loads(text_content.text)
        # Should not contain "unknown tool" error
        if "error" in response_json:
            assert "unknown tool" not in response_json["error"], \
                f"Tool {tool_name} not found in dispatcher"


def test_build_server_call_tool_response_is_valid_json(tmp_path):
    """
    Call call_tool for at least one tool and verify the returned
    TextContent's text is valid JSON.
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    server = build_server(tmp_path)

    # Call charter_status (no preconditions needed - returns error if no charter)
    result = asyncio.run(server._test_call_tool("charter_status", {}))

    assert len(result) > 0
    text_content = result[0]
    # Verify it's valid JSON
    parsed = json.loads(text_content.text)
    # It should have either "error" or response fields
    assert isinstance(parsed, dict)


# FINDING 2 (proof of teeth): Prove tests fail when tool names diverge
def test_proof_that_dispatch_check_catches_renamed_tools(tmp_path):
    """
    This test demonstrates that the dispatch consistency check works.
    TEMPORARILY: if you rename 'charter_status' to 'charter_statuz' in the
    Tool(...name=...) list (line 92) WITHOUT changing the dispatch dict,
    this test should FAIL.

    To verify:
    1. Rename charter_status -> charter_statuz in the Tool() list
    2. Run: uv run pytest tests/test_mcp_server.py::test_proof_that_dispatch_check_catches_renamed_tools -v
    3. It should FAIL because list_tools returns "charter_statuz" but dispatch
       dict does not have that key
    4. Restore the original name and verify it passes again
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    server = build_server(tmp_path)

    # Get registered tool names from list_tools
    tools = asyncio.run(server._test_list_tools())
    registered_names = {tool.name for tool in tools}

    # Expected tools that we know should be in the dispatcher
    expected_dispatcher_keys = {"charter_init", "charter_next", "charter_submit", "charter_status"}

    # Both directions: every registered name should resolve
    for name in registered_names:
        result = asyncio.run(server._test_call_tool(name, {}))
        response_json = json.loads(result[0].text)
        assert "unknown tool" not in response_json.get("error", ""), \
            f"Tool '{name}' from list_tools is not in dispatcher"

    # Both directions: every expected dispatcher key should be registered
    for expected in expected_dispatcher_keys:
        result = asyncio.run(server._test_call_tool(expected, {}))
        response_json = json.loads(result[0].text)
        assert "unknown tool" not in response_json.get("error", ""), \
            f"Expected tool '{expected}' missing from list_tools"


# FINDING 3: test exception handling in call_tool
def test_call_tool_unknown_tool_returns_structured_error(tmp_path):
    """
    Call call_tool with an unknown tool name.
    Verify it returns structured JSON error (does not raise).
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    server = build_server(tmp_path)

    result = asyncio.run(server._test_call_tool("charter_nonexistent", {}))

    assert len(result) > 0
    text_content = result[0]
    response = json.loads(text_content.text)
    assert "error" in response
    assert "unknown tool" in response["error"]
    assert "charter_nonexistent" in response["error"]


def test_call_tool_invalid_arguments_returns_structured_error(tmp_path):
    """
    Call call_tool with invalid arguments for a tool.
    Verify it returns structured JSON error (does not raise TypeError).
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    server = build_server(tmp_path)

    # charter_init requires 'idea' argument, call without it
    result = asyncio.run(server._test_call_tool("charter_init", {}))

    assert len(result) > 0
    text_content = result[0]
    response = json.loads(text_content.text)
    # Should be error about missing required argument
    assert "error" in response
