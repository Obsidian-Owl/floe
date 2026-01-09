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

# Phase 2 exports - Foundational utilities
from testing.fixtures.namespaces import (
    InvalidNamespaceError,
    generate_unique_namespace,
    validate_namespace,
)
from testing.fixtures.polling import (
    PollingConfig,
    PollingTimeoutError,
    wait_for_condition,
    wait_for_service,
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
]
