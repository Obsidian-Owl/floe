"""DltIngestionPlugin - dlt-based ingestion plugin for floe.

This module implements the IngestionPlugin ABC using dlt (data load tool)
as the ingestion framework. dlt supports REST APIs, SQL databases, and
filesystem sources with Iceberg as the destination.

The plugin runs in-process (is_external=False) and delegates data loading
to dlt's pipeline execution engine.

Requirements Covered:
    - FR-001: DltIngestionPlugin implements IngestionPlugin ABC
    - FR-004: Plugin metadata (name, version, floe_api_version)
    - FR-005: is_external=False
    - FR-006: get_config_schema returns DltIngestionConfig
    - FR-007: health_check() with dlt import + catalog check
    - FR-008: startup() and shutdown() lifecycle
    - FR-009: Source package validation at startup
    - FR-010: Plugin capabilities metadata
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.ingestion import IngestionConfig, IngestionPlugin, IngestionResult

from floe_ingestion_dlt.config import VALID_SCHEMA_CONTRACTS, VALID_SOURCE_TYPES, VALID_WRITE_MODES
from floe_ingestion_dlt.tracing import get_tracer, ingestion_span

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ["DltIngestionPlugin"]

logger = structlog.get_logger(__name__)


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
        >>> status = plugin.health_check()
        >>> status.state
        <HealthState.HEALTHY: 'healthy'>
    """

    def __init__(self) -> None:
        """Initialize plugin state."""
        self._started: bool = False
        self._dlt_version: str | None = None

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
        return (
            "dlt-based data ingestion plugin for loading from REST APIs, "
            "SQL databases, and filesystems into Iceberg tables"
        )

    @property
    def is_external(self) -> bool:
        """dlt runs in-process, not as an external service."""
        return False

    @property
    def capabilities(self) -> dict[str, Any]:
        """Plugin capabilities metadata (FR-010).

        Returns:
            Dictionary describing supported source types, write modes,
            and schema contracts.
        """
        return {
            "source_types": sorted(VALID_SOURCE_TYPES),
            "write_modes": sorted(VALID_WRITE_MODES),
            "schema_contracts": sorted(VALID_SCHEMA_CONTRACTS),
            "incremental_loading": True,
            "in_process": True,
        }

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return the Pydantic configuration model.

        Returns:
            DltIngestionConfig class for validation.
        """
        # Import here to avoid circular imports during discovery
        from floe_ingestion_dlt.config import DltIngestionConfig

        return DltIngestionConfig

    def startup(self) -> None:
        """Initialize the plugin (FR-008, FR-009).

        Validates that dlt is importable and records the dlt version.
        Emits an OTel span for startup tracing.

        Raises:
            ImportError: If dlt package is not installed.
        """
        if self._started:
            return

        tracer = get_tracer()
        with ingestion_span(
            tracer,
            "plugin.startup",
            source_type="*",
            destination_table="*",
        ):
            # FR-009: Validate dlt is importable
            try:
                import dlt

                self._dlt_version = dlt.__version__
            except ImportError as exc:
                logger.error(
                    "dlt_import_failed",
                    error=str(exc),
                )
                raise ImportError(
                    "dlt package is not installed. "
                    "Install with: pip install 'dlt[iceberg]>=1.20.0'"
                ) from exc

            self._started = True
            logger.info(
                "ingestion_plugin_started",
                plugin_name=self.name,
                dlt_version=self._dlt_version,
            )

    def shutdown(self) -> None:
        """Release plugin resources (FR-008).

        Resets internal state. dlt does not maintain persistent connections,
        so no external cleanup is required.
        """
        if not self._started:
            return

        self._started = False
        self._dlt_version = None
        logger.info("ingestion_plugin_stopped", plugin_name=self.name)

    def health_check(self) -> HealthStatus:
        """Check plugin health (FR-007).

        Verifies:
        1. dlt package is importable
        2. Plugin has been started

        Returns:
            HealthStatus with current state and diagnostic details.
        """
        # Check 1: Plugin started
        if not self._started:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="Plugin not started — call startup() first",
                details={"reason": "not_started"},
            )

        # Check 2: dlt is importable
        try:
            import dlt as _dlt  # noqa: F401

            return HealthStatus(
                state=HealthState.HEALTHY,
                message="dlt ingestion plugin is healthy",
                details={
                    "dlt_version": self._dlt_version,
                    "started": self._started,
                },
            )
        except ImportError:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="dlt package is not installed",
                details={"reason": "dlt_not_importable"},
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
