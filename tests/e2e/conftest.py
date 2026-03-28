"""E2E test configuration and fixtures.

This module provides fixtures for full end-to-end testing of the floe platform.
E2E tests validate complete workflows: compile → deploy → run → validate.

All E2E tests require the full platform stack running in K8s (Kind cluster).
"""

from __future__ import annotations

import importlib
import logging
import os
import re
import shutil
import subprocess
import uuid
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import httpx
import pytest

# Re-exported for backwards compatibility — other E2E files import from here.
from testing.fixtures.kubernetes import run_helm as run_helm
from testing.fixtures.kubernetes import run_kubectl as run_kubectl
from testing.fixtures.polling import wait_for_condition
from testing.fixtures.services import ServiceEndpoint, get_effective_port

logger = logging.getLogger(__name__)


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
    """Reorder destructive tests to run last and check for TQR anti-patterns.

    Moves tests from test_service_failure_resilience_e2e.py to the end of the
    collection so pod-killing tests don't cascade failures to subsequent modules.
    Also scans test source code for TQR violations and issues warnings.

    Args:
        config: pytest configuration object.
        items: List of collected test items.
    """
    import inspect
    import re
    import warnings

    # Reorder: move destructive (pod-killing) tests to the end
    destructive_module = "test_service_failure_resilience_e2e"
    non_destructive: list[pytest.Item] = []
    destructive: list[pytest.Item] = []
    for item in items:
        if destructive_module in item.nodeid:
            destructive.append(item)
        else:
            non_destructive.append(item)
    items[:] = non_destructive + destructive

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


@pytest.fixture(scope="session", autouse=True)
def infrastructure_smoke_check() -> None:
    """Abort test session if core infrastructure is unreachable.

    Checks TCP connectivity to Dagster, Polaris, and MinIO before any
    test runs. If infrastructure is dead (e.g. SSH tunnel died), aborts
    the session with a clear message instead of producing 72+ ERRORs.
    """
    import socket

    services = {
        "Dagster": int(os.environ.get("DAGSTER_WEBSERVER_PORT", "3100")),
        "Polaris": 8181,
        "MinIO": 9000,
    }
    failures: list[str] = []
    for name, port in services.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            result = sock.connect_ex(("localhost", port))
            if result != 0:
                failures.append(f"{name} (localhost:{port})")
        except OSError:
            failures.append(f"{name} (localhost:{port})")
        finally:
            sock.close()

    if failures:
        pytest.exit(
            f"Infrastructure unreachable: {', '.join(failures)}. "
            "Check SSH tunnels and port-forwards.",
            returncode=3,
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
        *,
        strict_status: bool = False,
    ) -> None:
        """Wait for HTTP service to become available.

        Args:
            url: URL to poll for HTTP 200 response.
            timeout: Maximum wait time in seconds. Defaults to 60.0.
            description: Description for error messages.
            strict_status: If True, require HTTP 200 exactly. If False,
                accept any non-5xx response. Use True for health endpoints
                that return 503 when not ready.

        Raises:
            TimeoutError: If service not ready within timeout.
        """
        effective_description = description or f"service at {url}"

        def check_http() -> bool:
            try:
                response = httpx.get(url, timeout=5.0)
                if strict_status:
                    return response.status_code == 200
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
    url = os.environ.get("DAGSTER_URL", ServiceEndpoint("dagster-webserver").url)
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
    polaris_url = os.environ.get("POLARIS_URL", ServiceEndpoint("polaris").url)
    polaris_mgmt_url = os.environ.get("POLARIS_MGMT_URL", ServiceEndpoint("polaris-management").url)
    # Extended timeout for CI environments where startup may be slower
    polaris_timeout = float(os.environ.get("POLARIS_TIMEOUT", "90"))
    # Use management health endpoint (port 8182) — does not require auth
    wait_for_service(
        f"{polaris_mgmt_url}/q/health/ready",
        timeout=polaris_timeout,
        description="Polaris management health",
        strict_status=True,
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
    minio_url = os.environ.get("MINIO_URL", ServiceEndpoint("minio").url)
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

    # --- Apply write grants defensively (idempotent) ---
    # Ensures the test principal has write permissions even if the Helm
    # bootstrap job didn't run or hasn't applied grants yet. Mirrors the
    # bootstrap job's 5-step grant process: create principal role, assign
    # principal role to root, create catalog role, grant privilege,
    # assign catalog role to principal role.
    cred = os.environ.get("POLARIS_CREDENTIAL", default_cred)
    client_id, client_secret = cred.split(":", 1)
    token_response = httpx.post(
        f"{polaris_url}/api/catalog/v1/oauth/tokens",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "PRINCIPAL_ROLE:ALL",
        },
        timeout=10.0,
    )
    if token_response.status_code != 200:
        pytest.fail(
            f"Failed to get Polaris admin token for grants: HTTP {token_response.status_code}. "
            "Tests requiring write access will fail without grants."
        )

    token = token_response.json().get("access_token")
    if not token:
        pytest.fail(
            "Polaris token response missing access_token field "
            f"(HTTP {token_response.status_code}). "
            "Cannot apply write grants without a valid token."
        )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    catalog_name = os.environ.get("POLARIS_WAREHOUSE", "floe-e2e")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", catalog_name):
        pytest.fail(f"POLARIS_WAREHOUSE contains unsafe characters: {catalog_name!r}")
    principal_role = os.environ.get("POLARIS_PRINCIPAL_ROLE", "floe-pipeline")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", principal_role):
        pytest.fail(f"POLARIS_PRINCIPAL_ROLE contains unsafe characters: {principal_role!r}")

    # Step 1: Create principal role (idempotent — 201 created, 409 exists)
    pr_create_response = httpx.post(
        f"{polaris_url}/api/management/v1/principal-roles",
        headers=headers,
        json={"principalRole": {"name": principal_role}},
        timeout=10.0,
    )
    if pr_create_response.status_code not in (201, 409):
        logger.warning(
            "Failed to create principal role %s: HTTP %s",
            principal_role,
            pr_create_response.status_code,
        )

    # Step 2: Assign principal role to root principal (idempotent)
    pr_assign_response = httpx.put(
        f"{polaris_url}/api/management/v1/principals/root/principal-roles",
        headers=headers,
        json={"principalRole": {"name": principal_role}},
        timeout=10.0,
    )
    if pr_assign_response.status_code not in (200, 201, 204, 409):
        logger.warning(
            "Failed to assign principal role %s to root: HTTP %s",
            principal_role,
            pr_assign_response.status_code,
        )

    # Step 3: Create catalog_admin role (idempotent — 201 created, 409 exists)
    role_response = httpx.post(
        f"{polaris_url}/api/management/v1/catalogs/{catalog_name}/catalog-roles",
        headers=headers,
        json={"catalogRole": {"name": "catalog_admin"}},
        timeout=10.0,
    )
    if role_response.status_code not in (201, 409):
        logger.warning(
            "Failed to create catalog_admin role: HTTP %s",
            role_response.status_code,
        )

    # Step 4: Grant CATALOG_MANAGE_CONTENT privilege
    grant_response = httpx.put(
        f"{polaris_url}/api/management/v1/catalogs/{catalog_name}"
        "/catalog-roles/catalog_admin/grants",
        headers=headers,
        json={"grant": {"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"}},
        timeout=10.0,
    )
    if grant_response.status_code not in (200, 201, 204, 409):
        logger.warning(
            "Failed to grant CATALOG_MANAGE_CONTENT: HTTP %s",
            grant_response.status_code,
        )

    # Step 5: Assign catalog role to principal role (idempotent — 200/204 ok, 409 exists)
    assign_response = httpx.put(
        f"{polaris_url}/api/management/v1/principal-roles/{principal_role}/catalog-roles/{catalog_name}",
        headers=headers,
        json={"catalogRole": {"name": "catalog_admin"}},
        timeout=10.0,
    )
    if assign_response.status_code not in (200, 204, 409):
        logger.warning(
            "Failed to assign catalog_admin to %s: HTTP %s",
            principal_role,
            assign_response.status_code,
        )

    logger.info("Write grants applied to polaris_client (catalog=%s)", catalog_name)
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
    legacy_port = os.environ.get("MARQUEZ_HOST_PORT")
    if legacy_port is not None:
        import warnings

        warnings.warn(
            "MARQUEZ_HOST_PORT is deprecated; use MARQUEZ_PORT instead",
            DeprecationWarning,
            stacklevel=1,
        )
        if not os.environ.get("MARQUEZ_PORT"):
            os.environ["MARQUEZ_PORT"] = legacy_port
    marquez_port = get_effective_port("marquez")
    marquez_url = os.environ.get("MARQUEZ_URL", ServiceEndpoint("marquez").url)
    marquez_timeout = float(os.environ.get("MARQUEZ_TIMEOUT", "90"))
    marquez_description = (
        "Marquez API (requires port-forward: "
        f"kubectl port-forward svc/floe-platform-marquez {marquez_port}:5000 -n floe-test)"
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
) -> Any:
    """Polaris client with write grants — thin wrapper over polaris_client.

    Write grants (CATALOG_MANAGE_CONTENT, which subsumes TABLE_CREATE,
    TABLE_WRITE_DATA, NAMESPACE_CREATE, etc.) are now applied by
    polaris_client directly. This fixture exists for backwards
    compatibility with tests that explicitly request it.

    Args:
        polaris_client: PyIceberg REST catalog with grants already applied.

    Returns:
        The same PyIceberg REST catalog instance.

    Example:
        table = polaris_with_write_grants.create_table(...)
    """
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
    jaeger_url = os.environ.get("JAEGER_URL", ServiceEndpoint("jaeger-query").url)
    wait_for_service(f"{jaeger_url}/api/services", timeout=60, description="Jaeger query API")

    return httpx.Client(base_url=jaeger_url, timeout=30.0)


# ---------------------------------------------------------------------------
# Lineage seeding helpers (used by seed_observability)
# ---------------------------------------------------------------------------

_LAUNCH_RUN_MUTATION = """
mutation LaunchRun($executionParams: ExecutionParams!) {
    launchRun(executionParams: $executionParams) {
        __typename
        ... on LaunchRunSuccess {
            run { runId status }
        }
        ... on PipelineNotFoundError { message }
        ... on PythonError { message }
        ... on RunConfigValidationInvalid { errors { message } }
    }
}
"""

_RUN_STATUS_QUERY = """
query RunStatus($runId: ID!) {
    runOrError(runId: $runId) {
        ... on Run { status }
    }
}
"""


def _discover_repo_for_asset(
    dagster_url: str,
    search_term: str,
) -> tuple[str, str, list[str], str] | None:
    """Return (repo, location, asset_path, job_name) for an asset.

    Searches all assets for one whose key path contains ``search_term``
    in any segment.  Resolves the ``__ASSET_JOB`` variant from the
    asset's ``jobNames``.

    Returns ``None`` if no repositories or matching assets are found
    (best-effort — callers log a warning and continue).

    Args:
        dagster_url: Base URL of the Dagster webserver.
        search_term: Term to match in any segment of an asset key path.

    Returns:
        4-tuple ``(repo_name, location_name, asset_path, job_name)``
        or ``None``.
    """
    asset_query = """
    {
        assetNodes {
            assetKey { path }
            repository { name location { name } }
            jobNames
        }
    }
    """
    try:
        response = httpx.post(
            f"{dagster_url}/graphql",
            json={"query": asset_query},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "seed_observability: assetNodes query failed: %s",
            type(exc).__name__,
        )
        return None

    if response.status_code != 200:
        logger.warning(
            "seed_observability: assetNodes returned HTTP %d",
            response.status_code,
        )
        return None

    nodes = response.json().get("data", {}).get("assetNodes", [])
    for node in nodes:
        path: list[str] = node["assetKey"]["path"]
        if search_term in path:
            repo = node["repository"]
            job_names: list[str] = node.get("jobNames", [])
            if "__ASSET_JOB" in job_names:
                job_name = "__ASSET_JOB"
            else:
                prefixed = sorted(j for j in job_names if j.startswith("__ASSET_JOB"))
                job_name = prefixed[0] if prefixed else "__ASSET_JOB"
            return (
                repo["name"],
                repo["location"]["name"],
                path,
                job_name,
            )

    available = [n["assetKey"]["path"] for n in nodes[:10]]
    logger.warning(
        "seed_observability: asset '%s' not found in assetNodes. Available (first 10): %s",
        search_term,
        available,
    )
    return None


def _trigger_lineage_run(
    wait_for_service: Callable[..., None],
    marquez_client: httpx.Client,
) -> None:
    """Trigger a Dagster asset run to emit runtime OpenLineage events.

    Triggers materialization of the ``stg_crm_customers`` asset in the
    customer-360 product, polls for run completion, then waits for Marquez
    to ingest the emitted lineage events.

    This function is best-effort: failures are logged as warnings rather
    than raising so that tests not dependent on lineage data are unaffected.

    Args:
        wait_for_service: Service readiness polling helper.
        marquez_client: Marquez HTTP client (used to poll for lineage ingestion).
    """
    dagster_url = os.environ.get("DAGSTER_URL", ServiceEndpoint("dagster-webserver").url)
    try:
        wait_for_service(
            f"{dagster_url}/server_info",
            timeout=60,
            description="Dagster webserver (lineage seeding)",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "seed_observability: Dagster not ready for lineage seeding (%s); skipping",
            type(exc).__name__,
        )
        return

    discovery = _discover_repo_for_asset(dagster_url, "stg_crm_customers")
    if discovery is None:
        logger.warning(
            "seed_observability: asset discovery returned None; skipping lineage run",
        )
        return

    repo_name, location_name, asset_path, job_name = discovery

    variables: dict[str, Any] = {
        "executionParams": {
            "selector": {
                "repositoryName": repo_name,
                "repositoryLocationName": location_name,
                "pipelineName": job_name,
                "assetSelection": [{"path": asset_path}],
            },
            "mode": "default",
        },
    }

    try:
        response = httpx.post(
            f"{dagster_url}/graphql",
            json={"query": _LAUNCH_RUN_MUTATION, "variables": variables},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "seed_observability: launchRun request failed (%s); skipping lineage run",
            type(exc).__name__,
        )
        return

    if response.status_code != 200:
        logger.warning(
            "seed_observability: launchRun returned HTTP %d; skipping lineage run",
            response.status_code,
        )
        return

    launch_result = response.json().get("data", {}).get("launchRun", {})
    launch_typename = launch_result.get("__typename", "unknown")

    if launch_typename != "LaunchRunSuccess":
        if launch_typename == "RunConfigValidationInvalid":
            errs = [e.get("message", "") for e in launch_result.get("errors", [])]
            error_msg = "; ".join(errs) or str(launch_result)
        else:
            error_msg = launch_result.get("message", str(launch_result))
        logger.warning(
            "seed_observability: launchRun returned %s: %s; skipping lineage run",
            launch_typename,
            error_msg,
        )
        return

    run_id: str = launch_result.get("run", {}).get("runId", "")
    if not run_id:
        logger.warning("seed_observability: no runId in LaunchRunSuccess; skipping poll")
        return

    logger.info("seed_observability: launched Dagster run %s for lineage seeding", run_id)

    # Poll for run completion.
    def _run_complete() -> bool:
        """Return True when the Dagster run has reached a terminal state."""
        try:
            resp = httpx.post(
                f"{dagster_url}/graphql",
                json={"query": _RUN_STATUS_QUERY, "variables": {"runId": run_id}},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return False
            status = resp.json().get("data", {}).get("runOrError", {}).get("status")
            return status in ("SUCCESS", "FAILURE", "CANCELED")
        except httpx.HTTPError:
            return False

    completed = wait_for_condition(
        _run_complete,
        timeout=180.0,
        interval=5.0,
        description=f"Dagster lineage run {run_id} to complete",
        raise_on_timeout=False,
    )
    if not completed:
        logger.warning(
            "seed_observability: lineage run %s did not complete within 180s; continuing",
            run_id,
        )
        return

    # Check terminal state — warn if the run did not succeed.
    try:
        status_resp = httpx.post(
            f"{dagster_url}/graphql",
            json={"query": _RUN_STATUS_QUERY, "variables": {"runId": run_id}},
            timeout=10.0,
        )
        final_status = (
            status_resp.json().get("data", {}).get("runOrError", {}).get("status")
            if status_resp.status_code == 200
            else None
        )
    except httpx.HTTPError:
        final_status = None

    if final_status != "SUCCESS":
        logger.warning(
            "seed_observability: lineage run %s ended with status %s; "
            "COMPLETE lineage events may be absent",
            run_id,
            final_status,
        )
        return

    logger.info("seed_observability: lineage run %s completed successfully", run_id)

    # Wait for Marquez to ingest the emitted OpenLineage events.
    def _marquez_has_lineage() -> bool:
        """Return True when Marquez has at least one job from the seeded run."""
        try:
            for ns in ("default", "floe-platform", "customer-360"):
                resp = marquez_client.get(f"/api/v1/namespaces/{ns}/jobs", timeout=10.0)
                if resp.status_code == 200:
                    jobs = resp.json().get("jobs", [])
                    if len(jobs) > 0:
                        return True
            return False
        except Exception:  # noqa: BLE001
            return False

    ingested = wait_for_condition(
        _marquez_has_lineage,
        timeout=30.0,
        interval=3.0,
        description="Marquez to ingest lineage events",
        raise_on_timeout=False,
    )
    if not ingested:
        logger.warning(
            "seed_observability: Marquez lineage ingestion not confirmed within 30s; continuing"
        )
    else:
        logger.info("seed_observability: Marquez lineage ingestion confirmed")


@pytest.fixture(scope="session")
def seed_observability(
    marquez_client: httpx.Client,
    wait_for_service: Callable[..., None],
) -> None:
    """Seed Jaeger and Marquez with real pipeline data.

    Phase 1 — OTel spans: Compiles all 3 demo products (customer-360,
    iot-telemetry, financial-risk) with per-product OTEL_SERVICE_NAME so
    Jaeger registers each as a distinct service.  Uses standard OTel env vars
    (OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_INSECURE).  Between
    products, reset_telemetry() shuts down the current TracerProvider
    (flushing pending spans) and clears the initialized flag so that the next
    ensure_telemetry_initialized() creates a fresh provider with the new
    service name.

    Phase 2 — OpenLineage events: Triggers a Dagster run for the
    stg_crm_customers asset (customer-360 product) so that LineageResource
    emits runtime OpenLineage events to Marquez.  Polls for run completion.
    A warning (not a failure) is logged if the Dagster run cannot be
    triggered, since some tests do not depend on lineage data.

    Args:
        marquez_client: Marquez HTTP client (ensures Marquez is ready).
        wait_for_service: Service readiness polling helper.

    Raises:
        pytest.Failed: If compilation seeding fails.
    """
    from floe_core.compilation.stages import compile_pipeline
    from floe_core.telemetry.initialization import (
        ensure_telemetry_initialized,
        reset_telemetry,
    )

    # Save OTel + OpenLineage env vars before mutation so we can restore in finally.
    old_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    old_insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE")
    old_service = os.environ.get("OTEL_SERVICE_NAME")
    old_lineage_url = os.environ.get("OPENLINEAGE_URL")

    # Standard OTel env vars for Kind cluster (no TLS)
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
    os.environ["OTEL_EXPORTER_OTLP_INSECURE"] = "true"
    # OpenLineage endpoint via port-forward (overrides K8s-internal manifest URL)
    os.environ["OPENLINEAGE_URL"] = "http://localhost:5100/api/v1/lineage"

    root = Path(__file__).parent.parent.parent
    manifest_path = root / "demo" / "manifest.yaml"

    demo_products = ["customer-360", "iot-telemetry", "financial-risk"]

    try:
        # ------------------------------------------------------------------
        # Phase 1: Compile each demo product to emit OTel spans to Jaeger.
        # ------------------------------------------------------------------
        for product in demo_products:
            reset_telemetry()
            os.environ["OTEL_SERVICE_NAME"] = product

            ensure_telemetry_initialized()

            spec_path = root / "demo" / product / "floe.yaml"
            compile_pipeline(spec_path, manifest_path)

        # Flush and shut down the final provider to avoid leaking the
        # BatchSpanProcessor background thread and gRPC connection.
        reset_telemetry()
    except Exception as exc:
        pytest.fail(f"Observability seeding failed (compile_pipeline): {exc}")
    finally:
        # Restore all mutated OTel env vars to avoid leaking to other fixtures.
        for key, old_val in (
            ("OTEL_EXPORTER_OTLP_ENDPOINT", old_endpoint),
            ("OTEL_EXPORTER_OTLP_INSECURE", old_insecure),
            ("OTEL_SERVICE_NAME", old_service),
            ("OPENLINEAGE_URL", old_lineage_url),
        ):
            if old_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_val

    # ----------------------------------------------------------------------
    # Phase 2: Trigger a Dagster run to emit runtime OpenLineage events.
    # ----------------------------------------------------------------------
    # This is best-effort: a warning is logged on failure rather than
    # pytest.fail(), so tests that only rely on OTel spans are not blocked.
    _trigger_lineage_run(wait_for_service, marquez_client)


# ---------------------------------------------------------------------------
# dbt Iceberg profile configuration
# ---------------------------------------------------------------------------

# Demo products: directory name → dbt profile name
_DBT_DEMO_PRODUCTS: dict[str, str] = {
    "customer-360": "customer_360",
    "iot-telemetry": "iot_telemetry",
    "financial-risk": "financial_risk",
}


def _build_dbt_iceberg_profile(
    profile_name: str,
    warehouse: str,
) -> str:
    """Build a dbt profiles.yml string for DuckDB + Iceberg via Polaris.

    The generated profile configures dbt-duckdb to attach a Polaris REST
    Iceberg catalog as the ``ice`` database, routing all materializations
    to Iceberg tables stored in MinIO/S3.

    Credentials and endpoints are referenced via dbt's ``env_var()`` Jinja
    function (FR-014), so **no secrets are written to disk**.  The calling
    fixture must ensure the referenced environment variables are set before
    dbt is invoked.

    Referenced env vars (set by ``dbt_e2e_profile`` fixture):
        FLOE_E2E_POLARIS_ENDPOINT, FLOE_E2E_POLARIS_CLIENT_ID,
        FLOE_E2E_POLARIS_CLIENT_SECRET, FLOE_E2E_POLARIS_OAUTH2_URI,
        FLOE_E2E_S3_ENDPOINT, FLOE_E2E_S3_USE_SSL,
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION.

    Args:
        profile_name: dbt profile name (must match dbt_project.yml ``profile`` key).
        warehouse: Polaris warehouse/catalog name (e.g. ``floe-e2e``).

    Returns:
        YAML string suitable for writing to ``profiles.yml``.
    """
    # Double braces in f-strings produce literal braces for dbt Jinja.
    # Pattern: f"{{{{ expr }}}}" → "{{ expr }}" in output.
    return (
        f"{profile_name}:\n"
        f"  target: dev\n"
        f"  outputs:\n"
        f"    dev:\n"
        f"      type: duckdb\n"
        f'      path: ":memory:"\n'
        f"      database: ice\n"
        f"      schema: {profile_name}\n"
        f"      threads: 1\n"
        f"      extensions:\n"
        f"        - httpfs\n"
        f"        - iceberg\n"
        f"      attach:\n"
        f"        - path: {warehouse}\n"
        f"          alias: ice\n"
        f"          type: iceberg\n"
        f"          options:\n"
        "            ENDPOINT: \"{{ env_var('FLOE_E2E_POLARIS_ENDPOINT') }}\"\n"
        "            CLIENT_ID: \"{{ env_var('FLOE_E2E_POLARIS_CLIENT_ID') }}\"\n"
        "            CLIENT_SECRET: \"{{ env_var('FLOE_E2E_POLARIS_CLIENT_SECRET') }}\"\n"
        "            OAUTH2_SERVER_URI: \"{{ env_var('FLOE_E2E_POLARIS_OAUTH2_URI') }}\"\n"
        f"            OAUTH2_SCOPE: PRINCIPAL_ROLE:ALL\n"
        f"            OAUTH2_GRANT_TYPE: client_credentials\n"
        f"            ACCESS_DELEGATION_MODE: none\n"
        f"      secrets:\n"
        f"        - type: s3\n"
        "          key_id: \"{{ env_var('AWS_ACCESS_KEY_ID') }}\"\n"
        "          secret: \"{{ env_var('AWS_SECRET_ACCESS_KEY') }}\"\n"
        "          endpoint: \"{{ env_var('FLOE_E2E_S3_ENDPOINT') }}\"\n"
        f"          url_style: path\n"
        "          use_ssl: \"{{ env_var('FLOE_E2E_S3_USE_SSL', 'false') }}\"\n"
        "          region: \"{{ env_var('AWS_REGION', 'us-east-1') }}\"\n"
    )


@pytest.fixture(scope="session")
def dbt_e2e_profile(
    project_root: Path,
) -> Generator[dict[str, Path], None, None]:
    """Configure dbt to write to Iceberg tables via Polaris REST catalog.

    Writes E2E ``profiles.yml`` files to an isolated directory at
    ``tests/e2e/generated_profiles/<product>/profiles.yml``.  Demo
    profiles are never overwritten.  The ``run_dbt()`` helper in
    ``dbt_utils.py`` auto-detects the generated profiles directory
    and uses it as ``--profiles-dir``.

    Credentials are sourced from environment variables, consistent with
    the ``polaris_client`` fixture.

    Yields:
        Dict mapping demo product directory names to their written
        ``profiles.yml`` paths.

    Note:
        Generated profiles are cleaned up on session teardown.
        Stale profiles from crashed prior sessions are cleaned at setup (P36).
    """
    # --- Resolve credentials from environment and publish as env vars ---
    # dbt profiles use {{ env_var(...) }} Jinja references (FR-014),
    # so credentials are resolved at runtime, never written to disk.
    polaris_url = os.environ.get("POLARIS_URL", ServiceEndpoint("polaris").url)
    minio_url = os.environ.get("MINIO_URL", ServiceEndpoint("minio").url)
    default_cred = "demo-admin:demo-secret"  # pragma: allowlist secret
    cred = os.environ.get("POLARIS_CREDENTIAL", default_cred)
    parts = cred.split(":", 1)
    if len(parts) != 2:
        pytest.fail(
            "POLARIS_CREDENTIAL must be 'client_id:client_secret'; "
            f"got a value with {len(cred)} characters and no ':' separator"
        )
    client_id, client_secret = parts
    warehouse = os.environ.get("POLARIS_WAREHOUSE", "floe-e2e")

    # Derive computed values
    s3_use_ssl = minio_url.startswith("https://")
    s3_endpoint = minio_url.replace("http://", "").replace("https://", "")

    # Set env vars that the profile's {{ env_var() }} references resolve against.
    # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION are set by the test
    # runner (test-e2e.sh); setdefault provides fallbacks for local runs.
    _e2e_env_vars: dict[str, str] = {
        "FLOE_E2E_POLARIS_ENDPOINT": f"{polaris_url}/api/catalog",
        "FLOE_E2E_POLARIS_CLIENT_ID": client_id,
        "FLOE_E2E_POLARIS_CLIENT_SECRET": client_secret,
        "FLOE_E2E_POLARIS_OAUTH2_URI": f"{polaris_url}/api/catalog/v1/oauth/tokens",
        "FLOE_E2E_S3_ENDPOINT": s3_endpoint,
        "FLOE_E2E_S3_USE_SSL": str(s3_use_ssl).lower(),
    }
    for var_name, var_value in _e2e_env_vars.items():
        os.environ[var_name] = var_value
    # Capture prior state of AWS vars so teardown can restore or remove them.
    _aws_vars_prior: dict[str, str | None] = {
        "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        "AWS_REGION": os.environ.get("AWS_REGION"),
    }
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "minioadmin")
    os.environ.setdefault(  # pragma: allowlist secret
        "AWS_SECRET_ACCESS_KEY", "minioadmin123"
    )
    os.environ.setdefault("AWS_REGION", "us-east-1")

    profile_paths: dict[str, Path] = {}

    # --- Profile isolation (WU-1 AC-3) ---
    # Write E2E profiles to tests/e2e/generated_profiles/<product>/profiles.yml
    # instead of overwriting demo/<product>/profiles.yml.  run_dbt() auto-detects
    # the generated_profiles directory and uses it as --profiles-dir.
    generated_profiles_root = Path(__file__).parent / "generated_profiles"

    # --- P36: Clean stale generated profiles from crashed prior sessions ---
    if generated_profiles_root.exists():
        logger.warning(
            "Stale generated_profiles detected — cleaning up "
            "(previous session likely crashed without teardown).",
        )
        shutil.rmtree(generated_profiles_root, ignore_errors=True)

    # --- Stale .bak migration (WU-36 AC-36.1) ---
    # Legacy sessions may have crashed leaving orphaned .bak files from the
    # old approach that overwrote demo profiles.  Restore them now so the
    # demo directory is clean.
    for product_dir in _DBT_DEMO_PRODUCTS:
        project_dir = project_root / "demo" / product_dir
        profile_path = project_dir / "profiles.yml"
        bak_path = project_dir / "profiles.yml.bak"
        if bak_path.exists():
            logger.warning(
                "Stale .bak detected for %s — restoring original profiles.yml "
                "(previous session likely crashed without teardown).",
                product_dir,
            )
            bak_path.rename(profile_path)

    # --- Copy custom materialization macro from floe-compute-duckdb plugin ---
    # Demo projects use macro-paths: ["../macros"], so macros must be in
    # demo/macros/. The custom table materialization (Iceberg-aware DROP+CREATE)
    # lives in the plugin package and needs to be copied here for dbt to find it.
    macro_dest_dir = project_root / "demo" / "macros" / "materializations"
    macro_dest = macro_dest_dir / "table.sql"
    _macro_copied = False

    try:
        macro_source = (
            Path(importlib.import_module("floe_compute_duckdb").__file__).parent
            / "dbt_macros"
            / "materializations"
            / "table.sql"
        )
    except (ImportError, TypeError):
        pytest.fail(
            "Custom table materialization not found in floe-compute-duckdb plugin.\n"
            "Install with: uv pip install -e plugins/floe-compute-duckdb\n"
            "The plugin provides the Iceberg-aware table materialization macro."
        )

    if not macro_source.exists():
        pytest.fail(
            f"Custom table materialization not found at {macro_source}.\n"
            "Expected: plugins/floe-compute-duckdb/src/floe_compute_duckdb/"
            "dbt_macros/materializations/table.sql"
        )

    macro_dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(macro_source, macro_dest)
    _macro_copied = True
    logger.info("Copied custom table materialization macro to %s", macro_dest)

    try:
        for product_dir, profile_name in _DBT_DEMO_PRODUCTS.items():
            gen_dir = generated_profiles_root / product_dir
            gen_dir.mkdir(parents=True, exist_ok=True)
            profile_path = gen_dir / "profiles.yml"

            # Write E2E profile (credentials via env_var, not plaintext)
            e2e_content = _build_dbt_iceberg_profile(
                profile_name=profile_name,
                warehouse=warehouse,
            )
            profile_path.write_text(e2e_content)
            profile_paths[product_dir] = profile_path
    except Exception:
        # Setup failed mid-loop — clean up any generated profiles
        if generated_profiles_root.exists():
            shutil.rmtree(generated_profiles_root, ignore_errors=True)
        if _macro_copied and macro_dest.exists():
            macro_dest.unlink()
        raise

    yield profile_paths

    # Clean up generated profiles directory
    if generated_profiles_root.exists():
        shutil.rmtree(generated_profiles_root, ignore_errors=True)
    # Clean up copied macro file
    if _macro_copied and macro_dest.exists():
        macro_dest.unlink()
        # Remove materializations dir if empty (we created it)
        if macro_dest_dir.exists() and not any(macro_dest_dir.iterdir()):
            macro_dest_dir.rmdir()
        logger.info("Cleaned up custom table materialization macro from %s", macro_dest)
    # Clean up env vars set for dbt env_var() resolution
    for var_name in _e2e_env_vars:
        os.environ.pop(var_name, None)
    # Restore AWS vars to their pre-fixture state
    for var_name, prior_value in _aws_vars_prior.items():
        if prior_value is None:
            os.environ.pop(var_name, None)
        else:
            os.environ[var_name] = prior_value
