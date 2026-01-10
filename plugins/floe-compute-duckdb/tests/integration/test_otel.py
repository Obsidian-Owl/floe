"""Integration tests for OTel metrics emission.

Tests for FR-024 (OTel metrics emission) with real DuckDB and real OTel SDK.

These tests verify that the OTel instrumentation in DuckDBComputePlugin
emits actual metrics when validate_connection is called. Uses in-memory
exporters to capture real OTel emissions - NO MOCKING.

Note: These tests require the OTel SDK and real DuckDB. They run in K8s
for production parity.
"""

from __future__ import annotations

import pytest
from floe_core import ComputeConfig, ConnectionStatus
from floe_core.observability import reset_for_testing
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Module-scoped OTel setup - providers can only be set once
_metric_reader: InMemoryMetricReader | None = None
_span_exporter: InMemorySpanExporter | None = None
_otel_initialized = False


def _setup_otel_once() -> tuple[InMemoryMetricReader, InMemorySpanExporter]:
    """Set up OTel providers once per test session.

    OTel providers can only be set once globally. This function ensures
    we set them up exactly once and reuse across tests.
    """
    global _metric_reader, _span_exporter, _otel_initialized

    if not _otel_initialized:
        # Reset any cached singletons from observability module
        reset_for_testing()

        # Set up tracing with in-memory exporter
        _span_exporter = InMemorySpanExporter()
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
        trace.set_tracer_provider(tracer_provider)

        # Set up metrics with in-memory reader
        _metric_reader = InMemoryMetricReader()
        meter_provider = MeterProvider(metric_readers=[_metric_reader])
        metrics.set_meter_provider(meter_provider)

        _otel_initialized = True

    return _metric_reader, _span_exporter  # type: ignore[return-value]


@pytest.fixture(scope="module")
def otel_exporters() -> tuple[InMemoryMetricReader, InMemorySpanExporter]:
    """Module-scoped OTel exporters for capturing real emissions."""
    return _setup_otel_once()


@pytest.fixture
def clear_otel_data(
    otel_exporters: tuple[InMemoryMetricReader, InMemorySpanExporter],
) -> tuple[InMemoryMetricReader, InMemorySpanExporter]:
    """Clear OTel data before each test while reusing providers."""
    metric_reader, span_exporter = otel_exporters
    span_exporter.clear()
    # Note: metric_reader doesn't have clear(), but get_metrics_data() consumes
    return metric_reader, span_exporter


@pytest.fixture
def duckdb_plugin():  # noqa: ANN201
    """Create a DuckDBComputePlugin instance for testing."""
    from floe_compute_duckdb import DuckDBComputePlugin

    # Reset observability singletons so they pick up our test providers
    reset_for_testing()
    return DuckDBComputePlugin()


@pytest.fixture
def memory_config() -> ComputeConfig:
    """Create an in-memory DuckDB ComputeConfig for testing."""
    return ComputeConfig(
        plugin="duckdb",
        threads=4,
        connection={"path": ":memory:"},
    )


class TestOTelMetricsIntegration:
    """Integration tests for OTel metrics emission (FR-024).

    These tests use real OTel SDK with in-memory exporters - no mocking.
    They verify actual metrics are emitted during real DuckDB validation.
    """

    @pytest.mark.requirement("001-FR-024")
    def test_validation_duration_histogram_emitted(
        self,
        clear_otel_data: tuple[InMemoryMetricReader, InMemorySpanExporter],
        duckdb_plugin,  # noqa: ANN001
        memory_config: ComputeConfig,
    ) -> None:
        """Test that validation_duration histogram is actually emitted."""
        metric_reader, _ = clear_otel_data

        # Run real validation with real DuckDB
        result = duckdb_plugin.validate_connection(memory_config)

        # Verify the result is healthy (real connection succeeded)
        assert result.status == ConnectionStatus.HEALTHY
        assert result.latency_ms > 0

        # Get actual metrics data from OTel SDK
        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None, "No metrics data collected"

        # Find the validation_duration histogram
        histogram_found = False
        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    if metric.name == "floe.compute.validation_duration":
                        histogram_found = True
                        # Verify histogram has data points
                        assert len(metric.data.data_points) > 0
                        # Verify attributes
                        data_point = metric.data.data_points[0]
                        attributes = dict(data_point.attributes)
                        assert attributes.get("compute.plugin") == "duckdb"
                        assert attributes.get("validation.status") == "healthy"
                        # Verify duration was recorded (sum > 0)
                        assert data_point.sum > 0

        assert histogram_found, "validation_duration histogram was not emitted"

    @pytest.mark.requirement("001-FR-024")
    def test_validation_span_emitted(
        self,
        clear_otel_data: tuple[InMemoryMetricReader, InMemorySpanExporter],
        duckdb_plugin,  # noqa: ANN001
        memory_config: ComputeConfig,
    ) -> None:
        """Test that OTel span is actually created during validation."""
        _, span_exporter = clear_otel_data

        # Run real validation with real DuckDB
        result = duckdb_plugin.validate_connection(memory_config)

        # Verify the result is healthy
        assert result.status == ConnectionStatus.HEALTHY

        # Get actual spans from OTel SDK
        spans = span_exporter.get_finished_spans()

        # Find the validation span
        validation_spans = [s for s in spans if s.name == "compute.validate_connection"]
        assert len(validation_spans) >= 1, "No validation span was created"

        # Verify span attributes
        span = validation_spans[-1]
        attributes = dict(span.attributes)
        assert attributes.get("compute.plugin") == "duckdb"
        assert attributes.get("db.path") == ":memory:"
        assert attributes.get("validation.status") == "healthy"

    @pytest.mark.requirement("001-FR-024")
    def test_latency_recorded_is_positive(
        self,
        clear_otel_data: tuple[InMemoryMetricReader, InMemorySpanExporter],
        duckdb_plugin,  # noqa: ANN001
        memory_config: ComputeConfig,
    ) -> None:
        """Test that latency recorded in histogram is positive."""
        metric_reader, _ = clear_otel_data

        # Run real validation
        result = duckdb_plugin.validate_connection(memory_config)
        assert result.latency_ms > 0

        # Get metrics
        metrics_data = metric_reader.get_metrics_data()

        # Find histogram and verify data was recorded
        histogram_found = False
        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    if metric.name == "floe.compute.validation_duration":
                        histogram_found = True
                        data_point = metric.data.data_points[0]
                        # Verify count incremented (at least 1 recording)
                        assert data_point.count >= 1, "Histogram should have recordings"
                        # Verify sum is positive (duration was recorded)
                        assert data_point.sum > 0, "Histogram sum should be positive"

        assert histogram_found, "validation_duration histogram was not found"

    @pytest.mark.requirement("001-FR-024")
    def test_no_error_counter_on_success(
        self,
        clear_otel_data: tuple[InMemoryMetricReader, InMemorySpanExporter],
        duckdb_plugin,  # noqa: ANN001
        memory_config: ComputeConfig,
    ) -> None:
        """Test that validation_errors counter is NOT emitted on success."""
        metric_reader, _ = clear_otel_data

        # Run successful validation
        result = duckdb_plugin.validate_connection(memory_config)
        assert result.status == ConnectionStatus.HEALTHY

        # Get metrics
        metrics_data = metric_reader.get_metrics_data()

        # Check that no error counter was incremented
        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    if metric.name == "floe.compute.validation_errors":
                        # If counter exists, verify no data points for duckdb
                        for data_point in metric.data.data_points:
                            attributes = dict(data_point.attributes)
                            if attributes.get("compute.plugin") == "duckdb":
                                pytest.fail(
                                    "validation_errors counter should not be "
                                    "emitted on successful validation"
                                )
