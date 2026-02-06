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

import re
import time
from typing import TYPE_CHECKING, Any

from floe_core.compute_config import (
    CatalogConfig,
    ComputeConfig,
    ConnectionResult,
    ConnectionStatus,
    ResourceSpec,
)
from floe_core.observability import (
    record_validation_duration,
    record_validation_error,
    start_validation_span,
)
from floe_core.plugins import ComputePlugin

if TYPE_CHECKING:
    from pydantic import BaseModel

# Regex pattern for valid SQL identifiers (alphanumeric + underscores only)
# Used to prevent SQL injection in ATTACH statements
_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_sql_identifier(value: str, field_name: str) -> None:
    """Validate that a value is a safe SQL identifier.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.

    Raises:
        ValueError: If the value contains unsafe characters.
    """
    if not _SAFE_IDENTIFIER_PATTERN.match(value):
        msg = (
            f"Invalid {field_name}: '{value}'. "
            "Must contain only alphanumeric characters and underscores, "
            "and must start with a letter or underscore."
        )
        raise ValueError(msg)


def _escape_sql_string(value: str) -> str:
    """Escape single quotes in SQL string literals.

    Escapes single quotes by doubling them, which is the standard
    SQL escaping mechanism for string literals.

    Args:
        value: The string value to escape.

    Returns:
        The escaped string safe for use in SQL literals.
    """
    return value.replace("'", "''")


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
                Uses config.connection dict with keys:
                - path: Database file path (default: ":memory:")
                - extensions: List of extensions to load
                - settings: DuckDB settings dict (memory_limit, etc.)
                - attach: List of AttachConfig dicts for attaching external databases
                Uses config.threads for thread count.

        Returns:
            Dictionary matching dbt-duckdb profile schema with keys:
            - type: Always "duckdb"
            - path: Database path
            - threads: Number of query threads
            - timeout_seconds: Query timeout in seconds (optional, FR-021)
            - extensions: Extensions to load (optional)
            - settings: DuckDB configuration (optional)
            - attach: List of attached databases (optional)

        Example:
            >>> config = ComputeConfig(
            ...     plugin="duckdb",
            ...     threads=8,
            ...     connection={"path": "/data/analytics.duckdb"}
            ... )
            >>> profile = plugin.generate_dbt_profile(config)
            >>> profile
            {'type': 'duckdb', 'path': '/data/analytics.duckdb', 'threads': 8}

            With attach configuration:
            >>> config = ComputeConfig(
            ...     plugin="duckdb",
            ...     threads=4,
            ...     connection={
            ...         "path": ":memory:",
            ...         "attach": [
            ...             {"path": "iceberg:polaris", "alias": "iceberg_db", "type": "iceberg"}
            ...         ]
            ...     }
            ... )
            >>> profile = plugin.generate_dbt_profile(config)
            >>> len(profile["attach"])
            1
        """
        connection = config.connection

        profile: dict[str, Any] = {
            "type": "duckdb",
            "path": connection.get("path", ":memory:"),
            "threads": config.threads,
        }

        # Add timeout if specified (FR-021: query timeout enforcement)
        # dbt-duckdb adapter handles actual timeout enforcement
        if config.timeout_seconds:
            profile["timeout_seconds"] = config.timeout_seconds

        # Add optional extensions if specified
        extensions = connection.get("extensions")
        if extensions:
            profile["extensions"] = extensions

        # Add optional settings if specified
        settings = connection.get("settings")
        if settings:
            profile["settings"] = settings

        # Add optional attach blocks if specified (for attaching external databases)
        attach_configs = connection.get("attach")
        if attach_configs:
            attach_list: list[dict[str, Any]] = []
            for attach in attach_configs:
                attach_entry: dict[str, Any] = {"path": attach["path"]}

                # Alias is optional but recommended
                if "alias" in attach:
                    attach_entry["alias"] = attach["alias"]

                # Type is optional (defaults to DuckDB native)
                if "type" in attach:
                    attach_entry["type"] = attach["type"]

                # Additional options can be included
                if "options" in attach and attach["options"]:
                    attach_entry.update(attach["options"])

                attach_list.append(attach_entry)

            profile["attach"] = attach_list

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

        Emits OpenTelemetry metrics (FR-024):
        - floe.compute.validation_duration histogram
        - floe.compute.validation_errors counter (on failure)

        Args:
            config: Compute configuration with DuckDB settings.

        Returns:
            ConnectionResult with status, latency_ms, and message.

        Example:
            >>> result = plugin.validate_connection(config)
            >>> result.status == ConnectionStatus.HEALTHY
            True
            >>> result.latency_ms < 100
            True
        """
        import duckdb

        path = config.connection.get("path", ":memory:")
        start_time = time.perf_counter()

        with start_validation_span(self.name) as span:
            span.set_attribute("db.path", path)

            try:
                conn = duckdb.connect(path, read_only=False)
                try:
                    # Simple validation query
                    query_result = conn.execute("SELECT 1").fetchone()
                    latency_ms = (time.perf_counter() - start_time) * 1000

                    if query_result and query_result[0] == 1:
                        result = ConnectionResult(
                            status=ConnectionStatus.HEALTHY,
                            latency_ms=latency_ms,
                            message=f"Connected to DuckDB successfully (path: {path})",
                        )
                        span.set_attribute("validation.status", "healthy")
                        record_validation_duration(self.name, latency_ms, "healthy")
                        return result

                    result = ConnectionResult(
                        status=ConnectionStatus.UNHEALTHY,
                        latency_ms=latency_ms,
                        message="DuckDB validation query returned unexpected result",
                    )
                    span.set_attribute("validation.status", "unhealthy")
                    record_validation_duration(self.name, latency_ms, "unhealthy")
                    record_validation_error(self.name, "unexpected_result")
                    return result
                finally:
                    conn.close()
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                span.set_attribute("validation.status", "unhealthy")
                span.set_attribute("error.message", str(e))
                record_validation_duration(self.name, latency_ms, "unhealthy")
                record_validation_error(self.name, type(e).__name__)
                return ConnectionResult(
                    status=ConnectionStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                    message=f"Failed to connect to DuckDB: {e}",
                    warnings=[f"Error details: {e!s}"],
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

        Raises:
            ValueError: If catalog_name contains invalid characters.
        """
        # Validate catalog_name as it's used as an SQL identifier (AS clause)
        # This prevents SQL injection via malicious catalog names
        _validate_sql_identifier(catalog_config.catalog_name, "catalog_name")

        statements: list[str] = [
            "INSTALL iceberg;",
            "LOAD iceberg;",
        ]

        # Escape string values to prevent SQL injection
        catalog_name_escaped = _escape_sql_string(catalog_config.catalog_name)

        # Build ATTACH statement with options
        attach_parts = [
            f"ATTACH '{catalog_name_escaped}' AS {catalog_config.catalog_name}",
            "(TYPE ICEBERG",
        ]

        if catalog_config.catalog_uri:
            uri_escaped = _escape_sql_string(catalog_config.catalog_uri)
            attach_parts.append(f", ENDPOINT '{uri_escaped}'")

        if catalog_config.warehouse:
            warehouse_escaped = _escape_sql_string(catalog_config.warehouse)
            attach_parts.append(f", WAREHOUSE '{warehouse_escaped}'")

        # Add credentials if provided (extract secret values and escape)
        creds = catalog_config.credentials
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")

        if client_id:
            # SecretStr: use get_secret_value() to extract, then escape
            value = _escape_sql_string(client_id.get_secret_value())
            attach_parts.append(f", CLIENT_ID '{value}'")
        if client_secret:
            value = _escape_sql_string(client_secret.get_secret_value())
            attach_parts.append(f", CLIENT_SECRET '{value}'")

        attach_parts.append(")")

        statements.append("".join(attach_parts) + ";")

        return statements

    def get_cube_datasource_config(
        self,
        *,
        catalog_config: CatalogConfig | None = None,
        database_path: str = ":memory:",
    ) -> dict[str, Any]:
        """Generate Cube datasource configuration for DuckDB.

        Returns a dictionary that Cube can use to configure DuckDB as its
        datasource. Optionally includes initSql with Iceberg extension
        INSTALL/LOAD/ATTACH statements when a catalog config is provided.

        Args:
            catalog_config: Optional Iceberg catalog config for initSql generation.
            database_path: DuckDB database file path. Defaults to :memory:.

        Returns:
            Cube-compatible datasource configuration dictionary.
        """
        config: dict[str, Any] = {
            "type": "duckdb",
            "database_path": database_path,
        }

        if catalog_config is not None:
            sql_statements = self.get_catalog_attachment_sql(catalog_config)
            if sql_statements:
                config["init_sql"] = " ".join(sql_statements)

        return config

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return Pydantic model for DuckDB configuration validation.

        Returns:
            None (configuration validation not yet implemented).
        """
        # Will be implemented in later task with DuckDBConfig model
        return None
