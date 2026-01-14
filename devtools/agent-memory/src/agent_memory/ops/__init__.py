"""Operational management modules for agent-memory.

This package contains modules for operational tasks:
- coverage: Coverage analysis (compare filesystem vs indexed)
- drift: Drift detection (detect stale/outdated entries)
- health: Health checking
- batch: Batch operations
- quality: Quality validation
"""

from __future__ import annotations

from agent_memory.ops.coverage import (
    CoverageReport,
    compare_filesystem_vs_indexed,
    identify_missing_files,
)
from agent_memory.ops.drift import (
    DriftReport,
    compute_content_hash,
    detect_deleted_files,
    detect_modified_files,
    detect_renamed_files,
)

__all__ = [
    # Coverage
    "CoverageReport",
    "compare_filesystem_vs_indexed",
    "identify_missing_files",
    # Drift
    "DriftReport",
    "compute_content_hash",
    "detect_deleted_files",
    "detect_modified_files",
    "detect_renamed_files",
]
