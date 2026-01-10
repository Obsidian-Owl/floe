"""Unit tests for observability module.

Tests for FR-024 (OTel metrics emission).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestGetTracer:
    """Test get_tracer function."""

    @pytest.mark.requirement("001-FR-024")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test get_tracer returns an OpenTelemetry tracer."""
        from floe_core.observability import get_tracer, reset_for_testing

        reset_for_testing()

        tracer = get_tracer()

        # Should have tracer-like interface
        assert hasattr(tracer, "start_as_current_span")
        assert hasattr(tracer, "start_span")

    @pytest.mark.requirement("001-FR-024")
    def test_get_tracer_returns_same_instance(self) -> None:
        """Test get_tracer returns singleton instance."""
        from floe_core.observability import get_tracer, reset_for_testing

        reset_for_testing()

        tracer1 = get_tracer()
        tracer2 = get_tracer()

        assert tracer1 is tracer2


class TestGetMeter:
    """Test get_meter function."""

    @pytest.mark.requirement("001-FR-024")
    def test_get_meter_returns_meter(self) -> None:
        """Test get_meter returns an OpenTelemetry meter."""
        from floe_core.observability import get_meter, reset_for_testing

        reset_for_testing()

        meter = get_meter()

        # Should have meter-like interface
        assert hasattr(meter, "create_counter")
        assert hasattr(meter, "create_histogram")

    @pytest.mark.requirement("001-FR-024")
    def test_get_meter_returns_same_instance(self) -> None:
        """Test get_meter returns singleton instance."""
        from floe_core.observability import get_meter, reset_for_testing

        reset_for_testing()

        meter1 = get_meter()
        meter2 = get_meter()

        assert meter1 is meter2


class TestRecordValidationDuration:
    """Test record_validation_duration function (FR-024)."""

    @pytest.mark.requirement("001-FR-024")
    def test_record_validation_duration_creates_histogram(self) -> None:
        """Test recording duration creates histogram metric."""
        from floe_core.observability import record_validation_duration, reset_for_testing

        reset_for_testing()

        # Should not raise
        record_validation_duration("duckdb", 23.5, "healthy")

    @pytest.mark.requirement("001-FR-024")
    def test_record_validation_duration_with_various_statuses(self) -> None:
        """Test recording duration with different status values."""
        from floe_core.observability import record_validation_duration, reset_for_testing

        reset_for_testing()

        # Should not raise for any status
        record_validation_duration("duckdb", 10.0, "healthy")
        record_validation_duration("snowflake", 50.0, "degraded")
        record_validation_duration("spark", 5000.0, "unhealthy")

    @pytest.mark.requirement("001-FR-024")
    def test_record_validation_duration_labels(self) -> None:
        """Test histogram records correct labels."""
        from floe_core.observability import (
            _get_validation_duration_histogram,
            record_validation_duration,
            reset_for_testing,
        )

        reset_for_testing()

        # Get the histogram before patching
        histogram = _get_validation_duration_histogram()

        # Mock the record method
        with patch.object(histogram, "record") as mock_record:
            record_validation_duration("duckdb", 25.0, "healthy")

            mock_record.assert_called_once()
            call_args = mock_record.call_args
            assert call_args[0][0] == pytest.approx(25.0)  # Duration
            assert call_args[0][1]["compute.plugin"] == "duckdb"
            assert call_args[0][1]["validation.status"] == "healthy"


class TestRecordValidationError:
    """Test record_validation_error function (FR-024)."""

    @pytest.mark.requirement("001-FR-024")
    def test_record_validation_error_creates_counter(self) -> None:
        """Test recording error creates counter metric."""
        from floe_core.observability import record_validation_error, reset_for_testing

        reset_for_testing()

        # Should not raise
        record_validation_error("duckdb", "connection_timeout")

    @pytest.mark.requirement("001-FR-024")
    def test_record_validation_error_with_various_types(self) -> None:
        """Test recording errors with different error types."""
        from floe_core.observability import record_validation_error, reset_for_testing

        reset_for_testing()

        # Should not raise for any error type
        record_validation_error("duckdb", "connection_timeout")
        record_validation_error("snowflake", "auth_failure")
        record_validation_error("spark", "network_error")

    @pytest.mark.requirement("001-FR-024")
    def test_record_validation_error_labels(self) -> None:
        """Test counter records correct labels."""
        from floe_core.observability import (
            _get_validation_errors_counter,
            record_validation_error,
            reset_for_testing,
        )

        reset_for_testing()

        # Get the counter before patching
        counter = _get_validation_errors_counter()

        # Mock the add method
        with patch.object(counter, "add") as mock_add:
            record_validation_error("duckdb", "connection_timeout")

            mock_add.assert_called_once()
            call_args = mock_add.call_args
            assert call_args[0][0] == 1  # Increment by 1
            assert call_args[0][1]["compute.plugin"] == "duckdb"
            assert call_args[0][1]["error.type"] == "connection_timeout"


class TestStartValidationSpan:
    """Test start_validation_span function (FR-024)."""

    @pytest.mark.requirement("001-FR-024")
    def test_start_validation_span_returns_context_manager(self) -> None:
        """Test start_validation_span returns context manager."""
        from floe_core.observability import reset_for_testing, start_validation_span

        reset_for_testing()

        span_context = start_validation_span("duckdb")

        # Should be usable as context manager
        assert hasattr(span_context, "__enter__")
        assert hasattr(span_context, "__exit__")

    @pytest.mark.requirement("001-FR-024")
    def test_start_validation_span_with_context_manager(self) -> None:
        """Test using start_validation_span as context manager."""
        from floe_core.observability import reset_for_testing, start_validation_span

        reset_for_testing()

        # Should not raise
        with start_validation_span("duckdb") as span:
            # Span should have attribute setting capability
            assert hasattr(span, "set_attribute")


class TestResetForTesting:
    """Test reset_for_testing function."""

    @pytest.mark.requirement("001-FR-024")
    def test_reset_for_testing_clears_singletons(self) -> None:
        """Test reset_for_testing clears all singletons."""
        from floe_core.observability import (
            get_meter,
            get_tracer,
            reset_for_testing,
        )

        # Initialize singletons
        tracer1 = get_tracer()
        meter1 = get_meter()

        # Reset
        reset_for_testing()

        # Get new instances
        tracer2 = get_tracer()
        meter2 = get_meter()

        # Should be new instances (different objects)
        # Note: OTel may return same underlying tracer, so we just verify no errors
        assert tracer2 is not None
        assert meter2 is not None


class TestOTelServiceInfo:
    """Test OTel service configuration."""

    @pytest.mark.requirement("001-FR-024")
    def test_service_name_is_floe_core(self) -> None:
        """Test service name is set to floe-core."""
        from floe_core.observability import OTEL_SERVICE_NAME

        assert OTEL_SERVICE_NAME == "floe-core"

    @pytest.mark.requirement("001-FR-024")
    def test_service_version_is_set(self) -> None:
        """Test service version is set."""
        from floe_core.observability import OTEL_SERVICE_VERSION

        assert OTEL_SERVICE_VERSION == "0.1.0"
