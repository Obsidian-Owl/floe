"""Dagster orchestrator plugin for floe data platform.

This package provides the Dagster orchestrator plugin implementation that enables
Dagster as the orchestration platform for floe data pipelines. The plugin
generates Dagster Definitions from CompiledArtifacts and provides Helm values
for K8s deployment.

Key Features:
    - Generates Dagster Definitions from CompiledArtifacts
    - Creates software-defined assets from dbt transforms
    - Provides Helm values for K8s deployment
    - Emits OpenLineage events for data lineage
    - Supports cron-based scheduling with timezone support

Example:
    >>> from floe_orchestrator_dagster import DagsterOrchestratorPlugin
    >>> plugin = DagsterOrchestratorPlugin()
    >>> plugin.name
    'dagster'
    >>> definitions = plugin.create_definitions(compiled_artifacts)

Entry Point:
    This plugin is registered via entry point `floe.orchestrators = dagster`
    and discovered automatically by the floe plugin registry.

Performance Note:
    This package uses lazy imports to minimize startup time. The main plugin
    class loads quickly (~250ms), while IOManager and Dagster-specific features
    are loaded on-demand when first accessed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Eager imports - these are lightweight and commonly needed
from floe_orchestrator_dagster.plugin import DagsterOrchestratorPlugin

# Metadata keys are string constants - no import overhead
ICEBERG_TABLE_KEY = "iceberg_table"
ICEBERG_NAMESPACE_KEY = "iceberg_namespace"
ICEBERG_WRITE_MODE_KEY = "iceberg_write_mode"
ICEBERG_PARTITION_FILTER_KEY = "iceberg_partition_filter"
ICEBERG_UPSERT_KEYS_KEY = "iceberg_upsert_keys"
ICEBERG_PARTITION_COLUMN_KEY = "iceberg_partition_column"
ICEBERG_SNAPSHOT_PROPS_KEY = "iceberg_snapshot_props"

if TYPE_CHECKING:
    from floe_orchestrator_dagster.io_manager import (
        IcebergIOManager,
        IcebergIOManagerConfig,
        create_iceberg_io_manager,
    )

__all__ = [
    # Plugin (eager)
    "DagsterOrchestratorPlugin",
    # IOManager (lazy - triggers dagster import)
    "IcebergIOManager",
    "IcebergIOManagerConfig",
    "create_iceberg_io_manager",
    # Metadata keys (eager - string constants)
    "ICEBERG_TABLE_KEY",
    "ICEBERG_NAMESPACE_KEY",
    "ICEBERG_WRITE_MODE_KEY",
    "ICEBERG_PARTITION_FILTER_KEY",
    "ICEBERG_UPSERT_KEYS_KEY",
    "ICEBERG_PARTITION_COLUMN_KEY",
    "ICEBERG_SNAPSHOT_PROPS_KEY",
]

__version__ = "0.1.0"

# Lazy imports for heavy Dagster dependencies
# These are loaded on first access to minimize startup time
_LAZY_IMPORTS = {
    "IcebergIOManager": "floe_orchestrator_dagster.io_manager",
    "IcebergIOManagerConfig": "floe_orchestrator_dagster.io_manager",
    "create_iceberg_io_manager": "floe_orchestrator_dagster.io_manager",
}


def __getattr__(name: str) -> Any:
    """Lazy import handler for IOManager and related classes.

    This enables lazy loading of the IOManager which triggers the full
    Dagster import chain (~400ms). The main plugin class loads quickly.

    Args:
        name: Attribute name being accessed.

    Returns:
        The lazily imported object.

    Raises:
        AttributeError: If the name is not a known lazy import.
    """
    if name in _LAZY_IMPORTS:
        module_path = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
