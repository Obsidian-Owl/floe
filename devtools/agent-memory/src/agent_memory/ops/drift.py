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
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from agent_memory.config import AgentMemoryConfig


class DriftReport(BaseModel):
    """Report of drift analysis comparing indexed state to filesystem.

    Attributes:
        deleted_files: Files that were indexed but no longer exist.
        renamed_files: Files renamed (same content, different path).
            Each tuple is (old_path, new_path).
        modified_files: Files with same path but different content.
        unchanged_files: Files that match both path and content.
    """

    deleted_files: list[str] = Field(
        default_factory=list, description="Indexed but deleted"
    )
    renamed_files: list[list[str]] = Field(
        default_factory=list, description="Renamed files [[old, new], ...]"
    )
    modified_files: list[str] = Field(
        default_factory=list, description="Modified content"
    )
    unchanged_files: list[str] = Field(default_factory=list, description="No changes")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected.

        Returns:
            True if there are deleted, renamed, or modified files.
        """
        return bool(self.deleted_files or self.renamed_files or self.modified_files)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_drifted(self) -> int:
        """Count total number of drifted files.

        Returns:
            Sum of deleted, renamed, and modified files.
        """
        return (
            len(self.deleted_files) + len(self.renamed_files) + len(self.modified_files)
        )


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
        if compute_content_hash(filesystem_content) != compute_content_hash(
            indexed_content
        ):
            modified.append(path)

    return sorted(modified)


def detect_drift(
    config: AgentMemoryConfig,
    base_path: Path | None = None,
    *,
    stored_checksums: dict[str, str] | None = None,
) -> DriftReport:
    """Detect drift between indexed files and current filesystem state.

    Loads checksums from `.cognee/checksums.json` (or uses provided checksums),
    compares to current filesystem state, and categorizes drift.

    Args:
        config: Agent memory configuration with content_sources.
        base_path: Base path for file resolution. Defaults to cwd.
        stored_checksums: Optional pre-loaded checksums. If not provided,
            will load from `.cognee/checksums.json`.

    Returns:
        DriftReport with categorized drift entries:
        - deleted_files: Indexed but no longer on filesystem
        - renamed_files: Same content, different path
        - modified_files: Same path, different content
        - unchanged_files: No changes

    Example:
        >>> config = get_config()
        >>> report = detect_drift(config)
        >>> if report.has_drift:
        ...     print(f"Drift detected: {report.total_drifted} files")
    """
    import json

    from agent_memory.ops.coverage import get_all_configured_files

    if base_path is None:
        base_path = Path.cwd()

    # Load stored checksums from file if not provided
    checksums: dict[str, str]
    if stored_checksums is not None:
        checksums = stored_checksums
    else:
        checksums_path = base_path / ".cognee" / "checksums.json"
        if checksums_path.exists():
            with checksums_path.open() as f:
                raw_checksums = json.load(f)
                # Convert relative paths to absolute paths for comparison
                # Relative paths in checksums.json are relative to base_path (where CLI runs from)
                checksums = {}
                for rel_path, file_hash in raw_checksums.items():
                    abs_path = str((base_path / rel_path).resolve())
                    checksums[abs_path] = file_hash
        else:
            checksums = {}

    # Get current filesystem files (returns absolute paths)
    filesystem_files = get_all_configured_files(config, base_path)

    # Build filesystem content map (path -> content)
    filesystem_content: dict[str, str] = {}
    for file_path in filesystem_files:
        path_obj = Path(file_path)
        if path_obj.exists():
            content = path_obj.read_text(encoding="utf-8", errors="replace")
            filesystem_content[file_path] = content

    # Detect deleted files (in checksums but not on filesystem)
    deleted = detect_deleted_files(filesystem_files, list(checksums.keys()))

    # Detect modified files (in both, but different hash)
    modified: list[str] = []
    for file_path, stored_hash in checksums.items():
        if file_path in filesystem_content:
            current_hash = compute_content_hash(filesystem_content[file_path])
            if current_hash != stored_hash:
                modified.append(file_path)

    # Detect renamed files (same hash, different path)
    # Build hash -> path maps (supporting multiple files per hash to handle duplicates)
    stored_hash_to_paths: dict[str, list[str]] = {}
    for path, file_hash in checksums.items():
        stored_hash_to_paths.setdefault(file_hash, []).append(path)

    current_hash_to_paths: dict[str, list[str]] = {}
    for path, content in filesystem_content.items():
        current_hash_to_paths.setdefault(compute_content_hash(content), []).append(path)

    renamed: list[list[str]] = []
    for stored_hash, stored_paths in stored_hash_to_paths.items():
        if stored_hash in current_hash_to_paths:
            current_paths = current_hash_to_paths[stored_hash]
            # Only detect rename when unambiguous: one stored path, one current path
            # and paths are different (actual rename, not same file)
            if len(stored_paths) == 1 and len(current_paths) == 1:
                stored_path = stored_paths[0]
                current_path = current_paths[0]
                if current_path != stored_path:
                    # Same content, different path = renamed
                    renamed.append([stored_path, current_path])

    # Unchanged files (in both with same hash)
    unchanged: list[str] = []
    for file_path, stored_hash in checksums.items():
        if file_path in filesystem_content:
            current_hash = compute_content_hash(filesystem_content[file_path])
            if current_hash == stored_hash:
                unchanged.append(file_path)

    return DriftReport(
        deleted_files=sorted(deleted),
        renamed_files=sorted(renamed, key=lambda x: x[0]),
        modified_files=sorted(modified),
        unchanged_files=sorted(unchanged),
    )
