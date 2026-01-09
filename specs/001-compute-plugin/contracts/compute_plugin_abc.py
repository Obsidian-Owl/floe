"""ComputePlugin ABC Contract Definition.

This file defines the abstract base class interface for ComputePlugin.
All compute plugin implementations MUST implement these abstract methods.

Location: packages/floe-core/src/floe_core/compute_plugin.py
"""
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floe_core.compute_config import CatalogConfig, ComputeConfig, ConnectionResult, ResourceSpec
    from floe_core.plugin_metadata import PluginMetadata


class ComputePlugin(PluginMetadata):
    """Abstract base class for compute target configuration.

    ComputePlugin generates dbt profiles.yml configuration (dbt handles SQL execution
    via its adapters), validates connections using native database drivers for fast
    health checks, and provides K8s resource requirements for dbt job pods.

    Key Constraint:
        ComputePlugin MUST NOT execute SQL directly - dbt adapters handle all SQL
        execution via profiles.yml configuration (FR-004a).

    Example:
        >>> class DuckDBComputePlugin(ComputePlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "duckdb"
        ...
        ...     def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
        ...         return {
        ...             "type": "duckdb",
        ...             "path": config.path,
        ...             "threads": config.threads,
        ...         }
    """

    @abstractmethod
    def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
        """Generate dbt profiles.yml configuration for this compute target.

        Creates the configuration dictionary that will be written to dbt profiles.yml.
        The dbt adapter (dbt-duckdb, dbt-snowflake, etc.) uses this configuration
        to establish connections and execute SQL.

        Args:
            config: Validated compute configuration containing connection settings,
                credentials, and plugin-specific options.

        Returns:
            Dictionary containing dbt profile configuration. Structure varies by
            adapter but typically includes: type, threads, and adapter-specific
            connection parameters.

        Raises:
            ComputeConfigurationError: If configuration is invalid for this compute.

        Example:
            >>> config = DuckDBConfig(path=":memory:", threads=4)
            >>> profile = plugin.generate_dbt_profile(config)
            >>> profile["type"]
            'duckdb'
        """
        ...

    @abstractmethod
    def get_required_dbt_packages(self) -> list[str]:
        """Return dbt packages required for this compute target.

        Returns the list of pip package names (with version constraints) needed
        to use this compute target with dbt. Used by deployment to build the
        dbt job container image.

        Returns:
            List of pip package specifications (e.g., ["dbt-duckdb>=1.9.0"]).

        Example:
            >>> plugin.get_required_dbt_packages()
            ['dbt-duckdb>=1.9.0', 'duckdb>=0.9.0']
        """
        ...

    @abstractmethod
    def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        """Test connection to compute target using native database driver.

        Performs a lightweight health check using the native database driver
        (not dbt debug) to verify connectivity. Must complete within 5 seconds
        per SC-007.

        Args:
            config: Validated compute configuration with credentials.

        Returns:
            ConnectionResult containing status (HEALTHY/DEGRADED/UNHEALTHY),
            latency_ms, and optional warnings.

        Note:
            This method uses native drivers (duckdb, snowflake-connector-python)
            for fast health checks, NOT dbt debug which is slower.

        Example:
            >>> result = plugin.validate_connection(config)
            >>> result.status
            <ConnectionStatus.HEALTHY: 'healthy'>
            >>> result.latency_ms
            23.5
        """
        ...

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for dbt job pods.

        Provides CPU, memory, and ephemeral storage requests/limits for
        Kubernetes job pods running dbt transforms on this compute target.

        Args:
            workload_size: Size preset ("small", "medium", "large") or custom.

        Returns:
            ResourceSpec with cpu_request, cpu_limit, memory_request,
            memory_limit, ephemeral_storage_request, ephemeral_storage_limit.

        Raises:
            ValueError: If workload_size is not recognized.

        Example:
            >>> spec = plugin.get_resource_requirements("medium")
            >>> spec.cpu_limit
            '2000m'
            >>> spec.memory_limit
            '4Gi'
        """
        ...

    @abstractmethod
    def get_catalog_attachment_sql(
        self, catalog_config: CatalogConfig
    ) -> list[str] | None:
        """Return SQL statements to attach compute engine to Iceberg catalog.

        For compute engines that support direct Iceberg catalog attachment
        (e.g., DuckDB with Iceberg extension), returns the SQL statements
        needed to attach to a REST catalog like Polaris.

        Args:
            catalog_config: Catalog connection configuration including URI,
                credentials, and warehouse path.

        Returns:
            List of SQL statements to execute for catalog attachment, or None
            if this compute engine doesn't support direct catalog attachment
            (e.g., Snowflake, BigQuery use their own catalog mechanisms).

        Example:
            >>> sql = plugin.get_catalog_attachment_sql(catalog_config)
            >>> sql[0]
            "INSTALL iceberg;"
            >>> sql[1]
            "LOAD iceberg;"
        """
        ...
