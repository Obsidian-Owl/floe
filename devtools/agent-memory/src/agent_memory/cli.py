"""CLI entry point for agent-memory commands.

Provides Typer-based CLI with async execution wrapper for Cognee operations.

Usage:
    agent-memory --help
    agent-memory init
    agent-memory health
    agent-memory sync [--dataset NAME]
    agent-memory search QUERY [--type TYPE] [--top-k N]
    agent-memory coverage
    agent-memory drift
    agent-memory repair [--dry-run]
    agent-memory reset [--confirm]
    agent-memory test

Example:
    >>> agent-memory init
    >>> agent-memory health
    >>> agent-memory search "how do plugins work"
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Any

import structlog
import typer

from agent_memory.cognee_client import CogneeClient, CogneeClientError
from agent_memory.config import AgentMemoryConfig, get_config

logger = structlog.get_logger(__name__)

app = typer.Typer(
    name="agent-memory",
    help="Cognee-based persistent memory for AI coding agents.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine synchronously.

    Args:
        coro: Async coroutine to execute.

    Returns:
        Result of the coroutine.
    """
    return asyncio.run(coro)


def _load_config() -> AgentMemoryConfig | None:
    """Load configuration, returning None on validation error.

    Returns:
        Validated config or None if validation fails.
    """
    try:
        return get_config()
    except Exception as e:
        typer.secho(f"Configuration error: {e}", fg=typer.colors.RED, err=True)
        typer.secho(
            "Ensure COGNEE_API_KEY and OPENAI_API_KEY are set in environment.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return None


def _exit_with_error(message: str, code: int = 1) -> None:
    """Print error message and exit.

    Args:
        message: Error message to display.
        code: Exit code (default 1).
    """
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=code)


@app.command()
def init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing configuration"),
    ] = False,
) -> None:
    """Initialize Cognee Cloud configuration.

    Creates .cognee/ directory with config.yaml and validates credentials.
    """
    cognee_dir = Path(".cognee")

    if cognee_dir.exists() and not force:
        typer.secho(
            ".cognee/ directory already exists. Use --force to reinitialize.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0)

    # Create directory structure
    cognee_dir.mkdir(exist_ok=True)

    # Validate config can be loaded
    config = _load_config()
    if config is None:
        _exit_with_error("Failed to load configuration")
        return

    typer.secho("Initialized .cognee/ directory", fg=typer.colors.GREEN)
    typer.echo(f"  Cognee API URL: {config.cognee_api_url}")
    typer.echo(f"  LLM Provider: {config.llm_provider}")

    # Create empty state files
    (cognee_dir / "state.json").write_text("{}")
    (cognee_dir / "checksums.json").write_text("{}")

    typer.secho("Configuration validated successfully", fg=typer.colors.GREEN)


@app.command()
def health() -> None:
    """Check Cognee Cloud and LLM provider connectivity.

    Validates API keys and reports component-level status.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _check_health() -> None:
        try:
            status = await client.health_check()

            # Overall status with color
            color = {
                "healthy": typer.colors.GREEN,
                "degraded": typer.colors.YELLOW,
                "unhealthy": typer.colors.RED,
            }.get(status.overall_status, typer.colors.WHITE)

            typer.secho(f"Overall Status: {status.overall_status.upper()}", fg=color)
            typer.echo()

            # Component details
            components = [
                ("Cognee Cloud", status.cognee_cloud),
                ("LLM Provider", status.llm_provider),
                ("Local State", status.local_state),
            ]

            for name, comp in components:
                comp_color = {
                    "healthy": typer.colors.GREEN,
                    "degraded": typer.colors.YELLOW,
                    "unhealthy": typer.colors.RED,
                }.get(comp.status, typer.colors.WHITE)

                typer.secho(f"  {name}: {comp.status}", fg=comp_color)
                if comp.message:
                    typer.echo(f"    {comp.message}")
                if comp.response_time_ms is not None:
                    typer.echo(f"    Response time: {comp.response_time_ms}ms")

            if status.overall_status == "unhealthy":
                raise typer.Exit(code=1)

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_check_health())


@app.command()
def sync(
    dataset: Annotated[
        str | None,
        typer.Option("--dataset", "-d", help="Specific dataset to sync"),
    ] = None,
    cognify: Annotated[
        bool,
        typer.Option("--cognify", help="Run cognify after adding content"),
    ] = True,
) -> None:
    """Sync content sources to Cognee Cloud.

    Indexes configured content sources and optionally processes with cognify.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    if not config.content_sources:
        typer.secho(
            "No content sources configured. Add sources to .cognee/config.yaml",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0)

    client = CogneeClient(config)

    async def _sync() -> None:
        try:
            sources = config.content_sources
            if dataset:
                sources = [s for s in sources if s.dataset == dataset]
                if not sources:
                    _exit_with_error(f"No sources found for dataset: {dataset}")
                    return

            typer.echo(f"Syncing {len(sources)} content source(s)...")

            for source in sources:
                typer.echo(f"  Processing: {source.path} -> {source.dataset}")
                # Actual sync will be implemented in ops modules
                # For now, placeholder logging

            if cognify:
                typer.echo("Running cognify...")
                await client.cognify(dataset_name=dataset)
                typer.secho("Cognify completed", fg=typer.colors.GREEN)

            typer.secho("Sync completed successfully", fg=typer.colors.GREEN)

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_sync())


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query string")],
    search_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Search type: GRAPH_COMPLETION, SUMMARIES, INSIGHTS, CHUNKS",
        ),
    ] = "GRAPH_COMPLETION",
    top_k: Annotated[
        int,
        typer.Option("--top-k", "-k", help="Maximum number of results"),
    ] = 10,
) -> None:
    """Search the knowledge graph.

    Queries indexed content using Cognee's graph-based search.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _search() -> None:
        try:
            result = await client.search(query, search_type=search_type, top_k=top_k)

            typer.echo(f"Query: {result.query}")
            typer.echo(f"Search type: {result.search_type}")
            typer.echo(f"Results: {result.total_count} (in {result.execution_time_ms}ms)")
            typer.echo()

            if not result.results:
                typer.secho("No results found", fg=typer.colors.YELLOW)
                return

            for i, item in enumerate(result.results, 1):
                typer.secho(f"[{i}]", fg=typer.colors.CYAN, nl=False)
                if item.source_path:
                    typer.echo(f" {item.source_path}")
                else:
                    typer.echo()

                typer.echo(f"    {item.content[:200]}...")
                if item.relevance_score > 0:
                    typer.echo(f"    Score: {item.relevance_score:.3f}")
                typer.echo()

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_search())


@app.command()
def coverage() -> None:
    """Show coverage report comparing indexed vs filesystem.

    Reports files indexed, missing, and orphaned.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    typer.echo("Coverage report:")
    typer.secho("  Not yet implemented - requires ops/coverage.py", fg=typer.colors.YELLOW)
    # Will be implemented in Phase 4


@app.command()
def drift() -> None:
    """Detect drift between indexed content and filesystem.

    Identifies files that have changed since indexing.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    typer.echo("Drift detection:")
    typer.secho("  Not yet implemented - requires ops/drift.py", fg=typer.colors.YELLOW)
    # Will be implemented in Phase 4


@app.command()
def repair(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be repaired without making changes"),
    ] = False,
) -> None:
    """Repair drift issues by re-indexing changed files.

    Re-indexes files detected as stale by drift detection.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    if dry_run:
        typer.echo("Repair (dry-run):")
    else:
        typer.echo("Repair:")
    typer.secho("  Not yet implemented - requires ops/repair.py", fg=typer.colors.YELLOW)
    # Will be implemented in Phase 4


@app.command()
def reset(
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help="Confirm reset without prompting"),
    ] = False,
) -> None:
    """Reset knowledge graph by deleting all datasets.

    WARNING: This is destructive and cannot be undone.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    if not confirm:
        confirmed = typer.confirm(
            "This will delete ALL indexed content. Are you sure?",
            default=False,
        )
        if not confirmed:
            typer.echo("Reset cancelled")
            raise typer.Exit(code=0)

    client = CogneeClient(config)

    async def _reset() -> None:
        try:
            datasets = await client.list_datasets()
            if not datasets:
                typer.echo("No datasets to delete")
                return

            typer.echo(f"Deleting {len(datasets)} dataset(s)...")
            for ds in datasets:
                typer.echo(f"  Deleting: {ds}")
                await client.delete_dataset(ds)

            # Clear local state
            state_file = Path(".cognee/state.json")
            checksums_file = Path(".cognee/checksums.json")
            if state_file.exists():
                state_file.write_text("{}")
            if checksums_file.exists():
                checksums_file.write_text("{}")

            typer.secho("Reset completed", fg=typer.colors.GREEN)

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_reset())


@app.command()
def test() -> None:
    """Run knowledge graph test queries.

    Validates indexed content with sample queries.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    typer.echo("Running test queries...")
    typer.secho("  Not yet implemented - requires test infrastructure", fg=typer.colors.YELLOW)
    # Will be implemented in Phase 5


@app.callback()
def main(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
) -> None:
    """Cognee-based persistent memory for AI coding agents.

    Provides commands to initialize, sync, search, and manage the knowledge graph
    used by AI coding agents for context recovery across sessions.
    """
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(0),  # DEBUG
        )


if __name__ == "__main__":
    app()
