"""DuckDB compute plugin for floe.

This module provides the DuckDBComputePlugin implementation that enables
DuckDB as a compute target for dbt transforms in the floe data platform.

DuckDB is a self-hosted, in-process analytical database that runs within
K8s job pods alongside dbt. It supports direct Iceberg catalog attachment
via the iceberg extension.

Example:
    >>> from floe_compute_duckdb import DuckDBComputePlugin
    >>> plugin = DuckDBComputePlugin()
    >>> plugin.name
    'duckdb'
    >>> profile = plugin.generate_dbt_profile(config)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from floe_core.plugins.compute import (
    CatalogConfig,
    ComputeConfig,
    ComputePlugin,
    ConnectionResult,
    ResourceSpec,
)

if TYPE_CHECKING:
    from pydantic import BaseModel


class DuckDBComputePlugin(ComputePlugin):
    """DuckDB compute plugin for floe data platform.

    DuckDB is a self-hosted, in-process analytical database optimized for
    analytical workloads. It runs within K8s job pods managed by floe and
    supports direct Iceberg catalog attachment.

    Key Features:
        - In-process: Runs alongside dbt in the same pod
        - Self-hosted: Managed by floe K8s infrastructure
        - Iceberg support: Direct catalog attachment via iceberg extension
        - Low overhead: No separate database server required

    Example:
        >>> plugin = DuckDBComputePlugin()
        >>> config = ComputeConfig(
        ...     database="analytics",
        ...     extra={"path": ":memory:", "threads": 4}
        ... )
        >>> profile = plugin.generate_dbt_profile(config)
        >>> profile["type"]
        'duckdb'
    """

    # Resource presets for different workload sizes
    _RESOURCE_PRESETS: dict[str, ResourceSpec] = {
        "small": ResourceSpec(
            cpu_request="100m",
            cpu_limit="500m",
            memory_request="256Mi",
            memory_limit="512Mi",
        ),
        "medium": ResourceSpec(
            cpu_request="500m",
            cpu_limit="2000m",
            memory_request="1Gi",
            memory_limit="4Gi",
        ),
        "large": ResourceSpec(
            cpu_request="2000m",
            cpu_limit="8000m",
            memory_request="4Gi",
            memory_limit="16Gi",
        ),
    }

    @property
    def name(self) -> str:
        """Plugin name identifier.

        Returns:
            The string 'duckdb'.
        """
        return "duckdb"

    @property
    def version(self) -> str:
        """Plugin version in semver format.

        Returns:
            Current plugin version.
        """
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Required floe API version.

        Returns:
            Minimum compatible floe API version.
        """
        return "1.0"

    @property
    def description(self) -> str:
        """Human-readable plugin description.

        Returns:
            Description of the DuckDB compute plugin.
        """
        return "DuckDB in-process analytical database for floe dbt transforms"

    @property
    def is_self_hosted(self) -> bool:
        """Whether DuckDB runs within the platform.

        DuckDB is self-hosted - it runs in-process within K8s job pods
        managed by the floe platform.

        Returns:
            True (DuckDB is always self-hosted).
        """
        return True

    def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
        """Generate dbt profile.yml configuration for DuckDB.

        Creates the target configuration section for dbt's profiles.yml file
        compatible with dbt-duckdb adapter.

        Args:
            config: Compute configuration containing DuckDB-specific settings.
                Expected extra keys:
                - path: Database file path (default: ":memory:")
                - threads: Number of threads (default from config.extra or 4)
                - extensions: List of extensions to load
                - settings: DuckDB settings dict (memory_limit, etc.)

        Returns:
            Dictionary matching dbt-duckdb profile schema with keys:
            - type: Always "duckdb"
            - path: Database path
            - threads: Number of query threads
            - extensions: Extensions to load (optional)
            - settings: DuckDB configuration (optional)

        Example:
            >>> config = ComputeConfig(
            ...     extra={"path": "/data/analytics.duckdb", "threads": 8}
            ... )
            >>> profile = plugin.generate_dbt_profile(config)
            >>> profile
            {'type': 'duckdb', 'path': '/data/analytics.duckdb', 'threads': 8}
        """
        extra = config.extra

        profile: dict[str, Any] = {
            "type": "duckdb",
            "path": extra.get("path", ":memory:"),
            "threads": extra.get("threads", 4),
        }

        # Add optional extensions if specified
        extensions = extra.get("extensions")
        if extensions:
            profile["extensions"] = extensions

        # Add optional settings if specified
        settings = extra.get("settings")
        if settings:
            profile["settings"] = settings

        return profile

    def get_required_dbt_packages(self) -> list[str]:
        """Return required dbt packages for DuckDB.

        Returns:
            List of pip package specifiers for dbt-duckdb and dependencies.

        Example:
            >>> plugin.get_required_dbt_packages()
            ['dbt-duckdb>=1.7.0', 'duckdb>=0.9.0']
        """
        return ["dbt-duckdb>=1.7.0", "duckdb>=0.9.0"]

    def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        """Test connection to DuckDB using native driver.

        Performs a lightweight connectivity test by creating a DuckDB
        connection and executing a simple query. For in-memory databases,
        this verifies DuckDB is available and working.

        Args:
            config: Compute configuration with DuckDB settings.

        Returns:
            ConnectionResult with success status and latency.

        Example:
            >>> result = plugin.validate_connection(config)
            >>> result.success
            True
            >>> result.latency_ms < 100
            True
        """
        import duckdb

        path = config.extra.get("path", ":memory:")
        start_time = time.perf_counter()

        try:
            conn = duckdb.connect(path, read_only=False)
            try:
                # Simple validation query
                result = conn.execute("SELECT 1").fetchone()
                latency_ms = (time.perf_counter() - start_time) * 1000

                if result and result[0] == 1:
                    return ConnectionResult(
                        success=True,
                        message="Connected to DuckDB successfully",
                        latency_ms=latency_ms,
                        details={"path": path},
                    )
                return ConnectionResult(
                    success=False,
                    message="DuckDB validation query returned unexpected result",
                    latency_ms=latency_ms,
                )
            finally:
                conn.close()
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ConnectionResult(
                success=False,
                message=f"Failed to connect to DuckDB: {e}",
                latency_ms=latency_ms,
                details={"error": str(e), "path": path},
            )

    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for DuckDB dbt job pods.

        DuckDB runs in-process with dbt, so resources are allocated to the
        job pod. Larger workloads need more memory for DuckDB's in-memory
        processing.

        Args:
            workload_size: One of "small", "medium", "large".

        Returns:
            ResourceSpec with K8s-compatible resource specifications.

        Raises:
            ValueError: If workload_size is not recognized.

        Example:
            >>> spec = plugin.get_resource_requirements("medium")
            >>> spec.memory_limit
            '4Gi'
        """
        if workload_size not in self._RESOURCE_PRESETS:
            valid_sizes = ", ".join(sorted(self._RESOURCE_PRESETS.keys()))
            msg = f"Unknown workload size: {workload_size}. Valid sizes: {valid_sizes}"
            raise ValueError(msg)

        return self._RESOURCE_PRESETS[workload_size]

    def get_catalog_attachment_sql(
        self,
        catalog_config: CatalogConfig,
    ) -> list[str] | None:
        """Return SQL statements to attach DuckDB to Iceberg catalog.

        DuckDB supports direct Iceberg catalog attachment via the iceberg
        extension. This method generates the SQL statements to:
        1. Install the iceberg extension
        2. Load the iceberg extension
        3. Attach to the REST catalog

        Args:
            catalog_config: Iceberg catalog configuration with URI and credentials.

        Returns:
            List of SQL statements to execute for catalog attachment.

        Example:
            >>> config = CatalogConfig(
            ...     catalog_name="ice",
            ...     catalog_uri="http://polaris:8181/api/catalog",
            ...     warehouse="floe_warehouse"
            ... )
            >>> sql = plugin.get_catalog_attachment_sql(config)
            >>> sql[0]
            'INSTALL iceberg;'
        """
        statements: list[str] = [
            "INSTALL iceberg;",
            "LOAD iceberg;",
        ]

        # Build ATTACH statement with options
        attach_parts = [
            f"ATTACH '{catalog_config.catalog_name}' AS {catalog_config.catalog_name}",
            "(TYPE ICEBERG",
        ]

        if catalog_config.catalog_uri:
            attach_parts.append(f", ENDPOINT '{catalog_config.catalog_uri}'")

        if catalog_config.warehouse:
            attach_parts.append(f", WAREHOUSE '{catalog_config.warehouse}'")

        # Add credentials if provided
        creds = catalog_config.credentials
        if creds.get("client_id"):
            attach_parts.append(f", CLIENT_ID '{creds['client_id']}'")
        if creds.get("client_secret"):
            attach_parts.append(f", CLIENT_SECRET '{creds['client_secret']}'")

        attach_parts.append(")")

        statements.append("".join(attach_parts) + ";")

        return statements

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return Pydantic model for DuckDB configuration validation.

        Returns:
            None (configuration validation not yet implemented).
        """
        # Will be implemented in later task with DuckDBConfig model
        return None
