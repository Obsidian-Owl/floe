"""Coverage analysis module for agent-memory.

Provides functionality to compare filesystem files vs indexed files
in Cognee to identify coverage gaps and drift.

Implementation: T037 (FLO-622)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient
    from agent_memory.config import AgentMemoryConfig


class CoverageReport(BaseModel):
    """Report of coverage analysis comparing filesystem to indexed state.

    Attributes:
        total_files: Total number of files on filesystem that should be indexed.
        indexed_files: Number of files that are currently indexed.
        missing_files: List of files on filesystem but not indexed.
        extra_files: List of files indexed but no longer on filesystem.
    """

    total_files: int = Field(ge=0, description="Total files on filesystem")
    indexed_files: int = Field(ge=0, description="Files currently indexed")
    missing_files: list[str] = Field(default_factory=list, description="Files not indexed")
    extra_files: list[str] = Field(default_factory=list, description="Stale indexed files")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage as percentage.

        Returns:
            Coverage percentage (0-100). Returns 100 if no files expected.
        """
        if self.total_files == 0:
            return 100.0
        return (self.indexed_files / self.total_files) * 100

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_complete(self) -> bool:
        """Check if coverage is complete (100%).

        Returns:
            True if all files are indexed and no extra files exist.
        """
        return len(self.missing_files) == 0 and len(self.extra_files) == 0


def compare_filesystem_vs_indexed(
    filesystem_files: list[str],
    indexed_files: list[str],
) -> CoverageReport:
    """Compare filesystem files against indexed files.

    Args:
        filesystem_files: List of file paths on filesystem.
        indexed_files: List of file paths that are indexed in Cognee.

    Returns:
        CoverageReport with comparison results.
    """
    filesystem_set = set(filesystem_files)
    indexed_set = set(indexed_files)

    # Files on filesystem but not indexed
    missing = sorted(filesystem_set - indexed_set)

    # Files indexed but not on filesystem (stale)
    extra = sorted(indexed_set - filesystem_set)

    # Count indexed files that are actually on filesystem
    valid_indexed = len(indexed_set & filesystem_set)

    return CoverageReport(
        total_files=len(filesystem_files),
        indexed_files=valid_indexed,
        missing_files=missing,
        extra_files=extra,
    )


def identify_missing_files(
    filesystem_files: list[str],
    indexed_files: list[str],
) -> list[str]:
    """Identify files that should be indexed but aren't.

    Args:
        filesystem_files: List of file paths on filesystem.
        indexed_files: List of file paths that are indexed.

    Returns:
        Sorted list of missing file paths.
    """
    filesystem_set = set(filesystem_files)
    indexed_set = set(indexed_files)
    return sorted(filesystem_set - indexed_set)


def get_files_from_source(
    source_path: Path,
    source_type: str,
    file_extensions: list[str],
    exclude_patterns: list[str],
    base_path: Path | None = None,
) -> list[str]:
    """Get list of files from a content source.

    Args:
        source_path: Path or glob pattern for the source.
        source_type: Type of source (directory, file, glob).
        file_extensions: File extensions to include.
        exclude_patterns: Glob patterns to exclude.
        base_path: Base path for relative paths. Defaults to cwd.

    Returns:
        List of absolute file paths.
    """
    if base_path is None:
        base_path = Path.cwd()

    # Resolve path relative to base
    if not source_path.is_absolute():
        source_path = base_path / source_path

    files: list[str] = []

    if source_type == "file":
        # Single file
        if source_path.exists() and source_path.is_file():
            files.append(str(source_path.resolve()))
    elif source_type == "directory":
        # Recursively find files in directory
        if source_path.exists() and source_path.is_dir():
            for ext in file_extensions:
                for file_path in source_path.rglob(f"*{ext}"):
                    if file_path.is_file():
                        files.append(str(file_path.resolve()))
    elif source_type == "glob":
        # Glob pattern
        for file_path in base_path.glob(str(source_path)):
            if file_path.is_file():
                ext = file_path.suffix
                if not file_extensions or ext in file_extensions:
                    files.append(str(file_path.resolve()))

    # Apply exclude patterns
    if exclude_patterns:
        filtered_files: list[str] = []
        for file_str in files:
            excluded = False
            file_path_obj = Path(file_str)
            for pattern in exclude_patterns:
                # Use PurePath.match() which properly handles ** patterns
                # PurePath.match() matches from the right side of the path
                if file_path_obj.match(pattern):
                    excluded = True
                    break
            if not excluded:
                filtered_files.append(file_str)
        files = filtered_files

    return sorted(set(files))


def get_all_configured_files(
    config: AgentMemoryConfig,
    base_path: Path | None = None,
) -> list[str]:
    """Get all files from configured content sources.

    Args:
        config: Agent memory configuration with content_sources.
        base_path: Base path for relative paths. Defaults to cwd.

    Returns:
        Sorted list of all unique file paths from all sources.
    """
    all_files: set[str] = set()

    for source in config.content_sources:
        source_files = get_files_from_source(
            source_path=source.path,
            source_type=source.source_type,
            file_extensions=source.file_extensions,
            exclude_patterns=source.exclude_patterns,
            base_path=base_path,
        )
        all_files.update(source_files)

    return sorted(all_files)


async def analyze_coverage(
    config: AgentMemoryConfig,
    client: CogneeClient,
    *,
    base_path: Path | None = None,
    indexed_files: list[str] | None = None,
) -> CoverageReport:
    """Analyze coverage by comparing filesystem to indexed content.

    Globs filesystem for configured source patterns, queries Cognee for
    indexed datasets, and compares to produce a coverage report.

    Args:
        config: Agent memory configuration with content_sources.
        client: Cognee client for querying indexed datasets.
        base_path: Base path for file resolution. Defaults to cwd.
        indexed_files: Optional list of indexed file paths. If not provided,
            will attempt to load from .cognee/checksums.json.

    Returns:
        CoverageReport with comparison results.

    Example:
        >>> config = get_config()
        >>> client = CogneeClient(config)
        >>> report = await analyze_coverage(config, client)
        >>> print(f"Coverage: {report.coverage_percentage:.1f}%")
    """
    import json

    if base_path is None:
        base_path = Path.cwd()

    # Get all files from configured sources
    filesystem_files = get_all_configured_files(config, base_path)

    # Get indexed files from checksums.json if not provided
    if indexed_files is None:
        checksums_path = base_path / ".cognee" / "checksums.json"
        if checksums_path.exists():
            with checksums_path.open() as f:
                checksums_data = json.load(f)
                # Extract file paths from checksums data and resolve relative paths
                # Relative paths in checksums.json are relative to base_path (where CLI runs from)
                indexed_files = []
                for rel_path in checksums_data:
                    abs_path = (base_path / rel_path).resolve()
                    indexed_files.append(str(abs_path))
        else:
            indexed_files = []

    # Also verify datasets exist in Cognee
    _ = await client.list_datasets()  # Verify connectivity

    # Compare filesystem to indexed
    return compare_filesystem_vs_indexed(filesystem_files, indexed_files)
