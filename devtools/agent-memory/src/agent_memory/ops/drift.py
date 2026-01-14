"""Drift detection module for agent-memory.

Provides functionality to detect drift between indexed files and
filesystem state:
- Deleted files (indexed but no longer on filesystem)
- Renamed files (same content, different path)
- Modified files (same path, different content)

Implementation: T038 (FLO-623)
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    pass


class DriftReport(BaseModel):
    """Report of drift analysis comparing indexed state to filesystem.

    Attributes:
        deleted_files: Files that were indexed but no longer exist.
        renamed_files: Files renamed (same content, different path).
            Each tuple is (old_path, new_path).
        modified_files: Files with same path but different content.
        unchanged_files: Files that match both path and content.
    """

    deleted_files: list[str] = Field(default_factory=list, description="Indexed but deleted")
    renamed_files: list[list[str]] = Field(
        default_factory=list, description="Renamed files [[old, new], ...]"
    )
    modified_files: list[str] = Field(default_factory=list, description="Modified content")
    unchanged_files: list[str] = Field(default_factory=list, description="No changes")

    @computed_field
    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected.

        Returns:
            True if there are deleted, renamed, or modified files.
        """
        return bool(self.deleted_files or self.renamed_files or self.modified_files)

    @computed_field
    @property
    def total_drifted(self) -> int:
        """Count total number of drifted files.

        Returns:
            Sum of deleted, renamed, and modified files.
        """
        return len(self.deleted_files) + len(self.renamed_files) + len(self.modified_files)


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: String content to hash.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def detect_deleted_files(
    filesystem_files: list[str],
    indexed_files: list[str],
) -> list[str]:
    """Detect files that were indexed but no longer exist on filesystem.

    Args:
        filesystem_files: List of file paths currently on filesystem.
        indexed_files: List of file paths that are indexed.

    Returns:
        Sorted list of deleted file paths (indexed but not on filesystem).
    """
    filesystem_set = set(filesystem_files)
    indexed_set = set(indexed_files)
    return sorted(indexed_set - filesystem_set)


def detect_renamed_files(
    filesystem_files: dict[str, str],
    indexed_files: dict[str, str],
) -> list[list[str]]:
    """Detect files that were renamed (same content, different path).

    Uses content hash to match files. If a file's content appears in
    indexed_files with a different path than in filesystem_files,
    it's considered renamed.

    Args:
        filesystem_files: Dict mapping path -> content for current files.
        indexed_files: Dict mapping path -> content for indexed files.

    Returns:
        List of [old_path, new_path] pairs for renamed files.
    """
    # Build hash -> path mappings
    filesystem_hashes: dict[str, str] = {}
    for path, content in filesystem_files.items():
        content_hash = compute_content_hash(content)
        filesystem_hashes[content_hash] = path

    indexed_hashes: dict[str, str] = {}
    for path, content in indexed_files.items():
        content_hash = compute_content_hash(content)
        indexed_hashes[content_hash] = path

    renamed: list[list[str]] = []

    # Find content that exists in both but with different paths
    for content_hash, indexed_path in indexed_hashes.items():
        if content_hash in filesystem_hashes:
            filesystem_path = filesystem_hashes[content_hash]
            # Different path but same content = renamed
            if filesystem_path != indexed_path:
                renamed.append([indexed_path, filesystem_path])

    return sorted(renamed, key=lambda x: x[0])


def detect_modified_files(
    filesystem_files: dict[str, str],
    indexed_files: dict[str, str],
) -> list[str]:
    """Detect files with same path but modified content.

    Args:
        filesystem_files: Dict mapping path -> content for current files.
        indexed_files: Dict mapping path -> content for indexed files.

    Returns:
        Sorted list of paths for files with modified content.
    """
    modified: list[str] = []

    # Only check files that exist in both
    common_paths = set(filesystem_files.keys()) & set(indexed_files.keys())

    for path in common_paths:
        filesystem_content = filesystem_files[path]
        indexed_content = indexed_files[path]

        # Compare content hashes
        if compute_content_hash(filesystem_content) != compute_content_hash(indexed_content):
            modified.append(path)

    return sorted(modified)
