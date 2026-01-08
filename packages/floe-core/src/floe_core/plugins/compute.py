"""ComputePlugin ABC for compute engine plugins.

This module defines the abstract base class for compute plugins that provide
database connectivity for dbt transforms. Compute plugins are responsible for:
- Generating dbt profile.yml configurations
- Validating connections to compute engines
- Providing K8s resource requirements for dbt job pods
- Optionally providing SQL to attach to Iceberg catalogs

Example:
    >>> from floe_core.plugins.compute import ComputePlugin
    >>> class DuckDBPlugin(ComputePlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "duckdb"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    from pydantic import BaseModel


@dataclass
class ComputeConfig:
    """Configuration for a compute engine connection.

    This is a minimal stub dataclass. Concrete implementations will
    use Pydantic models with full validation.

    Attributes:
        host: Database host address.
        port: Database port number.
        database: Database name.
        schema_name: Schema name (called schema_name to avoid shadowing builtin).
        credentials: Dictionary of credential key-value pairs.
        extra: Additional configuration options.

    Example:
        >>> config = ComputeConfig(
        ...     host="localhost",
        ...     port=5432,
        ...     database="analytics",
        ...     schema_name="public"
        ... )
    """

    host: str = ""
    port: int = 0
    database: str = ""
    schema_name: str = ""
    credentials: dict[str, Any] = field(default_factory=lambda: {})
    extra: dict[str, Any] = field(default_factory=lambda: {})


@dataclass
class ConnectionResult:
    """Result of a connection validation attempt.

    Attributes:
        success: Whether the connection was successful.
        message: Human-readable message about the connection status.
        latency_ms: Connection latency in milliseconds (if successful).
        details: Additional diagnostic information.

    Example:
        >>> result = ConnectionResult(
        ...     success=True,
        ...     message="Connected successfully",
        ...     latency_ms=42.5
        ... )
    """

    success: bool
    message: str = ""
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=lambda: {})


@dataclass
class ResourceSpec:
    """Kubernetes resource requirements specification.

    Follows K8s ResourceRequirements schema for CPU and memory
    requests and limits.

    Attributes:
        cpu_request: CPU request (e.g., "100m", "1").
        cpu_limit: CPU limit (e.g., "500m", "2").
        memory_request: Memory request (e.g., "256Mi", "1Gi").
        memory_limit: Memory limit (e.g., "512Mi", "2Gi").

    Example:
        >>> spec = ResourceSpec(
        ...     cpu_request="100m",
        ...     cpu_limit="1",
        ...     memory_request="256Mi",
        ...     memory_limit="1Gi"
        ... )
    """

    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "256Mi"
    memory_limit: str = "512Mi"


@dataclass
class CatalogConfig:
    """Configuration for an Iceberg catalog connection.

    Used by get_catalog_attachment_sql() to generate SQL statements
    for attaching compute engines to Iceberg catalogs.

    Attributes:
        catalog_name: Name of the catalog (e.g., "ice").
        catalog_uri: REST catalog URI (e.g., "http://polaris:8181/api/catalog").
        warehouse: Warehouse identifier.
        credentials: Catalog credentials.

    Example:
        >>> config = CatalogConfig(
        ...     catalog_name="ice",
        ...     catalog_uri="http://polaris:8181/api/catalog",
        ...     warehouse="floe_warehouse"
        ... )
    """

    catalog_name: str = ""
    catalog_uri: str = ""
    warehouse: str = ""
    credentials: dict[str, Any] = field(default_factory=lambda: {})


class ComputePlugin(PluginMetadata):
    """Abstract base class for compute engine plugins.

    ComputePlugin extends PluginMetadata with compute-specific methods
    for database connectivity where dbt transforms execute. Implementations
    include DuckDB, Snowflake, Databricks, Spark, and BigQuery.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - is_self_hosted property
        - generate_dbt_profile() method
        - get_required_dbt_packages() method
        - validate_connection() method
        - get_resource_requirements() method

    Optional override:
        - get_catalog_attachment_sql() for engines that need explicit catalog attachment

    Example:
        >>> class DuckDBPlugin(ComputePlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "duckdb"
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
        ...     def is_self_hosted(self) -> bool:
        ...         return True
        ...
        ...     def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        ...         return {"type": "duckdb", "path": "/data/floe.duckdb"}
        ...
        ...     def get_required_dbt_packages(self) -> list[str]:
        ...         return ["dbt-duckdb>=1.7.0"]
        ...
        ...     def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        ...         return ConnectionResult(success=True, message="Connected")
        ...
        ...     def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        ...         return ResourceSpec(cpu_request="500m", memory_request="1Gi")

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @property
    @abstractmethod
    def is_self_hosted(self) -> bool:
        """Whether this compute engine runs within the platform.

        Self-hosted engines (DuckDB, Spark) run in K8s pods managed by floe.
        External engines (Snowflake, BigQuery) are SaaS services.

        Returns:
            True if self-hosted (runs in platform K8s), False if external SaaS.

        Example:
            >>> plugin.is_self_hosted
            True  # DuckDB runs locally
            >>> snowflake_plugin.is_self_hosted
            False  # Snowflake is SaaS
        """
        ...

    @abstractmethod
    def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
        """Generate dbt profile.yml configuration for this compute engine.

        Creates the target configuration section for dbt's profiles.yml file.
        The returned dictionary should match dbt's expected schema for the
        specific adapter (duckdb, snowflake, etc.).

        Args:
            config: Compute engine configuration with connection details.

        Returns:
            Dictionary matching dbt profile.yml target schema.

        Example:
            >>> config = ComputeConfig(database="analytics")
            >>> profile = plugin.generate_dbt_profile(config)
            >>> profile
            {
                'type': 'duckdb',
                'path': '/data/floe.duckdb',
                'extensions': ['iceberg', 'httpfs']
            }

        See Also:
            - https://docs.getdbt.com/docs/core/connect-data-platform/profiles.yml
        """
        ...

    @abstractmethod
    def get_required_dbt_packages(self) -> list[str]:
        """Return required dbt adapter packages for this compute engine.

        Returns pip-installable package specifications for the dbt adapter
        and any required dependencies. Used during environment setup.

        Returns:
            List of pip package specifiers (e.g., ["dbt-duckdb>=1.7.0"]).

        Example:
            >>> plugin.get_required_dbt_packages()
            ['dbt-duckdb>=1.7.0', 'duckdb>=0.10.0']
        """
        ...

    @abstractmethod
    def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        """Test connection to the compute engine.

        Performs a lightweight connectivity test to verify the compute
        engine is reachable and credentials are valid. Should complete
        within 10 seconds.

        Args:
            config: Compute engine configuration with connection details.

        Returns:
            ConnectionResult with success status and diagnostic information.

        Example:
            >>> result = plugin.validate_connection(config)
            >>> if result.success:
            ...     print(f"Connected in {result.latency_ms}ms")
            ... else:
            ...     print(f"Failed: {result.message}")
        """
        ...

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for dbt job pods.

        Provides CPU and memory requests/limits based on workload size.
        Only applicable for self-hosted compute engines.

        Args:
            workload_size: One of "small", "medium", "large".

        Returns:
            ResourceSpec with K8s-compatible resource specifications.

        Raises:
            ValueError: If workload_size is not one of the valid options.

        Example:
            >>> spec = plugin.get_resource_requirements("medium")
            >>> spec.cpu_request
            '500m'
            >>> spec.memory_limit
            '2Gi'
        """
        ...

    def get_catalog_attachment_sql(
        self,
        catalog_config: CatalogConfig,  # noqa: ARG002
    ) -> list[str] | None:
        """Return SQL statements to attach compute engine to Iceberg catalog.

        Some compute engines (like DuckDB) require explicit SQL statements
        to attach to an Iceberg REST catalog. Others (Spark, Snowflake)
        configure catalog access differently and return None.

        Args:
            catalog_config: Iceberg catalog configuration.

        Returns:
            List of SQL statements to execute, or None if not applicable.

        Example:
            >>> # DuckDB returns ATTACH statements
            >>> sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)
            >>> sql
            ["ATTACH 'ice' AS ice (TYPE ICEBERG, ENDPOINT 'http://polaris:8181')"]

            >>> # Snowflake returns None (uses external catalog integration)
            >>> snowflake_plugin.get_catalog_attachment_sql(catalog_config)
            None
        """
        return None

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return the Pydantic model for compute configuration validation.

        Override this method to provide a Pydantic model that validates
        compute-specific configuration. The model should include all
        required connection parameters for this compute engine.

        Returns:
            A Pydantic BaseModel subclass for config validation, or None.

        Example:
            >>> from pydantic import BaseModel, Field
            >>> class DuckDBConfig(BaseModel):
            ...     path: str = Field(default="/data/floe.duckdb")
            ...     extensions: list[str] = Field(default_factory=list)
            ...
            >>> class DuckDBPlugin(ComputePlugin):
            ...     def get_config_schema(self) -> type[BaseModel]:
            ...         return DuckDBConfig
        """
        return None
