"""MCP surface.

Deliberately thin: all logic lives in the loop. `Handlers` is separated from
the transport so the tool behaviour is testable without an MCP client.
"""
import json
from pathlib import Path

from charter.kernel.methodology import UnknownMethodology, roster_for
from charter.library import load_methodologies, load_roles
from charter.loop.machine import Council
from charter.record.store import RecordStore


class Handlers:
    """The four charter tools, as plain functions returning JSON strings."""

    def __init__(self, repo: Path):
        self.repo = Path(repo)
        self.store = RecordStore(self.repo)

    def init(self, idea: str, methodology: str = "scrum") -> str:
        if self.store.exists():
            return self._error(
                f"charter already exists in this repository at {self.store.root} -- "
                "call charter_status to see the current build, or delete the state "
                "directory and try again")
        methodologies = load_methodologies()
        try:
            roster = roster_for(methodology, methodologies, load_roles())
        except UnknownMethodology as exc:
            return self._error(str(exc))
        self.store.init(roster, idea=idea,
                        phase=methodologies[methodology].phases[0])
        return json.dumps({
            "methodology": roster.methodology,
            "roles": roster.role_ids(),
            "state_dir": str(self.store.root),
        }, indent=2)

    def next(self) -> str:
        if not self.store.exists():
            return self._error(
                "no charter in this repository -- call charter_init first")
        return self._council().next().model_dump_json(indent=2)

    def submit(self, role: str, artifact: dict) -> str:
        if not self.store.exists():
            return self._error(
                "no charter in this repository -- call charter_init first")
        return self._council().submit(role, artifact).model_dump_json(indent=2)

    def status(self) -> str:
        if not self.store.exists():
            return self._error(
                "no charter in this repository -- call charter_init first")
        return self._council().status().model_dump_json(indent=2)

    def _council(self) -> Council:
        return Council(self.store, self.repo)

    def _error(self, message: str) -> str:
        return json.dumps({"error": message}, indent=2)


def build_server(repo: Path):
    """Wire the handlers onto an MCP server."""
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    handlers = Handlers(repo)
    server = Server("charter")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(name="charter_init",
                 description="Start a governed build in this repository.",
                 inputSchema={"type": "object", "properties": {
                     "idea": {"type": "string"},
                     "methodology": {"type": "string", "default": "scrum"}},
                     "required": ["idea"]}),
            Tool(name="charter_next",
                 description="Get the next role assignment and its contract.",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="charter_submit",
                 description="Submit a role's artifact for validation.",
                 inputSchema={"type": "object", "properties": {
                     "role": {"type": "string"},
                     "artifact": {"type": "object"}},
                     "required": ["role", "artifact"]}),
            Tool(name="charter_status",
                 description="Report roster, sign-offs and outstanding roles.",
                 inputSchema={"type": "object", "properties": {}}),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            fn = {"charter_init": handlers.init, "charter_next": handlers.next,
                  "charter_submit": handlers.submit,
                  "charter_status": handlers.status}[name]
        except KeyError:
            error_response = json.dumps({
                "error": f"unknown tool '{name}' -- available tools are: "
                "charter_init, charter_next, charter_submit, charter_status"
            }, indent=2)
            return [TextContent(type="text", text=error_response)]
        try:
            result = fn(**arguments)
        except TypeError as e:
            error_response = json.dumps({
                "error": f"invalid arguments for {name}: {str(e)}"
            }, indent=2)
            return [TextContent(type="text", text=error_response)]
        return [TextContent(type="text", text=result)]

    # Store references for testing (allows tests to call the real handlers)
    server._test_list_tools = list_tools
    server._test_call_tool = call_tool

    return server
