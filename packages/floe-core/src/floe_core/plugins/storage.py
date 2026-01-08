"""StoragePlugin ABC for object storage plugins.

This module defines the abstract base class for storage plugins that
provide object storage functionality for Iceberg data. Storage plugins
are responsible for:
- Providing PyIceberg-compatible FileIO instances
- Generating warehouse URIs for catalog configuration
- Providing dbt and Dagster configuration for storage access
- Providing Helm values for deploying self-hosted storage (MinIO, etc.)

Example:
    >>> from floe_core.plugins.storage import StoragePlugin
    >>> class S3Plugin(StoragePlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "s3"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    pass


@runtime_checkable
class FileIO(Protocol):
    """Protocol for PyIceberg-compatible FileIO interface.

    This protocol defines the minimal interface expected from a PyIceberg
    FileIO object. It allows type checking without requiring pyiceberg
    as a runtime dependency of floe-core.

    See Also:
        - pyiceberg.io.FileIO: Full PyIceberg FileIO interface
    """

    def new_input(self, location: str) -> Any:
        """Create a new input file for reading."""
        ...

    def new_output(self, location: str) -> Any:
        """Create a new output file for writing."""
        ...

    def delete(self, location: str) -> None:
        """Delete a file at the specified location."""
        ...


class StoragePlugin(PluginMetadata):
    """Abstract base class for object storage plugins.

    StoragePlugin extends PluginMetadata with storage-specific methods
    for managing object storage backends. Implementations include S3,
    GCS, Azure Blob Storage, and MinIO.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - get_pyiceberg_fileio() method
        - get_warehouse_uri() method
        - get_dbt_profile_config() method
        - get_dagster_io_manager_config() method
        - get_helm_values_override() method

    Example:
        >>> class S3Plugin(StoragePlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "s3"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def get_pyiceberg_fileio(self) -> FileIO:
        ...         from pyiceberg.io.fsspec import FsspecFileIO
        ...         return FsspecFileIO({"s3.region": "us-east-1"})
        ...
        ...     def get_warehouse_uri(self, namespace: str) -> str:
        ...         return f"s3://my-bucket/warehouse/{namespace}"

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @abstractmethod
    def get_pyiceberg_fileio(self) -> FileIO:
        """Create a PyIceberg FileIO instance for this storage backend.

        Returns a FileIO implementation configured for this storage backend.
        The FileIO is used by PyIceberg for reading and writing Iceberg
        table data and metadata files.

        Returns:
            A PyIceberg-compatible FileIO instance (S3FileIO, GCSFileIO, etc.).

        Example:
            >>> fileio = plugin.get_pyiceberg_fileio()
            >>> input_file = fileio.new_input("s3://bucket/table/data.parquet")
        """
        ...

    @abstractmethod
    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for Iceberg catalog configuration.

        Creates a storage URI for a specific namespace, used when registering
        namespaces with the Iceberg catalog.

        Args:
            namespace: Catalog namespace (e.g., "bronze", "silver", "gold").

        Returns:
            Storage URI for the namespace (e.g., "s3://bucket/warehouse/bronze").

        Example:
            >>> plugin.get_warehouse_uri("bronze")
            's3://my-bucket/warehouse/bronze'
            >>> plugin.get_warehouse_uri("silver")
            's3://my-bucket/warehouse/silver'
        """
        ...

    @abstractmethod
    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt profile configuration for this storage backend.

        Returns storage-specific configuration for dbt's profiles.yml.
        This is merged with compute plugin configuration to create
        the complete dbt profile.

        Returns:
            Dictionary with storage-specific config for dbt profiles.yml.

        Example:
            >>> config = plugin.get_dbt_profile_config()
            >>> config
            {
                's3_region': 'us-east-1',
                's3_access_key_id': '{{ env_var("AWS_ACCESS_KEY_ID") }}',
                's3_secret_access_key': '{{ env_var("AWS_SECRET_ACCESS_KEY") }}'
            }
        """
        ...

    @abstractmethod
    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager configuration for this storage backend.

        Returns configuration for Dagster's IOManager to read/write
        assets to this storage backend.

        Returns:
            Dictionary with storage config for Dagster IOManager.

        Example:
            >>> config = plugin.get_dagster_io_manager_config()
            >>> config
            {
                'bucket': 'my-bucket',
                'prefix': 'dagster-assets',
                'region_name': 'us-east-1'
            }
        """
        ...

    @abstractmethod
    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values for deploying storage services.

        Returns Helm chart values for self-hosted storage services
        (e.g., MinIO). Returns an empty dict for cloud storage (S3, GCS)
        that doesn't require deployment.

        Returns:
            Helm values dictionary for storage chart, or empty dict
            if storage is external (cloud).

        Example:
            >>> # MinIO (self-hosted) returns deployment config
            >>> minio_plugin.get_helm_values_override()
            {
                'mode': 'standalone',
                'replicas': 1,
                'persistence': {'size': '10Gi'}
            }

            >>> # S3 (cloud) returns empty dict
            >>> s3_plugin.get_helm_values_override()
            {}
        """
        ...
