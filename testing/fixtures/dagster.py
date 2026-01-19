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

import pytest
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


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def dagster_instance() -> Generator[DagsterInstance, None, None]:
    """Pytest fixture for ephemeral Dagster instance.

    Creates an ephemeral DagsterInstance with isolated storage for test isolation.
    The instance is automatically disposed after the test completes.

    Yields:
        Ephemeral DagsterInstance.

    Example:
        >>> def test_my_asset(dagster_instance):
        ...     result = materialize_asset(dagster_instance, [my_asset])
        ...     assert result.success
    """
    with ephemeral_instance() as instance:
        yield instance


@pytest.fixture
def dagster_config() -> DagsterConfig:
    """Create default DagsterConfig for testing.

    Returns:
        DagsterConfig with default settings.

    Example:
        >>> @pytest.fixture
        ... def config():
        ...     return dagster_config()
    """
    return DagsterConfig()


# =============================================================================
# Asset Materialization Helpers
# =============================================================================


def materialize_asset(
    instance: DagsterInstance,
    assets: list[Any],
    selection: list[str] | None = None,
    resources: dict[str, Any] | None = None,
    partition_key: str | None = None,
) -> Any:
    """Materialize assets in an ephemeral Dagster instance.

    Helper function to materialize one or more assets and return the result.
    Useful for testing asset definitions in isolation.

    Args:
        instance: DagsterInstance to use for materialization.
        assets: List of AssetsDefinition to materialize.
        selection: Optional list of asset keys to materialize (defaults to all).
        resources: Optional dict of resources to provide.
        partition_key: Optional partition key for partitioned assets.

    Returns:
        ExecuteInProcessResult with materialization status.

    Raises:
        DagsterConnectionError: If materialization fails due to configuration.

    Example:
        >>> with ephemeral_instance() as instance:
        ...     result = materialize_asset(instance, [my_asset])
        ...     assert result.success
    """
    try:
        from dagster import materialize as dagster_materialize
    except ImportError as e:
        raise DagsterConnectionError(
            "dagster not installed. Install with: pip install dagster"
        ) from e

    try:
        return dagster_materialize(
            assets,
            instance=instance,
            selection=selection,
            resources=resources or {},
            partition_key=partition_key,
        )
    except Exception as e:
        raise DagsterConnectionError(f"Asset materialization failed: {e}") from e


def materialize_to_memory(
    assets: list[Any],
    selection: list[str] | None = None,
    resources: dict[str, Any] | None = None,
    partition_key: str | None = None,
) -> Any:
    """Materialize assets without a persistent instance.

    Convenience function for quick asset testing without instance setup.
    Uses an ephemeral in-memory instance that is automatically cleaned up.

    Args:
        assets: List of AssetsDefinition to materialize.
        selection: Optional list of asset keys to materialize.
        resources: Optional dict of resources to provide.
        partition_key: Optional partition key for partitioned assets.

    Returns:
        ExecuteInProcessResult with materialization status.

    Example:
        >>> result = materialize_to_memory([my_asset])
        >>> assert result.success
        >>> output = result.output_for_node("my_asset")
    """
    with ephemeral_instance() as instance:
        return materialize_asset(
            instance,
            assets,
            selection=selection,
            resources=resources,
            partition_key=partition_key,
        )


# =============================================================================
# Job Execution Helpers
# =============================================================================


def execute_job(
    instance: DagsterInstance,
    job: Any,
    run_config: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> Any:
    """Execute a Dagster job and return the result.

    Args:
        instance: DagsterInstance to use for execution.
        job: JobDefinition to execute.
        run_config: Optional run configuration dictionary.
        resources: Optional dict of resources to provide.

    Returns:
        ExecuteInProcessResult with job execution status.

    Raises:
        DagsterConnectionError: If job execution fails due to configuration.

    Example:
        >>> with ephemeral_instance() as instance:
        ...     result = execute_job(instance, my_job)
        ...     assert result.success
    """
    try:
        return job.execute_in_process(
            instance=instance,
            run_config=run_config,
            resources=resources or {},
        )
    except Exception as e:
        raise DagsterConnectionError(f"Job execution failed: {e}") from e


def execute_job_to_memory(
    job: Any,
    run_config: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> Any:
    """Execute a job without a persistent instance.

    Convenience function for quick job testing without instance setup.

    Args:
        job: JobDefinition to execute.
        run_config: Optional run configuration dictionary.
        resources: Optional dict of resources to provide.

    Returns:
        ExecuteInProcessResult with job execution status.

    Example:
        >>> result = execute_job_to_memory(my_job)
        >>> assert result.success
    """
    with ephemeral_instance() as instance:
        return execute_job(instance, job, run_config=run_config, resources=resources)


# =============================================================================
# Run Status Helpers
# =============================================================================


def wait_for_run_completion(
    instance: DagsterInstance,
    run_id: str,
    timeout: float = 60.0,
    poll_interval: float = 1.0,
) -> str:
    """Wait for a Dagster run to complete with polling.

    Polls the run status until it reaches a terminal state (SUCCESS, FAILURE,
    or CANCELED) or the timeout is exceeded.

    Args:
        instance: DagsterInstance to query.
        run_id: The run ID to monitor.
        timeout: Maximum time to wait in seconds (default 60s).
        poll_interval: Time between status checks in seconds (default 1s).

    Returns:
        Final run status string (SUCCESS, FAILURE, CANCELED).

    Raises:
        DagsterConnectionError: If timeout exceeded or run not found.

    Example:
        >>> run_id = launch_run(instance, job)
        >>> status = wait_for_run_completion(instance, run_id, timeout=30.0)
        >>> assert status == "SUCCESS"
    """
    import time

    terminal_statuses = {"SUCCESS", "FAILURE", "CANCELED"}
    start_time = time.monotonic()

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= timeout:
            raise DagsterConnectionError(
                f"Run {run_id} did not complete within {timeout}s timeout"
            )

        run = instance.get_run_by_id(run_id)
        if run is None:
            raise DagsterConnectionError(f"Run {run_id} not found")

        status = run.status.value if hasattr(run.status, "value") else str(run.status)

        if status in terminal_statuses:
            return status

        time.sleep(poll_interval)


def get_run_status(instance: DagsterInstance, run_id: str) -> str:
    """Get the current status of a Dagster run.

    Args:
        instance: DagsterInstance to query.
        run_id: The run ID to check.

    Returns:
        Run status string.

    Raises:
        DagsterConnectionError: If run not found.

    Example:
        >>> status = get_run_status(instance, run_id)
        >>> print(f"Run status: {status}")
    """
    run = instance.get_run_by_id(run_id)
    if run is None:
        raise DagsterConnectionError(f"Run {run_id} not found")

    return run.status.value if hasattr(run.status, "value") else str(run.status)


__all__ = [
    # Configuration
    "DagsterConfig",
    "DagsterConnectionError",
    # Instance creation
    "check_webserver_health",
    "create_dagster_instance",
    "dagster_instance_context",
    "ephemeral_instance",
    "get_connection_info",
    # Pytest fixtures
    "dagster_instance",
    "dagster_config",
    # Asset materialization
    "materialize_asset",
    "materialize_to_memory",
    # Job execution
    "execute_job",
    "execute_job_to_memory",
    # Run status
    "wait_for_run_completion",
    "get_run_status",
]
