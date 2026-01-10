"""Contract test configuration.

Contract tests validate cross-package interfaces and API stability.
They ensure that changes to one package don't break consumers.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def reset_otel_global_state() -> Generator[None, None, None]:
    """Reset OpenTelemetry global state before and after each test.

    This fixture ensures test isolation by resetting the global
    TracerProvider and MeterProvider between tests. Required for
    compute plugin tests that use observability instrumentation.

    Uses NoOpTracerProvider/NoOpMeterProvider to avoid recursion issues
    that can occur with ProxyTracerProvider when no real provider is set.

    Yields:
        None after resetting state.
    """
    # Reset observability module singletons FIRST
    from floe_core.observability import reset_for_testing
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider

    reset_for_testing()

    # Set up real (but minimal) providers to avoid ProxyTracerProvider recursion
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = TracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = MeterProvider()

    yield

    # Reset after test
    reset_for_testing()

    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = TracerProvider()

    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = MeterProvider()
