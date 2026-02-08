"""Root test configuration for floe-orchestrator-dagster.

This module provides shared fixtures and configuration used by both
unit and integration tests for the Dagster orchestrator plugin.

Fixtures:
    reset_otel_global_state: Reset OpenTelemetry providers between tests
    reset_structlog_config: Reset structlog to defaults after tests
    reset_dagster_instance: Reset Dagster instance state for isolation

Requirements:
    NFR-004: Test isolation and deterministic behavior
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for the test suite."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Link test to specification requirement",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring K8s",
    )


@pytest.fixture(autouse=True)
def reset_otel_global_state(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Reset OpenTelemetry global state before and after each test.

    This fixture ensures test isolation by resetting the global
    TracerProvider and MeterProvider between tests. Without this,
    tests that call `trace.set_tracer_provider()` will cause
    subsequent tests to fail with "Overriding not allowed" errors.

    Uses SDK providers (not Proxy) to avoid recursion issues that can
    occur with ProxyTracerProvider when no real provider is configured.

    Yields:
        None after resetting state.
    """
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider

    # Reset before test - use SDK providers to allow clean state
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = TracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = MeterProvider()

    yield

    # Reset after test - use SDK providers to avoid recursion
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = TracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = MeterProvider()


@pytest.fixture(autouse=True)
def reset_structlog_config() -> Generator[None, None, None]:
    """Reset structlog configuration after each test.

    This ensures tests that configure logging don't pollute
    global structlog state for subsequent tests.

    Yields:
        None after test completes.
    """
    import structlog

    yield

    # Reset structlog to defaults after test
    structlog.reset_defaults()


@pytest.fixture
def isolated_plugin() -> Generator[DagsterOrchestratorPlugin, None, None]:
    """Create an isolated DagsterOrchestratorPlugin instance.

    This fixture ensures each test gets a fresh plugin instance
    with no shared state from previous tests. Any internal caches
    or stored schedules are cleared after the test.

    Yields:
        DagsterOrchestratorPlugin: Fresh plugin instance.
    """
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin

    plugin = DagsterOrchestratorPlugin()

    yield plugin

    # Clean up any stored schedules or internal state
    if hasattr(plugin, "_schedules"):
        plugin._schedules.clear()


@pytest.fixture
def unique_test_namespace(request: pytest.FixtureRequest) -> str:
    """Generate a unique namespace for test isolation.

    Creates a namespace based on the test function name and a unique
    identifier to prevent namespace collisions between tests.

    Args:
        request: pytest request fixture for accessing test metadata.

    Returns:
        str: Unique namespace like 'test_abc123_funcname'.
    """
    import uuid

    test_name = request.node.name[:20]  # Truncate long names
    unique_id = uuid.uuid4().hex[:8]
    return f"test_{unique_id}_{test_name}"
