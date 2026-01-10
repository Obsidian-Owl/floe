"""Unit tests for connection health monitoring.

Tests for FR-018 (validate_connection method) and FR-019 (ConnectionResult structure).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.compute_config import (
    ConnectionResult,
    ConnectionStatus,
)


class TestConnectionStatus:
    """Test ConnectionStatus enum for health monitoring (FR-018)."""

    @pytest.mark.requirement("001-FR-018")
    def test_connection_status_healthy(self) -> None:
        """Test HEALTHY status indicates successful connection."""
        status = ConnectionStatus.HEALTHY
        assert status.value == "healthy"

    @pytest.mark.requirement("001-FR-018")
    def test_connection_status_degraded(self) -> None:
        """Test DEGRADED status indicates connection with issues."""
        status = ConnectionStatus.DEGRADED
        assert status.value == "degraded"

    @pytest.mark.requirement("001-FR-018")
    def test_connection_status_unhealthy(self) -> None:
        """Test UNHEALTHY status indicates connection failure."""
        status = ConnectionStatus.UNHEALTHY
        assert status.value == "unhealthy"

    @pytest.mark.requirement("001-FR-018")
    def test_connection_status_from_string(self) -> None:
        """Test ConnectionStatus can be created from string value."""
        assert ConnectionStatus("healthy") == ConnectionStatus.HEALTHY
        assert ConnectionStatus("degraded") == ConnectionStatus.DEGRADED
        assert ConnectionStatus("unhealthy") == ConnectionStatus.UNHEALTHY


class TestConnectionResult:
    """Test ConnectionResult structure (FR-019).

    FR-019: validate_connection() MUST return ConnectionResult with
    status, latency_ms, and optional warnings.
    """

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_has_status_field(self) -> None:
        """Test ConnectionResult has status field (FR-019)."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=10.0,
        )
        assert hasattr(result, "status")
        assert result.status == ConnectionStatus.HEALTHY

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_has_latency_ms_field(self) -> None:
        """Test ConnectionResult has latency_ms field (FR-019)."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=23.5,
        )
        assert hasattr(result, "latency_ms")
        assert result.latency_ms == pytest.approx(23.5)

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_has_optional_warnings(self) -> None:
        """Test ConnectionResult has optional warnings field (FR-019)."""
        # Without warnings (defaults to empty list)
        result_no_warnings = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=10.0,
        )
        assert result_no_warnings.warnings == []

        # With warnings
        result_with_warnings = ConnectionResult(
            status=ConnectionStatus.DEGRADED,
            latency_ms=50.0,
            warnings=["iceberg extension not loaded", "httpfs extension not loaded"],
        )
        assert len(result_with_warnings.warnings) == 2
        assert "iceberg extension not loaded" in result_with_warnings.warnings

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_has_message_field(self) -> None:
        """Test ConnectionResult has message field for human-readable status."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=10.0,
            message="Connection successful",
        )
        assert result.message == "Connection successful"

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_message_defaults_to_empty(self) -> None:
        """Test ConnectionResult message defaults to empty string."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=10.0,
        )
        assert result.message == ""

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_frozen(self) -> None:
        """Test ConnectionResult is immutable (frozen model)."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=10.0,
        )
        with pytest.raises(ValidationError):
            result.status = ConnectionStatus.UNHEALTHY  # type: ignore[misc]

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_latency_must_be_non_negative(self) -> None:
        """Test ConnectionResult rejects negative latency."""
        with pytest.raises(ValidationError, match="latency_ms"):
            ConnectionResult(
                status=ConnectionStatus.HEALTHY,
                latency_ms=-1.0,
            )

    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_latency_zero_valid(self) -> None:
        """Test ConnectionResult accepts zero latency."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=0.0,
        )
        assert result.latency_ms == pytest.approx(0.0)

    @pytest.mark.requirement("001-FR-018")
    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_healthy_example(self) -> None:
        """Test typical healthy connection result."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=15.3,
            message="DuckDB connection successful",
            warnings=[],
        )
        assert result.status == ConnectionStatus.HEALTHY
        assert result.latency_ms == pytest.approx(15.3)
        assert result.message == "DuckDB connection successful"
        assert result.warnings == []

    @pytest.mark.requirement("001-FR-018")
    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_degraded_example(self) -> None:
        """Test typical degraded connection result."""
        result = ConnectionResult(
            status=ConnectionStatus.DEGRADED,
            latency_ms=100.0,
            message="Connection established with warnings",
            warnings=["iceberg extension not loaded"],
        )
        assert result.status == ConnectionStatus.DEGRADED
        assert len(result.warnings) == 1

    @pytest.mark.requirement("001-FR-018")
    @pytest.mark.requirement("001-FR-019")
    def test_connection_result_unhealthy_example(self) -> None:
        """Test typical unhealthy connection result."""
        result = ConnectionResult(
            status=ConnectionStatus.UNHEALTHY,
            latency_ms=5000.0,  # Timeout
            message="Connection timeout after 5 seconds",
            warnings=[],
        )
        assert result.status == ConnectionStatus.UNHEALTHY
        assert result.latency_ms == pytest.approx(5000.0)
