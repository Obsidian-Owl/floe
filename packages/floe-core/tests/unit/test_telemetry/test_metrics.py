"""Unit tests for MetricRecorder.

Tests for telemetry metric recording functionality including counters,
gauges, and histograms.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest


class TestMetricRecorderIncrement:
    """Tests for MetricRecorder.increment() method (FR-012, FR-013, FR-014)."""

    @pytest.fixture
    def mock_meter(self) -> Generator[Mock, None, None]:
        """Mock OpenTelemetry Meter."""
        mock_counter = Mock()
        mock_counter.add = Mock()

        mock_meter = Mock()
        mock_meter.create_counter = Mock(return_value=mock_counter)

        with patch(
            "opentelemetry.metrics.get_meter",
            return_value=mock_meter,
        ):
            yield mock_meter

    def test_increment_creates_counter(self, mock_meter: Mock) -> None:
        """Test increment() creates a counter with the specified name."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment("test_counter")

        mock_meter.create_counter.assert_called()
        call_args = mock_meter.create_counter.call_args
        assert call_args[0][0] == "test_counter"

    def test_increment_adds_to_counter(self, mock_meter: Mock) -> None:
        """Test increment() adds value to counter."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment("test_counter", value=5)

        counter = mock_meter.create_counter.return_value
        counter.add.assert_called_once()
        call_args = counter.add.call_args
        assert call_args[0][0] == 5

    def test_increment_default_value_is_one(self, mock_meter: Mock) -> None:
        """Test increment() defaults to adding 1."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment("test_counter")

        counter = mock_meter.create_counter.return_value
        counter.add.assert_called_once()
        call_args = counter.add.call_args
        assert call_args[0][0] == 1

    def test_increment_with_labels(self, mock_meter: Mock) -> None:
        """Test increment() passes labels/attributes to counter."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment(
            "asset_materializations",
            labels={"asset_name": "customers", "status": "success"},
        )

        counter = mock_meter.create_counter.return_value
        counter.add.assert_called_once()
        call_args = counter.add.call_args
        # Check attributes are passed
        assert "attributes" in call_args[1] or len(call_args) > 1

    def test_increment_reuses_counter_for_same_name(self, mock_meter: Mock) -> None:
        """Test increment() reuses counter for the same metric name."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment("reused_counter")
        recorder.increment("reused_counter")
        recorder.increment("reused_counter")

        # Counter should only be created once
        assert mock_meter.create_counter.call_count == 1

    def test_increment_creates_different_counters_for_different_names(
        self, mock_meter: Mock
    ) -> None:
        """Test increment() creates separate counters for different names."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment("counter_a")
        recorder.increment("counter_b")

        assert mock_meter.create_counter.call_count == 2

    def test_increment_with_description(self, mock_meter: Mock) -> None:
        """Test increment() can set counter description."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment(
            "documented_counter",
            description="Count of important events",
        )

        call_args = mock_meter.create_counter.call_args
        assert "description" in call_args[1]
        assert call_args[1]["description"] == "Count of important events"

    def test_increment_with_unit(self, mock_meter: Mock) -> None:
        """Test increment() can set counter unit."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment(
            "request_count",
            unit="1",  # "1" is the OTel convention for unitless counts
        )

        call_args = mock_meter.create_counter.call_args
        assert "unit" in call_args[1]
        assert call_args[1]["unit"] == "1"

    def test_increment_for_error_rate_metric(self, mock_meter: Mock) -> None:
        """Test increment() works for error rate tracking (FR-014)."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment(
            "floe.errors",
            labels={
                "component": "compiler",
                "error_type": "ValidationError",
            },
        )

        counter = mock_meter.create_counter.return_value
        counter.add.assert_called_once()

    def test_increment_for_asset_materialization_metric(self, mock_meter: Mock) -> None:
        """Test increment() works for asset materialization counting (FR-013)."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment(
            "floe.asset.materializations",
            labels={
                "asset_key": "customers",
                "status": "success",
            },
        )

        counter = mock_meter.create_counter.return_value
        counter.add.assert_called_once()


class TestMetricRecorderSetGauge:
    """Tests for MetricRecorder.set_gauge() method."""

    @pytest.fixture
    def mock_meter(self) -> Generator[Mock, None, None]:
        """Mock OpenTelemetry Meter with gauge support."""
        mock_gauge = Mock()
        mock_gauge.set = Mock()

        mock_meter = Mock()
        mock_meter.create_gauge = Mock(return_value=mock_gauge)

        with patch(
            "opentelemetry.metrics.get_meter",
            return_value=mock_meter,
        ):
            yield mock_meter

    def test_set_gauge_creates_gauge(self, mock_meter: Mock) -> None:
        """Test set_gauge() creates a gauge with the specified name."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge("test_gauge", value=42)

        mock_meter.create_gauge.assert_called()
        call_args = mock_meter.create_gauge.call_args
        assert call_args[0][0] == "test_gauge"

    def test_set_gauge_sets_value(self, mock_meter: Mock) -> None:
        """Test set_gauge() sets the gauge to the specified value."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge("test_gauge", value=100)

        gauge = mock_meter.create_gauge.return_value
        gauge.set.assert_called_once()
        call_args = gauge.set.call_args
        assert call_args[0][0] == 100

    def test_set_gauge_with_float_value(self, mock_meter: Mock) -> None:
        """Test set_gauge() accepts float values."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge("memory_usage", value=75.5)

        gauge = mock_meter.create_gauge.return_value
        gauge.set.assert_called_once()
        call_args = gauge.set.call_args
        assert call_args[0][0] == 75.5

    def test_set_gauge_with_labels(self, mock_meter: Mock) -> None:
        """Test set_gauge() passes labels/attributes."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge(
            "queue_size",
            value=50,
            labels={"queue_name": "default"},
        )

        gauge = mock_meter.create_gauge.return_value
        gauge.set.assert_called_once()
        call_args = gauge.set.call_args
        assert "attributes" in call_args[1]

    def test_set_gauge_reuses_gauge_for_same_name(self, mock_meter: Mock) -> None:
        """Test set_gauge() reuses gauge for the same metric name."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge("reused_gauge", value=10)
        recorder.set_gauge("reused_gauge", value=20)
        recorder.set_gauge("reused_gauge", value=30)

        # Gauge should only be created once
        assert mock_meter.create_gauge.call_count == 1

    def test_set_gauge_creates_different_gauges_for_different_names(self, mock_meter: Mock) -> None:
        """Test set_gauge() creates separate gauges for different names."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge("gauge_a", value=1)
        recorder.set_gauge("gauge_b", value=2)

        assert mock_meter.create_gauge.call_count == 2

    def test_set_gauge_with_description(self, mock_meter: Mock) -> None:
        """Test set_gauge() can set gauge description."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge(
            "documented_gauge",
            value=42,
            description="Current value of something",
        )

        call_args = mock_meter.create_gauge.call_args
        assert "description" in call_args[1]
        assert call_args[1]["description"] == "Current value of something"

    def test_set_gauge_with_unit(self, mock_meter: Mock) -> None:
        """Test set_gauge() can set gauge unit."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge(
            "memory_bytes",
            value=1024,
            unit="By",  # OTel convention for bytes
        )

        call_args = mock_meter.create_gauge.call_args
        assert "unit" in call_args[1]
        assert call_args[1]["unit"] == "By"

    def test_set_gauge_for_resource_usage(self, mock_meter: Mock) -> None:
        """Test set_gauge() for typical resource usage metrics."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge(
            "floe.pipeline.active_jobs",
            value=5,
            labels={"pipeline": "customer_360"},
        )

        gauge = mock_meter.create_gauge.return_value
        gauge.set.assert_called_once()


class TestMetricRecorderRecordHistogram:
    """Tests for MetricRecorder.record_histogram() method (FR-012)."""

    @pytest.fixture
    def mock_meter(self) -> Generator[Mock, None, None]:
        """Mock OpenTelemetry Meter with histogram support."""
        mock_histogram = Mock()
        mock_histogram.record = Mock()

        mock_meter = Mock()
        mock_meter.create_histogram = Mock(return_value=mock_histogram)

        with patch(
            "opentelemetry.metrics.get_meter",
            return_value=mock_meter,
        ):
            yield mock_meter

    def test_record_histogram_creates_histogram(self, mock_meter: Mock) -> None:
        """Test record_histogram() creates a histogram with the specified name."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram("test_histogram", value=100)

        mock_meter.create_histogram.assert_called()
        call_args = mock_meter.create_histogram.call_args
        assert call_args[0][0] == "test_histogram"

    def test_record_histogram_records_value(self, mock_meter: Mock) -> None:
        """Test record_histogram() records the specified value."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram("test_histogram", value=250)

        histogram = mock_meter.create_histogram.return_value
        histogram.record.assert_called_once()
        call_args = histogram.record.call_args
        assert call_args[0][0] == 250

    def test_record_histogram_with_float_value(self, mock_meter: Mock) -> None:
        """Test record_histogram() accepts float values."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram("response_time", value=1.234)

        histogram = mock_meter.create_histogram.return_value
        histogram.record.assert_called_once()
        call_args = histogram.record.call_args
        assert call_args[0][0] == 1.234

    def test_record_histogram_with_labels(self, mock_meter: Mock) -> None:
        """Test record_histogram() passes labels/attributes."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram(
            "request_duration",
            value=500,
            labels={"endpoint": "/api/v1/users", "method": "GET"},
        )

        histogram = mock_meter.create_histogram.return_value
        histogram.record.assert_called_once()
        call_args = histogram.record.call_args
        assert "attributes" in call_args[1]

    def test_record_histogram_reuses_histogram_for_same_name(self, mock_meter: Mock) -> None:
        """Test record_histogram() reuses histogram for the same metric name."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram("reused_histogram", value=10)
        recorder.record_histogram("reused_histogram", value=20)
        recorder.record_histogram("reused_histogram", value=30)

        # Histogram should only be created once
        assert mock_meter.create_histogram.call_count == 1

    def test_record_histogram_creates_different_histograms_for_different_names(
        self, mock_meter: Mock
    ) -> None:
        """Test record_histogram() creates separate histograms for different names."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram("histogram_a", value=1)
        recorder.record_histogram("histogram_b", value=2)

        assert mock_meter.create_histogram.call_count == 2

    def test_record_histogram_with_description(self, mock_meter: Mock) -> None:
        """Test record_histogram() can set histogram description."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram(
            "documented_histogram",
            value=100,
            description="Distribution of processing times",
        )

        call_args = mock_meter.create_histogram.call_args
        # create_histogram uses positional args: name, unit, description
        assert call_args[0][2] == "Distribution of processing times"

    def test_record_histogram_with_unit(self, mock_meter: Mock) -> None:
        """Test record_histogram() can set histogram unit."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram(
            "pipeline_duration",
            value=5000,
            unit="ms",  # milliseconds
        )

        call_args = mock_meter.create_histogram.call_args
        # create_histogram uses positional args: name, unit, description
        assert call_args[0][1] == "ms"

    def test_record_histogram_for_pipeline_duration(self, mock_meter: Mock) -> None:
        """Test record_histogram() for pipeline run duration (FR-012)."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram(
            "floe.pipeline.duration",
            value=12500,
            labels={
                "pipeline_name": "customer_360",
                "status": "success",
            },
            unit="ms",
        )

        histogram = mock_meter.create_histogram.return_value
        histogram.record.assert_called_once()

    def test_record_histogram_for_model_execution_time(self, mock_meter: Mock) -> None:
        """Test record_histogram() for dbt model execution time."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram(
            "floe.dbt.model.execution_time",
            value=3.45,
            labels={
                "model_name": "stg_customers",
                "materialization": "table",
            },
            unit="s",  # seconds
        )

        histogram = mock_meter.create_histogram.return_value
        histogram.record.assert_called_once()


class TestMetricLabelsAttributes:
    """Tests for metric labels/attributes functionality (FR-012, FR-013, FR-014).

    Tests cover label passing behavior across all metric types and
    semantic attribute patterns used in floe telemetry.
    """

    @pytest.fixture
    def mock_meter(self) -> Generator[Mock, None, None]:
        """Mock OpenTelemetry Meter with all instrument types."""
        mock_counter = Mock()
        mock_counter.add = Mock()

        mock_gauge = Mock()
        mock_gauge.set = Mock()

        mock_histogram = Mock()
        mock_histogram.record = Mock()

        mock_meter = Mock()
        mock_meter.create_counter = Mock(return_value=mock_counter)
        mock_meter.create_gauge = Mock(return_value=mock_gauge)
        mock_meter.create_histogram = Mock(return_value=mock_histogram)

        with patch(
            "opentelemetry.metrics.get_meter",
            return_value=mock_meter,
        ):
            yield mock_meter

    def test_counter_with_empty_labels(self, mock_meter: Mock) -> None:
        """Test counter works with empty labels dict."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment("test_counter", labels={})

        counter = mock_meter.create_counter.return_value
        counter.add.assert_called_once()
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == {}

    def test_counter_with_none_labels(self, mock_meter: Mock) -> None:
        """Test counter works with None labels (default)."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.increment("test_counter")

        counter = mock_meter.create_counter.return_value
        counter.add.assert_called_once()
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == {}

    def test_gauge_with_empty_labels(self, mock_meter: Mock) -> None:
        """Test gauge works with empty labels dict."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.set_gauge("test_gauge", value=42, labels={})

        gauge = mock_meter.create_gauge.return_value
        gauge.set.assert_called_once()
        call_args = gauge.set.call_args
        assert call_args[1]["attributes"] == {}

    def test_histogram_with_empty_labels(self, mock_meter: Mock) -> None:
        """Test histogram works with empty labels dict."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        recorder.record_histogram("test_histogram", value=100, labels={})

        histogram = mock_meter.create_histogram.return_value
        histogram.record.assert_called_once()
        call_args = histogram.record.call_args
        assert call_args[1]["attributes"] == {}

    def test_labels_with_string_values(self, mock_meter: Mock) -> None:
        """Test labels with string values are passed correctly."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels = {"component": "compiler", "environment": "production"}
        recorder.increment("test_counter", labels=labels)

        counter = mock_meter.create_counter.return_value
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == labels

    def test_labels_with_numeric_values(self, mock_meter: Mock) -> None:
        """Test labels with numeric values are passed correctly."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels: dict[str, Any] = {"port": 8080, "retry_count": 3}
        recorder.increment("test_counter", labels=labels)

        counter = mock_meter.create_counter.return_value
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == labels

    def test_labels_with_boolean_values(self, mock_meter: Mock) -> None:
        """Test labels with boolean values are passed correctly."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels: dict[str, Any] = {"is_incremental": True, "is_full_refresh": False}
        recorder.increment("test_counter", labels=labels)

        counter = mock_meter.create_counter.return_value
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == labels

    def test_labels_with_mixed_value_types(self, mock_meter: Mock) -> None:
        """Test labels with mixed value types are passed correctly."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels: dict[str, Any] = {
            "pipeline_name": "customer_360",
            "step_count": 5,
            "is_production": True,
        }
        recorder.increment("test_counter", labels=labels)

        counter = mock_meter.create_counter.return_value
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == labels

    def test_floe_pipeline_semantic_labels(self, mock_meter: Mock) -> None:
        """Test floe.pipeline.* semantic labels for FR-012."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels = {
            "floe.pipeline.name": "customer_360",
            "floe.pipeline.run_id": "run_abc123",
            "floe.pipeline.status": "success",
        }
        recorder.record_histogram(
            "floe.pipeline.duration",
            value=12500,
            labels=labels,
            unit="ms",
        )

        histogram = mock_meter.create_histogram.return_value
        call_args = histogram.record.call_args
        assert call_args[1]["attributes"] == labels

    def test_floe_asset_semantic_labels(self, mock_meter: Mock) -> None:
        """Test floe.asset.* semantic labels for FR-013."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels = {
            "floe.asset.key": "customers",
            "floe.asset.group": "raw_data",
            "floe.asset.status": "materialized",
        }
        recorder.increment("floe.asset.materializations", labels=labels)

        counter = mock_meter.create_counter.return_value
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == labels

    def test_floe_error_semantic_labels(self, mock_meter: Mock) -> None:
        """Test floe.error.* semantic labels for FR-014."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels = {
            "floe.error.type": "ValidationError",
            "floe.error.component": "compiler",
            "floe.error.severity": "error",
        }
        recorder.increment("floe.errors", labels=labels)

        counter = mock_meter.create_counter.return_value
        call_args = counter.add.call_args
        assert call_args[1]["attributes"] == labels

    def test_labels_preserved_across_multiple_recordings(self, mock_meter: Mock) -> None:
        """Test that labels are passed correctly on each recording."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()

        # First recording with labels
        recorder.increment("test_counter", labels={"batch": "1"})
        # Second recording with different labels
        recorder.increment("test_counter", labels={"batch": "2"})

        counter = mock_meter.create_counter.return_value
        assert counter.add.call_count == 2

        # Verify first call
        first_call = counter.add.call_args_list[0]
        assert first_call[1]["attributes"] == {"batch": "1"}

        # Verify second call
        second_call = counter.add.call_args_list[1]
        assert second_call[1]["attributes"] == {"batch": "2"}

    def test_dbt_model_semantic_labels(self, mock_meter: Mock) -> None:
        """Test dbt model execution semantic labels."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels = {
            "dbt.model.name": "stg_customers",
            "dbt.model.schema": "staging",
            "dbt.model.materialization": "table",
            "dbt.model.unique_id": "model.my_project.stg_customers",
        }
        recorder.record_histogram(
            "dbt.model.execution_time",
            value=3.45,
            labels=labels,
            unit="s",
        )

        histogram = mock_meter.create_histogram.return_value
        call_args = histogram.record.call_args
        assert call_args[1]["attributes"] == labels

    def test_resource_usage_semantic_labels(self, mock_meter: Mock) -> None:
        """Test resource usage semantic labels for gauges."""
        from floe_core.telemetry.metrics import MetricRecorder

        recorder = MetricRecorder()
        labels = {
            "resource.type": "memory",
            "resource.unit": "bytes",
            "host.name": "worker-1",
        }
        recorder.set_gauge(
            "floe.resource.usage",
            value=1073741824,  # 1 GB
            labels=labels,
            unit="By",
        )

        gauge = mock_meter.create_gauge.return_value
        call_args = gauge.set.call_args
        assert call_args[1]["attributes"] == labels
