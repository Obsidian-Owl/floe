"""Unit tests for DuckDB fixture.

Tests for testing.fixtures.duckdb module including DuckDBConfig,
connection creation, and in-memory database operations.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from testing.fixtures.duckdb import (
    DuckDBConfig,
    DuckDBConnectionError,
    create_duckdb_connection,
    create_file_connection,
    create_memory_connection,
    duckdb_connection_context,
    execute_script,
    get_connection_info,
)


class TestDuckDBConfig:
    """Tests for DuckDBConfig model."""

    @pytest.mark.requirement("9c-FR-011")
    def test_default_config_uses_memory(self) -> None:
        """Test default config uses in-memory database."""
        config = DuckDBConfig()
        assert config.database == ":memory:"
        assert config.is_memory is True

    @pytest.mark.requirement("9c-FR-011")
    def test_custom_database_path(self) -> None:
        """Test config with custom database path."""
        config = DuckDBConfig(database="/tmp/test.duckdb")
        assert config.database == "/tmp/test.duckdb"
        assert config.is_memory is False

    @pytest.mark.requirement("9c-FR-011")
    def test_read_only_config(self) -> None:
        """Test read-only configuration."""
        config = DuckDBConfig(read_only=True)
        assert config.read_only is True

    @pytest.mark.requirement("9c-FR-011")
    def test_extensions_config(self) -> None:
        """Test extensions configuration."""
        config = DuckDBConfig(extensions=("json", "parquet"))
        assert "json" in config.extensions
        assert "parquet" in config.extensions

    @pytest.mark.requirement("9c-FR-011")
    def test_frozen_model(self) -> None:
        """Test DuckDBConfig is immutable."""
        config = DuckDBConfig()
        with pytest.raises(Exception):
            config.database = "/tmp/other.duckdb"  # type: ignore[misc]


class TestCreateDuckDBConnection:
    """Tests for create_duckdb_connection function."""

    @pytest.mark.requirement("9c-FR-011")
    def test_creates_in_memory_connection(self) -> None:
        """Test creating in-memory DuckDB connection."""
        pytest.importorskip("duckdb")
        config = DuckDBConfig()
        conn = create_duckdb_connection(config)
        try:
            result = conn.execute("SELECT 42 AS answer").fetchone()
            assert result is not None
            assert result[0] == 42
        finally:
            conn.close()

    @pytest.mark.requirement("9c-FR-011")
    def test_creates_file_connection(self, tmp_path: Path) -> None:
        """Test creating file-based DuckDB connection."""
        pytest.importorskip("duckdb")
        db_path = tmp_path / "test.duckdb"
        config = DuckDBConfig(database=str(db_path))
        conn = create_duckdb_connection(config)
        try:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")
            result = conn.execute("SELECT * FROM test").fetchone()
            assert result is not None
            assert result[0] == 1
        finally:
            conn.close()
        # File should exist after connection
        assert db_path.exists()

    @pytest.mark.requirement("9c-FR-011")
    def test_connection_config_options(self) -> None:
        """Test connection with custom config options."""
        pytest.importorskip("duckdb")
        config = DuckDBConfig(
            database=":memory:",
            config={"threads": 2},
        )
        conn = create_duckdb_connection(config)
        try:
            # Connection should work with custom config
            result = conn.execute("SELECT 1").fetchone()
            assert result is not None
        finally:
            conn.close()


class TestDuckDBConnectionContext:
    """Tests for duckdb_connection_context context manager."""

    @pytest.mark.requirement("9c-FR-011")
    def test_context_manager_creates_connection(self) -> None:
        """Test context manager creates usable connection."""
        pytest.importorskip("duckdb")
        with duckdb_connection_context() as conn:
            result = conn.execute("SELECT 'hello'").fetchone()
            assert result is not None
            assert result[0] == "hello"

    @pytest.mark.requirement("9c-FR-011")
    def test_context_manager_closes_connection(self) -> None:
        """Test context manager closes connection on exit."""
        pytest.importorskip("duckdb")
        # Get a reference to the connection
        with duckdb_connection_context() as conn:
            conn.execute("CREATE TABLE test_close (id INTEGER)")
            # Connection should be open here
            conn.execute("SELECT 1")
        # After context, connection should be closed
        # Attempting to use it should fail
        with pytest.raises(Exception):
            conn.execute("SELECT 1")

    @pytest.mark.requirement("9c-FR-011")
    def test_context_manager_with_custom_config(self) -> None:
        """Test context manager with custom configuration."""
        pytest.importorskip("duckdb")
        config = DuckDBConfig(database=":memory:")
        with duckdb_connection_context(config) as conn:
            result = conn.execute("SELECT 42").fetchone()
            assert result is not None
            assert result[0] == 42


class TestCreateMemoryConnection:
    """Tests for create_memory_connection helper."""

    @pytest.mark.requirement("9c-FR-011")
    def test_creates_memory_connection(self) -> None:
        """Test creating in-memory connection."""
        pytest.importorskip("duckdb")
        conn = create_memory_connection()
        try:
            result = conn.execute("SELECT 1 + 1").fetchone()
            assert result is not None
            assert result[0] == 2
        finally:
            conn.close()


class TestCreateFileConnection:
    """Tests for create_file_connection helper."""

    @pytest.mark.requirement("9c-FR-011")
    def test_creates_file_connection(self, tmp_path: Path) -> None:
        """Test creating file-based connection."""
        pytest.importorskip("duckdb")
        db_path = tmp_path / "test.duckdb"
        conn = create_file_connection(db_path)
        try:
            conn.execute("CREATE TABLE file_test (value TEXT)")
            conn.execute("INSERT INTO file_test VALUES ('test')")
        finally:
            conn.close()
        assert db_path.exists()

    @pytest.mark.requirement("9c-FR-011")
    def test_read_only_file_connection(self, tmp_path: Path) -> None:
        """Test creating read-only file connection."""
        pytest.importorskip("duckdb")
        db_path = tmp_path / "readonly.duckdb"
        # First create the database
        conn = create_file_connection(db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.close()

        # Now open read-only
        conn = create_file_connection(db_path, read_only=True)
        try:
            result = conn.execute("SELECT * FROM test").fetchone()
            assert result is not None
            # Write should fail
            with pytest.raises(Exception):
                conn.execute("INSERT INTO test VALUES (2)")
        finally:
            conn.close()


class TestExecuteScript:
    """Tests for execute_script function."""

    @pytest.mark.requirement("9c-FR-011")
    def test_execute_multi_statement_script(self) -> None:
        """Test executing script with multiple statements."""
        pytest.importorskip("duckdb")
        conn = create_memory_connection()
        try:
            script = """
            CREATE TABLE script_test (id INTEGER, name TEXT);
            INSERT INTO script_test VALUES (1, 'one');
            INSERT INTO script_test VALUES (2, 'two');
            """
            execute_script(conn, script)
            result = conn.execute("SELECT COUNT(*) FROM script_test").fetchone()
            assert result is not None
            assert result[0] == 2
        finally:
            conn.close()


class TestGetConnectionInfo:
    """Tests for get_connection_info function."""

    @pytest.mark.requirement("9c-FR-011")
    def test_returns_connection_info(self) -> None:
        """Test get_connection_info returns expected fields."""
        config = DuckDBConfig(
            database="/tmp/test.duckdb",
            extensions=("json",),
        )
        info = get_connection_info(config)
        assert info["database"] == "/tmp/test.duckdb"
        assert info["is_memory"] is False
        assert "json" in info["extensions"]

    @pytest.mark.requirement("9c-FR-011")
    def test_memory_database_info(self) -> None:
        """Test connection info for in-memory database."""
        config = DuckDBConfig()
        info = get_connection_info(config)
        assert info["database"] == ":memory:"
        assert info["is_memory"] is True
