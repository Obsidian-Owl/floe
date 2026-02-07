# API Contract: Orchestrator Ingestion Wiring

**Created**: 2026-02-07
**Version**: 0.1.0
**Package**: `plugins/floe-orchestrator-dagster` (orchestrator-specific)

## Overview

This contract defines the orchestrator-side wiring for ingestion plugins. The pattern follows Epic 4E (semantic layer wiring) — two-function factory pattern with graceful degradation. All orchestrator-specific code lives in the orchestrator plugin, not in the ingestion plugin.

## Resource Factory Interface

```python
from __future__ import annotations

from typing import Any

from floe_core.compiled_artifacts import ResolvedPlugins
from floe_core.schemas.plugin_ref import PluginRef


def create_ingestion_resources(
    ingestion_ref: PluginRef,
) -> dict[str, Any]:
    """Create ingestion resources from a PluginRef.

    Loads the ingestion plugin via the plugin registry,
    applies configuration from PluginRef.config, and
    returns a dict of orchestrator resources.

    Args:
        ingestion_ref: PluginRef with type="dlt" and config dict.

    Returns:
        Dict of orchestrator resources. For Dagster:
        {"dlt": DagsterDltResource(...)}.

    Raises:
        Exception: If plugin loading or configuration fails.
    """
    ...


def try_create_ingestion_resources(
    plugins: ResolvedPlugins | None,
) -> dict[str, Any]:
    """Safe wrapper for create_ingestion_resources.

    Returns empty dict if plugins is None or plugins.ingestion
    is None (graceful degradation). Re-raises exceptions from
    create_ingestion_resources (does not swallow errors).

    Args:
        plugins: ResolvedPlugins from CompiledArtifacts, or None.

    Returns:
        Dict of orchestrator resources, or {} if no ingestion configured.

    Raises:
        Exception: Re-raised from create_ingestion_resources on failure.
    """
    ...
```

## Asset Factory Interface (Dagster-Specific)

```python
from dagster import AssetsDefinition
from dagster_embedded_elt.dlt import DagsterDltTranslator

from floe_core.compiled_artifacts import CompiledArtifacts
from floe_core.plugins.ingestion import IngestionPlugin


class FloeIngestionTranslator(DagsterDltTranslator):
    """Custom translator mapping dlt resources to Dagster asset keys.

    Naming convention: ingestion__{source_name}__{resource_name}

    Example:
        dlt resource "customers" from source "salesforce"
        -> Dagster asset key: ["ingestion", "salesforce", "customers"]
    """

    def get_asset_spec(self, data: ...) -> ...:
        """Override to produce floe naming convention.

        Includes metadata: source_type, destination_table, write_mode.
        """
        ...


def create_ingestion_assets(
    artifacts: CompiledArtifacts,
    dlt_plugin: IngestionPlugin,
) -> list[AssetsDefinition]:
    """Create Dagster asset definitions from ingestion config.

    For each source in the ingestion config, creates a @dlt_assets
    function that uses DagsterDltResource to run the dlt pipeline.

    Args:
        artifacts: CompiledArtifacts with plugins.ingestion configured.
        dlt_plugin: Loaded and configured IngestionPlugin instance.

    Returns:
        List of Dagster AssetsDefinition for all ingestion sources.
    """
    ...
```

## Wiring Integration Point

```python
# In plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py
# MODIFY existing create_definitions() method:

class DagsterOrchestratorPlugin:
    def create_definitions(self) -> Definitions:
        # ... existing code ...

        # Existing wiring
        resources = self._create_iceberg_resources(validated.plugins)
        semantic_resources = self._create_semantic_resources(validated.plugins)
        resources.update(semantic_resources)

        # NEW: Ingestion wiring
        ingestion_resources = self._create_ingestion_resources(validated.plugins)
        resources.update(ingestion_resources)

        # NEW: Ingestion assets
        if "dlt" in ingestion_resources:
            ingestion_assets = create_ingestion_assets(
                artifacts=validated,
                dlt_plugin=ingestion_resources["dlt"],
            )
            all_assets.extend(ingestion_assets)

        # ... rest of create_definitions ...
```

## Method Contracts

### try_create_ingestion_resources()

| Input | Condition | Output |
|-------|-----------|--------|
| None | N/A | `{}` (empty dict) |
| plugins with ingestion=None | N/A | `{}` (empty dict) |
| plugins with ingestion=PluginRef(type="dlt") | Success | `{"dlt": <resource>}` |
| plugins with ingestion=PluginRef(type="dlt") | Failure | Exception re-raised |

### create_ingestion_assets()

| Input | Output |
|-------|--------|
| artifacts with N sources configured | N AssetsDefinition objects |
| artifacts with 0 sources | Empty list |

### FloeIngestionTranslator

| dlt Resource Name | Source Name | Dagster Asset Key |
|-------------------|-------------|-------------------|
| "customers" | "salesforce" | `["ingestion", "salesforce", "customers"]` |
| "orders" | "shopify" | `["ingestion", "shopify", "orders"]` |
| "events" | "segment" | `["ingestion", "segment", "events"]` |
