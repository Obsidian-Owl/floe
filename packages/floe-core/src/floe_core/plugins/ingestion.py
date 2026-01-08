"""IngestionPlugin ABC for data ingestion plugins.

This module defines the abstract base class for ingestion plugins that
provide data loading from external sources. Ingestion plugins are
responsible for:
- Creating ingestion pipelines from configuration
- Executing pipelines to load data
- Providing destination configuration for Iceberg tables

Example:
    >>> from floe_core.plugins.ingestion import IngestionPlugin
    >>> class DLTPlugin(IngestionPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "dlt"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


@dataclass
class IngestionConfig:
    """Configuration for an ingestion pipeline.

    Attributes:
        source_type: Type of data source (e.g., "postgres", "salesforce", "api").
        source_config: Source-specific configuration.
        destination_table: Target Iceberg table path.
        write_mode: Write mode ("append", "replace", "merge").
        schema_contract: Schema contract mode ("evolve", "freeze", "discard_value").

    Example:
        >>> config = IngestionConfig(
        ...     source_type="postgres",
        ...     source_config={"connection_string": "postgresql://..."},
        ...     destination_table="bronze.raw_customers",
        ...     write_mode="append"
        ... )
    """

    source_type: str
    source_config: dict[str, Any] = field(default_factory=lambda: {})
    destination_table: str = ""
    write_mode: str = "append"
    schema_contract: str = "evolve"


@dataclass
class IngestionResult:
    """Result of an ingestion pipeline execution.

    Attributes:
        success: Whether the ingestion succeeded.
        rows_loaded: Number of rows loaded.
        bytes_written: Bytes written to destination.
        duration_seconds: Execution duration.
        errors: List of error messages if failed.

    Example:
        >>> result = IngestionResult(
        ...     success=True,
        ...     rows_loaded=10000,
        ...     bytes_written=1024000,
        ...     duration_seconds=12.5
        ... )
    """

    success: bool
    rows_loaded: int = 0
    bytes_written: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=lambda: [])


class IngestionPlugin(PluginMetadata):
    """Abstract base class for data ingestion plugins.

    IngestionPlugin extends PluginMetadata with ingestion-specific
    methods for loading data from external sources. Implementations
    include dlt and Airbyte.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - is_external property
        - create_pipeline() method
        - run() method
        - get_destination_config() method

    Example:
        >>> class DLTPlugin(IngestionPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "dlt"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     @property
        ...     def is_external(self) -> bool:
        ...         return False  # dlt runs in-process
        ...
        ...     def create_pipeline(self, config: IngestionConfig) -> Any:
        ...         import dlt
        ...         return dlt.pipeline(...)

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @property
    @abstractmethod
    def is_external(self) -> bool:
        """Whether this ingestion tool runs as an external service.

        In-process tools (dlt) run within the floe platform.
        External tools (Airbyte) run as separate services.

        Returns:
            True if external service, False if in-process.

        Example:
            >>> dlt_plugin.is_external
            False  # Runs in-process
            >>> airbyte_plugin.is_external
            True  # Runs as external service
        """
        ...

    @abstractmethod
    def create_pipeline(self, config: IngestionConfig) -> Any:
        """Create ingestion pipeline from configuration.

        Configures and returns a pipeline object that can be executed
        with the run() method.

        Args:
            config: Ingestion pipeline configuration.

        Returns:
            Pipeline object (implementation-specific).

        Raises:
            ValidationError: If config is invalid.
            ConnectionError: If unable to connect to source.

        Example:
            >>> config = IngestionConfig(
            ...     source_type="postgres",
            ...     source_config={"connection_string": "..."},
            ...     destination_table="bronze.raw_customers"
            ... )
            >>> pipeline = plugin.create_pipeline(config)
        """
        ...

    @abstractmethod
    def run(self, pipeline: Any, **kwargs: Any) -> IngestionResult:
        """Execute the ingestion pipeline.

        Runs the pipeline to load data from source to destination.

        Args:
            pipeline: Pipeline object from create_pipeline().
            **kwargs: Additional execution options.

        Returns:
            IngestionResult with execution status and metrics.

        Example:
            >>> result = plugin.run(pipeline)
            >>> result.success
            True
            >>> result.rows_loaded
            10000
        """
        ...

    @abstractmethod
    def get_destination_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        """Generate destination configuration for Iceberg.

        Creates destination configuration for writing to Iceberg tables
        via the platform's catalog.

        Args:
            catalog_config: Catalog connection configuration.

        Returns:
            Destination configuration dict for Iceberg.

        Example:
            >>> config = plugin.get_destination_config({
            ...     "uri": "http://polaris:8181/api/catalog",
            ...     "warehouse": "floe_warehouse"
            ... })
            >>> config
            {
                'destination': 'iceberg',
                'catalog_uri': 'http://polaris:8181/api/catalog',
                'warehouse': 'floe_warehouse'
            }
        """
        ...
