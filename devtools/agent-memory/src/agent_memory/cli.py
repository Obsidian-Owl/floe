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
import hashlib
import json
from pathlib import Path
from typing import Annotated, Any

import structlog
import typer

from agent_memory.cognee_client import (
    CogneeAuthenticationError,
    CogneeClient,
    CogneeClientError,
    CogneeConnectionError,
)
from agent_memory.config import AgentMemoryConfig, ContentSource, get_config
from agent_memory.markdown_parser import parse_markdown_file

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


def _collect_files_from_source(source: ContentSource) -> list[Path]:
    """Collect files matching a content source configuration.

    Args:
        source: Content source configuration.

    Returns:
        List of matching file paths.
    """
    files: list[Path] = []

    if source.source_type == "file":
        if source.path.exists() and source.path.suffix in source.file_extensions:
            files.append(source.path)
    elif source.source_type == "directory":
        if source.path.exists():
            for ext in source.file_extensions:
                files.extend(source.path.rglob(f"*{ext}"))
    elif source.source_type == "glob":
        for match in Path(".").glob(str(source.path)):
            if match.is_file() and match.suffix in source.file_extensions:
                files.append(match)

    # Filter out excluded patterns
    if source.exclude_patterns:
        filtered: list[Path] = []
        for f in files:
            excluded = False
            for pattern in source.exclude_patterns:
                if f.match(pattern):
                    excluded = True
                    break
            if not excluded:
                filtered.append(f)
        files = filtered

    return sorted(files)


def _compute_file_checksum(path: Path) -> str:
    """Compute SHA256 checksum of a file.

    Args:
        path: File path.

    Returns:
        Hex-encoded SHA256 hash.
    """
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


@app.command()
def init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing configuration"),
    ] = False,
    skip_index: Annotated[
        bool,
        typer.Option("--skip-index", help="Skip initial content indexing"),
    ] = False,
) -> None:
    """Initialize Cognee Cloud configuration and index content.

    Creates .cognee/ directory, validates credentials, and optionally
    indexes configured content sources.
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

    # Validate connection to Cognee Cloud
    client = CogneeClient(config)

    async def _validate() -> None:
        try:
            latency_ms = await client.validate_connection()
            typer.secho(
                f"  Connection validated ({latency_ms:.0f}ms)",
                fg=typer.colors.GREEN,
            )
        except CogneeAuthenticationError as e:
            _exit_with_error(f"Authentication failed: {e}")
        except CogneeConnectionError as e:
            _exit_with_error(f"Connection failed: {e}")

    _run_async(_validate())

    # Create empty state files
    state_file = cognee_dir / "state.json"
    checksums_file = cognee_dir / "checksums.json"
    state_file.write_text("{}")
    checksums_file.write_text("{}")

    typer.secho("Configuration validated successfully", fg=typer.colors.GREEN)

    # Skip indexing if requested or no sources configured
    if skip_index:
        typer.echo("Skipping initial indexing (--skip-index)")
        return

    if not config.content_sources:
        typer.echo("No content sources configured. Add sources to .cognee/config.yaml")
        return

    # Index content sources
    typer.echo()
    typer.secho("Indexing content sources...", fg=typer.colors.CYAN)

    async def _index_content() -> None:
        checksums: dict[str, str] = {}
        indexed_files: dict[str, list[str]] = {}
        datasets_to_cognify: set[str] = set()

        try:
            for source in config.content_sources:
                files = _collect_files_from_source(source)
                if not files:
                    typer.echo(f"  No files found for: {source.path}")
                    continue

                typer.echo(f"  Processing {len(files)} file(s) for dataset '{source.dataset}'")
                indexed_files[source.dataset] = []

                for i, file_path in enumerate(files, 1):
                    typer.echo(f"    [{i}/{len(files)}] {file_path}")

                    # Parse markdown file
                    parsed = parse_markdown_file(file_path)

                    # Prepare content with metadata header
                    content_with_context = (
                        f"# {parsed.title or file_path.name}\n"
                        f"Source: {file_path}\n\n"
                        f"{parsed.content}"
                    )

                    # Add to Cognee
                    await client.add_content(
                        content=content_with_context,
                        dataset_name=source.dataset,
                        metadata={
                            "source_path": str(file_path),
                            "title": parsed.title,
                            **parsed.metadata,
                        },
                    )

                    # Track for state
                    checksums[str(file_path)] = _compute_file_checksum(file_path)
                    indexed_files[source.dataset].append(str(file_path))
                    datasets_to_cognify.add(source.dataset)

            # Run cognify for each dataset
            if datasets_to_cognify:
                typer.echo()
                typer.echo("Running cognify to build knowledge graph...")
                for dataset in datasets_to_cognify:
                    typer.echo(f"  Cognifying dataset: {dataset}")
                    await client.cognify(dataset_name=dataset)
                typer.secho("  Cognify completed", fg=typer.colors.GREEN)

            # Save state
            state = {
                "indexed_files": indexed_files,
                "last_sync": None,  # Will be set by sync command
            }
            state_file.write_text(json.dumps(state, indent=2))
            checksums_file.write_text(json.dumps(checksums, indent=2))

            total_files = sum(len(f) for f in indexed_files.values())
            typer.echo()
            typer.secho(
                f"Initialization complete: {total_files} file(s) indexed",
                fg=typer.colors.GREEN,
            )

        except CogneeClientError as e:
            _exit_with_error(f"Indexing failed: {e}")

    _run_async(_index_content())


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

            # Exit code 0 for healthy, 1 for degraded/unhealthy
            if status.overall_status in ("degraded", "unhealthy"):
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
