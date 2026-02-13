"""E2E test configuration and fixtures.

This module provides fixtures for full end-to-end testing of the floe platform.
E2E tests validate complete workflows: compile → deploy → run → validate.

All E2E tests require the full platform stack running in K8s (Kind cluster).
"""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Callable, Generator
from typing import Any

import httpx
import pytest

from testing.fixtures.polling import wait_for_condition


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for E2E tests."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end (requires full platform stack)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Check for common test quality anti-patterns during collection.

    Scans test source code for TQR violations and issues warnings.
    This is ADVISORY ONLY - does not fail tests.

    Args:
        config: pytest configuration object.
        items: List of collected test items.
    """
    import inspect
    import re
    import warnings

    violations: list[str] = []

    for item in items:
        if not isinstance(item, pytest.Function):
            continue

        test_func = item.function
        test_name = item.nodeid

        try:
            source = inspect.getsource(test_func)
        except (OSError, TypeError):
            # Can't get source (e.g., dynamically generated)
            continue

        # TQR-001: Bare existence checks (assert X is not None without further checks)
        if re.search(r"assert\s+\w+\s+is\s+not\s+None", source):
            # Check if this is the ONLY assertion (crude heuristic)
            assertion_count = len(re.findall(r"\bassert\s+", source))
            if assertion_count == 1:
                violations.append(
                    f"TQR WARNING: {test_name} - TQR-001 violation: "
                    "Bare existence check (assert X is not None without behavioral validation)"
                )

        # TQR-002: Missing data content validation (checks len() > 0 but not content)
        if re.search(r"assert\s+len\([^)]+\)\s*>\s*0", source):
            # Check if there's any content validation after the length check
            if not re.search(r"\[\d+\]|\[.+\]|\.get\(", source):
                violations.append(
                    f"TQR WARNING: {test_name} - TQR-002 violation: "
                    "Length check without data content validation"
                )

        # TQR-010: dry_run=True in E2E tests
        if re.search(r"dry_run\s*=\s*True", source):
            violations.append(
                f"TQR WARNING: {test_name} - TQR-010 violation: "
                "dry_run=True found in E2E test (E2E should execute real operations)"
            )

        # TQR-004: pytest.skip usage
        if re.search(r"pytest\.skip\(|@pytest\.mark\.skip", source):
            violations.append(
                f"TQR WARNING: {test_name} - TQR-004 violation: "
                "pytest.skip() usage (tests should FAIL, never skip per constitution)"
            )

    # Emit all warnings
    for violation in violations:
        warnings.warn(violation, UserWarning, stacklevel=2)

    # Print summary if violations found
    if violations:
        print(f"\n{'=' * 70}")
        print(f"TQR CHECK SUMMARY: {len(violations)} potential quality issues detected")
        print("=" * 70)
        for violation in violations:
            print(violation)
        print("=" * 70)
        print("These are ADVISORY warnings. Review and fix as needed.")
        print("=" * 70)


def run_kubectl(
    args: list[str],
    namespace: str | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run kubectl command with optional namespace.

    Shared helper for E2E tests. Uses the real kubectl binary — no mocks.

    Args:
        args: kubectl arguments (e.g., ["get", "pods"]).
        namespace: K8s namespace to target. If provided, adds -n flag.
        timeout: Command timeout in seconds. Defaults to 60.

    Returns:
        Completed process result with stdout, stderr, and returncode.
    """
    cmd = ["kubectl"]
    if namespace:
        cmd.extend(["-n", namespace])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_helm(
    args: list[str],
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    """Run helm command with timeout.

    Shared helper for E2E tests. Uses the real helm binary — no mocks.

    Args:
        args: helm arguments (e.g., ["status", "floe-platform"]).
        timeout: Command timeout in seconds. Defaults to 900.

    Returns:
        Completed process result with stdout, stderr, and returncode.
    """
    return subprocess.run(
        ["helm"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.fixture(scope="session", autouse=True)
def helm_release_health() -> None:
    """Check Helm release health before E2E suite starts.

    Detects stuck Helm releases (pending-upgrade, pending-install, failed)
    and recovers via rollback. Runs automatically before all E2E tests.

    This prevents cascading test failures when a previous test run left
    the Helm release in a broken state (RC-3).

    When no K8s cluster is available (e.g., running DuckDB-only dbt tests
    locally), the fixture returns early as a no-op. K8s-dependent tests
    will still fail at their own service fixtures.

    Raises:
        RuntimeError: If recovery fails after detecting stuck state.
        ValueError: If helm status output is not valid JSON.
    """
    # Guard: skip Helm recovery when no K8s cluster is reachable.
    # This allows DuckDB-only E2E tests to run without a Kind cluster.
    try:
        cluster_check = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if cluster_check.returncode != 0:
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # kubectl not installed or cluster unreachable
        return

    from testing.fixtures.helm import recover_stuck_helm_release

    release = "floe-platform"
    namespace = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")

    recover_stuck_helm_release(
        release,
        namespace,
        rollback_timeout="5m",
        helm_runner=run_helm,
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
def k8s_namespace_teardown(platform_namespace: str) -> Generator[str, None, None]:
    """Create and teardown K8s namespace for E2E tests.

    Creates a fresh K8s namespace at session start and tears it down after all
    tests complete, ensuring full isolation between test suites per FR-008.

    Args:
        platform_namespace: Namespace string from platform_namespace fixture.

    Yields:
        Kubernetes namespace string for platform services.

    Raises:
        subprocess.CalledProcessError: If namespace creation fails.

    Example:
        def test_deployment(k8s_namespace_teardown: str):
            # Namespace already created, use it
            namespace = k8s_namespace_teardown
            kubectl_apply(namespace)
    """
    namespace = platform_namespace

    # Create namespace if it doesn't exist
    try:
        # Check if namespace exists
        result = subprocess.run(
            ["kubectl", "get", "namespace", namespace],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Namespace doesn't exist, create it
            print(f"Creating K8s namespace: {namespace}")
            subprocess.run(
                ["kubectl", "create", "namespace", namespace],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"K8s namespace created: {namespace}")
        else:
            print(f"K8s namespace already exists: {namespace}")

    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"Failed to create K8s namespace {namespace}: {e.stderr}\n"
            "Ensure kubectl is installed and cluster is accessible."
        )

    yield namespace

    # Teardown: delete namespace after all tests complete
    try:
        print(f"Tearing down K8s namespace: {namespace}")
        subprocess.run(
            ["kubectl", "delete", "namespace", namespace, "--ignore-not-found=true"],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for namespace deletion
        )
        print(f"K8s namespace deleted: {namespace}")
    except subprocess.CalledProcessError as e:
        # Log error but don't fail teardown (namespace may already be deleted)
        print(f"Warning: Failed to delete namespace {namespace}: {e.stderr}")
    except subprocess.TimeoutExpired:
        print(f"Warning: Namespace deletion timed out for {namespace}")


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
    # Extended timeout for CI environments where startup may be slower
    polaris_timeout = float(os.environ.get("POLARIS_TIMEOUT", "90"))
    wait_for_service(
        f"{polaris_url}/api/catalog/v1/config",
        timeout=polaris_timeout,
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
    # Demo credentials for local testing only - production uses K8s secrets
    default_cred = "demo-admin:demo-secret"  # pragma: allowlist secret
    minio_url = os.environ.get("MINIO_URL", "http://localhost:9000")
    catalog = pyiceberg_catalog.load_catalog(
        "polaris",
        **{
            "type": "rest",
            "uri": f"{polaris_url}/api/catalog",
            "credential": os.environ.get("POLARIS_CREDENTIAL", default_cred),
            "scope": "PRINCIPAL_ROLE:ALL",
            "warehouse": os.environ.get("POLARIS_WAREHOUSE", "floe-e2e"),
            "s3.endpoint": minio_url,
            # MinIO credentials for local testing - production uses IAM/IRSA
            "s3.access-key-id": os.environ.get(  # pragma: allowlist secret
                "AWS_ACCESS_KEY_ID", "minioadmin"
            ),
            "s3.secret-access-key": os.environ.get(  # pragma: allowlist secret
                "AWS_SECRET_ACCESS_KEY", "minioadmin123"
            ),
            "s3.region": os.environ.get("AWS_REGION", "us-east-1"),
            "s3.path-style-access": "true",
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
    marquez_url = os.environ.get("MARQUEZ_URL", "http://localhost:5000")
    marquez_timeout = float(os.environ.get("MARQUEZ_TIMEOUT", "90"))
    marquez_description = (
        "Marquez API (requires port-forward: "
        "kubectl port-forward svc/floe-platform-marquez 5000:5000 -n floe-test)"
    )
    wait_for_service(
        f"{marquez_url}/api/v1/namespaces",
        timeout=marquez_timeout,
        description=marquez_description,
    )

    return httpx.Client(base_url=marquez_url, timeout=30.0)


@pytest.fixture(scope="session")
def polaris_with_write_grants(
    polaris_client: Any,
    wait_for_service: Callable[..., None],
) -> Any:
    """Polaris client with write delegation grants configured.

    Sets up the test principal with CREATE_TABLE_DIRECT_WITH_WRITE_DELEGATION
    permission needed for schema evolution tests.

    Args:
        polaris_client: PyIceberg REST catalog fixture.
        wait_for_service: Helper fixture for service polling.

    Returns:
        PyIceberg REST catalog with write permissions granted.

    Raises:
        AssertionError: If RBAC setup fails.

    Example:
        table = polaris_with_write_grants.create_table(...)
    """
    polaris_url = os.environ.get("POLARIS_URL", "http://localhost:8181")

    # Get admin token
    token_response = httpx.post(
        f"{polaris_url}/api/catalog/v1/oauth/tokens",
        data={
            "grant_type": "client_credentials",
            "client_id": "demo-admin",  # pragma: allowlist secret
            "client_secret": "demo-secret",  # pragma: allowlist secret
            "scope": "PRINCIPAL_ROLE:ALL",
        },
        timeout=10.0,
    )
    if token_response.status_code != 200:
        pytest.fail(f"Failed to get Polaris admin token: {token_response.text}")

    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Grant catalog-level privileges to catalog_admin role
    catalog_name = os.environ.get("POLARIS_WAREHOUSE", "floe-e2e")
    grant_url = (
        f"{polaris_url}/api/management/v1/catalogs/"
        f"{catalog_name}/catalog-roles/catalog_admin/grants"
    )

    for privilege in [
        "TABLE_WRITE_DATA",
        "TABLE_CREATE",
        "NAMESPACE_CREATE",
        "TABLE_READ_DATA",
        "NAMESPACE_LIST",
        "TABLE_LIST",
    ]:
        grant_response = httpx.put(
            grant_url,
            headers=headers,
            json={
                "type": "catalog",
                "privilege": privilege,
            },
            timeout=10.0,
        )
        # Ignore 409 Conflict (privilege already granted)
        if grant_response.status_code not in (200, 201, 204, 409):
            pytest.fail(
                f"Failed to grant {privilege} privilege: "
                f"{grant_response.status_code} {grant_response.text}"
            )

    return polaris_client


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


@pytest.fixture(scope="session")
def otel_tracer_provider() -> Generator[Any, None, None]:
    """Initialize OTel TracerProvider for E2E test session.

    Sets up a TracerProvider with OTLP gRPC exporter pointing to the
    OTel Collector. Uses BatchSpanProcessor for non-blocking export.
    Service name is set to 'floe-platform' to match Jaeger queries.

    Yields:
        TracerProvider configured for the E2E test environment.

    Note:
        This fixture ensures traces generated during E2E tests
        (compilation, pipeline execution) flow through the OTel
        Collector to Jaeger.
    """
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    otel_endpoint = os.environ.get("OTEL_ENDPOINT", "http://localhost:4317")

    resource = Resource.create({"service.name": "floe-platform"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    yield provider

    provider.shutdown()
