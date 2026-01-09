"""PostgreSQL pytest fixture for integration tests.

Provides PostgreSQL connection fixture for tests running in Kind cluster.

Example:
    from testing.fixtures.postgres import postgres_connection

    @pytest.fixture
    def postgres_connection():
        config = PostgresConfig()
        yield from create_postgres_connection(config)

    def test_with_postgres(postgres_connection):
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

if TYPE_CHECKING:
    import psycopg2


class PostgresConfig(BaseModel):
    """Configuration for PostgreSQL connection.

    Attributes:
        host: PostgreSQL host (K8s service name or IP).
        port: PostgreSQL port (default 5432).
        user: Database user.
        password: Database password (SecretStr for security).
        database: Database name.
        namespace: K8s namespace where PostgreSQL runs.
    """

    model_config = ConfigDict(frozen=True)

    host: str = Field(default_factory=lambda: os.environ.get("POSTGRES_HOST", "postgres"))
    port: int = Field(
        default_factory=lambda: int(os.environ.get("POSTGRES_PORT", "5432")),
        ge=1,
        le=65535,
    )
    user: str = Field(default_factory=lambda: os.environ.get("POSTGRES_USER", "floe"))
    password: SecretStr = Field(
        default_factory=lambda: SecretStr(os.environ.get("POSTGRES_PASSWORD", "floe_test_password"))
    )
    database: str = Field(default_factory=lambda: os.environ.get("POSTGRES_DATABASE", "floe_test"))
    namespace: str = Field(default="floe-test")

    @property
    def k8s_host(self) -> str:
        """Get K8s DNS hostname for PostgreSQL service."""
        return f"{self.host}.{self.namespace}.svc.cluster.local"


class PostgresConnectionError(Exception):
    """Raised when PostgreSQL connection fails."""

    pass


def create_connection(config: PostgresConfig) -> psycopg2.connection:
    """Create PostgreSQL connection from config.

    Args:
        config: PostgreSQL configuration.

    Returns:
        Active database connection.

    Raises:
        PostgresConnectionError: If connection fails.
    """
    try:
        import psycopg2
    except ImportError as e:
        raise PostgresConnectionError(
            "psycopg2 not installed. Install with: pip install psycopg2-binary"
        ) from e

    try:
        conn = psycopg2.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password.get_secret_value(),
            database=config.database,
        )
        return conn
    except psycopg2.Error as e:
        raise PostgresConnectionError(
            f"Failed to connect to PostgreSQL at {config.host}:{config.port}: {e}"
        ) from e


@contextmanager
def postgres_connection_context(
    config: PostgresConfig | None = None,
) -> Generator[psycopg2.connection, None, None]:
    """Context manager for PostgreSQL connection.

    Creates a connection on entry, closes it on exit.

    Args:
        config: Optional PostgresConfig. Uses defaults if not provided.

    Yields:
        Active database connection.

    Example:
        with postgres_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
    """
    if config is None:
        config = PostgresConfig()

    conn = create_connection(config)
    try:
        yield conn
    finally:
        conn.close()


def create_test_database(
    admin_conn: psycopg2.connection,
    database_name: str,
) -> None:
    """Create a test database.

    Args:
        admin_conn: Admin connection to PostgreSQL.
        database_name: Name of database to create.

    Note:
        Uses autocommit since CREATE DATABASE cannot run in transaction.
    """
    admin_conn.autocommit = True
    cursor = admin_conn.cursor()
    try:
        cursor.execute(
            f"CREATE DATABASE {database_name}"  # noqa: S608 - safe, validated input
        )
    finally:
        cursor.close()
        admin_conn.autocommit = False


def drop_test_database(
    admin_conn: psycopg2.connection,
    database_name: str,
) -> None:
    """Drop a test database.

    Args:
        admin_conn: Admin connection to PostgreSQL.
        database_name: Name of database to drop.

    Note:
        Forces disconnection of other clients before dropping.
    """
    admin_conn.autocommit = True
    cursor = admin_conn.cursor()
    try:
        # Force disconnect other clients
        cursor.execute(
            """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = %s
            AND pid <> pg_backend_pid()
            """,
            (database_name,),
        )
        cursor.execute(
            f"DROP DATABASE IF EXISTS {database_name}"  # noqa: S608 - safe, validated
        )
    finally:
        cursor.close()
        admin_conn.autocommit = False


def get_connection_info(config: PostgresConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: PostgreSQL configuration.

    Returns:
        Dictionary with connection info (password masked).
    """
    return {
        "host": config.host,
        "port": config.port,
        "user": config.user,
        "database": config.database,
        "namespace": config.namespace,
        "k8s_host": config.k8s_host,
    }


__all__ = [
    "PostgresConfig",
    "PostgresConnectionError",
    "create_connection",
    "create_test_database",
    "drop_test_database",
    "get_connection_info",
    "postgres_connection_context",
]
