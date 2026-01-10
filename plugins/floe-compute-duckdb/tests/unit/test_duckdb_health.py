"""Unit tests for DuckDB connection health monitoring.

Tests for FR-018 (validate_connection method), FR-019 (latency measurement),
and FR-024 (OTel metrics emission).

Note: Unit tests mock the duckdb module. Integration tests with real DuckDB
should go in tests/integration/.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from floe_core import (
    ComputeConfig,
    ConnectionResult,
    ConnectionStatus,
)

from floe_compute_duckdb import DuckDBComputePlugin


@pytest.fixture
def plugin() -> DuckDBComputePlugin:
    """Create a DuckDBComputePlugin instance."""
    return DuckDBComputePlugin()


@pytest.fixture
def memory_config() -> ComputeConfig:
    """Create in-memory DuckDB config."""
    return ComputeConfig(
        plugin="duckdb",
        connection={"path": ":memory:"},
    )


@pytest.fixture
def mock_duckdb_success() -> MagicMock:
    """Create a mock duckdb module that succeeds."""
    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    mock_duckdb.connect.return_value = mock_conn
    return mock_duckdb


class TestValidateConnectionLatency:
    """Test validate_connection latency measurement (FR-019)."""

    @pytest.mark.requirement("001-FR-019")
    def test_validate_connection_returns_latency_ms(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection returns latency_ms in result."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            result = plugin.validate_connection(memory_config)

        assert hasattr(result, "latency_ms")
        assert isinstance(result.latency_ms, float)

    @pytest.mark.requirement("001-FR-019")
    def test_validate_connection_latency_is_non_negative(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection latency_ms is non-negative."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            result = plugin.validate_connection(memory_config)

        assert result.latency_ms >= 0

    @pytest.mark.requirement("001-FR-019")
    def test_validate_connection_latency_is_reasonable(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection latency_ms is reasonable (< 5 seconds)."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            result = plugin.validate_connection(memory_config)

        # Mocked connection should be very fast
        assert result.latency_ms < 5000  # 5 seconds max

    @pytest.mark.requirement("001-FR-019")
    def test_validate_connection_latency_measured_on_success(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test latency is measured on successful connection."""
        config = ComputeConfig(
            plugin="duckdb",
            connection={"path": ":memory:"},
        )

        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            result = plugin.validate_connection(config)

        # Latency should be measured (non-negative)
        assert result.latency_ms >= 0
        assert result.status == ConnectionStatus.HEALTHY


class TestValidateConnectionStatus:
    """Test validate_connection status reporting (FR-018)."""

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_returns_connection_result(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection returns ConnectionResult."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            result = plugin.validate_connection(memory_config)

        assert isinstance(result, ConnectionResult)

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_healthy_for_success(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection returns HEALTHY on successful connection."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            result = plugin.validate_connection(memory_config)

        assert result.status == ConnectionStatus.HEALTHY

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_includes_message(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection includes human-readable message."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            result = plugin.validate_connection(memory_config)

        assert result.message != ""
        assert ":memory:" in result.message or "DuckDB" in result.message

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_unhealthy_on_error(
        self, plugin: DuckDBComputePlugin
    ) -> None:
        """Test validate_connection returns UNHEALTHY on error."""
        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = Exception("Connection failed")

        with patch.dict("sys.modules", {"duckdb": mock_duckdb}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/nonexistent/path/db.duckdb"},
            )
            result = plugin.validate_connection(config)

        assert result.status == ConnectionStatus.UNHEALTHY
        assert "failed" in result.message.lower() or "error" in result.message.lower()

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_latency_measured_on_error(
        self, plugin: DuckDBComputePlugin
    ) -> None:
        """Test validate_connection measures latency even on error."""
        def delayed_error(*args: Any, **kwargs: Any) -> None:
            raise Exception("Connection failed")

        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = delayed_error

        with patch.dict("sys.modules", {"duckdb": mock_duckdb}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/nonexistent/path/db.duckdb"},
            )
            result = plugin.validate_connection(config)

        # Latency should still be measured
        assert result.latency_ms >= 0

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_unhealthy_includes_error_in_message(
        self, plugin: DuckDBComputePlugin
    ) -> None:
        """Test validate_connection includes error details in message."""
        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = Exception("Connection timeout")

        with patch.dict("sys.modules", {"duckdb": mock_duckdb}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/nonexistent/path/db.duckdb"},
            )
            result = plugin.validate_connection(config)

        assert result.status == ConnectionStatus.UNHEALTHY
        # Error details should be in the message
        assert "timeout" in result.message.lower() or "failed" in result.message.lower()

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_unhealthy_populates_warnings(
        self, plugin: DuckDBComputePlugin
    ) -> None:
        """Test validate_connection adds warnings with error details."""
        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = Exception("Connection timeout")

        with patch.dict("sys.modules", {"duckdb": mock_duckdb}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/nonexistent/path/db.duckdb"},
            )
            result = plugin.validate_connection(config)

        assert result.status == ConnectionStatus.UNHEALTHY
        # Should include error details in warnings list
        assert len(result.warnings) >= 1
        # At least one warning should contain relevant error info
        all_warnings = " ".join(result.warnings).lower()
        assert "timeout" in all_warnings or "error" in all_warnings or "failed" in all_warnings


class TestValidateConnectionNativeDriver:
    """Test validate_connection uses native driver (FR-018)."""

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_uses_duckdb_driver(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test validate_connection uses native duckdb driver, not dbt debug."""
        # This test verifies the implementation uses duckdb.connect directly
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": ":memory:"},
            )
            plugin.validate_connection(config)

        # Verify native driver was called
        mock_duckdb_success.connect.assert_called_once()

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_executes_validation_query(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test validate_connection executes a validation query."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": ":memory:"},
            )
            plugin.validate_connection(config)

        # Verify execute was called (validation query)
        mock_conn = mock_duckdb_success.connect.return_value
        mock_conn.execute.assert_called()

    @pytest.mark.requirement("001-FR-018")
    def test_validate_connection_closes_connection(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test validate_connection properly closes the connection."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": ":memory:"},
            )
            plugin.validate_connection(config)

        # Verify connection was closed
        mock_conn = mock_duckdb_success.connect.return_value
        mock_conn.close.assert_called_once()


class TestValidateConnectionOTelMetrics:
    """Test validate_connection OTel metrics emission (FR-024)."""

    @pytest.mark.requirement("001-FR-024")
    def test_validate_connection_records_duration_on_success(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection records duration metric on success."""
        with (
            patch.dict("sys.modules", {"duckdb": mock_duckdb_success}),
            patch("floe_compute_duckdb.plugin.record_validation_duration") as mock_record,
        ):
            plugin.validate_connection(memory_config)

        mock_record.assert_called_once()
        call_args = mock_record.call_args
        assert call_args[0][0] == "duckdb"  # plugin_name
        assert call_args[0][2] == "healthy"  # status

    @pytest.mark.requirement("001-FR-024")
    def test_validate_connection_records_duration_on_error(
        self, plugin: DuckDBComputePlugin
    ) -> None:
        """Test validate_connection records duration metric on error."""
        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = Exception("Connection failed")

        with (
            patch.dict("sys.modules", {"duckdb": mock_duckdb}),
            patch("floe_compute_duckdb.plugin.record_validation_duration") as mock_record,
            patch("floe_compute_duckdb.plugin.record_validation_error"),
        ):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/nonexistent/path/db.duckdb"},
            )
            plugin.validate_connection(config)

        mock_record.assert_called_once()
        call_args = mock_record.call_args
        assert call_args[0][0] == "duckdb"  # plugin_name
        assert call_args[0][2] == "unhealthy"  # status

    @pytest.mark.requirement("001-FR-024")
    def test_validate_connection_records_error_on_failure(
        self, plugin: DuckDBComputePlugin
    ) -> None:
        """Test validate_connection records error counter on failure."""
        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = Exception("Connection failed")

        with (
            patch.dict("sys.modules", {"duckdb": mock_duckdb}),
            patch("floe_compute_duckdb.plugin.record_validation_duration"),
            patch("floe_compute_duckdb.plugin.record_validation_error") as mock_error,
        ):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/nonexistent/path/db.duckdb"},
            )
            plugin.validate_connection(config)

        mock_error.assert_called_once()
        call_args = mock_error.call_args
        assert call_args[0][0] == "duckdb"  # plugin_name
        assert call_args[0][1] == "Exception"  # error_type

    @pytest.mark.requirement("001-FR-024")
    def test_validate_connection_no_error_counter_on_success(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection does not record error counter on success."""
        with (
            patch.dict("sys.modules", {"duckdb": mock_duckdb_success}),
            patch("floe_compute_duckdb.plugin.record_validation_duration"),
            patch("floe_compute_duckdb.plugin.record_validation_error") as mock_error,
        ):
            plugin.validate_connection(memory_config)

        mock_error.assert_not_called()

    @pytest.mark.requirement("001-FR-024")
    def test_validate_connection_starts_span(
        self,
        plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
        mock_duckdb_success: MagicMock,
    ) -> None:
        """Test validate_connection creates OTel span."""
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)

        with (
            patch.dict("sys.modules", {"duckdb": mock_duckdb_success}),
            patch(
                "floe_compute_duckdb.plugin.start_validation_span",
                return_value=mock_span,
            ) as mock_start,
            patch("floe_compute_duckdb.plugin.record_validation_duration"),
        ):
            plugin.validate_connection(memory_config)

        mock_start.assert_called_once_with("duckdb")
        mock_span.set_attribute.assert_any_call("db.path", ":memory:")
        mock_span.set_attribute.assert_any_call("validation.status", "healthy")
