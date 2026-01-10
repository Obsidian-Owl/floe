"""Pytest fixtures for K8s-native test services.

This module provides pytest fixtures for connecting to test services running
in the Kind cluster, including PostgreSQL, MinIO, Polaris, DuckDB, and Dagster.

Fixtures:
    postgres_connection: PostgreSQL database connection
    minio_client: MinIO S3 client
    polaris_catalog: Polaris catalog client
    duckdb_connection: DuckDB connection (in-memory or file)
    dagster_client: Dagster webserver client

Utilities:
    wait_for_condition: Poll until condition is true or timeout
    wait_for_service: Wait for service to become healthy
    generate_unique_namespace: Create isolated namespace for test

Example:
    from testing.fixtures import wait_for_condition

    def test_async_operation() -> None:
        job_id = start_background_job()
        assert wait_for_condition(
            lambda: job_status(job_id) == "complete",
            timeout=30.0,
            description="job completion"
        )
"""

from __future__ import annotations

# Phase 6 exports - Service fixtures
from testing.fixtures.dagster import (
    DagsterConfig,
    DagsterConnectionError,
    check_webserver_health,
    create_dagster_instance,
    dagster_instance_context,
    ephemeral_instance,
)
from testing.fixtures.data import (
    create_model_instance,
    generate_random_string,
    generate_test_data,
    generate_test_email,
    generate_test_id,
    generate_test_timestamp,
    sample_customer_data,
    sample_order_data,
    sample_records,
)
from testing.fixtures.duckdb import (
    DuckDBConfig,
    DuckDBConnectionError,
    create_duckdb_connection,
    create_file_connection,
    create_memory_connection,
    duckdb_connection_context,
    execute_script,
)
from testing.fixtures.minio import (
    MinIOConfig,
    MinIOConnectionError,
    cleanup_bucket,
    create_minio_client,
    delete_bucket_contents,
    ensure_bucket,
    minio_client_context,
)

# Phase 2 exports - Foundational utilities
from testing.fixtures.namespaces import (
    InvalidNamespaceError,
    generate_unique_namespace,
    validate_namespace,
)
from testing.fixtures.polaris import (
    PolarisConfig,
    PolarisConnectionError,
    create_polaris_catalog,
    create_test_namespace,
    drop_test_namespace,
    namespace_exists,
    polaris_catalog_context,
)
from testing.fixtures.polling import (
    PollingConfig,
    PollingTimeoutError,
    wait_for_condition,
    wait_for_service,
)
from testing.fixtures.postgres import (
    PostgresConfig,
    PostgresConnectionError,
    create_connection,
    create_test_database,
    drop_test_database,
    postgres_connection_context,
)
from testing.fixtures.services import (
    ServiceEndpoint,
    ServiceUnavailableError,
    check_infrastructure,
    check_service_health,
)

__all__ = [
    # Polling utilities
    "PollingConfig",
    "PollingTimeoutError",
    "wait_for_condition",
    "wait_for_service",
    # Namespace utilities
    "InvalidNamespaceError",
    "generate_unique_namespace",
    "validate_namespace",
    # Service utilities
    "ServiceEndpoint",
    "ServiceUnavailableError",
    "check_infrastructure",
    "check_service_health",
    # PostgreSQL fixtures
    "PostgresConfig",
    "PostgresConnectionError",
    "create_connection",
    "create_test_database",
    "drop_test_database",
    "postgres_connection_context",
    # MinIO fixtures
    "MinIOConfig",
    "MinIOConnectionError",
    "cleanup_bucket",
    "create_minio_client",
    "delete_bucket_contents",
    "ensure_bucket",
    "minio_client_context",
    # Polaris fixtures
    "PolarisConfig",
    "PolarisConnectionError",
    "create_polaris_catalog",
    "create_test_namespace",
    "drop_test_namespace",
    "namespace_exists",
    "polaris_catalog_context",
    # DuckDB fixtures
    "DuckDBConfig",
    "DuckDBConnectionError",
    "create_duckdb_connection",
    "create_file_connection",
    "create_memory_connection",
    "duckdb_connection_context",
    "execute_script",
    # Dagster fixtures
    "DagsterConfig",
    "DagsterConnectionError",
    "check_webserver_health",
    "create_dagster_instance",
    "dagster_instance_context",
    "ephemeral_instance",
    # Data generation helpers
    "create_model_instance",
    "generate_random_string",
    "generate_test_data",
    "generate_test_email",
    "generate_test_id",
    "generate_test_timestamp",
    "sample_customer_data",
    "sample_order_data",
    "sample_records",
]
