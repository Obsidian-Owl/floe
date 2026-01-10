"""ComputePlugin ABC for compute engine plugins.

This module defines the abstract base class for compute plugins that provide
database connectivity for dbt transforms. Compute plugins are responsible for:
- Generating dbt profile.yml configurations
- Validating connections to compute engines
- Providing K8s resource requirements for dbt job pods
- Optionally providing SQL to attach to Iceberg catalogs

The configuration models used by ComputePlugin are defined in compute_config.py
and include Pydantic models with full validation:
- ComputeConfig: Base configuration for compute plugins
- ConnectionResult: Result of validate_connection() with status enum
- ResourceSpec: K8s resource requirements
- CatalogConfig: Iceberg catalog configuration

Example:
    >>> from floe_core.plugins.compute import ComputePlugin
    >>> from floe_core.compute_config import (
    ...     ComputeConfig, ConnectionResult, ConnectionStatus, ResourceSpec
    ... )
    >>> class DuckDBPlugin(ComputePlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "duckdb"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from floe_core.compute_config import (
    CatalogConfig,
    ComputeConfig,
    ConnectionResult,
    ResourceSpec,
)
from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    from pydantic import BaseModel


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

    Configuration models (from compute_config.py):
        - ComputeConfig: Base Pydantic model with plugin, timeout_seconds, threads
        - ConnectionResult: Frozen Pydantic model with status enum, latency_ms
        - ResourceSpec: K8s resource requirements (cpu, memory, ephemeral storage)
        - CatalogConfig: Iceberg REST catalog configuration
        - WORKLOAD_PRESETS: Dict of small/medium/large ResourceSpec presets

    Example:
        >>> from floe_core.compute_config import (
        ...     ComputeConfig, ConnectionResult, ConnectionStatus,
        ...     ResourceSpec, WORKLOAD_PRESETS
        ... )
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
        ...         return {"type": "duckdb", "path": config.connection.get("path", ":memory:")}
        ...
        ...     def get_required_dbt_packages(self) -> list[str]:
        ...         return ["dbt-duckdb>=1.7.0"]
        ...
        ...     def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        ...         return ConnectionResult(
        ...             status=ConnectionStatus.HEALTHY,
        ...             latency_ms=10.5,
        ...             message="Connected successfully"
        ...         )
        ...
        ...     def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        ...         return WORKLOAD_PRESETS.get(workload_size, WORKLOAD_PRESETS["medium"])

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - floe_core.compute_config: Configuration Pydantic models
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
            config: ComputeConfig Pydantic model with plugin name, timeout,
                threads, connection dict, and credentials.

        Returns:
            Dictionary matching dbt profile.yml target schema.

        Example:
            >>> from floe_core.compute_config import ComputeConfig
            >>> config = ComputeConfig(
            ...     plugin="duckdb",
            ...     threads=4,
            ...     connection={"path": "/data/floe.duckdb"}
            ... )
            >>> profile = plugin.generate_dbt_profile(config)
            >>> profile
            {
                'type': 'duckdb',
                'path': '/data/floe.duckdb',
                'threads': 4
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
            ConnectionResult with status (HEALTHY/DEGRADED/UNHEALTHY),
            latency_ms, optional message, and warnings list.

        Example:
            >>> from floe_core.compute_config import ConnectionStatus
            >>> result = plugin.validate_connection(config)
            >>> if result.status == ConnectionStatus.HEALTHY:
            ...     print(f"Connected in {result.latency_ms}ms")
            >>> elif result.status == ConnectionStatus.DEGRADED:
            ...     print(f"Connected with warnings: {result.warnings}")
            >>> else:
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
