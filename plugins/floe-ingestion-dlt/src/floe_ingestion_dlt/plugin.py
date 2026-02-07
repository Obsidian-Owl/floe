"""DltIngestionPlugin - dlt-based ingestion plugin for floe.

This module implements the IngestionPlugin ABC using dlt (data load tool)
as the ingestion framework. dlt supports REST APIs, SQL databases, and
filesystem sources with Iceberg as the destination.

The plugin runs in-process (is_external=False) and delegates data loading
to dlt's pipeline execution engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.ingestion import IngestionConfig, IngestionPlugin, IngestionResult

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ["DltIngestionPlugin"]


class DltIngestionPlugin(IngestionPlugin):
    """dlt-based ingestion plugin for the floe data platform.

    Implements the IngestionPlugin ABC using dlt (data load tool) v1.21+
    for loading data from external sources into Iceberg tables.

    Features:
        - REST API, SQL database, and filesystem source support
        - Iceberg destination via Polaris REST catalog
        - Schema contract enforcement (evolve, freeze, discard_value)
        - Write modes: append, replace, merge
        - OTel tracing and structured logging
        - Retry with exponential backoff

    Example:
        >>> plugin = DltIngestionPlugin()
        >>> plugin.startup()
        >>> pipeline = plugin.create_pipeline(config)
        >>> result = plugin.run(pipeline)
        >>> result.success
        True
    """

    @property
    def name(self) -> str:
        """Plugin identifier."""
        return "dlt"

    @property
    def version(self) -> str:
        """Plugin version (semver)."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Required floe API version."""
        return "1.0"

    @property
    def description(self) -> str:
        """Human-readable plugin description."""
        return "dlt-based data ingestion plugin for loading from REST APIs, SQL databases, and filesystems into Iceberg tables"

    @property
    def is_external(self) -> bool:
        """dlt runs in-process, not as an external service."""
        return False

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return the Pydantic configuration model.

        Returns:
            DltIngestionConfig class for validation.
        """
        # Import here to avoid circular imports during discovery
        from floe_ingestion_dlt.config import DltIngestionConfig

        return DltIngestionConfig

    def startup(self) -> None:
        """Initialize the plugin.

        Validates that dlt is importable and source packages are available.
        """

    def shutdown(self) -> None:
        """Clean up plugin resources."""

    def health_check(self) -> HealthStatus:
        """Check plugin health.

        Verifies dlt is importable and catalog is reachable.

        Returns:
            HealthStatus with current state.
        """
        try:
            import dlt as _dlt  # noqa: F401

            return HealthStatus(
                state=HealthState.HEALTHY,
                message="dlt is available",
            )
        except ImportError:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="dlt package is not installed",
            )

    def create_pipeline(self, config: IngestionConfig) -> Any:
        """Create a dlt pipeline from configuration.

        Args:
            config: Ingestion pipeline configuration.

        Returns:
            Configured dlt pipeline object.

        Raises:
            NotImplementedError: Pending implementation in T021.
        """
        raise NotImplementedError("create_pipeline will be implemented in T021")

    def run(self, pipeline: Any, **kwargs: Any) -> IngestionResult:
        """Execute the dlt pipeline.

        Args:
            pipeline: Pipeline object from create_pipeline().
            **kwargs: Additional execution options.

        Returns:
            IngestionResult with execution metrics.

        Raises:
            NotImplementedError: Pending implementation in T022.
        """
        raise NotImplementedError("run will be implemented in T022")

    def get_destination_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        """Generate Iceberg destination configuration.

        Args:
            catalog_config: Catalog connection configuration.

        Returns:
            dlt destination configuration dict.

        Raises:
            NotImplementedError: Pending implementation in T023.
        """
        raise NotImplementedError("get_destination_config will be implemented in T023")
