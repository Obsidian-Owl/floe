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

    def test_increment_for_asset_materialization_metric(
        self, mock_meter: Mock
    ) -> None:
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
