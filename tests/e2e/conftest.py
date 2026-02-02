"""E2E test configuration and fixtures.

This module provides fixtures for full end-to-end testing of the floe platform.
E2E tests validate complete workflows: compile → deploy → run → validate.

All E2E tests require the full platform stack running in K8s (Kind cluster).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

# Import the polling utilities
from testing.fixtures.polling import wait_for_condition


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for E2E tests."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end (requires full platform stack)",
    )


@pytest.fixture(scope="session")
def e2e_namespace() -> str:
    """Generate unique namespace for E2E test session.

    Returns:
        Unique namespace string for test isolation.
    """
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def platform_namespace() -> str:
    """Get K8s namespace for E2E tests.

    Returns namespace from FLOE_E2E_NAMESPACE env var, or generates a unique one.

    Returns:
        Kubernetes namespace string for platform services.

    Example:
        FLOE_E2E_NAMESPACE=floe-test make test-e2e
    """
    env_namespace = os.environ.get("FLOE_E2E_NAMESPACE")
    if env_namespace:
        return env_namespace
    return f"floe-e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def wait_for_service() -> Callable[..., None]:
    """Create helper fixture for waiting on HTTP services.

    Returns callable that polls a URL until HTTP 200 or timeout.

    Returns:
        Callable that waits for service availability.

    Example:
        wait_for_service("http://localhost:3000/health", timeout=60)
    """

    def _wait_for_service(
        url: str,
        timeout: float = 60.0,
        description: str | None = None,
    ) -> None:
        """Wait for HTTP service to become available.

        Args:
            url: URL to poll for HTTP 200 response.
            timeout: Maximum wait time in seconds. Defaults to 60.0.
            description: Description for error messages.

        Raises:
            TimeoutError: If service not ready within timeout.
        """
        effective_description = description or f"service at {url}"

        def check_http() -> bool:
            try:
                response = httpx.get(url, timeout=5.0)
                return response.status_code < 500
            except (httpx.HTTPError, OSError):
                return False

        wait_for_condition(
            check_http,
            timeout=timeout,
            description=effective_description,
        )

    return _wait_for_service


@pytest.fixture(scope="session")
def compiled_artifacts(
    tmp_path_factory: pytest.TempPathFactory,
) -> Callable[[Path], Any]:
    """Create factory fixture for compiling floe.yaml files.

    Returns callable that compiles a floe.yaml path and returns CompiledArtifacts.

    Args:
        tmp_path_factory: pytest fixture for temp directories.

    Returns:
        Factory function that compiles specs.

    Example:
        artifacts = compiled_artifacts(Path("demo/floe.yaml"))
        assert artifacts.version == "0.5.0"
    """

    def _compile_artifacts(spec_path: Path) -> Any:
        """Compile floe.yaml to CompiledArtifacts.

        Args:
            spec_path: Path to floe.yaml file.

        Returns:
            CompiledArtifacts object.

        Raises:
            ValidationError: If spec validation fails.
            CompilationError: If compilation fails.
        """
        # Import here to fail properly if not available
        from datetime import datetime, timezone

        from floe_core.schemas.compiled_artifacts import (
            CompilationMetadata,
            CompiledArtifacts,
            ObservabilityConfig,
            PluginRef,
            ProductIdentity,
            ResolvedPlugins,
        )
        from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig

        # For E2E tests, create minimal valid CompiledArtifacts
        # (full compilation logic would use the actual compiler once available)
        artifacts = CompiledArtifacts(
            version="0.5.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(timezone.utc),
                floe_version="0.5.0",
                source_hash="sha256:test",
                product_name=spec_path.parent.name,
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id=f"default.{spec_path.parent.name}",
                domain="default",
                repository="file://localhost",
                namespace_registered=False,
            ),
            mode="simple",
            inheritance_chain=[],
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    resource_attributes=ResourceAttributes(
                        service_name=spec_path.parent.name,
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="default",
                        floe_product_name=spec_path.parent.name,
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace=spec_path.parent.name,
            ),
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),
                orchestrator=PluginRef(type="dagster", version="1.5.0"),
            ),
            dbt_profiles={},
        )

        return artifacts

    return _compile_artifacts


@pytest.fixture(scope="session")
def dagster_client(wait_for_service: Callable[..., None]) -> Any:
    """Create Dagster GraphQL client.

    Waits for Dagster webserver to be ready, then returns client.
    Fails if Dagster not available.

    Args:
        wait_for_service: Helper fixture for service polling.

    Returns:
        DagsterGraphQLClient instance.

    Raises:
        TimeoutError: If Dagster not ready within timeout.

    Example:
        status = dagster_client.get_run_status(run_id)
    """
    url = os.environ.get("DAGSTER_URL", "http://localhost:3000")
    wait_for_service(f"{url}/server_info", timeout=60, description="Dagster webserver")

    # Import here to fail properly if not installed
    try:
        import dagster_graphql
    except ImportError:
        pytest.fail(
            "dagster_graphql package not installed.\n"
            "Install with: uv pip install dagster-graphql\n"
            "This is a REQUIRED dependency for E2E tests."
        )

    # Extract host:port from URL
    host = url.replace("http://", "").replace("https://", "")
    return dagster_graphql.DagsterGraphQLClient(host)


@pytest.fixture(scope="session")
def polaris_client(wait_for_service: Callable[..., None]) -> Any:
    """Create Polaris REST catalog client.

    Waits for Polaris to be ready, then returns PyIceberg REST catalog.
    Fails if Polaris not available.

    Args:
        wait_for_service: Helper fixture for service polling.

    Returns:
        PyIceberg REST catalog instance.

    Raises:
        TimeoutError: If Polaris not ready within timeout.

    Example:
        tables = polaris_client.list_tables("my_namespace")
    """
    polaris_url = os.environ.get("POLARIS_URL", "http://localhost:8181")
    wait_for_service(
        f"{polaris_url}/api/catalog/v1/config",
        timeout=60,
        description="Polaris catalog",
    )

    # Import here to fail properly if not installed
    try:
        from pyiceberg import catalog as pyiceberg_catalog
    except ImportError:
        pytest.fail(
            "pyiceberg package not installed.\n"
            "Install with: uv pip install pyiceberg\n"
            "This is a REQUIRED dependency for E2E tests."
        )

    # Load catalog with REST configuration
    default_cred = "test-admin:test-secret"
    catalog = pyiceberg_catalog.load_catalog(
        "polaris",
        **{
            "type": "rest",
            "uri": f"{polaris_url}/api/catalog",
            "credential": os.environ.get("POLARIS_CREDENTIAL", default_cred),
            "scope": "PRINCIPAL_ROLE:ALL",
            "warehouse": os.environ.get("POLARIS_WAREHOUSE", "floe-e2e"),
        },
    )

    return catalog


@pytest.fixture(scope="session")
def marquez_client(wait_for_service: Callable[..., None]) -> httpx.Client:
    """Create Marquez HTTP client.

    Waits for Marquez API to be ready, then returns httpx client.
    Fails if Marquez not available.

    Args:
        wait_for_service: Helper fixture for service polling.

    Returns:
        httpx.Client configured for Marquez API.

    Raises:
        TimeoutError: If Marquez not ready within timeout.

    Example:
        response = marquez_client.get("/api/v1/namespaces")
        namespaces = response.json()["namespaces"]
    """
    marquez_url = os.environ.get("MARQUEZ_URL", "http://localhost:5001")
    wait_for_service(f"{marquez_url}/api/v1/namespaces", timeout=60, description="Marquez API (requires port-forward: kubectl port-forward svc/marquez 5001:5001 -n floe-test)")

    return httpx.Client(base_url=marquez_url, timeout=30.0)


@pytest.fixture(scope="session")
def jaeger_client(wait_for_service: Callable[..., None]) -> httpx.Client:
    """Create Jaeger query HTTP client.

    Waits for Jaeger query API to be ready, then returns httpx client.
    Fails if Jaeger not available.

    Args:
        wait_for_service: Helper fixture for service polling.

    Returns:
        httpx.Client configured for Jaeger query API.

    Raises:
        TimeoutError: If Jaeger not ready within timeout.

    Example:
        response = jaeger_client.get("/api/services")
        services = response.json()["data"]
    """
    jaeger_url = os.environ.get("JAEGER_URL", "http://localhost:16686")
    wait_for_service(f"{jaeger_url}/api/services", timeout=60, description="Jaeger query API")

    return httpx.Client(base_url=jaeger_url, timeout=30.0)
