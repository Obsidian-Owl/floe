"""MinIOStoragePlugin implementation for floe.

This module provides the concrete StoragePlugin implementation for
MinIO object storage using S3-compatible protocol settings.

Example:
    >>> from floe_storage_minio.plugin import MinIOStoragePlugin
    >>> from floe_storage_minio.config import MinIOStorageConfig
    >>> config = MinIOStorageConfig(
    ...     endpoint="http://minio:9000",
    ...     bucket="floe-data",
    ... )
    >>> plugin = MinIOStoragePlugin(config=config)
    >>> plugin.name
    'minio'

Requirements Covered:
    - AC-1: MinIOStoragePlugin exists and is discoverable
    - AC-2: MinIOStorageConfig validates manifest config
"""

from __future__ import annotations

import os
import warnings
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

import structlog
from floe_core.plugins.storage import StoragePlugin
from floe_core.schemas.compiled_artifacts import (
    DagsterStorageBinding,
    DbtStorageBinding,
    KubernetesSecretRef,
    StorageBucketRequirement,
    StorageCapabilities,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageProvisioningIntent,
    StorageRuntimeBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)
from floe_core.telemetry.metrics import MetricRecorder
from floe_core.telemetry.tracer_factory import get_tracer

from floe_storage_minio.config import MinIOStorageConfig

if TYPE_CHECKING:
    from floe_core.plugins.storage import FileIO
    from pydantic import BaseModel

TRACER_NAME = "floe.storage.minio"
STORAGE_OPERATIONS_METRIC = "floe.storage.minio.operations"
STORAGE_FAILURES_METRIC = "floe.storage.minio.failures"

logger = structlog.get_logger(__name__)


class MinIOStoragePlugin(StoragePlugin):
    """MinIO storage plugin implementing the StoragePlugin ABC.

    This plugin provides object storage functionality via MinIO, including
    PyIceberg FileIO creation using S3-compatible protocol keys,
    warehouse URI generation, and integration configs for dbt and Dagster.

    Attributes:
        config: The MinIOStorageConfig instance for this plugin, or None if
            not yet configured.

    Example:
        >>> config = MinIOStorageConfig(endpoint="http://minio:9000", bucket="data")
        >>> plugin = MinIOStoragePlugin(config=config)
        >>> plugin.get_warehouse_uri("bronze")
        's3://data/bronze/'
    """

    def __init__(self, config: MinIOStorageConfig | None = None) -> None:
        """Initialize the MinIO storage plugin.

        Args:
            config: Configuration for MinIO storage. When None, the plugin
                is in an unconfigured state (methods will raise RuntimeError).
        """
        super().__init__()
        self._config = config

    def _require_config(self) -> MinIOStorageConfig:
        """Return config or raise if not configured.

        Returns:
            The validated MinIOStorageConfig.

        Raises:
            PluginConfigurationError: If plugin is not configured.
        """
        if self._config is None:
            from floe_core.plugin_errors import PluginConfigurationError

            raise PluginConfigurationError(
                "minio",
                [{"field": "_config", "message": "Plugin 'minio' not configured"}],
            )
        return cast(MinIOStorageConfig, self._config)

    # =========================================================================
    # PluginMetadata abstract properties
    # =========================================================================

    @property
    def name(self) -> str:
        """Return the plugin name.

        Returns:
            The plugin identifier "minio".
        """
        return "minio"

    @property
    def version(self) -> str:
        """Return the plugin version.

        Returns:
            The plugin version in semver format.
        """
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return the required floe API version.

        Returns:
            The minimum floe API version this plugin requires.
        """
        return "1.0"

    @property
    def description(self) -> str:
        """Return the plugin description.

        Returns:
            Human-readable description of the plugin.
        """
        return "MinIO object storage plugin for Iceberg data"

    @property
    def tracer_name(self) -> str:
        """Return the OTel tracer name for this plugin.

        Returns:
            Dot-separated tracer name following project convention.
        """
        return TRACER_NAME

    # =========================================================================
    # Configuration methods
    # =========================================================================

    def get_config_schema(self) -> type[BaseModel]:
        """Return the configuration schema for this plugin.

        Returns:
            The MinIOStorageConfig Pydantic model class.
        """
        return MinIOStorageConfig

    # =========================================================================
    # StoragePlugin abstract methods
    # =========================================================================

    def _get_pyiceberg_s3_properties(self, *, include_credentials: bool = True) -> dict[str, str]:
        """Build PyIceberg S3 properties from validated plugin config."""
        config = self._require_config()

        properties: dict[str, str] = {
            "s3.endpoint": config.endpoint,
            "s3.region": config.region,
            "s3.path-style-access": str(config.path_style_access).lower(),
        }

        if not include_credentials:
            return properties

        # Source service-specific credentials first to avoid accidental AWS
        # credential reuse, while preserving AWS_* compatibility for S3 tooling.
        access_key = (
            config.access_key_id.get_secret_value()
            if config.access_key_id
            else os.environ.get("MINIO_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID", "")
        )
        secret_key = (
            config.secret_access_key.get_secret_value()
            if config.secret_access_key
            else os.environ.get("MINIO_SECRET_ACCESS_KEY")
            or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        )

        if access_key:
            properties["s3.access-key-id"] = access_key
        if secret_key:
            properties["s3.secret-access-key"] = secret_key

        return properties

    def get_pyiceberg_fileio(self) -> FileIO:
        """Create a PyIceberg FileIO instance for S3 storage.

        Returns a FsspecFileIO configured with S3 endpoint, region,
        and credentials. Credentials are sourced from config or
        environment variables (MINIO_ACCESS_KEY_ID/MINIO_SECRET_ACCESS_KEY,
        then AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY).

        Returns:
            A PyIceberg FsspecFileIO instance configured for S3.

        Raises:
            RuntimeError: If plugin is not configured.
        """
        from pyiceberg.io.fsspec import FsspecFileIO

        config = self._require_config()
        with _observe_storage_operation("get_pyiceberg_fileio", config):
            return FsspecFileIO(properties=self._get_pyiceberg_s3_properties())

    def get_pyiceberg_catalog_config(self) -> dict[str, Any]:
        """Return PyIceberg catalog config for S3-backed table loading.

        Uses the same normalized PyIceberg keys as ``get_pyiceberg_fileio()``
        so catalog plugins do not need to know S3 manifest field names.
        """
        config = self._require_config()
        with _observe_storage_operation("get_pyiceberg_catalog_config", config):
            return self._get_pyiceberg_s3_properties()

    def _credential_binding(self) -> StorageCredentialBinding:
        """Return the Kubernetes Secret reference for MinIO credentials."""
        config = self._require_config()
        return StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name=config.credential_secret_name,
                namespace=config.credential_secret_namespace,
                keys={
                    "accessKeyId": config.access_key_secret_key,
                    "secretAccessKey": config.secret_key_secret_key,
                },
            ),
        )

    def get_deployment_binding(self) -> StorageDeploymentBinding:
        """Return secret-free MinIO deployment binding for compiled artifacts."""
        config = self._require_config()
        with _observe_storage_operation(
            "get_deployment_binding",
            config,
            extra={"storage.artifact_bucket": config.artifact_bucket},
        ):
            warehouse_uri = f"s3://{config.bucket}"
            artifact_uri = f"s3://{config.artifact_bucket}"
            allowed_locations = [warehouse_uri]
            bucket_requirements = [
                StorageBucketRequirement(
                    name=config.bucket,
                    uri=warehouse_uri,
                    purpose="warehouse",
                    create_policy="create-if-missing",
                )
            ]
            if config.artifact_bucket != config.bucket:
                allowed_locations.append(artifact_uri)
                bucket_requirements.append(
                    StorageBucketRequirement(
                        name=config.artifact_bucket,
                        uri=artifact_uri,
                        purpose="artifacts",
                        create_policy="create-if-missing",
                    )
                )

            runtime_env_refs = {
                "accessKeyId": "AWS_ACCESS_KEY_ID",
                "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
            }
            s3_runtime_properties = {
                "s3.endpoint": config.endpoint,
                "s3.region": config.region,
                "s3.path-style-access": str(config.path_style_access).lower(),
            }
            dbt_profile_fragment = {
                "s3_endpoint": config.endpoint,
                "s3_region": config.region,
                "s3_path_style_access": config.path_style_access,
            }
            dagster_resources = {
                "bucket": config.bucket,
                "endpoint_url": config.endpoint,
                "region_name": config.region,
                "path_style_access": config.path_style_access,
            }

            return StorageDeploymentBinding(
                provider="minio",
                protocol="s3-compatible",
                endpoint=StorageServiceEndpoint(
                    internal_url=config.endpoint,
                    external_url=config.external_endpoint or config.endpoint,
                    region=config.region,
                    warehouse_path=warehouse_uri,
                    path_style_access=config.path_style_access,
                ),
                warehouse=StorageWarehouse(
                    uri=warehouse_uri,
                    bucket=config.bucket,
                ),
                allowed_locations=allowed_locations,
                buckets=bucket_requirements,
                credentials=self._credential_binding(),
                capabilities=StorageCapabilities(
                    protocols=["s3-compatible"],
                    credential_modes=["kubernetes-secret"],
                    sts_supported=False,
                    path_style_access=config.path_style_access,
                ),
                provisioning=StorageProvisioningIntent(
                    enabled=True,
                    mode="helm-job",
                    default_create_policy="create-if-missing",
                ),
                runtime=StorageRuntimeBinding(
                    pyiceberg_properties=s3_runtime_properties,
                    dbt_profile_fragment=dbt_profile_fragment,
                    dagster_resources=dagster_resources,
                    env_refs=runtime_env_refs,
                ),
                dbt=DbtStorageBinding(
                    profile_name="floe",
                    target_name="dev",
                    schema_name="analytics",
                    profile_fragment=dbt_profile_fragment,
                    env_refs={
                        "s3_access_key_id": "AWS_ACCESS_KEY_ID",
                        "s3_secret_access_key": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
                    },
                ),
                dagster=DagsterStorageBinding(
                    resource_key="minio_storage",
                    asset_io_manager_key="iceberg_io_manager",
                    resources=dagster_resources,
                    env_refs={
                        "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
                        "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret  # noqa: E501
                    },
                ),
                notes=[
                    "MinIO uses S3-compatible protocol settings.",
                    "Credentials are referenced through Kubernetes Secret keys.",
                    f"Artifact bucket: {config.artifact_bucket}",
                ],
            )

    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for a namespace.

        Args:
            namespace: Catalog namespace (e.g., "bronze", "silver").

        Returns:
            S3 URI for the namespace (e.g., "s3://floe-data/bronze/").

        Raises:
            RuntimeError: If plugin is not configured.
        """
        config = self._require_config()
        with _observe_storage_operation(
            "get_warehouse_uri",
            config,
            extra={"storage.namespace": namespace},
        ):
            return f"s3://{config.bucket}/{namespace}/"

    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt profile configuration for S3 storage.

        Returns storage-specific configuration for dbt's profiles.yml,
        using Jinja env_var() for credential sourcing.

        Returns:
            Dictionary with S3-specific config for dbt profiles.

        Raises:
            RuntimeError: If plugin is not configured.
        """
        config = self._require_config()
        with _observe_storage_operation("get_dbt_profile_config", config):
            return {
                "s3_region": config.region,
                "s3_access_key_id": '{{ env_var("AWS_ACCESS_KEY_ID") }}',
                "s3_secret_access_key": '{{ env_var("AWS_SECRET_ACCESS_KEY") }}',  # nosec B105 — Jinja template for dbt, not a hardcoded secret
                "s3_endpoint": config.endpoint,
                "s3_path_style_access": config.path_style_access,
            }

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager configuration for MinIO storage.

        Returns:
            Dictionary with MinIO S3-compatible config for Dagster IOManager.

        Raises:
            RuntimeError: If plugin is not configured.
        """
        config = self._require_config()
        with _observe_storage_operation("get_dagster_io_manager_config", config):
            return {
                "bucket": config.bucket,
                "endpoint_url": config.endpoint,
                "region_name": config.region,
                "path_style_access": config.path_style_access,
            }

    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate deprecated chart values for legacy StoragePlugin callers.

        Returns:
            Helm values using Kubernetes Secret references instead of
            credential values.
        """
        warnings.warn(
            "MinIOStoragePlugin.get_helm_values_override() is deprecated; use "
            "get_deployment_binding() and deployment renderers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        config = self._require_config()
        bucket_names = ",".join([config.bucket, config.artifact_bucket])
        return {
            "minio": {
                "enabled": True,
                "fullnameOverride": "floe-platform-minio",
                "auth": {"existingSecret": config.credential_secret_name},
                "defaultBuckets": bucket_names,
                "provisioning": {"enabled": False, "fallbackJob": True},
            },
            "polaris": {
                "storage": {
                    "s3": {
                        "enabled": True,
                        "endpoint": config.endpoint,
                        "region": config.region,
                        "pathStyleAccess": config.path_style_access,
                        "credentialSecretName": config.credential_secret_name,
                        "accessKeySecretKey": config.access_key_secret_key,
                        "secretKeySecretKey": config.secret_key_secret_key,
                    }
                },
                "bootstrap": {
                    "defaultBaseLocation": f"s3://{config.bucket}",
                    "allowedLocations": [f"s3://{config.bucket}"],
                },
            },
        }


@contextmanager
def _observe_storage_operation(
    operation: str,
    config: MinIOStorageConfig,
    *,
    extra: dict[str, Any] | None = None,
) -> Any:
    """Observe a MinIO storage-owned operation with secret-free attributes."""
    tracer = get_tracer(TRACER_NAME)
    attrs = _storage_attributes(operation, config)
    if extra:
        attrs.update(extra)
    metrics = MetricRecorder(name="floe.storage.minio.runtime", version="0.1.0")
    with tracer.start_as_current_span(
        f"storage.{operation}",
        attributes=attrs,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_attribute("storage.status", "failure")
            span.set_attribute("error.type", type(exc).__name__)
            _record_storage_metric(metrics, operation, "failure")
            logger.info("minio_storage_operation_failed", **attrs, error_type=type(exc).__name__)
            raise
        span.set_attribute("storage.status", "success")
        _record_storage_metric(metrics, operation, "success")
        logger.info("minio_storage_operation_completed", **attrs, storage_status="success")


def _storage_attributes(operation: str, config: MinIOStorageConfig) -> dict[str, str | bool]:
    return {
        "storage.operation": operation,
        "storage.provider": "minio",
        "storage.protocol": "s3-compatible",
        "storage.endpoint": _safe_endpoint_identity(config.endpoint),
        "storage.bucket": config.bucket,
        "storage.region": config.region,
        "storage.path_style_access": config.path_style_access,
    }


def _record_storage_metric(
    metrics: MetricRecorder,
    operation: str,
    status: str,
) -> None:
    labels = {
        "storage.provider": "minio",
        "storage.operation": operation,
        "storage.status": status,
    }
    try:
        metrics.increment(
            STORAGE_OPERATIONS_METRIC,
            labels=labels,
            description="MinIO storage plugin operations",
            unit="1",
        )
        if status != "success":
            metrics.increment(
                STORAGE_FAILURES_METRIC,
                labels=labels,
                description="MinIO storage plugin operation failures",
                unit="1",
            )
    except Exception as exc:  # pragma: no cover - defensive telemetry isolation
        logger.debug("minio_storage_metric_failed", error_type=type(exc).__name__)


def _safe_endpoint_identity(uri: str) -> str:
    parsed = urlsplit(uri)
    if not (parsed.scheme and parsed.hostname):
        return "[REDACTED]"
    hostname = parsed.hostname
    host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    try:
        netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
    except ValueError:
        return "[REDACTED]"
    return urlunsplit(
        SplitResult(
            scheme=parsed.scheme,
            netloc=netloc,
            path="",
            query="",
            fragment="",
        )
    )
