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

# Exports will be added as fixtures are implemented in Phase 2 and Phase 6
__all__: list[str] = []
