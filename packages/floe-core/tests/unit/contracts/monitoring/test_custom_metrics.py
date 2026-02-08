"""Unit tests for custom metric definitions.

Tasks: T078 (Epic 3D)
Requirements: 3D-FR-046
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from floe_core.contracts.monitoring.custom_metrics import (
    CustomMetricDefinition,
    MetricRecorder,
)


# --- CustomMetricDefinition Tests ---


@pytest.mark.requirement("3D-FR-046")
def test_custom_metric_definition_model() -> None:
    """Test CustomMetricDefinition model with all fields."""
    metric = CustomMetricDefinition(
        name="ingestion_rate",
        description="Number of records ingested per second",
        unit="records/sec",
        labels=["pipeline_name", "environment"],
    )

    assert metric.name == "ingestion_rate"
    assert metric.description == "Number of records ingested per second"
    assert metric.unit == "records/sec"
    assert metric.labels == ["pipeline_name", "environment"]


@pytest.mark.requirement("3D-FR-046")
def test_custom_metric_definition_defaults() -> None:
    """Test CustomMetricDefinition default values."""
    metric = CustomMetricDefinition(
        name="error_count",
        description="Total number of errors",
        unit="count",
    )

    assert metric.name == "error_count"
    assert metric.description == "Total number of errors"
    assert metric.unit == "count"
    assert metric.labels == []


@pytest.mark.requirement("3D-FR-046")
def test_custom_metric_definition_frozen() -> None:
    """Test CustomMetricDefinition is frozen (immutable)."""
    metric = CustomMetricDefinition(
        name="test_metric",
        description="Test metric",
        unit="count",
    )

    with pytest.raises(Exception, match="frozen"):
        metric.name = "new_name"


# --- MetricRecorder Tests ---


@pytest.mark.requirement("3D-FR-046")
def test_register_custom_metric() -> None:
    """Test registering a custom metric with MetricRecorder."""
    recorder = MetricRecorder()

    metric_def = CustomMetricDefinition(
        name="rows_processed",
        description="Total rows processed",
        unit="count",
    )

    recorder.register(metric_def)

    # Verify metric is registered
    registered = recorder.get_registered()
    assert len(registered) == 1
    assert registered[0].name == "rows_processed"
    assert registered[0].description == "Total rows processed"


@pytest.mark.requirement("3D-FR-046")
def test_emit_custom_metric() -> None:
    """Test emitting a value for a custom metric."""
    recorder = MetricRecorder()

    metric_def = CustomMetricDefinition(
        name="processing_time",
        description="Time to process batch",
        unit="seconds",
    )
    recorder.register(metric_def)

    # Emit a value
    recorder.emit("processing_time", 5.25)

    # Verify recording
    recordings = recorder.get_recordings("processing_time")
    assert len(recordings) == 1
    assert recordings[0]["value"] == pytest.approx(5.25)
    assert recordings[0]["labels"] == {}
    assert isinstance(recordings[0]["timestamp"], datetime)


@pytest.mark.requirement("3D-FR-046")
def test_get_registered_metrics() -> None:
    """Test listing all registered custom metrics."""
    recorder = MetricRecorder()

    metric1 = CustomMetricDefinition(
        name="metric_one",
        description="First metric",
        unit="count",
    )
    metric2 = CustomMetricDefinition(
        name="metric_two",
        description="Second metric",
        unit="percent",
    )

    recorder.register(metric1)
    recorder.register(metric2)

    registered = recorder.get_registered()
    assert len(registered) == 2
    names = {m.name for m in registered}
    assert names == {"metric_one", "metric_two"}


@pytest.mark.requirement("3D-FR-046")
def test_duplicate_metric_name_rejected() -> None:
    """Test registering same metric name twice raises ValueError."""
    recorder = MetricRecorder()

    metric1 = CustomMetricDefinition(
        name="duplicate_metric",
        description="First definition",
        unit="count",
    )
    metric2 = CustomMetricDefinition(
        name="duplicate_metric",
        description="Second definition",
        unit="percent",
    )

    recorder.register(metric1)

    with pytest.raises(ValueError, match="already registered"):
        recorder.register(metric2)


@pytest.mark.requirement("3D-FR-046")
def test_emit_unregistered_metric_raises() -> None:
    """Test emitting for unknown metric raises KeyError."""
    recorder = MetricRecorder()

    with pytest.raises(KeyError, match="not registered"):
        recorder.emit("unknown_metric", 42.0)


@pytest.mark.requirement("3D-FR-046")
def test_custom_metric_with_labels() -> None:
    """Test emitting metric with label values."""
    recorder = MetricRecorder()

    metric_def = CustomMetricDefinition(
        name="request_duration",
        description="HTTP request duration",
        unit="seconds",
        labels=["endpoint", "status_code"],
    )
    recorder.register(metric_def)

    # Emit with labels
    recorder.emit(
        "request_duration",
        0.125,
        labels={"endpoint": "/api/v1/contracts", "status_code": "200"},
    )
    recorder.emit(
        "request_duration",
        0.250,
        labels={"endpoint": "/api/v1/violations", "status_code": "500"},
    )

    # Verify both recordings
    recordings = recorder.get_recordings("request_duration")
    assert len(recordings) == 2

    assert recordings[0]["value"] == pytest.approx(0.125)
    assert recordings[0]["labels"] == {"endpoint": "/api/v1/contracts", "status_code": "200"}

    assert recordings[1]["value"] == pytest.approx(0.250)
    assert recordings[1]["labels"] == {"endpoint": "/api/v1/violations", "status_code": "500"}


@pytest.mark.requirement("3D-FR-046")
def test_multiple_emissions_same_metric() -> None:
    """Test multiple emissions for the same metric are recorded separately."""
    recorder = MetricRecorder()

    metric_def = CustomMetricDefinition(
        name="cpu_usage",
        description="CPU usage percentage",
        unit="percent",
    )
    recorder.register(metric_def)

    # Emit multiple values
    recorder.emit("cpu_usage", 45.5)
    recorder.emit("cpu_usage", 62.3)
    recorder.emit("cpu_usage", 78.9)

    # Verify all recordings
    recordings = recorder.get_recordings("cpu_usage")
    assert len(recordings) == 3
    values = [r["value"] for r in recordings]
    assert values[0] == pytest.approx(45.5)
    assert values[1] == pytest.approx(62.3)
    assert values[2] == pytest.approx(78.9)


@pytest.mark.requirement("3D-FR-046")
def test_get_recordings_empty() -> None:
    """Test get_recordings for registered but unemitted metric returns empty list."""
    recorder = MetricRecorder()

    metric_def = CustomMetricDefinition(
        name="unused_metric",
        description="Registered but never emitted",
        unit="count",
    )
    recorder.register(metric_def)

    recordings = recorder.get_recordings("unused_metric")
    assert recordings == []


@pytest.mark.requirement("3D-FR-046")
def test_get_recordings_unregistered_raises() -> None:
    """Test get_recordings for unregistered metric raises KeyError."""
    recorder = MetricRecorder()

    with pytest.raises(KeyError, match="not registered"):
        recorder.get_recordings("unknown_metric")
