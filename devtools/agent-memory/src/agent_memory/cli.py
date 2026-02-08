"""CLI entry point for agent-memory commands.

Provides Typer-based CLI with async execution wrapper for Cognee operations.

Usage:
    agent-memory --help
    agent-memory init
    agent-memory health
    agent-memory sync [--dataset NAME]
    agent-memory search QUERY [--type TYPE] [--top-k N]
    agent-memory codify [--pattern GLOB] [--progress] [--dry-run]
    agent-memory coverage
    agent-memory drift
    agent-memory repair [--dry-run]
    agent-memory reset [--confirm]
    agent-memory test [--verbose] [--threshold N]
    agent-memory session-save [--issues IDS] [--decisions DESCS]
    agent-memory session-recover --work-area TOPIC

Example:
    >>> agent-memory init
    >>> agent-memory health
    >>> agent-memory search "how do plugins work"
    >>> agent-memory codify --progress
    >>> agent-memory session-save --issues "FLO-123" --summary "Implemented auth"
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
from agent_memory.docstring_extractor import DocstringEntry, extract_docstrings
from agent_memory.markdown_parser import ParsedContent, parse_markdown_file

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


def _collect_python_files(
    patterns: list[str], exclude_patterns: list[str] | None = None
) -> list[Path]:
    """Collect Python files matching glob patterns.

    Args:
        patterns: List of glob patterns (e.g., ["packages/*/src/**/*.py"]).
        exclude_patterns: Optional patterns to exclude.

    Returns:
        Sorted list of matching Python file paths.
    """
    files: list[Path] = []
    exclude = exclude_patterns or []

    for pattern in patterns:
        for match in Path(".").glob(pattern):
            if match.is_file() and match.suffix == ".py":
                # Check exclusions
                excluded = False
                for exc_pattern in exclude:
                    if match.match(exc_pattern):
                        excluded = True
                        break
                if not excluded:
                    files.append(match)

    # Deduplicate and sort
    return sorted(set(files))


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
    progress: Annotated[
        bool,
        typer.Option("--progress", "-p", help="Show progress bar during indexing"),
    ] = False,
    resume: Annotated[
        bool,
        typer.Option("--resume", "-r", help="Resume from last checkpoint"),
    ] = False,
) -> None:
    """Initialize Cognee Cloud configuration and index content.

    Creates .cognee/ directory, validates credentials, and optionally
    indexes configured content sources.

    Use --progress to show a progress bar during indexing.
    Use --resume to continue from the last checkpoint if interrupted.
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
    typer.echo(f"  Deployment Mode: {config.cognee_deployment_mode}")
    if config.cognee_deployment_mode == "cloud":
        typer.secho(
            "  Note: Cognee Cloud does not support memify. Use self-hosted for full features.",
            fg=typer.colors.YELLOW,
        )
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

    # Load checkpoint if resuming
    checkpoint_file = cognee_dir / "checkpoint.json"
    completed_files: set[str] = set()
    if resume and checkpoint_file.exists():
        try:
            checkpoint_data = json.loads(checkpoint_file.read_text())
            completed_files = set(checkpoint_data.get("completed_files", []))
            typer.echo(
                f"  Resuming from checkpoint ({len(completed_files)} files already indexed)"
            )
        except (json.JSONDecodeError, KeyError):
            typer.secho(
                "  Warning: Could not read checkpoint, starting fresh",
                fg=typer.colors.YELLOW,
            )

    async def _index_content() -> None:
        checksums: dict[str, str] = {}
        indexed_files: dict[str, list[str]] = {}
        datasets_to_cognify: set[str] = set()
        all_processed_files: list[str] = list(completed_files)

        try:
            for source in config.content_sources:
                files = _collect_files_from_source(source)
                if not files:
                    typer.echo(f"  No files found for: {source.path}")
                    continue

                # Filter out already completed files if resuming
                if resume:
                    files = [f for f in files if str(f) not in completed_files]
                    if not files:
                        typer.echo(f"  All files already indexed for: {source.path}")
                        continue

                typer.echo(
                    f"  Processing {len(files)} file(s) for dataset '{source.dataset}'"
                )
                indexed_files[source.dataset] = []

                if progress:
                    # Use progress bar
                    with typer.progressbar(
                        files,
                        label=f"    {source.dataset}",
                        show_eta=True,
                        show_pos=True,
                    ) as progress_bar:
                        for file_path in progress_bar:
                            parsed: ParsedContent = parse_markdown_file(file_path)
                            content_with_context = (
                                f"# {parsed.title or file_path.name}\n"
                                f"Source: {file_path}\n\n"
                                f"{parsed.content}"
                            )
                            await client.add_content(
                                content=content_with_context,
                                dataset_name=source.dataset,
                                metadata={
                                    "source_path": str(file_path),
                                    "title": parsed.title,
                                    **parsed.metadata,
                                },
                            )
                            checksums[str(file_path)] = _compute_file_checksum(
                                file_path
                            )
                            indexed_files[source.dataset].append(str(file_path))
                            all_processed_files.append(str(file_path))
                            datasets_to_cognify.add(source.dataset)

                            # Save checkpoint after each file
                            checkpoint_file.write_text(
                                json.dumps(
                                    {
                                        "completed_files": all_processed_files,
                                    }
                                )
                            )
                else:
                    # Standard output without progress bar
                    for i, file_path in enumerate(files, 1):
                        typer.echo(f"    [{i}/{len(files)}] {file_path}")

                        parsed = parse_markdown_file(file_path)
                        content_with_context = (
                            f"# {parsed.title or file_path.name}\n"
                            f"Source: {file_path}\n\n"
                            f"{parsed.content}"
                        )
                        await client.add_content(
                            content=content_with_context,
                            dataset_name=source.dataset,
                            metadata={
                                "source_path": str(file_path),
                                "title": parsed.title,
                                **parsed.metadata,
                            },
                        )
                        checksums[str(file_path)] = _compute_file_checksum(file_path)
                        indexed_files[source.dataset].append(str(file_path))
                        all_processed_files.append(str(file_path))
                        datasets_to_cognify.add(source.dataset)

                        # Save checkpoint after each file
                        checkpoint_file.write_text(
                            json.dumps(
                                {
                                    "completed_files": all_processed_files,
                                }
                            )
                        )

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

            # Remove checkpoint on successful completion
            if checkpoint_file.exists():
                checkpoint_file.unlink()

            total_files = sum(len(f) for f in indexed_files.values()) + len(
                completed_files
            )
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
    files: Annotated[
        list[str] | None,
        typer.Option(
            "--files",
            "-f",
            help="Specific files to sync (can be repeated)",
        ),
    ] = None,
    all_files: Annotated[
        bool,
        typer.Option(
            "--all", "-a", help="Sync all configured sources, not just changed"
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be synced without syncing"),
    ] = False,
    dataset: Annotated[
        str | None,
        typer.Option("--dataset", "-d", help="Specific dataset to sync"),
    ] = None,
    cognify: Annotated[
        bool,
        typer.Option("--cognify/--no-cognify", help="Run cognify after adding content"),
    ] = True,
    since: Annotated[
        str,
        typer.Option(
            "--since", "-s", help="Git reference to compare against for changes"
        ),
    ] = "HEAD~1",
    verify: Annotated[
        bool,
        typer.Option(
            "--verify/--no-verify",
            help="Verify content is searchable after sync (FR-011)",
        ),
    ] = False,
) -> None:
    """Sync changed files to Cognee Cloud.

    Detects changed files via git diff and indexes them to the knowledge graph.
    Markdown files are parsed and added, Python files have docstrings extracted.

    Example:
        agent-memory sync                    # Sync files changed since HEAD~1
        agent-memory sync --all              # Sync all configured sources
        agent-memory sync --files src/foo.py # Sync specific files
        agent-memory sync --dry-run          # Show what would sync
        agent-memory sync --since main       # Sync changes since main branch
        agent-memory sync --verify           # Verify content is searchable after sync
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _sync() -> None:
        try:
            files_to_sync: list[Path] = []
            datasets_to_cognify: set[str] = set()  # Track datasets for cognify

            if files:
                # Explicit files specified
                files_to_sync = [Path(f) for f in files]
                typer.echo(f"Syncing {len(files_to_sync)} specified file(s)...")
            elif all_files:
                # Sync all configured sources
                typer.echo("Syncing all configured sources...")
                files_to_sync = _get_all_source_files(config)
            else:
                # Detect changes via git diff
                from agent_memory.git_diff import GitError, get_changed_files

                try:
                    include_patterns = ["*.py", "*.md"]
                    exclude_patterns = ["**/test_*.py", "**/__pycache__/*", "**/.*"]

                    files_to_sync = get_changed_files(
                        since=since,
                        include_patterns=include_patterns,
                        exclude_patterns=exclude_patterns,
                    )
                    if not files_to_sync:
                        typer.secho(
                            f"No changed files found since {since}",
                            fg=typer.colors.YELLOW,
                        )
                        raise typer.Exit(code=0)

                    typer.echo(
                        f"Found {len(files_to_sync)} changed file(s) since {since}..."
                    )
                except GitError as e:
                    typer.secho(f"Git error: {e}", fg=typer.colors.RED, err=True)
                    typer.echo("Falling back to syncing all configured sources...")
                    files_to_sync = _get_all_source_files(config)

            # Filter to dataset if specified
            if dataset:
                files_to_sync = _filter_by_dataset(files_to_sync, config, dataset)
                if not files_to_sync:
                    typer.secho(
                        f"No files match dataset: {dataset}",
                        fg=typer.colors.YELLOW,
                    )
                    raise typer.Exit(code=0)

            # Categorize files
            md_files = [f for f in files_to_sync if f.suffix == ".md"]
            py_files = [f for f in files_to_sync if f.suffix == ".py"]

            if dry_run:
                typer.secho("\n[DRY RUN] Would sync:", fg=typer.colors.CYAN)
                if md_files:
                    typer.echo(f"  Markdown files ({len(md_files)}):")
                    for f in md_files[:10]:
                        typer.echo(f"    - {f}")
                    if len(md_files) > 10:
                        typer.echo(f"    ... and {len(md_files) - 10} more")
                if py_files:
                    typer.echo(f"  Python files ({len(py_files)}):")
                    for f in py_files[:10]:
                        typer.echo(f"    - {f}")
                    if len(py_files) > 10:
                        typer.echo(f"    ... and {len(py_files) - 10} more")
                raise typer.Exit(code=0)

            # Sync markdown files
            if md_files:
                typer.echo(f"\nSyncing {len(md_files)} markdown file(s)...")
                md_datasets = await _sync_markdown_files(
                    client, config, md_files, verify=verify
                )
                datasets_to_cognify.update(md_datasets)

            # Sync Python files (extract docstrings)
            if py_files:
                typer.echo(f"\nSyncing {len(py_files)} Python file(s)...")
                py_datasets = await _sync_python_files(
                    client, config, py_files, verify=verify
                )
                datasets_to_cognify.update(py_datasets)

            # Run cognify for each dataset that had files synced
            if cognify and datasets_to_cognify:
                typer.echo("\nRunning cognify for synced datasets...")
                for ds in datasets_to_cognify:
                    typer.echo(f"  Cognifying dataset: {ds}")
                    await client.cognify(dataset_name=ds)
                typer.secho("Cognify completed", fg=typer.colors.GREEN)

            typer.secho(
                f"\nSync completed: {len(md_files)} markdown, {len(py_files)} Python files",
                fg=typer.colors.GREEN,
            )

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_sync())


def _get_all_source_files(config: AgentMemoryConfig) -> list[Path]:
    """Get all files from configured content sources.

    Args:
        config: Agent memory configuration.

    Returns:
        List of file paths from all configured sources.
    """
    from pathlib import Path

    files: list[Path] = []

    for source in config.content_sources:
        if source.source_type == "file":
            if source.path.exists():
                files.append(source.path)
        elif source.source_type == "directory":
            if source.path.exists():
                for ext in source.file_extensions:
                    files.extend(source.path.rglob(f"*{ext}"))
        elif source.source_type == "glob":
            # Glob pattern
            import glob as glob_module

            matched = glob_module.glob(str(source.path), recursive=True)
            files.extend(Path(p) for p in matched)

    # Apply exclude patterns
    return files


def _filter_by_dataset(
    files: list[Path], config: AgentMemoryConfig, dataset: str
) -> list[Path]:
    """Filter files to those matching a specific dataset.

    Args:
        files: List of files to filter.
        config: Configuration with content sources.
        dataset: Dataset name to match.

    Returns:
        Filtered list of files.
    """
    # Build set of paths belonging to the dataset
    dataset_paths: set[Path] = set()
    for source in config.content_sources:
        if source.dataset == dataset:
            if source.source_type == "file":
                dataset_paths.add(source.path)
            elif source.source_type == "directory":
                # Add all files under the directory
                for ext in source.file_extensions:
                    dataset_paths.update(source.path.rglob(f"*{ext}"))

    # Filter files to those in the dataset
    return [f for f in files if f in dataset_paths or _is_under_path(f, dataset_paths)]


def _is_under_path(file: Path, paths: set[Path]) -> bool:
    """Check if file is under any of the given paths."""
    for p in paths:
        if p.is_dir():
            try:
                file.relative_to(p)
                return True
            except ValueError:
                continue
    return False


async def _sync_markdown_files(
    client: CogneeClient,
    config: AgentMemoryConfig,
    files: list[Path],
    *,
    verify: bool = False,
) -> set[str]:
    """Sync markdown files to Cognee.

    Args:
        client: Cognee client.
        config: Configuration.
        files: Markdown files to sync.
        verify: If True, verify content is searchable after add (FR-011).

    Returns:
        Set of dataset names that received content.
    """
    datasets_used: set[str] = set()

    for file_path in files:
        try:
            typer.echo(f"  Processing: {file_path}")

            # Parse markdown
            parsed = parse_markdown_file(file_path)

            # Determine dataset from config or use default
            dataset_name = _get_dataset_for_file(file_path, config)

            # Add to Cognee
            await client.add_content(
                content=parsed.content,
                dataset_name=dataset_name,
                metadata={
                    "source_path": str(file_path),
                    "title": parsed.title or file_path.stem,
                },
                verify=verify,
            )
            datasets_used.add(dataset_name)
        except Exception as e:
            typer.secho(f"  Error processing {file_path}: {e}", fg=typer.colors.RED)

    return datasets_used


async def _sync_python_files(
    client: CogneeClient,
    config: AgentMemoryConfig,
    files: list[Path],
    *,
    verify: bool = False,
) -> set[str]:
    """Sync Python files by extracting docstrings.

    Args:
        client: Cognee client.
        config: Configuration.
        files: Python files to sync.
        verify: If True, verify content is searchable after add (FR-011).

    Returns:
        Set of dataset names that received content.
    """
    datasets_used: set[str] = set()

    for file_path in files:
        try:
            typer.echo(f"  Processing: {file_path}")

            # Extract docstrings
            entries = extract_docstrings(file_path)

            if not entries:
                typer.echo(f"    No docstrings found in {file_path}")
                continue

            # Determine dataset
            dataset_name = config.default_dataset

            # Format and add to Cognee
            for entry in entries:
                formatted_content = _format_docstring_entry(entry)
                await client.add_content(
                    content=formatted_content,
                    dataset_name=dataset_name,
                    metadata={
                        "source_path": str(file_path),
                        "entry_type": entry.entry_type,
                        "name": entry.name,
                        "line_number": entry.line_number,
                    },
                    verify=verify,
                )

            datasets_used.add(dataset_name)
            typer.echo(f"    Added {len(entries)} docstring(s)")

        except Exception as e:
            typer.secho(f"  Error processing {file_path}: {e}", fg=typer.colors.RED)

    return datasets_used


def _get_dataset_for_file(file_path: Path, config: AgentMemoryConfig) -> str:
    """Determine the appropriate dataset for a file.

    All knowledge content goes to a single unified dataset for maximum
    knowledge graph connectivity. Content sources can override this
    if explicitly configured.

    Args:
        file_path: Path to the file.
        config: Configuration with content sources.

    Returns:
        Dataset name for the file.
    """
    # Check if file matches any content source (allows explicit overrides)
    for source in config.content_sources:
        if source.source_type == "file" and source.path == file_path:
            return source.dataset
        if source.source_type == "directory":
            try:
                file_path.relative_to(source.path)
                return source.dataset
            except ValueError:
                continue

    # Default: single unified dataset for all knowledge
    return config.default_dataset


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
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            "-d",
            help="Filter results by dataset (architecture, governance, etc.)",
        ),
    ] = None,
    top_k: Annotated[
        int,
        typer.Option("--top-k", "-k", help="Maximum number of results"),
    ] = 10,
) -> None:
    """Search the knowledge graph.

    Queries indexed content using Cognee's graph-based search.
    Optionally filter results by dataset name.
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _search() -> None:
        try:
            # Pass dataset to API for server-side scoping (not client-side filtering)
            result = await client.search(
                query,
                dataset_name=dataset,
                search_type=search_type,
                top_k=top_k,
            )

            typer.echo(f"Query: {result.query}")
            typer.echo(f"Search type: {result.search_type}")
            if dataset:
                typer.echo(f"Dataset: {dataset}")
            typer.echo(
                f"Results: {result.total_count} (in {result.execution_time_ms}ms)"
            )
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

                # Truncate long content
                content_preview = item.content[:200]
                if len(item.content) > 200:
                    content_preview += "..."
                typer.echo(f"    {content_preview}")
                if item.relevance_score > 0:
                    typer.echo(f"    Score: {item.relevance_score:.3f}")
                if item.dataset:
                    typer.echo(f"    Dataset: {item.dataset}")
                typer.echo()

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_search())


@app.command()
def memify(
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            "-d",
            help="Dataset to optimize. Uses default dataset if not specified.",
        ),
    ] = None,
) -> None:
    """Optimize knowledge graph using memify post-processing pipeline.

    Memify improves search relevance by:
    - Pruning stale nodes (removes outdated knowledge)
    - Strengthening frequent connections
    - Adding derived facts and associations

    Run this after sync + cognify to enhance graph quality without rebuilding.

    Note: Memify is only available with self-hosted Cognee. Cognee Cloud
    (api.cognee.ai) does not currently expose this endpoint.

    Example:
        agent-memory sync --all && agent-memory memify --dataset floe
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _memify() -> None:
        try:
            effective_dataset = dataset or config.default_dataset
            typer.echo(f"Running memify on dataset: {effective_dataset}")

            success = await client.memify(dataset_name=effective_dataset)

            if success:
                typer.secho("Memify completed successfully!", fg=typer.colors.GREEN)
            else:
                typer.secho(
                    "Memify not available: Cognee Cloud does not expose the memify endpoint.",
                    fg=typer.colors.YELLOW,
                )
                typer.echo()
                typer.echo(
                    "This is a known limitation of Cognee Cloud (api.cognee.ai)."
                )
                typer.echo(
                    "The memify endpoint is only available in self-hosted Cognee."
                )
                typer.echo()
                typer.echo("Your knowledge graph is still functional:")
                typer.echo("  - sync: Adds content to the graph")
                typer.echo("  - cognify: Builds the knowledge graph")
                typer.echo("  - search: Queries the graph (working)")
                typer.echo()
                typer.echo(
                    "Memify is an optional optimization, not required for basic functionality."
                )
        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_memify())


@app.command()
def coverage(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed list of missing files"),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table, json"),
    ] = "table",
) -> None:
    """Show coverage report comparing indexed vs filesystem.

    Reports total files, indexed files, coverage percentage, and optionally
    lists missing and extra (stale) files.

    Examples:
        agent-memory coverage              # Show summary
        agent-memory coverage --verbose    # Show missing files
        agent-memory coverage --format json  # JSON output
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _coverage() -> None:
        from agent_memory.ops.coverage import analyze_coverage

        try:
            report = await analyze_coverage(config, client)

            if output_format == "json":
                typer.echo(report.model_dump_json(indent=2))
                return

            # Table format output
            typer.secho("Coverage Report", fg=typer.colors.CYAN, bold=True)
            typer.echo()

            # Determine status color
            if report.coverage_percentage >= 100.0:
                status_color = typer.colors.GREEN
                status = "COMPLETE"
            elif report.coverage_percentage >= 80.0:
                status_color = typer.colors.YELLOW
                status = "PARTIAL"
            else:
                status_color = typer.colors.RED
                status = "LOW"

            typer.echo(f"  Total files:    {report.total_files}")
            typer.echo(f"  Indexed files:  {report.indexed_files}")
            typer.secho(
                f"  Coverage:       {report.coverage_percentage:.1f}% ({status})",
                fg=status_color,
            )

            if report.missing_files:
                typer.echo(f"  Missing files:  {len(report.missing_files)}")
            if report.extra_files:
                typer.echo(f"  Stale files:    {len(report.extra_files)}")

            # Show details if verbose
            if verbose:
                if report.missing_files:
                    typer.echo()
                    typer.secho("Missing files (not indexed):", fg=typer.colors.YELLOW)
                    for f in report.missing_files:
                        typer.echo(f"  - {f}")

                if report.extra_files:
                    typer.echo()
                    typer.secho(
                        "Stale files (indexed but not on filesystem):",
                        fg=typer.colors.YELLOW,
                    )
                    for f in report.extra_files:
                        typer.echo(f"  - {f}")

            # Exit with appropriate code
            if not report.is_complete:
                raise typer.Exit(code=1)

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_coverage())


@app.command()
def drift(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table, json"),
    ] = "table",
) -> None:
    """Detect drift between indexed content and filesystem.

    Identifies files that have changed since last indexing:
    - Modified: Same path, different content
    - Deleted: Indexed but no longer on filesystem
    - Renamed: Same content, different path

    Examples:
        agent-memory drift                 # Show summary
        agent-memory drift --format json   # JSON output
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    from agent_memory.ops.drift import detect_drift

    report = detect_drift(config)

    if output_format == "json":
        typer.echo(report.model_dump_json(indent=2))
        return

    # Table format output
    typer.secho("Drift Report", fg=typer.colors.CYAN, bold=True)
    typer.echo()

    # Summary
    if report.has_drift:
        typer.secho(
            f"  Drift detected: {report.total_drifted} file(s)", fg=typer.colors.YELLOW
        )
    else:
        typer.secho("  No drift detected", fg=typer.colors.GREEN)
    typer.echo()

    # Modified files
    if report.modified_files:
        typer.secho(f"Modified ({len(report.modified_files)}):", fg=typer.colors.YELLOW)
        for f in report.modified_files:
            typer.echo(f"  {f}")
        typer.echo()

    # Deleted files
    if report.deleted_files:
        typer.secho(f"Deleted ({len(report.deleted_files)}):", fg=typer.colors.RED)
        for f in report.deleted_files:
            typer.echo(f"  {f}")
        typer.echo()

    # Renamed files
    if report.renamed_files:
        typer.secho(f"Renamed ({len(report.renamed_files)}):", fg=typer.colors.BLUE)
        for old_path, new_path in report.renamed_files:
            typer.echo(f"  {old_path} -> {new_path}")
        typer.echo()

    # Unchanged summary
    if report.unchanged_files:
        typer.echo(f"Unchanged: {len(report.unchanged_files)} file(s)")

    # Exit with appropriate code
    if report.has_drift:
        raise typer.Exit(code=1)


@app.command()
def repair(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be repaired without making changes"
        ),
    ] = False,
) -> None:
    """Repair drift issues by re-indexing changed files.

    For each type of drift:
    - Modified: Re-index the file with updated content
    - Deleted: Remove from checksums (already gone from filesystem)
    - Renamed: Update path in checksums

    Examples:
        agent-memory repair            # Fix all drift
        agent-memory repair --dry-run  # Show what would be fixed
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    from agent_memory.ops.drift import compute_content_hash, detect_drift

    report = detect_drift(config)

    if not report.has_drift:
        typer.secho("No drift detected - nothing to repair", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)

    typer.secho("Repair Report", fg=typer.colors.CYAN, bold=True)
    typer.echo()

    if dry_run:
        typer.secho(
            "[DRY RUN] Would perform the following repairs:", fg=typer.colors.YELLOW
        )
        typer.echo()

        if report.modified_files:
            typer.echo(f"  Re-index {len(report.modified_files)} modified file(s):")
            for f in report.modified_files:
                typer.echo(f"    - {f}")

        if report.deleted_files:
            typer.echo(
                f"  Remove {len(report.deleted_files)} deleted file(s) from checksums:"
            )
            for f in report.deleted_files:
                typer.echo(f"    - {f}")

        if report.renamed_files:
            typer.echo(
                f"  Update {len(report.renamed_files)} renamed file(s) in checksums:"
            )
            for old_path, new_path in report.renamed_files:
                typer.echo(f"    - {old_path} -> {new_path}")

        raise typer.Exit(code=0)

    # Load current checksums
    checksums_path = Path(".cognee") / "checksums.json"
    checksums: dict[str, str] = {}
    if checksums_path.exists():
        checksums = json.loads(checksums_path.read_text())

    client = CogneeClient(config)

    async def _repair() -> None:
        nonlocal checksums
        repaired_count = 0

        # Handle modified files - re-index
        if report.modified_files:
            typer.echo(f"Re-indexing {len(report.modified_files)} modified file(s)...")
            for file_path in report.modified_files:
                path_obj = Path(file_path)
                if path_obj.exists():
                    try:
                        typer.echo(f"  {file_path}")
                        content = path_obj.read_text(encoding="utf-8", errors="replace")
                        await client.add_content(content, config.default_dataset)
                        checksums[file_path] = compute_content_hash(content)
                        repaired_count += 1
                    except Exception as e:
                        typer.secho(f"    Error: {e}", fg=typer.colors.RED)

        # Handle deleted files - remove from checksums
        if report.deleted_files:
            typer.echo(
                f"Removing {len(report.deleted_files)} deleted file(s) from checksums..."
            )
            for file_path in report.deleted_files:
                if file_path in checksums:
                    del checksums[file_path]
                    repaired_count += 1
                    typer.echo(f"  {file_path}")

        # Handle renamed files - update path in checksums
        if report.renamed_files:
            typer.echo(
                f"Updating {len(report.renamed_files)} renamed file(s) in checksums..."
            )
            for old_path, new_path in report.renamed_files:
                if old_path in checksums:
                    # Move checksum to new path
                    checksums[new_path] = checksums.pop(old_path)
                    repaired_count += 1
                    typer.echo(f"  {old_path} -> {new_path}")

        # Save updated checksums
        checksums_path.write_text(json.dumps(checksums, indent=2))

        typer.echo()
        typer.secho(
            f"Repair complete: {repaired_count} file(s) repaired", fg=typer.colors.GREEN
        )

    _run_async(_repair())


@app.command()
def reset(
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm", help="Confirm reset without prompting (required for safety)"
        ),
    ] = False,
) -> None:
    """Reset knowledge graph by pruning all data and clearing local state.

    WARNING: This is destructive and cannot be undone.

    This command:
    - Prunes the Cognee Cloud system (graph, vector, metadata)
    - Deletes .cognee/state.json and .cognee/checksums.json
    - Requires --confirm flag for safety

    Examples:
        agent-memory reset --confirm   # Full reset
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    if not confirm:
        typer.secho(
            "ERROR: Reset requires --confirm flag for safety.",
            fg=typer.colors.RED,
            err=True,
        )
        typer.echo()
        typer.echo("This will delete ALL indexed content including:")
        typer.echo("  - All datasets and their knowledge graph nodes")
        typer.echo("  - Vector embeddings and metadata")
        typer.echo("  - Local state files (.cognee/state.json, .cognee/checksums.json)")
        typer.echo()
        typer.echo("To proceed, run:")
        typer.secho("  agent-memory reset --confirm", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _reset() -> None:
        try:
            typer.echo("Pruning Cognee Cloud system...")
            typer.echo("  Deleting all datasets (with graph nodes)...")

            # Prune the Cognee system (deletes all datasets with hard mode)
            await client.prune_system()

            typer.secho("  Cognee Cloud pruned", fg=typer.colors.GREEN)

            # Clear local state files
            typer.echo()
            typer.echo("Clearing local state files...")

            state_file = Path(".cognee/state.json")
            checksums_file = Path(".cognee/checksums.json")

            if state_file.exists():
                state_file.unlink()
                typer.echo(f"  Deleted: {state_file}")

            if checksums_file.exists():
                checksums_file.unlink()
                typer.echo(f"  Deleted: {checksums_file}")

            # Also clear checkpoint if present
            checkpoint_file = Path(".cognee/checkpoint.json")
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                typer.echo(f"  Deleted: {checkpoint_file}")

            typer.echo()
            typer.secho("Reset completed successfully", fg=typer.colors.GREEN)

        except CogneeClientError as e:
            _exit_with_error(str(e))

    _run_async(_reset())


@app.command()
def test(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed results for each query"),
    ] = False,
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Pass rate threshold (default: 100)"),
    ] = 100.0,
) -> None:
    """Run quality validation tests against the knowledge graph.

    Executes test queries and validates that expected keywords appear in results.
    Returns exit code 0 if pass rate meets threshold, 1 otherwise.

    Examples:
        agent-memory test                 # Run with default queries
        agent-memory test --verbose       # Show detailed results
        agent-memory test --threshold 80  # Pass if >=80% queries pass
    """
    from agent_memory.ops.quality import (
        QualityReport,
        create_default_test_queries,
        validate_quality,
    )

    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _run_tests() -> QualityReport:
        # Get default test queries
        test_queries = create_default_test_queries()

        typer.echo(f"Running {len(test_queries)} quality validation tests...")
        typer.echo()

        report = await validate_quality(client, test_queries)

        # Display results
        for result in report.results:
            if result.passed:
                status = typer.style("PASS", fg=typer.colors.GREEN)
            else:
                status = typer.style("FAIL", fg=typer.colors.RED)

            typer.echo(f"  [{status}] {result.query}")

            if verbose:
                if result.result_count > 0:
                    typer.echo(f"         Results: {result.result_count}")
                if result.found_keywords:
                    typer.echo(f"         Found: {', '.join(result.found_keywords)}")
                if result.missing_keywords:
                    typer.echo(
                        f"         Missing: {', '.join(result.missing_keywords)}"
                    )
                if result.error:
                    typer.echo(f"         Error: {result.error}")

        typer.echo()

        # Summary
        if report.all_passed:
            typer.secho(
                f"All tests passed ({report.passed_tests}/{report.total_tests})",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                f"Tests: {report.passed_tests}/{report.total_tests} passed "
                f"({report.pass_rate:.1f}%)",
                fg=(
                    typer.colors.YELLOW
                    if report.pass_rate >= threshold
                    else typer.colors.RED
                ),
            )

        return report

    try:
        report = _run_async(_run_tests())

        # Exit code based on threshold
        if report.pass_rate >= threshold:
            raise typer.Exit(code=0)
        else:
            typer.echo(
                f"\nFailed: Pass rate {report.pass_rate:.1f}% < {threshold}% threshold"
            )
            raise typer.Exit(code=1)

    except CogneeClientError as e:
        _exit_with_error(str(e))


@app.command(name="session-save")
def session_save(
    issues: Annotated[
        str | None,
        typer.Option(
            "--issues",
            "-i",
            help="Comma-separated list of issue IDs (e.g., FLO-123,FLO-456)",
        ),
    ] = None,
    decisions: Annotated[
        str | None,
        typer.Option(
            "--decisions",
            "-d",
            help="Comma-separated list of decisions made during the session",
        ),
    ] = None,
    work_areas: Annotated[
        str | None,
        typer.Option(
            "--work-areas",
            "-w",
            help="Comma-separated list of files/areas being worked on",
        ),
    ] = None,
    summary: Annotated[
        str | None,
        typer.Option(
            "--summary",
            "-s",
            help="Summary of the session conversation",
        ),
    ] = None,
    dataset: Annotated[
        str,
        typer.Option(
            "--dataset",
            help="Dataset name to store context in (default: sessions)",
        ),
    ] = "sessions",
) -> None:
    """Save session context to the knowledge graph.

    Captures the current session context including active issues,
    decisions made, work areas touched, and an optional summary.
    This context can later be retrieved for session recovery.

    Example:
        agent-memory session-save --issues "FLO-123,FLO-456"
        agent-memory session-save --decisions "Use REST API,Add caching"
        agent-memory session-save --issues "FLO-123" --summary "Implemented auth"
    """
    from agent_memory.session import capture_session_context, save_session_context

    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    # Parse comma-separated arguments
    issue_list = [i.strip() for i in issues.split(",")] if issues else []
    decision_list = [d.strip() for d in decisions.split(",")] if decisions else []
    work_area_list = [w.strip() for w in work_areas.split(",")] if work_areas else []

    # Capture session context
    context = capture_session_context(
        active_issues=issue_list,
        decisions=decision_list,
        work_areas=work_area_list if work_area_list else None,
        summary=summary,
    )

    async def _save_context() -> None:
        client = CogneeClient(config)
        await save_session_context(client, context, dataset=dataset)

    try:
        _run_async(_save_context())

        # Display success information
        typer.secho("Session context saved successfully!", fg=typer.colors.GREEN)
        typer.echo(f"  Session ID: {context.session_id}")
        typer.echo(f"  Captured at: {context.captured_at.isoformat()}")

        if issue_list:
            typer.echo(f"  Issues: {', '.join(issue_list)}")
        if decision_list:
            typer.echo(f"  Decisions: {len(decision_list)}")
        if work_area_list:
            typer.echo(f"  Work areas: {len(work_area_list)}")
        if summary:
            typer.echo(f"  Summary: {summary[:50]}{'...' if len(summary) > 50 else ''}")

    except CogneeClientError as e:
        _exit_with_error(str(e))


@app.command(name="session-recover")
def session_recover(
    work_area: Annotated[
        str,
        typer.Option(
            "--work-area",
            "-w",
            help="Topic/area to recover session context for",
        ),
    ],
) -> None:
    """Recover session context from the knowledge graph.

    Queries the knowledge graph for prior session context related to
    the specified work area. Displays prior work, closed tasks, and
    decision history to help resume work.

    Example:
        agent-memory session-recover --work-area "plugin-system"
        agent-memory session-recover --work-area "authentication"
    """
    from agent_memory.session import retrieve_session_context

    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    async def _retrieve_context() -> None:
        client = CogneeClient(config)
        context = await retrieve_session_context(client, work_area)

        if context is None:
            typer.secho(
                f"No prior session context found for '{work_area}'",
                fg=typer.colors.YELLOW,
            )
            return

        # Display session header
        typer.secho("Session Context Recovered", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  Session ID: {context.session_id}")
        typer.echo(f"  Captured at: {context.captured_at.isoformat()}")
        typer.echo()

        # Display work areas
        if context.active_work_areas:
            typer.secho("Work Areas:", bold=True)
            for area in context.active_work_areas:
                typer.echo(f"  - {area}")
            typer.echo()

        # Display related closed tasks
        if context.related_closed_tasks:
            typer.secho("Related Closed Tasks:", bold=True)
            for task in context.related_closed_tasks:
                typer.echo(f"  - {task}")
            typer.echo()

        # Display decisions
        if context.recent_decisions:
            typer.secho("Decision History:", bold=True)
            for decision in context.recent_decisions:
                typer.echo(f"  - {decision.decision}")
                if decision.rationale:
                    typer.echo(f"    Rationale: {decision.rationale}")
            typer.echo()

        # Display summary
        if context.conversation_summary:
            typer.secho("Session Summary:", bold=True)
            typer.echo(f"  {context.conversation_summary}")

    try:
        _run_async(_retrieve_context())

    except CogneeClientError as e:
        _exit_with_error(str(e))


@app.command()
def codify(
    patterns: Annotated[
        list[str] | None,
        typer.Option(
            "--pattern",
            "-p",
            help="Glob patterns for Python files (default: packages/*/src/**/*.py)",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            "-e",
            help="Patterns to exclude (default: **/test_*, **/__pycache__/*)",
        ),
    ] = None,
    progress: Annotated[
        bool,
        typer.Option("--progress", help="Show progress bar during indexing"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be indexed without indexing"),
    ] = False,
) -> None:
    """Extract and index Python docstrings to the codebase dataset.

    Parses Python source files to extract docstrings from modules, classes,
    functions, and methods. Indexed content includes:
    - Module-level docstrings
    - Class docstrings with base classes and method names
    - Function/method docstrings with signatures
    - Google-style sections (Args, Returns, Raises, Examples)

    Example:
        agent-memory codify
        agent-memory codify --pattern "src/**/*.py" --progress
        agent-memory codify --dry-run
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    # Default patterns
    source_patterns = patterns or [
        "packages/*/src/**/*.py",
        "plugins/*/src/**/*.py",
        "devtools/*/src/**/*.py",
    ]
    exclude_patterns = exclude or [
        "**/test_*",
        "**/__pycache__/*",
        "**/conftest.py",
    ]

    # Collect Python files
    typer.echo("Collecting Python files...")
    files = _collect_python_files(source_patterns, exclude_patterns)

    if not files:
        typer.secho("No Python files found matching patterns", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    typer.echo(f"Found {len(files)} Python file(s)")

    if dry_run:
        typer.echo()
        typer.secho("Dry run - files that would be indexed:", fg=typer.colors.CYAN)
        for f in files:
            typer.echo(f"  {f}")
        raise typer.Exit(code=0)

    client = CogneeClient(config)
    dataset_name = config.default_dataset

    async def _codify_content() -> None:
        cognee_dir = Path(".cognee")
        state_file = cognee_dir / "state.json"
        checksums_file = cognee_dir / "checksums.json"

        # Load existing state
        try:
            existing_state = (
                json.loads(state_file.read_text()) if state_file.exists() else {}
            )
            existing_checksums = (
                json.loads(checksums_file.read_text())
                if checksums_file.exists()
                else {}
            )
        except json.JSONDecodeError:
            existing_state = {}
            existing_checksums = {}

        indexed_files: list[str] = []
        total_entries = 0
        checksums: dict[str, str] = dict(existing_checksums)

        try:
            if progress:
                with typer.progressbar(
                    files,
                    label="Extracting docstrings",
                    show_eta=True,
                    show_pos=True,
                ) as progress_bar:
                    for file_path in progress_bar:
                        entries = _process_python_file(file_path)
                        if entries:
                            for entry in entries:
                                content = _format_docstring_entry(entry)
                                await client.add_content(
                                    content=content,
                                    dataset_name=dataset_name,
                                    metadata={
                                        "source_path": str(entry.source_path),
                                        "entry_type": entry.entry_type,
                                        "name": entry.name,
                                        "line_number": entry.line_number,
                                    },
                                )
                            total_entries += len(entries)
                            indexed_files.append(str(file_path))
                            checksums[str(file_path)] = _compute_file_checksum(
                                file_path
                            )
            else:
                for i, file_path in enumerate(files, 1):
                    typer.echo(f"  [{i}/{len(files)}] {file_path}")
                    entries = _process_python_file(file_path)
                    if entries:
                        for entry in entries:
                            content = _format_docstring_entry(entry)
                            await client.add_content(
                                content=content,
                                dataset_name=dataset_name,
                                metadata={
                                    "source_path": str(entry.source_path),
                                    "entry_type": entry.entry_type,
                                    "name": entry.name,
                                    "line_number": entry.line_number,
                                },
                            )
                        total_entries += len(entries)
                        indexed_files.append(str(file_path))
                        checksums[str(file_path)] = _compute_file_checksum(file_path)
                        typer.echo(f"      {len(entries)} docstring(s) extracted")

            # Run cognify to build knowledge graph
            if indexed_files:
                typer.echo()
                typer.echo("Running cognify to build knowledge graph...")
                await client.cognify(dataset_name=dataset_name)
                typer.secho("  Cognify completed", fg=typer.colors.GREEN)

            # Update state
            if dataset_name not in existing_state.get("indexed_files", {}):
                existing_state.setdefault("indexed_files", {})[dataset_name] = []
            existing_state["indexed_files"][dataset_name].extend(indexed_files)
            existing_state["indexed_files"][dataset_name] = list(
                set(existing_state["indexed_files"][dataset_name])
            )

            # Save state files
            if cognee_dir.exists():
                state_file.write_text(json.dumps(existing_state, indent=2))
                checksums_file.write_text(json.dumps(checksums, indent=2))

            typer.echo()
            typer.secho(
                f"Codify complete: {len(indexed_files)} file(s), {total_entries} docstring(s)",
                fg=typer.colors.GREEN,
            )

        except CogneeClientError as e:
            _exit_with_error(f"Codify failed: {e}")

    _run_async(_codify_content())


def _process_python_file(file_path: Path) -> list[DocstringEntry]:
    """Extract docstrings from a Python file.

    Args:
        file_path: Path to the Python file.

    Returns:
        List of extracted docstring entries, empty if parsing fails.
    """
    try:
        return extract_docstrings(file_path)
    except FileNotFoundError:
        return []
    except Exception:
        # Log but don't fail for individual file errors
        logger.warning("Failed to parse file", file_path=str(file_path))
        return []


def _format_docstring_entry(entry: DocstringEntry) -> str:
    """Format a docstring entry for indexing.

    Args:
        entry: The docstring entry to format.

    Returns:
        Formatted content string for Cognee indexing.
    """
    parts = [
        f"# {entry.entry_type.title()}: {entry.name}",
        f"Source: {entry.source_path}:{entry.line_number}",
    ]

    if entry.entry_type == "class" and entry.bases:
        parts.append(f"Bases: {', '.join(entry.bases)}")

    if entry.signature:
        parts.append(f"Signature: {entry.name}{entry.signature}")

    if entry.entry_type == "class" and entry.methods:
        parts.append(f"Methods: {', '.join(entry.methods)}")

    parts.append("")
    parts.append(entry.docstring)

    if entry.sections:
        parts.append("")
        for section_name, section_content in entry.sections.items():
            parts.append(f"## {section_name}")
            parts.append(section_content)

    return "\n".join(parts)


@app.command(name="mcp-config")
def mcp_config(
    install: Annotated[
        bool,
        typer.Option(
            "--install",
            "-i",
            help="Update .claude/mcp.json with the configuration",
        ),
    ] = False,
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="MCP server hostname"),
    ] = "localhost",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="MCP server port"),
    ] = 8000,
) -> None:
    """Generate MCP server configuration for Claude Code.

    Displays the MCP configuration JSON needed to connect Claude Code
    to the Cognee knowledge graph server.

    Examples:
        # Display configuration
        agent-memory mcp-config

        # Install to .claude/mcp.json
        agent-memory mcp-config --install

        # Custom port
        agent-memory mcp-config --port 9000
    """
    from agent_memory.mcp_config import generate_mcp_config

    config = generate_mcp_config(host=host, port=port)

    if install:
        # Find the .claude directory (look in repo root)
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fall back to current directory
            repo_root = Path.cwd()

        claude_dir = repo_root / ".claude"
        mcp_json_path = claude_dir / "mcp.json"

        # Ensure .claude directory exists
        claude_dir.mkdir(exist_ok=True)

        # Load existing config if present
        existing_config: dict[str, Any] = {}
        if mcp_json_path.exists():
            try:
                existing_config = json.loads(mcp_json_path.read_text())
                typer.echo(f"Updating existing {mcp_json_path}")
            except json.JSONDecodeError:
                typer.secho(
                    f"Warning: Could not parse existing {mcp_json_path}, will overwrite",
                    fg=typer.colors.YELLOW,
                )

        # Merge configurations
        if "mcpServers" not in existing_config:
            existing_config["mcpServers"] = {}

        existing_config["mcpServers"].update(config["mcpServers"])

        # Write updated config
        mcp_json_path.write_text(json.dumps(existing_config, indent=2) + "\n")
        typer.secho(
            f"MCP configuration installed to {mcp_json_path}",
            fg=typer.colors.GREEN,
        )
        typer.echo()
        typer.echo("Next steps:")
        typer.echo("  1. Start the MCP server: make cognee-mcp-start")
        typer.echo("  2. Restart Claude Code to load the new configuration")
    else:
        # Just display the configuration
        typer.echo("MCP Configuration for Claude Code:")
        typer.echo()
        typer.echo(json.dumps(config, indent=2))
        typer.echo()
        typer.echo("To install this configuration, run:")
        typer.secho("  agent-memory mcp-config --install", fg=typer.colors.CYAN)


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
