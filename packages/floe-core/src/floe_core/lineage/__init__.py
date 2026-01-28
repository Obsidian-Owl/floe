"""Core lineage types and protocols for OpenLineage integration.

This module provides floe's portable lineage types that abstract over
the OpenLineage SDK. Orchestrator plugins (Dagster, Airflow, Prefect)
use these types instead of importing openlineage.* directly.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
"""

from floe_core.lineage.protocols import LineageExtractor, LineageTransport
from floe_core.lineage.types import (
    LineageDataset,
    LineageEvent,
    LineageJob,
    LineageRun,
    RunState,
)

__all__ = [
    "LineageDataset",
    "LineageEvent",
    "LineageJob",
    "LineageRun",
    "RunState",
    "LineageExtractor",
    "LineageTransport",
]
