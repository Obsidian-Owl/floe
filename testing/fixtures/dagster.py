"""Dagster pytest fixture for integration tests.

Provides Dagster instance fixture for tests running in Kind cluster.

Example:
    from testing.fixtures.dagster import dagster_instance_context

    def test_with_dagster():
        with dagster_instance_context() as instance:
            # Materialize assets, check run status, etc.
            pass
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from dagster import DagsterInstance


class DagsterConfig(BaseModel):
    """Configuration for Dagster instance.

    Attributes:
        host: Dagster webserver host (for GraphQL API).
        port: Dagster webserver port.
        storage_root: Root directory for ephemeral storage.
        use_ephemeral: Use ephemeral in-memory instance.
        namespace: K8s namespace where Dagster runs.
    """

    model_config = ConfigDict(frozen=True)

    host: str = Field(default_factory=lambda: os.environ.get("DAGSTER_HOST", "dagster-webserver"))
    port: int = Field(
        default_factory=lambda: int(os.environ.get("DAGSTER_PORT", "3000")),
        ge=1,
        le=65535,
    )
    storage_root: str | None = Field(default=None)
    use_ephemeral: bool = Field(default=True)
    namespace: str = Field(default="floe-test")

    @property
    def k8s_host(self) -> str:
        """Get K8s DNS hostname for Dagster webserver."""
        return f"{self.host}.{self.namespace}.svc.cluster.local"

    @property
    def graphql_url(self) -> str:
        """Get GraphQL endpoint URL."""
        return f"http://{self.host}:{self.port}/graphql"


class DagsterConnectionError(Exception):
    """Raised when Dagster connection fails."""

    pass


def create_dagster_instance(config: DagsterConfig) -> DagsterInstance:
    """Create Dagster instance from config.

    Args:
        config: Dagster configuration.

    Returns:
        DagsterInstance (ephemeral or configured).

    Raises:
        DagsterConnectionError: If instance creation fails.
    """
    try:
        from dagster import DagsterInstance
    except ImportError as e:
        raise DagsterConnectionError(
            "dagster not installed. Install with: pip install dagster"
        ) from e

    try:
        if config.use_ephemeral:
            return DagsterInstance.ephemeral(
                tempdir=config.storage_root,
            )

        # For non-ephemeral, use default instance or configured
        return DagsterInstance.get()
    except Exception as e:
        raise DagsterConnectionError(f"Failed to create Dagster instance: {e}") from e


@contextmanager
def dagster_instance_context(
    config: DagsterConfig | None = None,
) -> Generator[DagsterInstance, None, None]:
    """Context manager for Dagster instance.

    Creates instance on entry, cleans up on exit.

    Args:
        config: Optional DagsterConfig. Uses defaults if not provided.

    Yields:
        DagsterInstance.

    Example:
        with dagster_instance_context() as instance:
            # Use instance for test
            pass
    """
    if config is None:
        config = DagsterConfig()

    instance = create_dagster_instance(config)
    try:
        yield instance
    finally:
        if config.use_ephemeral:
            instance.dispose()


@contextmanager
def ephemeral_instance() -> Generator[DagsterInstance, None, None]:
    """Create a temporary ephemeral Dagster instance.

    Convenience function for quick testing without configuration.

    Yields:
        Ephemeral DagsterInstance.

    Example:
        with ephemeral_instance() as instance:
            result = execute_in_process(my_job)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DagsterConfig(
            use_ephemeral=True,
            storage_root=tmpdir,
        )
        instance = create_dagster_instance(config)
        try:
            yield instance
        finally:
            instance.dispose()


def check_webserver_health(config: DagsterConfig) -> bool:
    """Check if Dagster webserver is healthy.

    Args:
        config: Dagster configuration.

    Returns:
        True if webserver responds to health check.
    """
    import urllib.error
    import urllib.request

    health_url = f"http://{config.host}:{config.port}/server_info"

    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, TimeoutError):
        return False


def get_connection_info(config: DagsterConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: Dagster configuration.

    Returns:
        Dictionary with connection info.
    """
    return {
        "host": config.host,
        "port": config.port,
        "use_ephemeral": config.use_ephemeral,
        "storage_root": config.storage_root,
        "namespace": config.namespace,
        "k8s_host": config.k8s_host,
        "graphql_url": config.graphql_url,
    }


__all__ = [
    "DagsterConfig",
    "DagsterConnectionError",
    "check_webserver_health",
    "create_dagster_instance",
    "dagster_instance_context",
    "ephemeral_instance",
    "get_connection_info",
]
