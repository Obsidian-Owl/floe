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
from typing import TYPE_CHECKING, Any, cast

from floe_core.plugins.storage import StoragePlugin
from floe_core.schemas.compiled_artifacts import (
    DagsterStorageBinding,
    DbtStorageBinding,
    KubernetesSecretRef,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageServiceEndpoint,
)

from floe_storage_minio.config import MinIOStorageConfig

if TYPE_CHECKING:
    from floe_core.plugins.storage import FileIO
    from pydantic import BaseModel

NOT_CONFIGURED_MSG = "MinIOStoragePlugin not configured - instantiate with config parameter"
TRACER_NAME = "floe.storage.minio"


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

        # Source credentials from config or environment
        access_key = (
            config.access_key_id.get_secret_value()
            if config.access_key_id
            else os.environ.get("AWS_ACCESS_KEY_ID", "")
        )
        secret_key = (
            config.secret_access_key.get_secret_value()
            if config.secret_access_key
            else os.environ.get("AWS_SECRET_ACCESS_KEY", "")
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
        environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).

        Returns:
            A PyIceberg FsspecFileIO instance configured for S3.

        Raises:
            RuntimeError: If plugin is not configured.
        """
        from pyiceberg.io.fsspec import FsspecFileIO

        return FsspecFileIO(properties=self._get_pyiceberg_s3_properties())

    def get_pyiceberg_catalog_config(self) -> dict[str, Any]:
        """Return PyIceberg catalog config for S3-backed table loading.

        Uses the same normalized PyIceberg keys as ``get_pyiceberg_fileio()``
        so catalog plugins do not need to know S3 manifest field names.
        """
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
        return StorageDeploymentBinding(
            provider="minio",
            endpoint=StorageServiceEndpoint(
                internal_url=config.endpoint,
                external_url=config.external_endpoint or config.endpoint,
                region=config.region,
                warehouse_path=f"s3://{config.bucket}",
            ),
            credentials=self._credential_binding(),
            dbt=DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
                profile_fragment={
                    "s3_endpoint": config.endpoint,
                    "s3_region": config.region,
                    "s3_path_style_access": config.path_style_access,
                },
                env_refs={
                    "s3_access_key_id": "AWS_ACCESS_KEY_ID",
                    "s3_secret_access_key": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
                },
            ),
            dagster=DagsterStorageBinding(
                resource_key="minio_storage",
                asset_io_manager_key="iceberg_io_manager",
                resources={
                    "namespace": "default",
                    "bucket": config.bucket,
                    "endpoint_url": config.endpoint,
                    "region_name": config.region,
                    "path_style_access": config.path_style_access,
                },
                env_refs={
                    "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
                    "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
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
        return {
            "bucket": config.bucket,
            "endpoint_url": config.endpoint,
            "region_name": config.region,
            "path_style_access": config.path_style_access,
        }

    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate chart values for MinIO and Polaris from MinIO config.

        Returns:
            Helm values using Kubernetes Secret references instead of
            credential values.
        """
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
