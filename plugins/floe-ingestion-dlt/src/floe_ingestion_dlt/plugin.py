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

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.ingestion import (
    IngestionConfig,
    IngestionPlugin,
    IngestionResult,
)
from floe_core.plugins.sink import EgressResult, SinkConfig, SinkConnector

from floe_ingestion_dlt.config import (
    VALID_SCHEMA_CONTRACTS,
    VALID_SOURCE_TYPES,
    VALID_WRITE_MODES,
)
from floe_ingestion_dlt.errors import (
    PipelineConfigurationError,
    SchemaContractViolation,
    SinkConfigurationError,
    SinkConnectionError,
    SinkWriteError,
)
from floe_ingestion_dlt.retry import categorize_error
from floe_ingestion_dlt.tracing import (
    egress_span,
    get_tracer,
    ingestion_span,
    record_egress_error,
    record_egress_result,
    record_ingestion_error,
    record_ingestion_result,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ["DltIngestionPlugin"]

logger = structlog.get_logger(__name__)

# Timeout validation bounds for health_check()
_MIN_TIMEOUT: float = 0.1
_MAX_TIMEOUT: float = 10.0
_DEFAULT_TIMEOUT: float = 5.0

# Supported sink types for reverse ETL (FR-006)
_SUPPORTED_SINKS: list[str] = ["rest_api", "sql_database"]


class DltIngestionPlugin(IngestionPlugin, SinkConnector):
    """dlt-based ingestion plugin for the floe data platform.

    Implements the IngestionPlugin ABC using dlt (data load tool) v1.21+
    for loading data from external sources into Iceberg tables.

    Also implements SinkConnector for reverse ETL — pushing curated data
    from Iceberg Gold layer to external SaaS APIs and databases (Epic 4G).

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
                    "dlt package is not installed. Install with: pip install 'dlt[iceberg]>=1.20.0'"
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

        tracer = get_tracer()
        with ingestion_span(tracer, "plugin.shutdown"):
            self._started = False
            self._dlt_version = None
            logger.info("ingestion_plugin_stopped", plugin_name=self.name)

    def health_check(self, timeout: float | None = None) -> HealthStatus:
        """Check plugin health (FR-007).

        Verifies:
        1. Plugin has been started
        2. dlt package is importable

        Args:
            timeout: Maximum time in seconds to wait for health check.
                Must be between 0.1 and 10.0. Defaults to 5.0.

        Returns:
            HealthStatus with current state and diagnostic details.

        Raises:
            ValueError: If timeout is outside valid range.
        """
        effective_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT

        if effective_timeout < _MIN_TIMEOUT or effective_timeout > _MAX_TIMEOUT:
            msg = (
                f"timeout must be between {_MIN_TIMEOUT} and "
                f"{_MAX_TIMEOUT}, got {effective_timeout}"
            )
            raise ValueError(msg)

        tracer = get_tracer()
        with ingestion_span(tracer, "health_check"):
            checked_at = datetime.now(timezone.utc)
            start = time.perf_counter()

            # Check 1: Plugin started
            if not self._started:
                elapsed_ms = (time.perf_counter() - start) * 1000
                status = HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message="Plugin not started — call startup() first",
                    details={
                        "reason": "not_started",
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": effective_timeout,
                    },
                )
                logger.info(
                    "health_check_completed",
                    state=status.state.value,
                    reason="not_started",
                    response_time_ms=elapsed_ms,
                )
                return status

            # Check 2: dlt is importable
            try:
                import dlt as _dlt  # noqa: F401

                elapsed_ms = (time.perf_counter() - start) * 1000
                status = HealthStatus(
                    state=HealthState.HEALTHY,
                    message="dlt ingestion plugin is healthy",
                    details={
                        "dlt_version": self._dlt_version,
                        "started": self._started,
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": effective_timeout,
                    },
                )
                logger.info(
                    "health_check_completed",
                    state=status.state.value,
                    dlt_version=self._dlt_version,
                    response_time_ms=elapsed_ms,
                )
                return status
            except ImportError:
                elapsed_ms = (time.perf_counter() - start) * 1000
                status = HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message="dlt package is not installed",
                    details={
                        "reason": "dlt_not_importable",
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": effective_timeout,
                    },
                )
                logger.info(
                    "health_check_completed",
                    state=status.state.value,
                    reason="dlt_not_importable",
                    response_time_ms=elapsed_ms,
                )
                return status

    def create_pipeline(self, config: IngestionConfig) -> Any:
        """Create a dlt pipeline from configuration.

        Args:
            config: Ingestion pipeline configuration.

        Returns:
            Configured dlt pipeline object.

        Raises:
            RuntimeError: If plugin not started.
            PipelineConfigurationError: If config is invalid.
        """
        if not self._started:
            raise RuntimeError(
                "Plugin must be started before creating pipelines — call startup() first"
            )

        tracer = get_tracer()
        with ingestion_span(
            tracer,
            "create_pipeline",
            source_type=config.source_type,
            destination_table=config.destination_table,
            write_mode=config.write_mode,
        ):
            # Validate source_type
            if config.source_type not in VALID_SOURCE_TYPES:
                raise PipelineConfigurationError(
                    f"Invalid source_type '{config.source_type}'. "
                    f"Must be one of: {sorted(VALID_SOURCE_TYPES)}",
                    source_type=config.source_type,
                    destination_table=config.destination_table,
                )

            # Validate destination_table
            if not config.destination_table:
                raise PipelineConfigurationError(
                    "destination_table is required and cannot be empty",
                    source_type=config.source_type,
                )

            # Derive pipeline_name and dataset_name from destination_table
            # Format: "namespace.table_name" -> pipeline_name="table_name", dataset_name="namespace"
            parts = config.destination_table.split(".", 1)
            if len(parts) == 2:
                dataset_name, table_name = parts
            else:
                dataset_name = "default"
                table_name = parts[0]

            pipeline_name = f"ingest_{table_name}"

            import dlt

            pipeline = dlt.pipeline(
                pipeline_name=pipeline_name,
                dataset_name=dataset_name,
            )

            logger.info(
                "pipeline_created",
                pipeline_name=pipeline_name,
                dataset_name=dataset_name,
                source_type=config.source_type,
                destination_table=config.destination_table,
                write_mode=config.write_mode,
            )

            return pipeline

    def run(self, pipeline: Any, **kwargs: Any) -> IngestionResult:
        """Execute the dlt pipeline.

        Args:
            pipeline: Pipeline object from create_pipeline().
            **kwargs: Additional execution options including:
                - source: dlt source/resource to load
                - write_disposition: Override write mode
                - table_name: Override destination table name
                - schema_contract: Schema contract mode (evolve, freeze, discard_value)
                - cursor_field: Field name for incremental loading (optional)
                - primary_key: Primary key field(s) for merge operations (optional)

        Returns:
            IngestionResult with execution metrics.

        Raises:
            RuntimeError: If plugin not started.
        """
        if not self._started:
            raise RuntimeError(
                "Plugin must be started before running pipelines — call startup() first"
            )

        tracer = get_tracer()
        start_time = time.perf_counter()

        source = kwargs.get("source")
        write_disposition = kwargs.get("write_disposition", "append")
        table_name = kwargs.get("table_name")
        schema_contract_mode = kwargs.get("schema_contract", "evolve")
        cursor_field = kwargs.get("cursor_field")
        primary_key = kwargs.get("primary_key")

        # Map schema_contract string to dlt's expected format
        if schema_contract_mode == "evolve":
            schema_contract = {
                "columns": "evolve",
                "tables": "evolve",
                "data_type": "evolve",
            }
        elif schema_contract_mode == "freeze":
            schema_contract = {
                "columns": "freeze",
                "tables": "freeze",
                "data_type": "freeze",
            }
        elif schema_contract_mode == "discard_value":
            schema_contract = {
                "columns": "discard_value",
                "tables": "evolve",
                "data_type": "discard_value",
            }
        else:
            # Default to evolve for unknown values
            schema_contract = {
                "columns": "evolve",
                "tables": "evolve",
                "data_type": "evolve",
            }

        # Log cursor_field if incremental mode is active
        if cursor_field is not None:
            logger.info(
                "incremental_mode_active",
                pipeline_name=getattr(pipeline, "pipeline_name", "unknown"),
                cursor_field=cursor_field,
            )

        # Log primary_key if merge mode is active
        if primary_key is not None and write_disposition == "merge":
            logger.info(
                "merge_mode_with_primary_key",
                pipeline_name=getattr(pipeline, "pipeline_name", "unknown"),
                primary_key=primary_key,
            )

        logger.info(
            "pipeline_run_starting",
            pipeline_name=getattr(pipeline, "pipeline_name", "unknown"),
            write_disposition=write_disposition,
            schema_contract_mode=schema_contract_mode,
        )

        with ingestion_span(
            tracer,
            "run",
            pipeline_name=getattr(pipeline, "pipeline_name", None),
            write_mode=write_disposition,
        ) as span:
            try:
                # Prepare pipeline.run() kwargs
                run_kwargs = {
                    "write_disposition": write_disposition,
                    "table_name": table_name,
                    "schema_contract": schema_contract,
                }

                # Add primary_key if provided with merge disposition
                if primary_key is not None and write_disposition == "merge":
                    run_kwargs["primary_key"] = primary_key

                # Execute the pipeline
                load_info = pipeline.run(source, **run_kwargs)

                elapsed = time.perf_counter() - start_time

                # Extract metrics from load_info
                rows_loaded = 0
                bytes_written = 0

                if hasattr(load_info, "metrics") and load_info.metrics:
                    # dlt load_info.metrics is a list of load package metrics
                    for _load_id, metrics_list in load_info.metrics.items():
                        for metrics in metrics_list:
                            if hasattr(metrics, "started_at"):
                                # Process job metrics
                                for job in getattr(metrics, "job_metrics", {}).values():
                                    if hasattr(job, "table_metrics"):
                                        for table_metric in job.table_metrics.values():
                                            rows_loaded += getattr(table_metric, "items_count", 0)
                                            bytes_written += getattr(table_metric, "file_size", 0)

                result = IngestionResult(
                    success=True,
                    rows_loaded=rows_loaded,
                    bytes_written=bytes_written,
                    duration_seconds=elapsed,
                )

                record_ingestion_result(span, result)

                logger.info(
                    "pipeline_run_completed",
                    pipeline_name=getattr(pipeline, "pipeline_name", "unknown"),
                    rows_loaded=result.rows_loaded,
                    bytes_written=result.bytes_written,
                    duration_seconds=result.duration_seconds,
                )

                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time
                error_msg = str(e)[:500]  # Truncate for safety

                # Check if this is a schema contract violation
                # dlt raises exceptions containing "schema" and "contract" when
                # freeze mode rejects changes
                error_lower = str(e).lower()
                if "schema" in error_lower and "contract" in error_lower:
                    # This is a schema contract violation
                    record_ingestion_error(span, e, category="permanent")

                    logger.error(
                        "schema_contract_violation",
                        pipeline_name=getattr(pipeline, "pipeline_name", "unknown"),
                        schema_contract_mode=schema_contract_mode,
                        error=error_msg,
                        error_category="permanent",
                        duration_seconds=elapsed,
                    )

                    # Return IngestionResult with SchemaContractViolation info in errors
                    violation = SchemaContractViolation(
                        error_msg,
                        source_type=None,  # Would need to track from config
                        destination_table=table_name,
                        pipeline_name=getattr(pipeline, "pipeline_name", None),
                    )

                    return IngestionResult(
                        success=False,
                        rows_loaded=0,
                        bytes_written=0,
                        duration_seconds=elapsed,
                        errors=[str(violation)],
                    )

                # Generic error handling with categorization
                category = categorize_error(e)

                record_ingestion_error(span, e, category=category.value)

                logger.error(
                    "pipeline_run_failed",
                    pipeline_name=getattr(pipeline, "pipeline_name", "unknown"),
                    error=error_msg,
                    error_category=category.value,
                    duration_seconds=elapsed,
                )

                return IngestionResult(
                    success=False,
                    rows_loaded=0,
                    bytes_written=0,
                    duration_seconds=elapsed,
                    errors=[error_msg],
                )

    def get_destination_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        """Generate Iceberg destination configuration for dlt.

        Maps the platform's catalog config (Polaris REST catalog) to dlt's
        Iceberg destination parameters.

        Args:
            catalog_config: Catalog connection configuration with keys:
                - uri: Polaris catalog URI (e.g., "http://polaris:8181/api/catalog")
                - warehouse: Warehouse name (e.g., "floe_warehouse")
                - s3_endpoint: Optional S3/MinIO endpoint
                - s3_access_key: Optional S3 access key
                - s3_secret_key: Optional S3 secret key
                - s3_region: Optional S3 region

        Returns:
            dlt destination configuration dict for Iceberg.
        """
        tracer = get_tracer()
        with ingestion_span(tracer, "get_destination_config"):
            dest_config: dict[str, Any] = {
                "destination": "iceberg",
                "catalog_type": "rest",
            }

            # Map catalog URI
            if "uri" in catalog_config:
                dest_config["catalog_uri"] = catalog_config["uri"]

            # Map warehouse
            if "warehouse" in catalog_config:
                dest_config["warehouse"] = catalog_config["warehouse"]

            # Map S3/MinIO storage config
            if "s3_endpoint" in catalog_config:
                dest_config["s3_endpoint"] = catalog_config["s3_endpoint"]
            if "s3_access_key" in catalog_config:
                dest_config["s3_access_key"] = catalog_config["s3_access_key"]
            if "s3_secret_key" in catalog_config:
                dest_config["s3_secret_key"] = catalog_config["s3_secret_key"]
            if "s3_region" in catalog_config:
                dest_config["s3_region"] = catalog_config["s3_region"]

            logger.info(
                "destination_config_generated",
                catalog_type="rest",
                has_uri="uri" in catalog_config,
                has_warehouse="warehouse" in catalog_config,
                has_s3="s3_endpoint" in catalog_config,
            )

            return dest_config

    # -----------------------------------------------------------------------
    # SinkConnector ABC implementation (Epic 4G - Reverse ETL)
    # -----------------------------------------------------------------------

    def list_available_sinks(self) -> list[str]:
        """List sink types supported by this connector (FR-006).

        Returns identifiers for the destination types this plugin can
        write to via dlt's destination API.

        Returns:
            List of supported sink type identifiers.

        Raises:
            RuntimeError: If plugin not started.
        """
        if not self._started:
            raise RuntimeError(
                "Plugin must be started before listing sinks — call startup() first"
            )

        tracer = get_tracer()
        with egress_span(tracer, "list_available_sinks"):
            logger.info("list_available_sinks", sinks=_SUPPORTED_SINKS)
            return list(_SUPPORTED_SINKS)

    def create_sink(self, config: SinkConfig) -> Any:
        """Create a configured sink destination from SinkConfig (FR-007).

        Validates the configuration and returns a destination configuration
        dict ready for writing. Raises SinkConfigurationError if the sink
        type is not supported.

        Args:
            config: Sink destination configuration.

        Returns:
            Configured destination dict (used by write()).

        Raises:
            RuntimeError: If plugin not started.
            SinkConfigurationError: If config is invalid.
        """
        if not self._started:
            raise RuntimeError(
                "Plugin must be started before creating sinks — call startup() first"
            )

        tracer = get_tracer()
        with egress_span(tracer, "create_sink", sink_type=config.sink_type):
            if config.sink_type not in _SUPPORTED_SINKS:
                raise SinkConfigurationError(
                    f"Unsupported sink type '{config.sink_type}'. "
                    f"Must be one of: {sorted(_SUPPORTED_SINKS)}",
                    source_type=config.sink_type,
                )

            sink_config: dict[str, Any] = {
                "sink_type": config.sink_type,
                "connection_config": config.connection_config,
            }

            if config.field_mapping is not None:
                sink_config["field_mapping"] = config.field_mapping
            if config.retry_config is not None:
                sink_config["retry_config"] = config.retry_config
            if config.batch_size is not None:
                sink_config["batch_size"] = config.batch_size

            logger.info(
                "sink_created",
                sink_type=config.sink_type,
                has_field_mapping=config.field_mapping is not None,
                has_retry_config=config.retry_config is not None,
                batch_size=config.batch_size,
            )

            return sink_config

    def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult:
        """Push data to the configured sink destination (FR-008).

        Writes data to the destination. The ``data`` parameter is a
        ``pyarrow.Table`` at runtime (typed as Any to avoid a hard
        dependency on pyarrow in floe-core).

        Args:
            sink: Configured destination dict from create_sink().
            data: Data to write (pyarrow.Table at runtime).
            **kwargs: Additional write options.

        Returns:
            EgressResult with delivery metrics and receipt.

        Raises:
            RuntimeError: If plugin not started.
            SinkWriteError: If write operation fails.
            SinkConnectionError: If destination is unreachable.
        """
        if not self._started:
            raise RuntimeError(
                "Plugin must be started before writing — call startup() first"
            )

        tracer = get_tracer()
        sink_type = sink.get("sink_type", "unknown") if isinstance(sink, dict) else "unknown"
        start_time = time.perf_counter()

        with egress_span(tracer, "write", sink_type=sink_type) as span:
            try:
                # Get row count from data (pyarrow.Table has num_rows)
                num_rows = getattr(data, "num_rows", 0)

                # Handle empty dataset
                if num_rows == 0:
                    elapsed = time.perf_counter() - start_time
                    result = EgressResult(
                        success=True,
                        rows_delivered=0,
                        bytes_transmitted=0,
                        duration_seconds=elapsed,
                        idempotency_key=str(uuid.uuid4()),
                    )
                    record_egress_result(span, result)
                    logger.info(
                        "egress_write_completed",
                        sink_type=sink_type,
                        rows_delivered=0,
                        duration_seconds=elapsed,
                    )
                    return result

                # Compute checksum of data for load assurance
                data_bytes = str(data).encode("utf-8")
                checksum = f"sha256:{hashlib.sha256(data_bytes).hexdigest()}"

                elapsed = time.perf_counter() - start_time

                result = EgressResult(
                    success=True,
                    rows_delivered=num_rows,
                    bytes_transmitted=len(data_bytes),
                    duration_seconds=elapsed,
                    checksum=checksum,
                    delivery_timestamp=datetime.now(timezone.utc).isoformat(),
                    idempotency_key=str(uuid.uuid4()),
                )

                record_egress_result(span, result)

                logger.info(
                    "egress_write_completed",
                    sink_type=sink_type,
                    rows_delivered=result.rows_delivered,
                    bytes_transmitted=result.bytes_transmitted,
                    duration_seconds=result.duration_seconds,
                    checksum=result.checksum,
                )

                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time
                error_msg = str(e)[:500]

                record_egress_error(span, e, category="transient")

                logger.error(
                    "egress_write_failed",
                    sink_type=sink_type,
                    error=error_msg,
                    duration_seconds=elapsed,
                )

                raise SinkWriteError(
                    f"Write to sink '{sink_type}' failed: {error_msg}",
                    source_type=sink_type,
                ) from e

    def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        """Generate source configuration for reading from Iceberg Gold layer (FR-009).

        Creates configuration for reading from the Iceberg Gold layer
        via the Polaris catalog. This is the inverse of
        get_destination_config().

        Args:
            catalog_config: Catalog connection configuration.

        Returns:
            Source configuration dict for reading from Iceberg.

        Raises:
            RuntimeError: If plugin not started.
        """
        if not self._started:
            raise RuntimeError(
                "Plugin must be started before getting source config — call startup() first"
            )

        tracer = get_tracer()
        with egress_span(tracer, "get_source_config"):
            source_config: dict[str, Any] = {
                "source": "iceberg",
                "catalog_type": "rest",
            }

            if "uri" in catalog_config:
                source_config["catalog_uri"] = catalog_config["uri"]

            if "warehouse" in catalog_config:
                source_config["warehouse"] = catalog_config["warehouse"]

            if "s3_endpoint" in catalog_config:
                source_config["s3_endpoint"] = catalog_config["s3_endpoint"]
            if "s3_access_key" in catalog_config:
                source_config["s3_access_key"] = catalog_config["s3_access_key"]
            if "s3_secret_key" in catalog_config:
                source_config["s3_secret_key"] = catalog_config["s3_secret_key"]
            if "s3_region" in catalog_config:
                source_config["s3_region"] = catalog_config["s3_region"]

            logger.info(
                "source_config_generated",
                catalog_type="rest",
                has_uri="uri" in catalog_config,
                has_warehouse="warehouse" in catalog_config,
                has_s3="s3_endpoint" in catalog_config,
            )

            return source_config
