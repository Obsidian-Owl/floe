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
import os
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import fsspec
import httpx
import structlog
from floe_core.composition.models import PluginRequirements, RequirementSet
from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.ingestion import (
    IngestionConfig,
    IngestionPlugin,
    IngestionResult,
)
from floe_core.plugins.sink import EgressResult, SinkConfig, SinkConnector
from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    DltIngestionBinding,
    IngestionDeploymentBinding,
    StorageDeploymentBinding,
)
from floe_core.telemetry.sanitization import sanitize_error_message

from floe_ingestion_dlt.config import (
    VALID_SCHEMA_CONTRACTS,
    VALID_SOURCE_TYPES,
    VALID_WRITE_MODES,
)
from floe_ingestion_dlt.errors import (
    PipelineConfigurationError,
    SchemaContractViolation,
    SinkConfigurationError,
    SinkWriteError,
)
from floe_ingestion_dlt.retry import categorize_error
from floe_ingestion_dlt.tracing import (
    TRACER_NAME,
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

    _iceberg_env_lock = threading.RLock()
    _health_slots_lock = threading.Lock()
    _health_check_slots: dict[str, threading.Lock] = {}

    def __init__(self) -> None:
        """Initialize plugin state."""
        super().__init__()
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
    def tracer_name(self) -> str:
        """Return the OpenTelemetry tracer name.

        Returns:
            The tracer name for this plugin's operations.
        """
        return TRACER_NAME

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

    def get_composition_requirements(self) -> PluginRequirements:
        """Return storage and catalog requirements for dlt Iceberg ingestion."""
        return PluginRequirements(
            plugin_type="ingestion",
            plugin_name=self.name,
            requirements=RequirementSet(
                protocols=["s3-compatible", "s3"],
                credential_modes=["kubernetes-secret", "environment", "workload-identity"],
                catalog_providers=["iceberg-rest"],
                table_formats=["iceberg"],
            ),
        )

    def build_deployment_binding(
        self,
        *,
        storage: StorageDeploymentBinding,
        catalog: CatalogDeploymentBinding,
    ) -> IngestionDeploymentBinding:
        """Translate composed storage/catalog bindings into dlt runtime config."""
        if storage.warehouse is None:
            raise PipelineConfigurationError("dlt ingestion requires storage warehouse binding")
        if catalog.provider != "polaris":
            raise PipelineConfigurationError(
                "dlt ingestion currently supports polaris catalog bindings, "
                f"got {catalog.provider!r}"
            )

        source_filesystem = {
            "endpoint_url": storage.endpoint.internal_url,
            "region_name": storage.endpoint.region,
            "s3_url_style": "path" if storage.endpoint.path_style_access else "virtual",
        }
        destination_filesystem = {
            "bucket_url": storage.warehouse.uri,
            "credentials": {
                "endpoint_url": storage.endpoint.internal_url,
                "region_name": storage.endpoint.region,
            },
        }
        if storage.endpoint.path_style_access:
            destination_filesystem["credentials"]["s3_url_style"] = "path"

        iceberg_catalog_env = self._compile_safe_iceberg_environment(
            catalog_name="polaris",
            uri=catalog.polaris.endpoint_internal,
            warehouse=catalog.polaris.warehouse,
            s3_endpoint=storage.endpoint.internal_url,
            s3_region=storage.endpoint.region,
            s3_path_style_access=storage.endpoint.path_style_access,
        )

        return IngestionDeploymentBinding(
            provider="dlt",
            dlt=DltIngestionBinding(
                plugin_name=self.name,
                destination="filesystem",
                table_format="iceberg",
                source_filesystem=source_filesystem,
                destination_filesystem=destination_filesystem,
                iceberg_catalog_env=iceberg_catalog_env,
                env_refs=dict(storage.runtime.env_refs),
            ),
        )

    @staticmethod
    def _compile_safe_iceberg_environment(
        *,
        catalog_name: str,
        uri: str,
        warehouse: str | None,
        s3_endpoint: str,
        s3_region: str,
        s3_path_style_access: bool,
    ) -> dict[str, str]:
        """Build secret-free PyIceberg env from explicit deployment bindings only."""
        env_catalog = catalog_name.upper().replace("-", "_")
        prefix = f"PYICEBERG_CATALOG__{env_catalog}__"
        env = {
            "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": catalog_name,
            "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
            f"{prefix}TYPE": "rest",
            f"{prefix}URI": uri,
            f"{prefix}S3__ENDPOINT": s3_endpoint,
            f"{prefix}S3__REGION": s3_region,
        }
        if warehouse is not None:
            env[f"{prefix}WAREHOUSE"] = warehouse
        if s3_path_style_access:
            env[f"{prefix}S3__PATH_STYLE_ACCESS"] = "true"
        return env

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

            try:
                import dlt as _dlt  # noqa: F401
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

            catalog_config = self._configured_catalog_config()
            deadline = start + effective_timeout
            bucket_url = self._bucket_url(catalog_config) if catalog_config else None
            object_storage_check = self._object_storage_check_state(bucket_url)
            if catalog_config:
                catalog_error = self._call_health_probe_with_deadline(
                    self._check_catalog_reachable,
                    catalog_config,
                    deadline,
                    check_name="catalog",
                )
                if catalog_error is not None:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    return HealthStatus(
                        state=HealthState.UNHEALTHY,
                        message="Iceberg catalog is unreachable",
                        details={
                            "reason": "catalog_unreachable",
                            "catalog_error": catalog_error,
                            "response_time_ms": elapsed_ms,
                            "checked_at": checked_at,
                            "timeout": effective_timeout,
                        },
                    )

                if object_storage_check == "configured":
                    object_storage_error = self._call_health_probe_with_deadline(
                        self._check_object_storage_reachable,
                        catalog_config,
                        deadline,
                        check_name="object_storage",
                    )
                    if object_storage_error is not None:
                        elapsed_ms = (time.perf_counter() - start) * 1000
                        return HealthStatus(
                            state=HealthState.UNHEALTHY,
                            message="Object storage is unreachable",
                            details={
                                "reason": "object_storage_unreachable",
                                "object_storage_error": object_storage_error,
                                "response_time_ms": elapsed_ms,
                                "checked_at": checked_at,
                                "timeout": effective_timeout,
                            },
                        )
                    object_storage_check = "reachable"

            elapsed_ms = (time.perf_counter() - start) * 1000
            status = HealthStatus(
                state=HealthState.HEALTHY,
                message="dlt ingestion plugin is healthy",
                details={
                    "dlt_version": self._dlt_version,
                    "started": self._started,
                    "catalog_check": "reachable" if catalog_config else "not_configured",
                    "object_storage_check": object_storage_check,
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

            pipeline_kwargs: dict[str, Any] = {
                "pipeline_name": pipeline_name,
                "dataset_name": dataset_name,
            }
            catalog_config = self._pipeline_catalog_config(config)
            if self.is_configured and not catalog_config:
                raise PipelineConfigurationError(
                    "catalog_config is required for configured dlt ingestion pipelines",
                    source_type=config.source_type,
                    destination_table=config.destination_table,
                )
            if catalog_config:
                from dlt.destinations import filesystem

                pipeline_kwargs["destination"] = filesystem(
                    **self.get_destination_config(catalog_config)
                )

            pipeline = dlt.pipeline(**pipeline_kwargs)
            if catalog_config:
                pipeline._floe_iceberg_catalog_config = catalog_config

            logger.info(
                "pipeline_created",
                pipeline_name=pipeline_name,
                dataset_name=dataset_name,
                source_type=config.source_type,
                destination_table=config.destination_table,
                write_mode=config.write_mode,
                has_destination=bool(catalog_config),
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
        source_name = kwargs.get("source_name")
        source_path = kwargs.get("source_path")

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
                    "table_format": kwargs.get("table_format", "iceberg"),
                }

                # Add primary_key if provided with merge disposition
                if primary_key is not None and write_disposition == "merge":
                    run_kwargs["primary_key"] = primary_key

                # Execute the pipeline
                catalog_config = getattr(pipeline, "_floe_iceberg_catalog_config", None)
                if not isinstance(catalog_config, dict):
                    catalog_config = None
                with self._temporary_iceberg_environment(catalog_config):
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
                error_msg = self._with_source_error_context(
                    str(e),
                    source_name=source_name,
                    source_path=source_path,
                )

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

    @staticmethod
    def _with_source_error_context(
        error_msg: str,
        *,
        source_name: Any,
        source_path: Any,
        max_length: int = 500,
    ) -> str:
        """Prefix an ingestion error with source identity when provided."""
        context: list[str] = []
        if source_name not in (None, ""):
            context.append(f"source={source_name}")
        if source_path not in (None, ""):
            context.append(f"path={source_path}")
        if not context:
            return sanitize_error_message(error_msg, max_length=max_length)
        return sanitize_error_message(f"{', '.join(context)}: {error_msg}", max_length=max_length)

    def get_destination_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        """Generate Iceberg destination configuration for dlt.

        Maps platform catalog/storage settings to dlt filesystem destination
        kwargs. dlt's Iceberg support is the filesystem destination plus
        PyIceberg catalog configuration, not a standalone ``iceberg`` destination.

        Args:
            catalog_config: Catalog connection configuration with keys:
                - uri: Polaris catalog URI (e.g., "http://polaris:8181/api/catalog")
                - warehouse: Warehouse name (e.g., "floe_warehouse")
                - s3_endpoint: Optional S3/MinIO endpoint
                - s3_access_key: Optional S3 access key
                - s3_secret_key: Optional S3 secret key
                - s3_region: Optional S3 region

        Returns:
            dlt filesystem destination kwargs for Iceberg writes.
        """
        tracer = get_tracer()
        with ingestion_span(tracer, "get_destination_config"):
            dest_config: dict[str, Any] = {}

            bucket_url = self._bucket_url(catalog_config)
            if bucket_url is not None:
                dest_config["bucket_url"] = bucket_url

            credentials: dict[str, Any] = {}
            s3_endpoint = self._first_config_value(
                catalog_config,
                "s3_endpoint",
                "endpoint",
                "minio_endpoint",
            )
            if s3_endpoint is not None:
                credentials["endpoint_url"] = str(s3_endpoint)
            s3_region = self._first_config_value(catalog_config, "s3_region", "region")
            if s3_region is not None:
                credentials["region_name"] = str(s3_region)
            path_style = catalog_config.get(
                "s3_path_style_access",
                catalog_config.get("path_style_access", s3_endpoint is not None),
            )
            if path_style:
                credentials["s3_url_style"] = "path"
            if credentials:
                dest_config["credentials"] = credentials

            if "s3_access_key" in catalog_config or "s3_secret_key" in catalog_config:
                logger.warning(
                    "s3_credentials_in_config",
                    message="S3 credentials should use environment variables "
                    "(AWS_ACCESS_KEY_ID), not config passthrough. See FR-018.",
                )

            logger.info(
                "destination_config_generated",
                destination="filesystem",
                has_bucket_url="bucket_url" in dest_config,
                has_s3_endpoint=bool(credentials.get("endpoint_url")),
            )

            return dest_config

    def _configured_catalog_config(self) -> dict[str, Any]:
        catalog_config = getattr(self._config, "catalog_config", None)
        return dict(catalog_config) if isinstance(catalog_config, dict) else {}

    def _pipeline_catalog_config(self, config: IngestionConfig) -> dict[str, Any]:
        source_catalog_config = config.source_config.get("catalog_config")
        if isinstance(source_catalog_config, dict) and source_catalog_config:
            return dict(source_catalog_config)
        return self._configured_catalog_config()

    @staticmethod
    def _first_config_value(catalog_config: dict[str, Any], *keys: str) -> Any | None:
        for key in keys:
            value = catalog_config.get(key)
            if value not in (None, ""):
                return value
        return None

    def _bucket_url(self, catalog_config: dict[str, Any]) -> str | None:
        bucket_url = self._first_config_value(
            catalog_config,
            "bucket_url",
            "storage_url",
            "base_location",
            "default_base_location",
        )
        if bucket_url is not None:
            return str(bucket_url)
        bucket = self._first_config_value(catalog_config, "bucket", "s3_bucket")
        if bucket is None:
            return None
        bucket_str = str(bucket)
        return bucket_str if "://" in bucket_str else f"s3://{bucket_str}"

    def _pyiceberg_catalog_properties(self, catalog_config: dict[str, Any]) -> dict[str, str]:
        properties: dict[str, str] = {}
        uri = self._first_config_value(catalog_config, "uri", "catalog_uri")
        if uri is not None:
            properties["uri"] = str(uri)
        warehouse = self._first_config_value(catalog_config, "warehouse")
        if warehouse is not None:
            properties["warehouse"] = str(warehouse)

        oauth2 = catalog_config.get("oauth2")
        credential = os.environ.get("POLARIS_CREDENTIAL") or self._first_config_value(
            catalog_config,
            "credential",
        )
        if credential is None and isinstance(oauth2, dict):
            client_id = oauth2.get("client_id")
            client_secret = oauth2.get("client_secret")
            if client_id and client_secret:
                credential = f"{client_id}:{client_secret}"
        if credential is not None:
            properties["credential"] = str(credential)

        scope = os.environ.get("POLARIS_SCOPE") or self._first_config_value(catalog_config, "scope")
        if scope is None and isinstance(oauth2, dict):
            scope = oauth2.get("scope")
        if scope is not None:
            properties["scope"] = str(scope)

        oauth2_server_uri = self._first_config_value(
            catalog_config,
            "oauth2_server_uri",
            "oauth2-server-uri",
            "token_url",
        )
        if oauth2_server_uri is None and isinstance(oauth2, dict):
            oauth2_server_uri = oauth2.get("token_url") or oauth2.get("oauth2_server_uri")
        if oauth2_server_uri is not None:
            properties["oauth2-server-uri"] = str(oauth2_server_uri)

        s3_endpoint = self._first_config_value(catalog_config, "s3_endpoint", "endpoint")
        if s3_endpoint is not None:
            properties["s3.endpoint"] = str(s3_endpoint)
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        if aws_access_key:
            properties["s3.access-key-id"] = aws_access_key
        aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if aws_secret_key:
            properties["s3.secret-access-key"] = aws_secret_key
        region = os.environ.get("AWS_REGION") or self._first_config_value(
            catalog_config,
            "s3_region",
            "region",
        )
        if region is not None:
            properties["s3.region"] = str(region)
        path_style = catalog_config.get(
            "s3_path_style_access",
            catalog_config.get("path_style_access", s3_endpoint is not None),
        )
        if path_style:
            properties["s3.path-style-access"] = "true"
        return properties

    def _iceberg_environment(self, catalog_config: dict[str, Any]) -> dict[str, str]:
        catalog_name = str(catalog_config.get("catalog_name", "polaris"))
        env_catalog = catalog_name.upper().replace("-", "_")
        prefix = f"PYICEBERG_CATALOG__{env_catalog}__"

        env = {
            "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": catalog_name,
            "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
            f"{prefix}TYPE": "rest",
        }
        for key, value in self._pyiceberg_catalog_properties(catalog_config).items():
            env_key = key.upper().replace(".", "__").replace("-", "_")
            env[f"{prefix}{env_key}"] = value
        return env

    @contextmanager
    def _temporary_iceberg_environment(self, catalog_config: dict[str, Any] | None) -> Any:
        if not catalog_config:
            yield
            return

        with self._iceberg_env_lock:
            plugin_env = self._iceberg_environment(catalog_config)
            previous = {key: os.environ.get(key) for key in plugin_env}
            try:
                os.environ.update(plugin_env)
                yield
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def _catalog_health_url(self, catalog_config: dict[str, Any]) -> str:
        uri = str(self._first_config_value(catalog_config, "uri", "catalog_uri") or "").rstrip("/")
        warehouse = self._first_config_value(catalog_config, "warehouse")
        if not uri:
            raise ValueError("catalog uri is required for catalog health check")
        health_url = f"{uri}/v1/config"
        if warehouse is not None:
            health_url = f"{health_url}?warehouse={warehouse}"
        return health_url

    def _check_catalog_reachable(
        self,
        catalog_config: dict[str, Any],
        timeout: float,
    ) -> str | None:
        def _catalog_check() -> None:
            with httpx.Client(timeout=timeout) as client:
                client.get(self._catalog_health_url(catalog_config))

        try:
            self._run_health_check_with_timeout(
                _catalog_check,
                timeout,
                check_name="catalog",
            )
            return None
        except Exception as exc:
            return f"{type(exc).__name__}: {sanitize_error_message(str(exc))}"

    def _check_object_storage_reachable(
        self,
        catalog_config: dict[str, Any],
        timeout: float,
    ) -> str | None:
        bucket_url = self._bucket_url(catalog_config)
        if bucket_url is None or not bucket_url.startswith("s3://"):
            return None

        def _object_storage_check() -> None:
            fs, _, paths = fsspec.get_fs_token_paths(
                bucket_url,
                key=os.environ.get("AWS_ACCESS_KEY_ID"),
                secret=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                client_kwargs={
                    "endpoint_url": self._first_config_value(
                        catalog_config,
                        "s3_endpoint",
                        "endpoint",
                    ),
                    "region_name": os.environ.get("AWS_REGION")
                    or self._first_config_value(catalog_config, "s3_region", "region"),
                },
                config_kwargs={
                    "connect_timeout": timeout,
                    "read_timeout": timeout,
                    "s3": {"addressing_style": "path"},
                },
            )
            fs.ls(paths[0], detail=False, max_items=1)

        try:
            self._run_health_check_with_timeout(
                _object_storage_check,
                timeout,
                check_name="object_storage",
            )
            return None
        except Exception as exc:
            return f"{type(exc).__name__}: {sanitize_error_message(str(exc))}"

    @staticmethod
    def _object_storage_check_state(bucket_url: str | None) -> str:
        if bucket_url is None:
            return "not_configured"
        if not bucket_url.startswith("s3://"):
            return "skipped_non_s3"
        return "configured"

    def _call_health_probe_with_deadline(
        self,
        probe: Callable[[dict[str, Any], float], str | None],
        catalog_config: dict[str, Any],
        deadline: float,
        *,
        check_name: str,
    ) -> str | None:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return f"TimeoutError: {check_name} health check exceeded 0s"

        result: list[str | None] = []

        def _probe() -> None:
            result.append(probe(catalog_config, remaining))

        try:
            self._run_health_check_with_timeout(
                _probe,
                remaining,
                check_name=f"{check_name}_budget",
            )
        except TimeoutError:
            return f"TimeoutError: {check_name} health check exceeded {remaining}s"
        except Exception as exc:
            return f"{type(exc).__name__}: {sanitize_error_message(str(exc))}"

        return result[0] if result else None

    @classmethod
    def _run_health_check_with_timeout(
        cls,
        check: Callable[[], None],
        timeout: float,
        *,
        check_name: str,
    ) -> None:
        slot = cls._health_check_slot(check_name)
        if not slot.acquire(blocking=False):
            raise TimeoutError(f"{check_name} health check already running")

        done = threading.Event()
        errors: list[BaseException] = []

        def _worker() -> None:
            try:
                check()
            except BaseException as exc:  # noqa: BLE001 - propagated to caller
                errors.append(exc)
            finally:
                done.set()
                slot.release()

        thread = threading.Thread(
            target=_worker,
            name=f"dlt-health-{check_name}",
            daemon=True,
        )
        try:
            thread.start()
        except BaseException:
            slot.release()
            raise

        if not done.wait(timeout):
            raise TimeoutError(f"{check_name} health check exceeded {timeout}s")
        if errors:
            raise errors[0]

    @classmethod
    def _health_check_slot(cls, check_name: str) -> threading.Lock:
        with cls._health_slots_lock:
            return cls._health_check_slots.setdefault(check_name, threading.Lock())

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
            raise RuntimeError("Plugin must be started before listing sinks — call startup() first")

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

        Writes data to the destination via a dlt egress pipeline.
        The ``data`` parameter is a ``pyarrow.Table`` at runtime
        (typed as Any to avoid a hard dependency on pyarrow in floe-core).

        Args:
            sink: Configured destination dict from create_sink().
            data: Data to write (pyarrow.Table at runtime).
            **kwargs: Additional write options (table_name, write_disposition).

        Returns:
            EgressResult with delivery metrics and receipt.

        Raises:
            RuntimeError: If plugin not started.
            SinkWriteError: If write operation fails or dlt reports failed jobs.
            SinkConnectionError: If destination is unreachable.
        """
        if not self._started:
            raise RuntimeError("Plugin must be started before writing — call startup() first")

        tracer = get_tracer()
        sink_type = sink.get("sink_type", "unknown") if isinstance(sink, dict) else "unknown"
        connection_config = sink.get("connection_config", {}) if isinstance(sink, dict) else {}
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

                # Compute checksum via Arrow IPC wire format (safe, reproducible)
                import pyarrow as pa

                if isinstance(data, pa.Table):
                    hasher = hashlib.sha256()
                    sink_buf = pa.BufferOutputStream()
                    writer = pa.ipc.new_stream(sink_buf, data.schema)
                    for batch in data.to_batches():
                        writer.write_batch(batch)
                    writer.close()
                    ipc_bytes = sink_buf.getvalue()
                    hasher.update(ipc_bytes)
                    checksum = f"sha256:{hasher.hexdigest()}"
                    data_bytes_len = len(ipc_bytes)
                else:
                    # Fallback for non-Arrow data
                    data_bytes = str(data).encode("utf-8")
                    checksum = f"sha256:{hashlib.sha256(data_bytes).hexdigest()}"
                    data_bytes_len = len(data_bytes)

                # Execute dlt egress pipeline to deliver data to destination
                import dlt

                table_name = kwargs.get("table_name", "egress_output")
                write_disposition = kwargs.get("write_disposition", "append")

                pipeline_kwargs: dict[str, Any] = {
                    "pipeline_name": f"floe_egress_{sink_type}",
                    "destination": sink_type,
                }
                if connection_config:
                    pipeline_kwargs["credentials"] = connection_config
                pipeline = dlt.pipeline(**pipeline_kwargs)

                load_info = pipeline.run(
                    data,
                    table_name=table_name,
                    write_disposition=write_disposition,
                )

                # Verify delivery — dlt marks failed jobs on load_info
                if getattr(load_info, "has_failed_jobs", False):
                    raise SinkWriteError(
                        f"dlt egress pipeline reported failed jobs for sink '{sink_type}'",
                        source_type=sink_type,
                    )

                elapsed = time.perf_counter() - start_time

                result = EgressResult(
                    success=True,
                    rows_delivered=num_rows,
                    bytes_transmitted=data_bytes_len,
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
                error_msg = sanitize_error_message(str(e))

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
                logger.warning(
                    "s3_credentials_in_config",
                    message="S3 credentials should use environment variables "
                    "(AWS_ACCESS_KEY_ID), not config passthrough. See FR-018.",
                )
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
