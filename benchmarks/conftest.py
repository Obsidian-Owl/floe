"""Benchmark test fixtures.

Provides fixtures for performance benchmarking with CodSpeed.
Ensures OpenTelemetry global state is properly reset between tests.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

if TYPE_CHECKING:
    from floe_core.telemetry import TelemetryConfig


@pytest.fixture(autouse=True)
def reset_otel_global_state() -> Generator[None, None, None]:
    """Reset OpenTelemetry global state before and after each test.

    This fixture ensures benchmark isolation by resetting the global
    TracerProvider and MeterProvider between tests, and sets up a
    working tracer for tracing benchmarks.

    Yields:
        None after resetting state.
    """
    from opentelemetry import metrics, trace
    from opentelemetry.metrics._internal import _ProxyMeterProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.trace import ProxyTracerProvider

    from floe_core.telemetry.tracing import set_tracer

    # Reset OTel global state
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = ProxyTracerProvider()
    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = _ProxyMeterProvider()

    # Set up a real TracerProvider for tracing benchmarks
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Inject tracer into the tracing module so @traced and create_span work
    test_tracer = provider.get_tracer("benchmark")
    set_tracer(test_tracer)

    # Set up a real MeterProvider so metrics work
    trace.set_tracer_provider(provider)
    meter_provider = MeterProvider()
    metrics.set_meter_provider(meter_provider)

    yield

    # Reset tracer
    set_tracer(None)

    # Reset OTel global state
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = ProxyTracerProvider()
    metrics._internal._METER_PROVIDER_SET_ONCE._done = False
    metrics._internal._METER_PROVIDER = _ProxyMeterProvider()


@pytest.fixture
def benchmark_resource_attributes() -> dict[str, str]:
    """Return valid ResourceAttributes constructor kwargs for benchmarks.

    Returns:
        Dictionary with all required fields for ResourceAttributes.
    """
    return {
        "service_name": "benchmark-service",
        "service_version": "1.0.0",
        "deployment_environment": "dev",
        "floe_namespace": "benchmark",
        "floe_product_name": "perf-test",
        "floe_product_version": "1.0.0",
        "floe_mode": "dev",
    }


class MockTelemetryBackendPlugin:
    """Mock telemetry backend plugin for benchmarks."""

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "console"

    def create_span_exporter(self, config: TelemetryConfig) -> InMemorySpanExporter:
        """Create a span exporter."""
        return InMemorySpanExporter()

    def create_metric_exporter(self, config: TelemetryConfig) -> None:
        """Create a metric exporter (not needed for benchmarks)."""
        return None


@pytest.fixture
def mock_backend_plugin() -> Generator[None, None, None]:
    """Mock the telemetry backend plugin for provider benchmarks.

    Patches load_telemetry_backend to return a mock plugin.
    """
    with patch(
        "floe_core.telemetry.provider.load_telemetry_backend",
        return_value=MockTelemetryBackendPlugin(),
    ):
        yield


@pytest.fixture
def benchmark_telemetry_config(
    benchmark_resource_attributes: dict[str, str],
) -> TelemetryConfig:
    """Create a TelemetryConfig for benchmark tests.

    Args:
        benchmark_resource_attributes: Valid resource attributes.

    Returns:
        TelemetryConfig instance for benchmarking.
    """
    from floe_core.telemetry import ResourceAttributes, TelemetryConfig

    return TelemetryConfig(
        enabled=True,
        otlp_endpoint="http://localhost:4317",
        resource_attributes=ResourceAttributes(**benchmark_resource_attributes),  # type: ignore[arg-type]
    )
