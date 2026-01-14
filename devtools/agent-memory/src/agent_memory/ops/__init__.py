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
    analyze_coverage,
    compare_filesystem_vs_indexed,
    get_all_configured_files,
    get_files_from_source,
    identify_missing_files,
)
from agent_memory.ops.drift import (
    DriftReport,
    compute_content_hash,
    detect_deleted_files,
    detect_drift,
    detect_modified_files,
    detect_renamed_files,
)
from agent_memory.ops.health import (
    ComponentHealth,
    HealthCheckResult,
    check_cognee_cloud,
    check_llm_provider,
    check_local_state,
    health_check,
)

__all__ = [
    # Coverage
    "CoverageReport",
    "analyze_coverage",
    "compare_filesystem_vs_indexed",
    "get_all_configured_files",
    "get_files_from_source",
    "identify_missing_files",
    # Drift
    "DriftReport",
    "compute_content_hash",
    "detect_deleted_files",
    "detect_drift",
    "detect_modified_files",
    "detect_renamed_files",
    # Health
    "ComponentHealth",
    "HealthCheckResult",
    "check_cognee_cloud",
    "check_llm_provider",
    "check_local_state",
    "health_check",
]
