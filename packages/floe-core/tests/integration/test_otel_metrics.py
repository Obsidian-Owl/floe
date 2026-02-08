"""Integration tests for metric export to OTLP.

Tests cover:
- T050: Integration test for metric export to OTLP

Requirements Covered:
- FR-012: Record pipeline run duration as histogram metric
- FR-013: Record asset materialization counts as counter metric
- FR-014: Record error rates by component as counter metric

These tests use real OpenTelemetry SDK with InMemoryMetricReader to verify
that MetricRecorder correctly records metrics with the expected values,
labels, and aggregation types.

Note: These tests use InMemoryMetricReader to capture metrics for assertion
rather than requiring a real OTLP Collector, testing the metric recording path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from floe_core.telemetry.metrics import MetricRecorder

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry.sdk.metrics.export import MetricsData


def get_metric_by_name(
    metrics_data: MetricsData | None, name: str
) -> dict[str, Any] | None:
    """Extract a metric by name from MetricsData.

    Args:
        metrics_data: The MetricsData from InMemoryMetricReader, or None.
        name: The name of the metric to find.

    Returns:
        Dictionary with metric info if found, None otherwise.
    """
    if metrics_data is None:
        return None

    for resource_metrics in metrics_data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == name:
                    return {
                        "name": metric.name,
                        "description": metric.description,
                        "unit": metric.unit,
                        "data": metric.data,
                    }
    return None


def get_data_point_value(metric_dict: dict[str, Any] | None) -> int | float | None:
    """Extract the value from a metric's data point.

    Args:
        metric_dict: Dictionary from get_metric_by_name, or None.

    Returns:
        The value from the first data point, or None if not found.
    """
    if metric_dict is None:
        return None

    data = metric_dict.get("data")
    if data is None:
        return None

    data_points = getattr(data, "data_points", None)
    if data_points is None or len(data_points) == 0:
        return None

    point = data_points[0]
    # Counter uses 'value', Histogram uses 'sum' or 'count'
    if hasattr(point, "value"):
        return point.value
    if hasattr(point, "sum"):
        return point.sum
    return None


def get_data_point_attributes(
    metric_dict: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Extract attributes from a metric's data point.

    Args:
        metric_dict: Dictionary from get_metric_by_name, or None.

    Returns:
        The attributes dict from the first data point, or None if not found.
    """
    if metric_dict is None:
        return None

    data = metric_dict.get("data")
    if data is None:
        return None

    data_points = getattr(data, "data_points", None)
    if data_points is None or len(data_points) == 0:
        return None

    point = data_points[0]
    return dict(point.attributes) if point.attributes else {}


class TestCounterMetricRecording:
    """Integration tests for counter metric recording.

    These tests verify that MetricRecorder correctly records counter
    metrics using the real OpenTelemetry SDK.

    Requirements: FR-013, FR-014
    """

    @pytest.fixture
    def metric_setup(
        self,
    ) -> Generator[tuple[MetricRecorder, InMemoryMetricReader], None, None]:
        """Set up MetricRecorder with InMemoryMetricReader.

        Yields:
            Tuple of (MetricRecorder, InMemoryMetricReader).
        """
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        # Create a MetricRecorder but patch its meter to use our provider
        recorder = MetricRecorder(name="test.metrics", version="1.0.0")
        recorder._meter = provider.get_meter("test.metrics", "1.0.0")
        recorder._counters = {}  # Clear cached instruments
        recorder._gauges = {}
        recorder._histograms = {}

        yield recorder, reader

        provider.shutdown()

    @pytest.mark.requirement("FR-013")
    def test_increment_records_counter_value(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test increment() records counter value correctly.

        Validates that counter metrics are recorded with the expected value
        and can be retrieved from the metrics reader.
        """
        recorder, reader = metric_setup

        recorder.increment("test_counter", value=5)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "test_counter")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 5

    @pytest.mark.requirement("FR-013")
    def test_increment_default_value_is_one(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test increment() defaults to adding 1."""
        recorder, reader = metric_setup

        recorder.increment("default_counter")

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "default_counter")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 1

    @pytest.mark.requirement("FR-013")
    def test_increment_accumulates_values(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test multiple increments accumulate in the counter."""
        recorder, reader = metric_setup

        recorder.increment("accumulated_counter", value=10)
        recorder.increment("accumulated_counter", value=20)
        recorder.increment("accumulated_counter", value=15)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "accumulated_counter")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 45  # 10 + 20 + 15

    @pytest.mark.requirement("FR-013")
    def test_asset_materialization_counter(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test asset materialization counting per FR-013.

        Validates that asset materializations can be counted with
        appropriate labels for asset name and status.
        """
        recorder, reader = metric_setup

        recorder.increment(
            "floe.asset_materializations",
            labels={
                "asset_name": "customers",
                "status": "success",
            },
        )

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "floe.asset_materializations")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 1

        attrs = get_data_point_attributes(metric)
        assert attrs is not None
        assert attrs.get("asset_name") == "customers"
        assert attrs.get("status") == "success"

    @pytest.mark.requirement("FR-014")
    def test_error_rate_counter(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test error rate counting per FR-014.

        Validates that error rates can be tracked by component
        with appropriate labels.
        """
        recorder, reader = metric_setup

        recorder.increment(
            "floe.errors",
            labels={
                "component": "compiler",
                "error_type": "ValidationError",
            },
        )

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "floe.errors")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 1

        attrs = get_data_point_attributes(metric)
        assert attrs is not None
        assert attrs.get("component") == "compiler"
        assert attrs.get("error_type") == "ValidationError"

    @pytest.mark.requirement("FR-014")
    def test_multiple_error_types_tracked_separately(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test different error types are tracked with their own labels.

        Each unique set of labels creates a separate time series.
        """
        recorder, reader = metric_setup

        recorder.increment(
            "floe.errors",
            value=3,
            labels={"component": "compiler", "error_type": "ValidationError"},
        )
        recorder.increment(
            "floe.errors",
            value=2,
            labels={"component": "compiler", "error_type": "SyntaxError"},
        )
        recorder.increment(
            "floe.errors",
            value=5,
            labels={"component": "executor", "error_type": "RuntimeError"},
        )

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "floe.errors")

        assert metric is not None
        # Should have 3 data points for 3 different label combinations
        data_points = list(metric["data"].data_points)
        assert len(data_points) == 3


class TestGaugeMetricRecording:
    """Integration tests for gauge metric recording.

    These tests verify that MetricRecorder correctly records gauge
    metrics using the real OpenTelemetry SDK.

    Requirements: FR-012
    """

    @pytest.fixture
    def metric_setup(
        self,
    ) -> Generator[tuple[MetricRecorder, InMemoryMetricReader], None, None]:
        """Set up MetricRecorder with InMemoryMetricReader.

        Yields:
            Tuple of (MetricRecorder, InMemoryMetricReader).
        """
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        recorder = MetricRecorder(name="test.metrics", version="1.0.0")
        recorder._meter = provider.get_meter("test.metrics", "1.0.0")
        recorder._counters = {}
        recorder._gauges = {}
        recorder._histograms = {}

        yield recorder, reader

        provider.shutdown()

    @pytest.mark.requirement("FR-012")
    def test_set_gauge_records_value(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test set_gauge() records the current value."""
        recorder, reader = metric_setup

        recorder.set_gauge("queue_size", value=42)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "queue_size")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 42

    @pytest.mark.requirement("FR-012")
    def test_set_gauge_with_float_value(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test set_gauge() handles float values."""
        recorder, reader = metric_setup

        recorder.set_gauge("memory_usage_percent", value=75.5)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "memory_usage_percent")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == pytest.approx(75.5)  # type: ignore[reportUnknownMemberType]

    @pytest.mark.requirement("FR-012")
    def test_set_gauge_with_labels(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test set_gauge() records labels/attributes."""
        recorder, reader = metric_setup

        recorder.set_gauge(
            "active_connections",
            value=100,
            labels={"pool": "primary", "region": "us-east-1"},
        )

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "active_connections")

        assert metric is not None
        attrs = get_data_point_attributes(metric)
        assert attrs is not None
        assert attrs.get("pool") == "primary"
        assert attrs.get("region") == "us-east-1"

    @pytest.mark.requirement("FR-012")
    def test_set_gauge_overwrites_previous_value(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test set_gauge() overwrites the previous value.

        Gauges represent current state, not accumulation.
        """
        recorder, reader = metric_setup

        recorder.set_gauge("current_value", value=10)
        recorder.set_gauge("current_value", value=50)
        recorder.set_gauge("current_value", value=25)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "current_value")

        assert metric is not None
        # Last value should be recorded
        value = get_data_point_value(metric)
        assert value == 25


class TestHistogramMetricRecording:
    """Integration tests for histogram metric recording.

    These tests verify that MetricRecorder correctly records histogram
    metrics for distribution analysis (e.g., latencies, durations).

    Requirements: FR-012
    """

    @pytest.fixture
    def metric_setup(
        self,
    ) -> Generator[tuple[MetricRecorder, InMemoryMetricReader], None, None]:
        """Set up MetricRecorder with InMemoryMetricReader.

        Yields:
            Tuple of (MetricRecorder, InMemoryMetricReader).
        """
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        recorder = MetricRecorder(name="test.metrics", version="1.0.0")
        recorder._meter = provider.get_meter("test.metrics", "1.0.0")
        recorder._counters = {}
        recorder._gauges = {}
        recorder._histograms = {}

        yield recorder, reader

        provider.shutdown()

    @pytest.mark.requirement("FR-012")
    def test_record_histogram_records_value(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test record_histogram() records distribution value."""
        recorder, reader = metric_setup

        recorder.record_histogram("request_duration", value=150)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "request_duration")

        assert metric is not None
        # Histogram sum should equal the recorded value
        data_points = list(metric["data"].data_points)
        assert len(data_points) == 1
        assert data_points[0].sum == 150
        assert data_points[0].count == 1

    @pytest.mark.requirement("FR-012")
    def test_pipeline_duration_histogram(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test pipeline run duration tracking per FR-012.

        Validates that pipeline durations can be recorded as histogram
        with appropriate labels for pipeline identification.
        """
        recorder, reader = metric_setup

        recorder.record_histogram(
            "floe.pipeline_duration",
            value=12500,  # 12.5 seconds in ms
            labels={"pipeline": "customer_360", "status": "success"},
            unit="ms",
        )

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "floe.pipeline_duration")

        assert metric is not None
        assert metric["unit"] == "ms"

        data_points = list(metric["data"].data_points)
        assert len(data_points) == 1
        assert data_points[0].sum == 12500
        assert data_points[0].count == 1

        attrs = dict(data_points[0].attributes)
        assert attrs.get("pipeline") == "customer_360"
        assert attrs.get("status") == "success"

    @pytest.mark.requirement("FR-012")
    def test_histogram_tracks_distribution(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test histogram tracks distribution of multiple values."""
        recorder, reader = metric_setup

        # Record multiple pipeline durations
        recorder.record_histogram("pipeline_duration", value=100)
        recorder.record_histogram("pipeline_duration", value=200)
        recorder.record_histogram("pipeline_duration", value=150)
        recorder.record_histogram("pipeline_duration", value=300)
        recorder.record_histogram("pipeline_duration", value=250)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "pipeline_duration")

        assert metric is not None
        data_points = list(metric["data"].data_points)
        assert len(data_points) == 1

        point = data_points[0]
        assert point.count == 5
        assert point.sum == 1000  # 100 + 200 + 150 + 300 + 250
        assert point.min == 100
        assert point.max == 300

    @pytest.mark.requirement("FR-012")
    def test_histogram_with_float_values(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test histogram handles float values correctly."""
        recorder, reader = metric_setup

        recorder.record_histogram("latency_seconds", value=0.125)
        recorder.record_histogram("latency_seconds", value=0.250)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "latency_seconds")

        assert metric is not None
        data_points = list(metric["data"].data_points)
        assert data_points[0].sum == pytest.approx(0.375)  # type: ignore[reportUnknownMemberType]
        assert data_points[0].count == 2

    @pytest.mark.requirement("FR-012")
    def test_histogram_with_description_and_unit(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test histogram records description and unit."""
        recorder, reader = metric_setup

        recorder.record_histogram(
            "api_response_time",
            value=50,
            description="API response time in milliseconds",
            unit="ms",
        )

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "api_response_time")

        assert metric is not None
        # Unit should be recorded
        assert metric["unit"] == "ms"


class TestMetricLabelsIntegration:
    """Integration tests for metric labels/attributes.

    These tests verify that labels are correctly attached to metrics
    and can be used for filtering and aggregation.

    Requirements: FR-012, FR-013, FR-014
    """

    @pytest.fixture
    def metric_setup(
        self,
    ) -> Generator[tuple[MetricRecorder, InMemoryMetricReader], None, None]:
        """Set up MetricRecorder with InMemoryMetricReader.

        Yields:
            Tuple of (MetricRecorder, InMemoryMetricReader).
        """
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        recorder = MetricRecorder(name="test.metrics", version="1.0.0")
        recorder._meter = provider.get_meter("test.metrics", "1.0.0")
        recorder._counters = {}
        recorder._gauges = {}
        recorder._histograms = {}

        yield recorder, reader

        provider.shutdown()

    @pytest.mark.requirement("FR-012")
    @pytest.mark.requirement("FR-013")
    def test_empty_labels_works(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test metrics work with empty labels dict."""
        recorder, reader = metric_setup

        recorder.increment("no_labels_counter", labels={})

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "no_labels_counter")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 1

    @pytest.mark.requirement("FR-012")
    @pytest.mark.requirement("FR-013")
    def test_none_labels_works(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test metrics work with None labels."""
        recorder, reader = metric_setup

        recorder.increment("none_labels_counter", labels=None)

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "none_labels_counter")

        assert metric is not None
        value = get_data_point_value(metric)
        assert value == 1

    @pytest.mark.requirement("FR-013")
    @pytest.mark.requirement("FR-014")
    def test_labels_create_separate_time_series(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test different labels create separate time series.

        This is essential for per-component error tracking (FR-014)
        and per-asset materialization counting (FR-013).
        """
        recorder, reader = metric_setup

        # Same metric name, different labels = different time series
        recorder.increment("requests", value=10, labels={"method": "GET"})
        recorder.increment("requests", value=5, labels={"method": "POST"})
        recorder.increment("requests", value=2, labels={"method": "DELETE"})

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "requests")

        assert metric is not None
        data_points = list(metric["data"].data_points)
        assert len(data_points) == 3

        # Verify each has different attributes
        methods: list[str] = [
            str(dict(p.attributes).get("method", "")) for p in data_points
        ]
        assert sorted(methods) == ["DELETE", "GET", "POST"]

    @pytest.mark.requirement("FR-012")
    def test_floe_standard_labels(
        self,
        metric_setup: tuple[MetricRecorder, InMemoryMetricReader],
    ) -> None:
        """Test floe standard labels are properly recorded.

        Standard labels include namespace, product, and mode.
        """
        recorder, reader = metric_setup

        recorder.record_histogram(
            "floe.operation_duration",
            value=500,
            labels={
                "floe.namespace": "analytics",
                "floe.product": "customer_360",
                "floe.mode": "prod",
                "operation": "compile",
            },
        )

        metrics_data = reader.get_metrics_data()
        metric = get_metric_by_name(metrics_data, "floe.operation_duration")

        assert metric is not None
        attrs = get_data_point_attributes(metric)
        assert attrs is not None
        assert attrs.get("floe.namespace") == "analytics"
        assert attrs.get("floe.product") == "customer_360"
        assert attrs.get("floe.mode") == "prod"
        assert attrs.get("operation") == "compile"


class TestMetricRecorderInitialization:
    """Integration tests for MetricRecorder initialization.

    These tests verify that MetricRecorder correctly initializes
    with the OpenTelemetry SDK.

    Requirements: FR-012, FR-013, FR-014
    """

    @pytest.mark.requirement("FR-012")
    @pytest.mark.requirement("FR-013")
    @pytest.mark.requirement("FR-014")
    def test_default_meter_name(self) -> None:
        """Test MetricRecorder uses default meter name."""
        recorder = MetricRecorder()

        # The meter should be created with default name
        assert recorder._meter is not None

    @pytest.mark.requirement("FR-012")
    def test_custom_meter_name_and_version(self) -> None:
        """Test MetricRecorder accepts custom name and version."""
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])

        recorder = MetricRecorder(
            name="custom.meter.name",
            version="2.0.0",
        )
        recorder._meter = provider.get_meter("custom.meter.name", "2.0.0")
        recorder._counters = {}

        recorder.increment("test_metric")

        metrics_data = reader.get_metrics_data()
        assert metrics_data is not None

        # Verify scope info contains custom name
        found_scope = False
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                if scope_metrics.scope.name == "custom.meter.name":
                    found_scope = True
                    assert scope_metrics.scope.version == "2.0.0"

        assert found_scope, "Custom meter name not found in scope metrics"

        provider.shutdown()

    @pytest.mark.requirement("FR-012")
    @pytest.mark.requirement("FR-013")
    @pytest.mark.requirement("FR-014")
    def test_recorder_caches_instruments(self) -> None:
        """Test MetricRecorder caches instruments for reuse."""
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])

        recorder = MetricRecorder()
        recorder._meter = provider.get_meter("test.metrics", "1.0.0")
        recorder._counters = {}
        recorder._gauges = {}
        recorder._histograms = {}

        # Create various instruments
        recorder.increment("counter_1")
        recorder.set_gauge("gauge_1", value=10)
        recorder.record_histogram("histogram_1", value=100)

        # Verify instruments are cached
        assert "counter_1" in recorder._counters
        assert "gauge_1" in recorder._gauges
        assert "histogram_1" in recorder._histograms

        # Use them again
        recorder.increment("counter_1")
        recorder.set_gauge("gauge_1", value=20)
        recorder.record_histogram("histogram_1", value=200)

        # Cache should still have same objects
        assert len(recorder._counters) == 1
        assert len(recorder._gauges) == 1
        assert len(recorder._histograms) == 1

        provider.shutdown()
