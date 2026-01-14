"""CLI entry point for agent-memory commands.

Usage:
    agent-memory --help
    agent-memory init
    agent-memory health
    agent-memory sync
    agent-memory search QUERY
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="agent-memory",
    help="Cognee-based persistent memory for AI coding agents.",
    no_args_is_help=True,
)


@app.command()
def init() -> None:
    """Initialize Cognee Cloud configuration."""
    typer.echo("init command - not yet implemented")


@app.command()
def health() -> None:
    """Check Cognee Cloud connectivity."""
    typer.echo("health command - not yet implemented")


@app.command()
def sync() -> None:
    """Sync content to Cognee Cloud."""
    typer.echo("sync command - not yet implemented")


@app.command()
def search(query: str) -> None:
    """Search indexed content."""
    typer.echo(f"search command for '{query}' - not yet implemented")


if __name__ == "__main__":
    app()
