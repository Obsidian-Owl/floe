"""Unit tests for OCI metrics instrumentation.

This module tests the OCIMetrics class for OpenTelemetry metrics emission.

Requirements tested:
    FR-020: OpenTelemetry metrics are emitted for all OCI operations
    FR-021: Metric names follow floe_oci_ naming convention

Task ID: T042
Phase: 8 - US6 (Add Missing Test Coverage)
User Story: US6 - Add Missing Test Coverage
"""

from __future__ import annotations

# Import directly from metrics module to avoid client.py which requires oras
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Load metrics module directly without going through __init__.py
# Path: tests/unit/oci/test_metrics.py -> parents[3] = packages/floe-core
metrics_path = Path(__file__).parents[3] / "src" / "floe_core" / "oci" / "metrics.py"
spec = importlib.util.spec_from_file_location("oci_metrics", metrics_path)
assert spec is not None and spec.loader is not None
oci_metrics_module = importlib.util.module_from_spec(spec)
sys.modules["oci_metrics"] = oci_metrics_module
spec.loader.exec_module(oci_metrics_module)

# Import classes from loaded module
OCIMetrics = oci_metrics_module.OCIMetrics
CircuitBreakerStateValue = oci_metrics_module.CircuitBreakerStateValue
get_oci_metrics = oci_metrics_module.get_oci_metrics
set_oci_metrics = oci_metrics_module.set_oci_metrics

if TYPE_CHECKING:
    pass


class TestOCIMetricsInit:
    """Tests for OCIMetrics initialization."""

    @pytest.mark.requirement("FR-020")
    def test_oci_metrics_creates_with_defaults(self) -> None:
        """OCIMetrics initializes with default meter and tracer names."""
        metrics = OCIMetrics()
        assert metrics._meter is not None
        assert metrics._tracer is not None

    @pytest.mark.requirement("FR-020")
    def test_oci_metrics_accepts_custom_names(self) -> None:
        """OCIMetrics accepts custom meter and tracer names."""
        metrics = OCIMetrics(
            meter_name="custom.oci",
            meter_version="2.0.0",
            tracer_name="custom.oci.tracer",
        )
        assert metrics._meter is not None
        assert metrics._tracer is not None


class TestOCIMetricsNaming:
    """Tests for metric naming conventions."""

    @pytest.mark.requirement("FR-021")
    def test_metric_names_have_floe_oci_prefix(self) -> None:
        """All metric names start with floe_oci_ prefix."""
        metric_names = [
            OCIMetrics.OPERATIONS_TOTAL,
            OCIMetrics.CACHE_OPERATIONS_TOTAL,
            OCIMetrics.OPERATION_DURATION_SECONDS,
            OCIMetrics.ARTIFACT_SIZE_BYTES,
            OCIMetrics.CIRCUIT_BREAKER_STATE,
            OCIMetrics.CIRCUIT_BREAKER_FAILURES,
            OCIMetrics.CACHE_SIZE_BYTES,
            OCIMetrics.CACHE_ENTRIES_COUNT,
        ]

        for name in metric_names:
            assert name.startswith(
                "floe_oci_"
            ), f"Metric {name} should start with 'floe_oci_' prefix"

    @pytest.mark.requirement("FR-021")
    def test_span_names_have_floe_oci_prefix(self) -> None:
        """All span names start with floe.oci. prefix."""
        span_names = [
            OCIMetrics.SPAN_PUSH,
            OCIMetrics.SPAN_PULL,
            OCIMetrics.SPAN_INSPECT,
            OCIMetrics.SPAN_LIST,
            OCIMetrics.SPAN_AUTH,
            OCIMetrics.SPAN_UPLOAD_LAYER,
            OCIMetrics.SPAN_DOWNLOAD_LAYER,
        ]

        for name in span_names:
            assert name.startswith("floe.oci."), f"Span {name} should start with 'floe.oci.' prefix"


class TestRecordOperation:
    """Tests for record_operation method."""

    @pytest.mark.requirement("FR-020")
    def test_record_operation_success(self) -> None:
        """record_operation records successful operation."""
        metrics = OCIMetrics()
        # This should not raise
        metrics.record_operation("push", "harbor.example.com", success=True)

    @pytest.mark.requirement("FR-020")
    def test_record_operation_failure(self) -> None:
        """record_operation records failed operation."""
        metrics = OCIMetrics()
        # This should not raise
        metrics.record_operation("pull", "harbor.example.com", success=False)

    @pytest.mark.requirement("FR-020")
    def test_record_operation_with_labels(self) -> None:
        """record_operation accepts additional labels."""
        metrics = OCIMetrics()
        metrics.record_operation(
            "push",
            "harbor.example.com",
            success=True,
            labels={"tag": "v1.0.0", "namespace": "floe"},
        )


class TestRecordDuration:
    """Tests for record_duration method."""

    @pytest.mark.requirement("FR-020")
    def test_record_duration(self) -> None:
        """record_duration records operation duration."""
        metrics = OCIMetrics()
        metrics.record_duration("push", "harbor.example.com", 1.5)

    @pytest.mark.requirement("FR-020")
    def test_record_duration_with_labels(self) -> None:
        """record_duration accepts additional labels."""
        metrics = OCIMetrics()
        metrics.record_duration(
            "pull",
            "harbor.example.com",
            2.5,
            labels={"tag": "v1.0.0"},
        )


class TestRecordArtifactSize:
    """Tests for record_artifact_size method."""

    @pytest.mark.requirement("FR-020")
    def test_record_artifact_size(self) -> None:
        """record_artifact_size records artifact size."""
        metrics = OCIMetrics()
        metrics.record_artifact_size("push", 1024 * 1024)  # 1MB

    @pytest.mark.requirement("FR-020")
    def test_record_artifact_size_with_labels(self) -> None:
        """record_artifact_size accepts additional labels."""
        metrics = OCIMetrics()
        metrics.record_artifact_size(
            "pull",
            2048 * 1024,
            labels={"content_type": "application/json"},
        )


class TestRecordCacheOperation:
    """Tests for record_cache_operation method."""

    @pytest.mark.requirement("FR-020")
    def test_record_cache_hit(self) -> None:
        """record_cache_operation records cache hit."""
        metrics = OCIMetrics()
        metrics.record_cache_operation("hit")

    @pytest.mark.requirement("FR-020")
    def test_record_cache_miss(self) -> None:
        """record_cache_operation records cache miss."""
        metrics = OCIMetrics()
        metrics.record_cache_operation("miss")

    @pytest.mark.requirement("FR-020")
    def test_record_cache_evict(self) -> None:
        """record_cache_operation records cache eviction."""
        metrics = OCIMetrics()
        metrics.record_cache_operation("evict")

    @pytest.mark.requirement("FR-020")
    def test_record_cache_operation_with_labels(self) -> None:
        """record_cache_operation accepts additional labels."""
        metrics = OCIMetrics()
        metrics.record_cache_operation("hit", labels={"artifact": "v1.0.0"})


class TestCircuitBreakerState:
    """Tests for circuit breaker state tracking."""

    @pytest.mark.requirement("FR-020")
    def test_circuit_breaker_state_values(self) -> None:
        """CircuitBreakerStateValue has correct numeric values."""
        assert CircuitBreakerStateValue.CLOSED == 0
        assert CircuitBreakerStateValue.OPEN == 1
        assert CircuitBreakerStateValue.HALF_OPEN == 2

    @pytest.mark.requirement("FR-020")
    def test_set_circuit_breaker_state_closed(self) -> None:
        """set_circuit_breaker_state records closed state."""
        metrics = OCIMetrics()
        metrics.set_circuit_breaker_state(
            "harbor.example.com",
            CircuitBreakerStateValue.CLOSED,
        )

    @pytest.mark.requirement("FR-020")
    def test_set_circuit_breaker_state_open(self) -> None:
        """set_circuit_breaker_state records open state."""
        metrics = OCIMetrics()
        metrics.set_circuit_breaker_state(
            "harbor.example.com",
            CircuitBreakerStateValue.OPEN,
            failure_count=5,
        )

    @pytest.mark.requirement("FR-020")
    def test_set_circuit_breaker_state_half_open(self) -> None:
        """set_circuit_breaker_state records half-open state."""
        metrics = OCIMetrics()
        metrics.set_circuit_breaker_state(
            "harbor.example.com",
            CircuitBreakerStateValue.HALF_OPEN,
        )


class TestCacheStats:
    """Tests for cache statistics tracking."""

    @pytest.mark.requirement("FR-020")
    def test_set_cache_stats(self) -> None:
        """set_cache_stats records cache size and entry count."""
        metrics = OCIMetrics()
        metrics.set_cache_stats(size_bytes=10240, entry_count=5)


class TestOperationTimer:
    """Tests for operation_timer context manager."""

    @pytest.mark.requirement("FR-020")
    def test_operation_timer_success(self) -> None:
        """operation_timer records success on normal completion."""
        metrics = OCIMetrics()

        with metrics.operation_timer("push", "harbor.example.com"):
            pass  # Simulate successful operation

    @pytest.mark.requirement("FR-020")
    def test_operation_timer_failure(self) -> None:
        """operation_timer records failure on exception."""
        metrics = OCIMetrics()

        with pytest.raises(ValueError):
            with metrics.operation_timer("push", "harbor.example.com"):
                raise ValueError("Test error")

    @pytest.mark.requirement("FR-020")
    def test_operation_timer_with_labels(self) -> None:
        """operation_timer accepts additional labels."""
        metrics = OCIMetrics()

        with metrics.operation_timer(
            "pull",
            "harbor.example.com",
            labels={"tag": "v1.0.0"},
        ):
            pass


class TestCreateSpan:
    """Tests for create_span context manager."""

    @pytest.mark.requirement("FR-020")
    def test_create_span_success(self) -> None:
        """create_span creates span for successful operation."""
        metrics = OCIMetrics()

        with metrics.create_span(OCIMetrics.SPAN_PUSH) as span:
            span.set_attribute("test", "value")

    @pytest.mark.requirement("FR-020")
    def test_create_span_with_attributes(self) -> None:
        """create_span accepts initial attributes."""
        metrics = OCIMetrics()

        with metrics.create_span(
            OCIMetrics.SPAN_PULL,
            attributes={"registry": "harbor.example.com", "tag": "v1.0.0"},
        ) as span:
            assert span is not None

    @pytest.mark.requirement("FR-020")
    def test_create_span_records_exception(self) -> None:
        """create_span records exception on failure."""
        metrics = OCIMetrics()

        with pytest.raises(RuntimeError):
            with metrics.create_span(OCIMetrics.SPAN_PUSH):
                raise RuntimeError("Simulated failure")


class TestRegistryNormalization:
    """Tests for registry URI normalization."""

    @pytest.mark.requirement("FR-021")
    def test_normalize_registry_removes_oci_prefix(self) -> None:
        """_normalize_registry removes oci:// prefix."""
        metrics = OCIMetrics()
        result = metrics._normalize_registry("oci://harbor.example.com/namespace/repo")
        assert result == "harbor.example.com"

    @pytest.mark.requirement("FR-021")
    def test_normalize_registry_extracts_hostname(self) -> None:
        """_normalize_registry extracts hostname from path."""
        metrics = OCIMetrics()
        result = metrics._normalize_registry("harbor.example.com/namespace/repo")
        assert result == "harbor.example.com"

    @pytest.mark.requirement("FR-021")
    def test_normalize_registry_handles_simple_hostname(self) -> None:
        """_normalize_registry handles simple hostname."""
        metrics = OCIMetrics()
        result = metrics._normalize_registry("harbor.example.com")
        assert result == "harbor.example.com"


class TestSingleton:
    """Tests for module-level singleton."""

    @pytest.mark.requirement("FR-020")
    def test_get_oci_metrics_returns_instance(self) -> None:
        """get_oci_metrics returns OCIMetrics instance."""
        # Reset singleton first
        set_oci_metrics(None)

        metrics = get_oci_metrics()
        assert isinstance(metrics, OCIMetrics)

    @pytest.mark.requirement("FR-020")
    def test_get_oci_metrics_returns_same_instance(self) -> None:
        """get_oci_metrics returns same instance on repeated calls."""
        # Reset singleton first
        set_oci_metrics(None)

        metrics1 = get_oci_metrics()
        metrics2 = get_oci_metrics()
        assert metrics1 is metrics2

    @pytest.mark.requirement("FR-020")
    def test_set_oci_metrics_replaces_singleton(self) -> None:
        """set_oci_metrics replaces the singleton instance."""
        custom_metrics = OCIMetrics(meter_name="custom")
        set_oci_metrics(custom_metrics)

        assert get_oci_metrics() is custom_metrics

        # Clean up
        set_oci_metrics(None)

    @pytest.mark.requirement("FR-020")
    def test_set_oci_metrics_to_none_resets(self) -> None:
        """set_oci_metrics(None) resets singleton."""
        # Get initial instance
        metrics1 = get_oci_metrics()

        # Reset
        set_oci_metrics(None)

        # Get new instance
        metrics2 = get_oci_metrics()

        # Should be different instance
        assert metrics1 is not metrics2


class TestLazyInstrumentCreation:
    """Tests for lazy instrument creation."""

    @pytest.mark.requirement("FR-020")
    def test_operations_counter_created_lazily(self) -> None:
        """Operations counter is created on first access."""
        metrics = OCIMetrics()
        assert metrics._operations_counter is None

        _ = metrics.operations_counter
        assert metrics._operations_counter is not None

    @pytest.mark.requirement("FR-020")
    def test_cache_operations_counter_created_lazily(self) -> None:
        """Cache operations counter is created on first access."""
        metrics = OCIMetrics()
        assert metrics._cache_operations_counter is None

        _ = metrics.cache_operations_counter
        assert metrics._cache_operations_counter is not None

    @pytest.mark.requirement("FR-020")
    def test_duration_histogram_created_lazily(self) -> None:
        """Duration histogram is created on first access."""
        metrics = OCIMetrics()
        assert metrics._duration_histogram is None

        _ = metrics.duration_histogram
        assert metrics._duration_histogram is not None

    @pytest.mark.requirement("FR-020")
    def test_size_histogram_created_lazily(self) -> None:
        """Size histogram is created on first access."""
        metrics = OCIMetrics()
        assert metrics._size_histogram is None

        _ = metrics.size_histogram
        assert metrics._size_histogram is not None
