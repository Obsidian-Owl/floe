# API Contract: DltIngestionPlugin

**Created**: 2026-02-07
**Version**: 0.1.0
**Package**: `plugins/floe-ingestion-dlt`

## Overview

DltIngestionPlugin is the default implementation of the `IngestionPlugin` ABC. It wraps dlt (data load tool) v1.21.0 to provide data pipeline creation and execution. Destination handoff is runtime-bound: platform composition builds the storage/catalog binding, the orchestrator passes it through `IngestionConfig.runtime_binding`, and the plugin uses `destination_filesystem` to configure dlt's filesystem destination. The plugin is orchestrator-agnostic; all orchestrator-specific wiring lives in the orchestrator plugin.

## Class Interface

```python
from __future__ import annotations

from typing import Any

from floe_core.plugins.ingestion import (
    IngestionConfig,
    IngestionPlugin,
    IngestionResult,
)
from floe_core.plugin_metadata import HealthState, HealthStatus

from floe_ingestion_dlt.config import DltIngestionConfig


class DltIngestionPlugin(IngestionPlugin):
    """dlt-based implementation of IngestionPlugin.

    Provides data ingestion via dlt pipelines using the filesystem destination
    with table_format="iceberg" and catalog environment from DltIngestionBinding.
    Supports REST API, SQL Database, and Filesystem source types.

    Example:
        >>> from floe_ingestion_dlt import DltIngestionPlugin, DltIngestionConfig
        >>> config = DltIngestionConfig(sources=[...])
        >>> plugin = DltIngestionPlugin(config=config)
        >>> plugin.startup()
        >>> pipeline = plugin.create_pipeline(ingestion_config_with_runtime_binding)
        >>> result = plugin.run(pipeline)
        >>> plugin.shutdown()

    Args:
        config: Plugin configuration with ingestion-owned source and retry details.
    """

    def __init__(self, config: DltIngestionConfig) -> None:
        """Initialize plugin with configuration.

        Args:
            config: Validated DltIngestionConfig instance.
        """
        ...

    # ──────────────────────────────────────────────
    # PluginMetadata properties
    # ──────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Plugin name: 'dlt'."""
        ...

    @property
    def version(self) -> str:
        """Plugin version: '0.1.0'."""
        ...

    @property
    def floe_api_version(self) -> str:
        """Floe API version: '1.0'."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        ...

    # ──────────────────────────────────────────────
    # IngestionPlugin abstract property
    # ──────────────────────────────────────────────

    @property
    def is_external(self) -> bool:
        """Returns False — dlt runs in-process, not as an external service."""
        ...

    # ──────────────────────────────────────────────
    # Lifecycle methods (from PluginMetadata)
    # ──────────────────────────────────────────────

    def startup(self) -> None:
        """Initialize plugin.

        Validates config, verifies dlt is importable, verifies
        required source packages are available.

        Raises:
            ImportError: If dlt or required source packages are missing.
            PipelineConfigurationError: If config is invalid.

        OTel Span: floe.ingestion.startup
        """
        ...

    def shutdown(self) -> None:
        """Cleanup plugin resources.

        Releases any held resources and logs shutdown.

        OTel Span: floe.ingestion.shutdown
        """
        ...

    def health_check(self) -> HealthStatus:
        """Check plugin health.

        Verifies:
        1. dlt is importable
        2. Plugin lifecycle state is ready for runtime use
        3. Runtime binding is present when destination configuration is needed
           (catalog and object storage network checks are deferred to create/run)

        Returns:
            HealthStatus with state=HEALTHY or UNHEALTHY.

        OTel Span: floe.ingestion.health_check
        """
        ...

    def get_config_schema(self) -> type[DltIngestionConfig]:
        """Return the Pydantic config model class.

        Returns:
            DltIngestionConfig class (not instance).
        """
        ...

    # ──────────────────────────────────────────────
    # IngestionPlugin abstract methods
    # ──────────────────────────────────────────────

    def create_pipeline(self, config: IngestionConfig) -> Any:
        """Create a dlt pipeline from ingestion config.

        Configures a dlt pipeline with:
        - pipeline_name derived from destination_table
        - destination="filesystem" using runtime_binding.destination_filesystem
        - dataset_name from Iceberg namespace

        Args:
            config: Pipeline configuration with source_type,
                     source_config, destination_table, write_mode.

        Returns:
            Configured dlt pipeline object ready for execution.

        Raises:
            ValidationError: If config is invalid.
            SourceConnectionError: If source is unreachable.
            PipelineConfigurationError: If dlt source package missing.

        OTel Span: floe.ingestion.create_pipeline
            Attributes:
            - ingestion.source_type
            - ingestion.destination_table
            - ingestion.pipeline_name
        """
        ...

    def run(self, pipeline: Any, **kwargs: Any) -> IngestionResult:
        """Execute a dlt pipeline and return results.

        Runs the pipeline with the configured write disposition
        and schema contract. Handles incremental loading via dlt's
        cursor mechanism. Applies retry logic for transient errors.

        Args:
            pipeline: dlt pipeline object from create_pipeline().
            **kwargs: Additional arguments passed to dlt pipeline.run().

        Returns:
            IngestionResult with success status, metrics, and errors.

        OTel Span: floe.ingestion.run
            Attributes:
            - ingestion.rows_loaded
            - ingestion.bytes_written
            - ingestion.duration_seconds
            - ingestion.write_mode
            - ingestion.schema_contract
            On error:
            - error.type
            - error.message
            - error.category
        """
        ...

```

## Method Contracts

### create_pipeline()

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| config | IngestionConfig | Yes | Source type, config, destination, write mode, runtime binding |

| Output | Type | Description |
|--------|------|-------------|
| pipeline | dlt.Pipeline | Configured dlt pipeline with filesystem destination ready for run() |

| Error | When | Category |
|-------|------|----------|
| ValidationError | Invalid source_type, empty fields | CONFIGURATION |
| PipelineConfigurationError | Missing runtime binding or destination_filesystem | CONFIGURATION |
| SourceConnectionError | Source unreachable | TRANSIENT |
| PipelineConfigurationError | dlt source package not installed | CONFIGURATION |

### run()

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| pipeline | Any (dlt.Pipeline) | Yes | Pipeline from create_pipeline() |
| **kwargs | Any | No | Pass-through to dlt pipeline.run() |

| Output | Type | Description |
|--------|------|-------------|
| result | IngestionResult | Success/failure, metrics, errors |

| Error | When | Category |
|-------|------|----------|
| DestinationWriteError | Iceberg write fails | TRANSIENT |
| SchemaContractViolation | Schema freeze rejects change | PERMANENT |
| SourceConnectionError | Source fails during extract | TRANSIENT |

### Runtime destination handoff

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| config.runtime_binding.destination_filesystem | dict[str, Any] | Yes | dlt filesystem destination settings including bucket URL and storage credentials |
| config.runtime_binding.iceberg_catalog_env | dict[str, str] | Yes | PyIceberg catalog environment for Polaris REST catalog resolution |

| Output | Type | Description |
|--------|------|-------------|
| pipeline | dlt.Pipeline | dlt pipeline configured with `filesystem(**destination_filesystem)` and runtime catalog environment |

### health_check()

| Output | Type | Description |
|--------|------|-------------|
| status | HealthStatus | HEALTHY or UNHEALTHY with message |

## Entry Point Registration

```toml
[project.entry-points."floe.ingestion"]
dlt = "floe_ingestion_dlt:DltIngestionPlugin"
```

## Plugin Metadata

| Property | Value |
|----------|-------|
| name | "dlt" |
| version | "0.1.0" |
| floe_api_version | "1.0" |
| is_external | False |
| description | "dlt ingestion plugin for floe data platform" |
