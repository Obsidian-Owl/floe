"""Coverage analysis module for agent-memory.

Provides functionality to compare filesystem files vs indexed files
in Cognee to identify coverage gaps and drift.

Implementation: T037 (FLO-622)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    pass


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

    @computed_field
    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage as percentage.

        Returns:
            Coverage percentage (0-100). Returns 100 if no files expected.
        """
        if self.total_files == 0:
            return 100.0
        return (self.indexed_files / self.total_files) * 100

    @computed_field
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
