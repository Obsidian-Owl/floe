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

from floe_orchestrator_dagster.plugin import DagsterOrchestratorPlugin

__all__ = ["DagsterOrchestratorPlugin"]

__version__ = "0.1.0"
