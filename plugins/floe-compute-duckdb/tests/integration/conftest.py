"""Integration test fixtures for floe-compute-duckdb.

Integration tests require DuckDB to be available and may use real
database connections.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def reset_otel_global_state() -> Generator[None, None, None]:
    """Reset OpenTelemetry global state before and after each test.

    Required for integration tests that use observability instrumentation.
    Uses SDK TracerProvider/MeterProvider to avoid ProxyTracerProvider recursion.

    Yields:
        None after resetting state.
    """
    from floe_core.observability import reset_for_testing
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider

    reset_for_testing()

    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = TracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = MeterProvider()

    yield

    reset_for_testing()

    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = TracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = MeterProvider()


@pytest.fixture
def duckdb_plugin() -> Any:
    """Create a DuckDBComputePlugin instance for testing."""
    from floe_compute_duckdb import DuckDBComputePlugin

    return DuckDBComputePlugin()


@pytest.fixture
def memory_config() -> Any:
    """Create an in-memory DuckDB ComputeConfig for testing."""
    from floe_core.compute_config import ComputeConfig

    return ComputeConfig(
        plugin="duckdb",
        threads=4,
        connection={
            "path": ":memory:",
        },
    )


@pytest.fixture
def catalog_config() -> Any:
    """Create an Iceberg CatalogConfig for testing."""
    from floe_core.compute_config import CatalogConfig
    from pydantic import SecretStr

    return CatalogConfig(
        catalog_type="rest",
        catalog_name="ice",
        catalog_uri="http://polaris:8181/api/catalog",
        warehouse="floe_warehouse",
        credentials={
            "client_id": SecretStr("test_client"),
            "client_secret": SecretStr("test_secret"),
        },
    )
