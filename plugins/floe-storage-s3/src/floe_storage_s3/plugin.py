"""S3StoragePlugin implementation for floe.

This module provides the concrete StoragePlugin implementation for
S3-compatible object storage (AWS S3, MinIO, etc.).

Example:
    >>> from floe_storage_s3.plugin import S3StoragePlugin
    >>> from floe_storage_s3.config import S3StorageConfig
    >>> config = S3StorageConfig(
    ...     endpoint="http://minio:9000",
    ...     bucket="floe-data",
    ... )
    >>> plugin = S3StoragePlugin(config=config)
    >>> plugin.name
    's3'

Requirements Covered:
    - AC-1: S3StoragePlugin exists and is discoverable
    - AC-2: S3StorageConfig validates manifest config
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from floe_core.plugins.storage import StoragePlugin

from floe_storage_s3.config import S3StorageConfig

if TYPE_CHECKING:
    from floe_core.plugins.storage import FileIO
    from pydantic import BaseModel

NOT_CONFIGURED_MSG = "S3StoragePlugin not configured — instantiate with config parameter"


class S3StoragePlugin(StoragePlugin):
    """S3-compatible storage plugin implementing the StoragePlugin ABC.

    This plugin provides object storage functionality via S3-compatible
    backends (AWS S3, MinIO, etc.), including PyIceberg FileIO creation,
    warehouse URI generation, and integration configs for dbt and Dagster.

    Attributes:
        config: The S3StorageConfig instance for this plugin, or None if
            not yet configured.

    Example:
        >>> config = S3StorageConfig(endpoint="http://minio:9000", bucket="data")
        >>> plugin = S3StoragePlugin(config=config)
        >>> plugin.get_warehouse_uri("bronze")
        's3://data/bronze/'
    """

    def __init__(self, config: S3StorageConfig | None = None) -> None:
        """Initialize the S3 storage plugin.

        Args:
            config: Configuration for S3 storage. When None, the plugin
                is in an unconfigured state (methods will raise RuntimeError).
        """
        self._config = config

    def _require_config(self) -> S3StorageConfig:
        """Return config or raise if not configured.

        Returns:
            The validated S3StorageConfig.

        Raises:
            RuntimeError: If plugin was instantiated without config.
        """
        if self._config is None:
            raise RuntimeError(NOT_CONFIGURED_MSG)
        return self._config

    # =========================================================================
    # PluginMetadata abstract properties
    # =========================================================================

    @property
    def name(self) -> str:
        """Return the plugin name.

        Returns:
            The plugin identifier "s3".
        """
        return "s3"

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
        return "S3-compatible object storage plugin for Iceberg data"

    # =========================================================================
    # Configuration methods
    # =========================================================================

    def get_config_schema(self) -> type[BaseModel]:
        """Return the configuration schema for this plugin.

        Returns:
            The S3StorageConfig Pydantic model class.
        """
        return S3StorageConfig

    # =========================================================================
    # StoragePlugin abstract methods
    # =========================================================================

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

        config = self._require_config()

        properties: dict[str, str] = {
            "s3.endpoint": config.endpoint,
            "s3.region": config.region,
            "s3.path-style-access": str(config.path_style_access).lower(),
        }

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

        return FsspecFileIO(properties=properties)

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
            "s3_secret_access_key": '{{ env_var("AWS_SECRET_ACCESS_KEY") }}',
            "s3_endpoint": config.endpoint,
            "s3_path_style_access": config.path_style_access,
        }

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager configuration for S3 storage.

        Returns:
            Dictionary with S3 config for Dagster IOManager.

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
        """Generate Helm values for S3 storage.

        S3 is an external service — no Helm deployment is needed.
        Returns an empty dict.

        Returns:
            Empty dictionary (S3 is external, not self-hosted).
        """
        return {}
