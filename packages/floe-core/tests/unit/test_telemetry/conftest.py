"""Telemetry unit test fixtures.

Provides fixtures specific to telemetry module unit tests.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.telemetry import ResourceAttributes, SamplingConfig


@pytest.fixture(autouse=True)
def reset_otel_global_state() -> Generator[None, None, None]:
    """Reset OpenTelemetry global state before and after each test.

    This fixture ensures test isolation by resetting the global
    TracerProvider and MeterProvider between tests. Without this,
    tests that call `trace.set_tracer_provider()` will cause
    subsequent tests to fail with "Overriding not allowed" errors.

    Yields:
        None after resetting state.
    """
    from opentelemetry import metrics, trace
    from opentelemetry.trace import ProxyTracerProvider
    from opentelemetry.metrics._internal import _ProxyMeterProvider

    # Reset before test
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = ProxyTracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = _ProxyMeterProvider()

    yield

    # Reset after test
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = ProxyTracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = _ProxyMeterProvider()


@pytest.fixture(autouse=True)
def reset_structlog_after_test() -> Generator[None, None, None]:
    """Reset structlog configuration after each test.

    This ensures tests that call configure_logging() don't pollute
    global structlog state for subsequent tests.

    Yields:
        None after test completes.
    """
    import structlog

    yield

    # Reset structlog to defaults after test
    structlog.reset_defaults()


@pytest.fixture
def valid_resource_attributes() -> dict[str, str]:
    """Return valid ResourceAttributes constructor kwargs.

    Returns:
        Dictionary with all required fields for ResourceAttributes.
    """
    return {
        "service_name": "test-service",
        "service_version": "1.0.0",
        "deployment_environment": "dev",
        "floe_namespace": "analytics",
        "floe_product_name": "customer-360",
        "floe_product_version": "2.1.0",
        "floe_mode": "dev",
    }


@pytest.fixture
def sample_resource_attributes(
    valid_resource_attributes: dict[str, str],
) -> ResourceAttributes:
    """Create a sample ResourceAttributes instance.

    Args:
        valid_resource_attributes: Valid constructor kwargs.

    Returns:
        ResourceAttributes instance for testing.
    """
    from floe_core.telemetry import ResourceAttributes

    return ResourceAttributes(**valid_resource_attributes)  # type: ignore[arg-type]


@pytest.fixture
def default_sampling_config() -> SamplingConfig:
    """Create SamplingConfig with default values.

    Returns:
        SamplingConfig with dev=1.0, staging=0.5, prod=0.1.
    """
    from floe_core.telemetry import SamplingConfig

    return SamplingConfig()
