"""Operational management modules for agent-memory.

This package contains modules for operational tasks:
- batch: Batch operations
- coverage: Coverage analysis (compare filesystem vs indexed)
- drift: Drift detection (detect stale/outdated entries)
- health: Health checking
- quality: Quality validation
"""

from __future__ import annotations

from agent_memory.ops.batch import (
    BatchCheckpoint,
    BatchProgress,
    BatchResult,
    batch_load,
    clear_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
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
from agent_memory.ops.quality import (
    QualityReport,
    TestQuery,
    TestResult,
    check_keywords_in_results,
    create_default_test_queries,
    validate_quality,
)

__all__ = [
    # Batch
    "BatchCheckpoint",
    "BatchProgress",
    "BatchResult",
    "batch_load",
    "clear_checkpoint",
    "load_checkpoint",
    "save_checkpoint",
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
    # Quality
    "QualityReport",
    "TestQuery",
    "TestResult",
    "check_keywords_in_results",
    "create_default_test_queries",
    "validate_quality",
]
