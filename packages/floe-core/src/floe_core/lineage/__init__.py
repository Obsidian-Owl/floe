"""Core lineage types and protocols for OpenLineage integration.

This module provides floe's portable lineage types that abstract over
the OpenLineage SDK. Orchestrator plugins (Dagster, Airflow, Prefect)
use these types instead of importing openlineage.* directly.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
"""

from floe_core.lineage.catalog_integration import (
    CatalogDatasetResolver,
    CentralizedNamespaceStrategy,
    DataMeshNamespaceStrategy,
    NamespaceResolver,
    NamespaceStrategy,
    SimpleNamespaceStrategy,
)
from floe_core.lineage.emitter import LineageEmitter, create_emitter
from floe_core.lineage.events import EventBuilder, to_openlineage_event
from floe_core.lineage.extractors import DbtLineageExtractor
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
    "LineageEmitter",
    "LineageEvent",
    "LineageJob",
    "LineageRun",
    "RunState",
    "LineageExtractor",
    "LineageTransport",
    "EventBuilder",
    "create_emitter",
    "to_openlineage_event",
    "DbtLineageExtractor",
    "NamespaceStrategy",
    "SimpleNamespaceStrategy",
    "CentralizedNamespaceStrategy",
    "DataMeshNamespaceStrategy",
    "NamespaceResolver",
    "CatalogDatasetResolver",
]
