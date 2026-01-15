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
    agent-memory test

Example:
    >>> agent-memory init
    >>> agent-memory health
    >>> agent-memory search "how do plugins work"
    >>> agent-memory codify --progress
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
            typer.echo(f"  Resuming from checkpoint ({len(completed_files)} files already indexed)")
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

                typer.echo(f"  Processing {len(files)} file(s) for dataset '{source.dataset}'")
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
                            checksums[str(file_path)] = _compute_file_checksum(file_path)
                            indexed_files[source.dataset].append(str(file_path))
                            all_processed_files.append(str(file_path))
                            datasets_to_cognify.add(source.dataset)

                            # Save checkpoint after each file
                            checkpoint_file.write_text(json.dumps({
                                "completed_files": all_processed_files,
                            }))
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
                        checkpoint_file.write_text(json.dumps({
                            "completed_files": all_processed_files,
                        }))

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

            total_files = sum(len(f) for f in indexed_files.values()) + len(completed_files)
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
        typer.Option("--all", "-a", help="Sync all configured sources, not just changed"),
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
        typer.Option("--since", "-s", help="Git reference to compare against for changes"),
    ] = "HEAD~1",
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
    """
    config = _load_config()
    if config is None:
        raise typer.Exit(code=1)

    client = CogneeClient(config)

    async def _sync() -> None:
        try:
            files_to_sync: list[Path] = []

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
                await _sync_markdown_files(client, config, md_files)

            # Sync Python files (extract docstrings)
            if py_files:
                typer.echo(f"\nSyncing {len(py_files)} Python file(s)...")
                await _sync_python_files(client, config, py_files)

            # Run cognify if requested
            if cognify and (md_files or py_files):
                typer.echo("\nRunning cognify...")
                await client.cognify(dataset_name=dataset)
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
    client: CogneeClient, config: AgentMemoryConfig, files: list[Path]
) -> None:
    """Sync markdown files to Cognee.

    Args:
        client: Cognee client.
        config: Configuration.
        files: Markdown files to sync.
    """
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
            )
        except Exception as e:
            typer.secho(f"  Error processing {file_path}: {e}", fg=typer.colors.RED)


async def _sync_python_files(
    client: CogneeClient, config: AgentMemoryConfig, files: list[Path]
) -> None:
    """Sync Python files by extracting docstrings.

    Args:
        client: Cognee client.
        config: Configuration.
        files: Python files to sync.
    """
    for file_path in files:
        try:
            typer.echo(f"  Processing: {file_path}")

            # Extract docstrings
            entries = extract_docstrings(file_path)

            if not entries:
                typer.echo(f"    No docstrings found in {file_path}")
                continue

            # Determine dataset
            dataset_name = config.codebase_dataset

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
                )

            typer.echo(f"    Added {len(entries)} docstring(s)")

        except Exception as e:
            typer.secho(f"  Error processing {file_path}: {e}", fg=typer.colors.RED)


def _get_dataset_for_file(file_path: Path, config: AgentMemoryConfig) -> str:
    """Determine the appropriate dataset for a file.

    Args:
        file_path: Path to the file.
        config: Configuration with content sources.

    Returns:
        Dataset name for the file.
    """
    # Check if file matches any content source
    for source in config.content_sources:
        if source.source_type == "file" and source.path == file_path:
            return source.dataset
        if source.source_type == "directory":
            try:
                file_path.relative_to(source.path)
                return source.dataset
            except ValueError:
                continue

    # Default dataset based on file type
    if file_path.suffix == ".py":
        return config.codebase_dataset
    if "architecture" in str(file_path).lower() or "docs" in str(file_path).lower():
        return config.architecture_dataset
    if "claude" in str(file_path).lower() or "rules" in str(file_path).lower():
        return config.governance_dataset

    return config.architecture_dataset  # Default


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
            result = await client.search(query, search_type=search_type, top_k=top_k)

            # Filter results by dataset if specified
            filtered_results = result.results
            if dataset:
                filtered_results = [
                    item for item in result.results
                    if item.dataset == dataset or (
                        item.source_path and dataset in item.source_path
                    )
                ]

            typer.echo(f"Query: {result.query}")
            typer.echo(f"Search type: {result.search_type}")
            if dataset:
                typer.echo(f"Dataset filter: {dataset}")
            typer.echo(
                f"Results: {len(filtered_results)}"
                f"{f' (filtered from {result.total_count})' if dataset else ''}"
                f" (in {result.execution_time_ms}ms)"
            )
            typer.echo()

            if not filtered_results:
                typer.secho("No results found", fg=typer.colors.YELLOW)
                return

            for i, item in enumerate(filtered_results, 1):
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
    dataset_name = config.codebase_dataset

    async def _codify_content() -> None:
        cognee_dir = Path(".cognee")
        state_file = cognee_dir / "state.json"
        checksums_file = cognee_dir / "checksums.json"

        # Load existing state
        try:
            existing_state = json.loads(state_file.read_text()) if state_file.exists() else {}
            existing_checksums = (
                json.loads(checksums_file.read_text()) if checksums_file.exists() else {}
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
                            checksums[str(file_path)] = _compute_file_checksum(file_path)
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
