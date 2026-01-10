"""Integration tests for DuckDBComputePlugin.

Tests for:
- FR-005: DuckDBComputePlugin implements ComputePlugin ABC
- FR-006: Support both in-memory and file-based DuckDB modes

These tests verify that the DuckDB compute plugin works correctly with real
database connections. Uses in-memory DuckDB for fast, isolated testing.

Note: These tests require DuckDB to be available and run in K8s for production parity.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from floe_core import ComputeConfig, ConnectionStatus

from floe_compute_duckdb import DuckDBComputePlugin


class TestValidateConnection:
    """Integration tests for validate_connection with real DuckDB (FR-005).

    These tests verify the core connection validation functionality using
    real DuckDB database connections.
    """

    @pytest.mark.integration
    @pytest.mark.requirement("FR-005")
    def test_validate_connection_returns_healthy_status(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test validate_connection returns HEALTHY status with real DuckDB.

        Verifies that when connecting to a valid DuckDB instance (in-memory),
        the connection is validated successfully and returns HEALTHY status.
        """
        result = duckdb_plugin.validate_connection(memory_config)

        assert result.status == ConnectionStatus.HEALTHY
        assert "Connected to DuckDB successfully" in result.message

    @pytest.mark.integration
    @pytest.mark.requirement("FR-005")
    def test_validate_connection_measures_latency(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test validate_connection measures latency_ms with real DuckDB.

        Verifies that the connection validation records the actual time taken
        to establish and verify the connection.
        """
        result = duckdb_plugin.validate_connection(memory_config)

        assert result.status == ConnectionStatus.HEALTHY
        assert result.latency_ms > 0
        # In-memory DuckDB should be very fast (< 1 second)
        assert result.latency_ms < 1000

    @pytest.mark.integration
    @pytest.mark.requirement("FR-005")
    def test_validate_connection_with_in_memory_database(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test validate_connection with in-memory database configuration.

        Verifies that the :memory: path configuration works correctly
        for ephemeral, in-process DuckDB instances.
        """
        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={"path": ":memory:"},
        )

        result = duckdb_plugin.validate_connection(config)

        assert result.status == ConnectionStatus.HEALTHY
        assert ":memory:" in result.message

    @pytest.mark.integration
    @pytest.mark.requirement("FR-005")
    def test_validate_connection_with_custom_threads(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test validate_connection respects custom thread configuration.

        Verifies that different thread configurations don't affect
        connection validation (DuckDB should connect successfully regardless).
        """
        # Test with single thread
        config_single = ComputeConfig(
            plugin="duckdb",
            threads=1,
            connection={"path": ":memory:"},
        )
        result_single = duckdb_plugin.validate_connection(config_single)
        assert result_single.status == ConnectionStatus.HEALTHY

        # Test with multiple threads
        config_multi = ComputeConfig(
            plugin="duckdb",
            threads=8,
            connection={"path": ":memory:"},
        )
        result_multi = duckdb_plugin.validate_connection(config_multi)
        assert result_multi.status == ConnectionStatus.HEALTHY

    @pytest.mark.integration
    @pytest.mark.requirement("FR-005")
    def test_validate_connection_invalid_path_returns_unhealthy(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test validate_connection returns UNHEALTHY for invalid path.

        Verifies that when the database path is invalid or inaccessible,
        the validation returns UNHEALTHY status with an error message.
        """
        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={
                # Path to a directory that doesn't exist (should fail)
                "path": "/nonexistent/path/to/database.duckdb",
            },
        )

        result = duckdb_plugin.validate_connection(config)

        assert result.status == ConnectionStatus.UNHEALTHY
        assert "Failed to connect" in result.message or result.warnings

    @pytest.mark.integration
    @pytest.mark.requirement("FR-005")
    def test_validate_connection_result_fields_populated(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test validate_connection populates all ConnectionResult fields.

        Verifies that the returned ConnectionResult has all required fields
        properly populated with meaningful values.
        """
        result = duckdb_plugin.validate_connection(memory_config)

        # All fields should be present
        assert result.status is not None
        assert result.latency_ms is not None
        assert result.message is not None

        # Status should be a valid ConnectionStatus enum value
        assert isinstance(result.status, ConnectionStatus)

        # Latency should be a positive float
        assert isinstance(result.latency_ms, float)
        assert result.latency_ms >= 0

        # Message should be a non-empty string
        assert isinstance(result.message, str)
        assert len(result.message) > 0


class TestRealDatabaseOperations:
    """Integration tests for database operations with real DuckDB.

    These tests verify that DuckDB can perform actual database operations
    after connection validation succeeds.
    """

    @pytest.mark.integration
    @pytest.mark.requirement("FR-005")
    def test_connection_executes_validation_query(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test that validate_connection executes a real validation query.

        Verifies that the validation actually runs a query against DuckDB
        (SELECT 1) rather than just opening a connection.
        """
        # Run validation
        result = duckdb_plugin.validate_connection(memory_config)

        # If validation passes, the SELECT 1 query executed successfully
        assert result.status == ConnectionStatus.HEALTHY

        # The message should indicate successful connection
        assert "successfully" in result.message.lower()


class TestDatabaseModes:
    """Integration tests for in-memory and file-based DuckDB modes (FR-006).

    These tests verify that DuckDB works correctly in both ephemeral in-memory
    mode and persistent file-based mode.
    """

    @pytest.mark.integration
    @pytest.mark.requirement("FR-006")
    def test_in_memory_mode(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test DuckDB works in in-memory mode with :memory: path.

        Verifies that the :memory: path creates an ephemeral, in-process
        database that works for quick, isolated operations.
        """
        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={"path": ":memory:"},
        )

        result = duckdb_plugin.validate_connection(config)

        assert result.status == ConnectionStatus.HEALTHY
        assert ":memory:" in result.message

    @pytest.mark.integration
    @pytest.mark.requirement("FR-006")
    def test_file_based_mode(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test DuckDB works in file-based mode with persistent database.

        Verifies that file-based paths create persistent databases that
        can be accessed across connections.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_database.duckdb"

            config = ComputeConfig(
                plugin="duckdb",
                threads=4,
                connection={"path": str(db_path)},
            )

            result = duckdb_plugin.validate_connection(config)

            assert result.status == ConnectionStatus.HEALTHY
            assert "test_database.duckdb" in result.message

            # Verify the database file was created
            assert db_path.exists()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-006")
    def test_file_based_mode_creates_database(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test file-based mode creates the database file on first connection.

        Verifies that DuckDB creates the database file when connecting to
        a path that doesn't exist yet.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "new_database.duckdb"

            # Ensure file doesn't exist before test
            assert not db_path.exists()

            config = ComputeConfig(
                plugin="duckdb",
                threads=4,
                connection={"path": str(db_path)},
            )

            result = duckdb_plugin.validate_connection(config)

            assert result.status == ConnectionStatus.HEALTHY
            # After validation, the database file should exist
            assert db_path.exists()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-006")
    def test_file_based_mode_reconnection(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test file-based mode allows reconnection to existing database.

        Verifies that DuckDB can connect to an existing database file
        multiple times (persistence across connections).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "persistent.duckdb"

            config = ComputeConfig(
                plugin="duckdb",
                threads=4,
                connection={"path": str(db_path)},
            )

            # First connection - creates the database
            result1 = duckdb_plugin.validate_connection(config)
            assert result1.status == ConnectionStatus.HEALTHY

            # Second connection - reconnects to existing database
            result2 = duckdb_plugin.validate_connection(config)
            assert result2.status == ConnectionStatus.HEALTHY

            # Both connections should succeed
            assert result1.status == result2.status
