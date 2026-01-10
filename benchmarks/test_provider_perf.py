"""Provider initialization performance benchmarks.

Measures overhead of TelemetryProvider lifecycle:
- Provider initialization
- Provider shutdown
- Full initialize/shutdown cycle

These benchmarks track provider startup cost for application boot time.
"""

from __future__ import annotations

import pytest
from floe_core.telemetry import ResourceAttributes, TelemetryConfig, TelemetryProvider


@pytest.mark.benchmark
@pytest.mark.usefixtures("mock_backend_plugin")
def test_provider_initialization(
    benchmark_telemetry_config: TelemetryConfig,
) -> None:
    """Benchmark TelemetryProvider initialization overhead.

    Measures the time to initialize the telemetry provider,
    which occurs once at application startup.
    """
    for _ in range(10):
        provider = TelemetryProvider(benchmark_telemetry_config)
        provider.initialize()
        provider.shutdown()


@pytest.mark.benchmark
@pytest.mark.usefixtures("mock_backend_plugin")
def test_provider_shutdown(
    benchmark_telemetry_config: TelemetryConfig,
) -> None:
    """Benchmark TelemetryProvider shutdown overhead.

    Measures the time to cleanly shutdown the provider,
    which occurs once at application exit.
    """
    for _ in range(10):
        provider = TelemetryProvider(benchmark_telemetry_config)
        provider.initialize()
        provider.shutdown()


@pytest.mark.benchmark
@pytest.mark.usefixtures("mock_backend_plugin")
def test_provider_context_manager(
    benchmark_telemetry_config: TelemetryConfig,
) -> None:
    """Benchmark provider context manager overhead.

    Measures combined init/shutdown using context manager pattern.
    """
    for _ in range(10):
        with TelemetryProvider(benchmark_telemetry_config):
            pass  # Provider active


@pytest.mark.benchmark
def test_provider_noop_mode() -> None:
    """Benchmark provider in no-op mode.

    Measures overhead when telemetry is disabled.
    """
    import os

    original = os.environ.get("OTEL_SDK_DISABLED")
    os.environ["OTEL_SDK_DISABLED"] = "true"

    try:
        config = TelemetryConfig(
            enabled=False,
            resource_attributes=ResourceAttributes(
                service_name="noop-service",
                service_version="1.0.0",
                deployment_environment="dev",
                floe_namespace="benchmark",
                floe_product_name="perf-test",
                floe_product_version="1.0.0",
                floe_mode="dev",
            ),
        )
        for _ in range(10):
            with TelemetryProvider(config):
                pass
    finally:
        if original is not None:
            os.environ["OTEL_SDK_DISABLED"] = original
        else:
            os.environ.pop("OTEL_SDK_DISABLED", None)


@pytest.mark.benchmark
def test_config_creation_overhead() -> None:
    """Benchmark TelemetryConfig creation overhead.

    Measures Pydantic model validation cost for configuration.
    """
    for _ in range(100):
        _ = TelemetryConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317",
            resource_attributes=ResourceAttributes(
                service_name="benchmark-service",
                service_version="1.0.0",
                deployment_environment="dev",
                floe_namespace="benchmark",
                floe_product_name="perf-test",
                floe_product_version="1.0.0",
                floe_mode="dev",
            ),
        )


@pytest.mark.benchmark
def test_resource_attributes_creation() -> None:
    """Benchmark ResourceAttributes creation overhead.

    Measures Pydantic model validation for resource attributes.
    """
    for _ in range(100):
        _ = ResourceAttributes(
            service_name="benchmark-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="benchmark",
            floe_product_name="perf-test",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
