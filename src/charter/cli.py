"""Command line entry point."""
import json
from pathlib import Path

import typer

from charter.mcp_server import Handlers, build_server
from charter.skillgen import write_skill

app = typer.Typer(add_completion=False, help="Governed multi-role delivery.")


@app.command()
def init(
    idea: str,
    methodology: str = typer.Option("scrum", help="scrum or cicd"),
    repo: Path = typer.Option(Path("."), help="target repository"),
) -> None:
    """Start a governed build in this repository."""
    out = json.loads(Handlers(repo).init(idea=idea, methodology=methodology))
    if "error" in out:
        typer.echo(out["error"])
        raise typer.Exit(1)
    typer.echo(f"methodology: {out['methodology']}")
    typer.echo(f"roles:       {', '.join(out['roles'])}")
    typer.echo(f"state:       {out['state_dir']}")


@app.command()
def status(repo: Path = typer.Option(Path("."), help="target repository")) -> None:
    """Show roster, sign-offs and outstanding roles."""
    out = json.loads(Handlers(repo).status())
    if "error" in out:
        typer.echo(out["error"])
        raise typer.Exit(1)
    typer.echo(json.dumps(out, indent=2))


@app.command("gen-skill")
def gen_skill(dest: Path = typer.Option(..., help="directory for SKILL.md")) -> None:
    """Generate the bootstrap Claude Skill from the role library."""
    typer.echo(str(write_skill(dest)))


@app.command()
def serve(repo: Path = typer.Option(Path("."), help="target repository")) -> None:
    """Run the MCP server on stdio."""
    import asyncio

    from mcp.server.stdio import stdio_server

    async def _run() -> None:
        server = build_server(repo)
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    app()
