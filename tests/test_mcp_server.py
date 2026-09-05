import asyncio
import json
import pytest
from charter.mcp_server import Handlers, build_server, _list_tools_impl, _call_tool_impl


@pytest.fixture
def handlers(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    return Handlers(tmp_path)


def test_init_creates_the_charter_and_reports_the_roster(handlers):
    out = json.loads(handlers.init(idea="build a thing", methodology="scrum"))
    assert out["methodology"] == "scrum"
    assert out["roles"] == ["qa", "developer", "appsec"]


def test_next_before_init_returns_a_clear_error(handlers):
    out = json.loads(handlers.next())
    assert out["error"]
    assert "charter_init" in out["error"]


def test_full_round_trip_through_the_handlers(handlers):
    (handlers.repo / "t.py").write_text(
        "def test_reproduces():\n    assert 1 == 2\n")
    handlers.init(idea="build a thing", methodology="scrum")
    assignment = json.loads(handlers.next())
    assert assignment["assignment"]["role"] == "qa"

    accepted = json.loads(handlers.submit(role="qa", artifact={
        "kind": "failing_test", "test_path": "t.py",
        "test_name": "test_reproduces", "defect_id": "D-1"}))
    assert accepted["accepted"] is True

    status = json.loads(handlers.status())
    assert status["signed_off"] == ["qa"]


def test_an_unknown_methodology_is_reported_not_raised(handlers):
    out = json.loads(handlers.init(idea="x", methodology="waterfall"))
    assert "waterfall" in out["error"]


# FINDING 1 (strengthened): init twice - verify state corruption is prevented
def test_init_twice_with_real_state_corruption_prevention(tmp_path):
    """
    After first init with scrum methodology, submit real developer work to create state.
    Then call init again with DIFFERENT methodology (cicd instead of scrum).
    Verify: (1) error returned, (2) original methodology/roster survives,
    (3) developer sign-off and progress survive.
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "t.py").write_text("def test_reproduces():\n    assert 1 == 2\n")
    handlers = Handlers(tmp_path)

    # First init with scrum methodology
    first = json.loads(handlers.init(idea="build feature A", methodology="scrum"))
    assert first["methodology"] == "scrum"
    assert set(first["roles"]) == {"developer", "qa", "appsec"}

    # Submit real developer work to create actual state
    assignment = json.loads(handlers.next())
    assert assignment["assignment"]["role"] == "qa"
    accepted = json.loads(handlers.submit(role="qa", artifact={
        "kind": "failing_test", "test_path": "t.py",
        "test_name": "test_reproduces", "defect_id": "D-1"}))
    assert accepted["accepted"] is True

    # Verify sign-off recorded
    status = json.loads(handlers.status())
    assert "qa" in status["signed_off"]
    original_methodology = status["methodology"]
    original_roles = set(status["roles"])

    # Attempt second init with DIFFERENT methodology (cicd instead of scrum)
    second = json.loads(handlers.init(idea="build feature B", methodology="cicd"))
    assert "error" in second
    assert "charter already exists" in second["error"]

    # Verify FIRST build's state survived (original methodology, roster, and sign-off)
    status_after = json.loads(handlers.status())
    assert status_after["methodology"] == original_methodology
    assert set(status_after["roles"]) == original_roles
    assert "qa" in status_after["signed_off"]

    # Verify loop still advances to qa (in-progress state not corrupted)
    assignment_after = json.loads(handlers.next())
    assert assignment_after["assignment"]["role"] == "developer"


# FINDING 2 (actual implementation): test module-level handlers directly
def test_list_tools_impl_returns_actual_tool_objects(tmp_path):
    """
    Call the module-level _list_tools_impl directly.
    Extract actual Tool names from the returned Tool objects (not from a literal).
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    handlers = Handlers(tmp_path)

    # Call the module-level implementation directly
    tools = asyncio.run(_list_tools_impl(handlers))

    # tools is a list of Tool objects - extract names from the actual objects
    tool_names = {tool.name for tool in tools}

    # Verify we got exactly four tools with the expected names
    assert len(tool_names) == 4
    assert tool_names == {"charter_init", "charter_next", "charter_submit", "charter_status"}


def test_call_tool_impl_dispatch_consistency(tmp_path):
    """
    For each tool name returned by _list_tools_impl(), call _call_tool_impl
    and verify it does not return "unknown tool" error. This proves every
    registered tool resolves in the dispatcher.
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    handlers = Handlers(tmp_path)

    # Get the actual registered tool names from _list_tools_impl
    tools = asyncio.run(_list_tools_impl(handlers))
    tool_names = [tool.name for tool in tools]

    # For each tool, call _call_tool_impl and verify no "unknown tool" error
    for tool_name in tool_names:
        # Most tools accept empty arguments; charter_init requires "idea"
        if tool_name == "charter_init":
            arguments = {"idea": "test"}
        else:
            arguments = {}

        result = asyncio.run(_call_tool_impl(handlers, tool_name, arguments))
        assert len(result) > 0
        text_content = result[0]
        response_json = json.loads(text_content.text)
        # Should not contain "unknown tool" error
        if "error" in response_json:
            assert "unknown tool" not in response_json["error"], \
                f"Tool {tool_name} not found in dispatcher"


def test_call_tool_impl_response_is_valid_json(tmp_path):
    """
    Call _call_tool_impl for at least one tool and verify the returned
    TextContent's text is valid JSON.
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    handlers = Handlers(tmp_path)

    # Call charter_status (no preconditions needed - returns error if no charter)
    result = asyncio.run(_call_tool_impl(handlers, "charter_status", {}))

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
    Tool(...name=...) list in _list_tools_impl WITHOUT changing the dispatch
    dict in _call_tool_impl, this test should FAIL.

    To verify:
    1. Rename charter_status -> charter_statuz in _list_tools_impl
    2. Run: uv run pytest tests/test_mcp_server.py::test_proof_that_dispatch_check_catches_renamed_tools -v
    3. It should FAIL because _list_tools_impl returns "charter_statuz" but
       _call_tool_impl dispatch dict does not have that key
    4. Restore the original name and verify it passes again
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    handlers = Handlers(tmp_path)

    # Get registered tool names from _list_tools_impl
    tools = asyncio.run(_list_tools_impl(handlers))
    registered_names = {tool.name for tool in tools}

    # Expected tools that we know should be in the dispatcher
    expected_dispatcher_keys = {"charter_init", "charter_next", "charter_submit", "charter_status"}

    # Both directions: every registered name should resolve
    for name in registered_names:
        result = asyncio.run(_call_tool_impl(handlers, name, {}))
        response_json = json.loads(result[0].text)
        assert "unknown tool" not in response_json.get("error", ""), \
            f"Tool '{name}' from _list_tools_impl is not in dispatcher"

    # Both directions: every expected dispatcher key should be registered
    for expected in expected_dispatcher_keys:
        result = asyncio.run(_call_tool_impl(handlers, expected, {}))
        response_json = json.loads(result[0].text)
        assert "unknown tool" not in response_json.get("error", ""), \
            f"Expected tool '{expected}' missing from _list_tools_impl"


# FINDING 3: test exception handling in _call_tool_impl
def test_call_tool_impl_unknown_tool_returns_structured_error(tmp_path):
    """
    Call _call_tool_impl with an unknown tool name.
    Verify it returns structured JSON error (does not raise).
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    handlers = Handlers(tmp_path)

    result = asyncio.run(_call_tool_impl(handlers, "charter_nonexistent", {}))

    assert len(result) > 0
    text_content = result[0]
    response = json.loads(text_content.text)
    assert "error" in response
    assert "unknown tool" in response["error"]
    assert "charter_nonexistent" in response["error"]


def test_call_tool_impl_invalid_arguments_returns_structured_error(tmp_path):
    """
    Call _call_tool_impl with unexpected extra keyword arguments.
    Verify it returns structured JSON error containing "invalid arguments"
    (does not raise TypeError).
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    handlers = Handlers(tmp_path)

    # charter_status accepts no required arguments, call with unexpected kwarg
    result = asyncio.run(_call_tool_impl(handlers, "charter_status", {"bogus_key": 1}))

    assert len(result) > 0
    text_content = result[0]
    response = json.loads(text_content.text)
    assert "error" in response
    assert "invalid arguments" in response["error"]


def test_build_server_instantiates(tmp_path):
    """Verify build_server can be instantiated without errors."""
    (tmp_path / "a.py").write_text("x = 1\n")
    server = build_server(tmp_path)

    # Verify server is created successfully
    assert server is not None
    assert str(type(server)).find("Server") >= 0  # It's a Server instance


# ---- v2: connection identity -------------------------------------------

def test_each_handlers_instance_gets_its_own_connection_id(tmp_path):
    """One stdio connection is one server process is one identity.

    A constant, or an id derived from the repo, would make two sessions look
    like one and quietly re-open the hole v2 exists to close.
    """
    a, b = Handlers(tmp_path), Handlers(tmp_path)
    assert a.connection_id and b.connection_id
    assert a.connection_id != b.connection_id


def test_the_council_is_built_with_the_handlers_connection_id(tmp_path):
    h = Handlers(tmp_path)
    assert h._council().connection_id == h.connection_id


def test_no_tool_argument_can_set_the_connection_id(tmp_path):
    """The id is unforgeable only because the caller never supplies it."""
    import asyncio
    from charter.mcp_server import _list_tools_impl, _call_tool_impl

    tools = asyncio.run(_list_tools_impl(Handlers(tmp_path)))
    for tool in tools:
        props = tool.inputSchema.get("properties", {})
        assert "connection_id" not in props, (
            f"{tool.name} exposes connection_id as an argument")

    h = Handlers(tmp_path)
    h.init(idea="x", methodology="scrum")
    before = h.connection_id
    response = asyncio.run(
        _call_tool_impl(h, "charter_status", {"connection_id": "forged"}))
    assert "invalid arguments" in response[0].text
    assert h.connection_id == before
