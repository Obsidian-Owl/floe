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
"""

from __future__ import annotations

from floe_orchestrator_dagster.io_manager import (
    ICEBERG_NAMESPACE_KEY,
    ICEBERG_PARTITION_COLUMN_KEY,
    ICEBERG_PARTITION_FILTER_KEY,
    ICEBERG_SNAPSHOT_PROPS_KEY,
    ICEBERG_TABLE_KEY,
    ICEBERG_UPSERT_KEYS_KEY,
    ICEBERG_WRITE_MODE_KEY,
    IcebergIOManager,
    IcebergIOManagerConfig,
    create_iceberg_io_manager,
)
from floe_orchestrator_dagster.plugin import DagsterOrchestratorPlugin

__all__ = [
    # Plugin
    "DagsterOrchestratorPlugin",
    # IOManager
    "IcebergIOManager",
    "IcebergIOManagerConfig",
    "create_iceberg_io_manager",
    # Metadata keys
    "ICEBERG_TABLE_KEY",
    "ICEBERG_NAMESPACE_KEY",
    "ICEBERG_WRITE_MODE_KEY",
    "ICEBERG_PARTITION_FILTER_KEY",
    "ICEBERG_UPSERT_KEYS_KEY",
    "ICEBERG_PARTITION_COLUMN_KEY",
    "ICEBERG_SNAPSHOT_PROPS_KEY",
]

__version__ = "0.1.0"
