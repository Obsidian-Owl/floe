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
def reset_otel_global_state(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Reset OpenTelemetry global state before and after each test.

    This fixture ensures test isolation by resetting the global
    TracerProvider and MeterProvider between tests. Without this,
    tests that call `trace.set_tracer_provider()` will cause
    subsequent tests to fail with "Overriding not allowed" errors.

    Only applies to tests in the test_telemetry directory to avoid
    affecting other test suites that may have their own OTel setup.

    Uses NoOp providers after test to avoid recursion issues that can
    occur with ProxyTracerProvider when no real provider is configured.

    Yields:
        None after resetting state.
    """
    # Only apply to tests in the test_telemetry directory
    test_path = str(request.fspath)
    if "test_telemetry" not in test_path:
        yield
        return

    from opentelemetry import metrics, trace
    from opentelemetry.metrics._internal import _ProxyMeterProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import ProxyTracerProvider

    # Reset before test - use Proxy to allow test to set its own provider
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = ProxyTracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = _ProxyMeterProvider()

    yield

    # Reset after test - use SDK providers (not Proxy) to avoid recursion
    # when subsequent tests access tracers/meters without setting a provider
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = TracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = MeterProvider()


@pytest.fixture(autouse=True)
def reset_structlog_after_test(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Reset structlog configuration after each test.

    This ensures tests that call configure_logging() don't pollute
    global structlog state for subsequent tests.

    Only applies to tests in the test_telemetry directory.

    Yields:
        None after test completes.
    """
    # Only apply to tests in the test_telemetry directory
    test_path = str(request.fspath)
    if "test_telemetry" not in test_path:
        yield
        return

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
