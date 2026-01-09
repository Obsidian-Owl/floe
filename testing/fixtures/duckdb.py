"""DuckDB pytest fixture for unit and integration tests.

Provides DuckDB connection fixture that works both in-memory (unit tests)
and with file-based databases (integration tests).

Example:
    from testing.fixtures.duckdb import duckdb_connection_context

    def test_with_duckdb():
        with duckdb_connection_context() as conn:
            result = conn.execute("SELECT 42").fetchone()
            assert result[0] == 42
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import duckdb


class DuckDBConfig(BaseModel):
    """Configuration for DuckDB connection.

    Attributes:
        database: Database path or `:memory:` for in-memory.
        read_only: Open database in read-only mode.
        extensions: List of extensions to load.
        config: Additional DuckDB configuration options.
    """

    model_config = ConfigDict(frozen=True)

    database: str = Field(
        default_factory=lambda: os.environ.get("DUCKDB_DATABASE", ":memory:")
    )
    read_only: bool = Field(default=False)
    extensions: tuple[str, ...] = Field(default=())
    config: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_memory(self) -> bool:
        """Check if using in-memory database."""
        return self.database == ":memory:"


class DuckDBConnectionError(Exception):
    """Raised when DuckDB connection fails."""

    pass


def create_duckdb_connection(config: DuckDBConfig) -> duckdb.DuckDBPyConnection:
    """Create DuckDB connection from config.

    Args:
        config: DuckDB configuration.

    Returns:
        DuckDB connection instance.

    Raises:
        DuckDBConnectionError: If connection fails.
    """
    try:
        import duckdb
    except ImportError as e:
        raise DuckDBConnectionError(
            "duckdb not installed. Install with: pip install duckdb"
        ) from e

    try:
        conn = duckdb.connect(
            database=config.database,
            read_only=config.read_only,
            config=config.config,
        )

        # Load extensions
        for ext in config.extensions:
            conn.execute(f"INSTALL {ext}")
            conn.execute(f"LOAD {ext}")

        return conn
    except Exception as e:
        raise DuckDBConnectionError(
            f"Failed to create DuckDB connection for {config.database}: {e}"
        ) from e


@contextmanager
def duckdb_connection_context(
    config: DuckDBConfig | None = None,
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Context manager for DuckDB connection.

    Creates connection on entry, closes it on exit.

    Args:
        config: Optional DuckDBConfig. Uses defaults if not provided.

    Yields:
        DuckDB connection instance.

    Example:
        with duckdb_connection_context() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
    """
    if config is None:
        config = DuckDBConfig()

    conn = create_duckdb_connection(config)
    try:
        yield conn
    finally:
        conn.close()


def create_memory_connection(
    extensions: tuple[str, ...] = (),
) -> duckdb.DuckDBPyConnection:
    """Create in-memory DuckDB connection.

    Convenience function for quick in-memory database.

    Args:
        extensions: Optional extensions to load.

    Returns:
        In-memory DuckDB connection.
    """
    config = DuckDBConfig(database=":memory:", extensions=extensions)
    return create_duckdb_connection(config)


def create_file_connection(
    path: str | Path,
    *,
    read_only: bool = False,
    extensions: tuple[str, ...] = (),
) -> duckdb.DuckDBPyConnection:
    """Create file-based DuckDB connection.

    Args:
        path: Path to database file.
        read_only: Open in read-only mode.
        extensions: Optional extensions to load.

    Returns:
        File-based DuckDB connection.
    """
    config = DuckDBConfig(
        database=str(path),
        read_only=read_only,
        extensions=extensions,
    )
    return create_duckdb_connection(config)


def execute_script(
    conn: duckdb.DuckDBPyConnection,
    script: str,
) -> None:
    """Execute a SQL script (multiple statements).

    Args:
        conn: DuckDB connection.
        script: SQL script with multiple statements.
    """
    # DuckDB can execute multiple statements in one call
    conn.execute(script)


def get_connection_info(config: DuckDBConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: DuckDB configuration.

    Returns:
        Dictionary with connection info.
    """
    return {
        "database": config.database,
        "is_memory": config.is_memory,
        "read_only": config.read_only,
        "extensions": list(config.extensions),
    }


__all__ = [
    "DuckDBConfig",
    "DuckDBConnectionError",
    "create_duckdb_connection",
    "create_file_connection",
    "create_memory_connection",
    "duckdb_connection_context",
    "execute_script",
    "get_connection_info",
]
