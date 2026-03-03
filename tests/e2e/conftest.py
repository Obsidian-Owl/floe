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
from pathlib import Path
from typing import Any

import httpx
import pytest
from opentelemetry import trace

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
    polaris_mgmt_url = os.environ.get("POLARIS_MGMT_URL", "http://localhost:8182")
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

    # Get admin token - read credentials from env, consistent with polaris_client
    default_cred = "demo-admin:demo-secret"  # pragma: allowlist secret
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
    # insecure=True: local Kind cluster does not expose TLS on gRPC port
    exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    yield provider

    provider.shutdown()


@pytest.fixture(scope="session")
def seed_observability(
    otel_tracer_provider: Any,
    marquez_client: httpx.Client,
) -> None:
    """Seed Marquez and Jaeger with real pipeline data via compile_pipeline().

    Runs compile_pipeline() with MARQUEZ_URL set so OpenLineage events flow
    to Marquez, and with OTel tracing active so spans flow to Jaeger via
    the OTel Collector.

    The fixture temporarily sets MARQUEZ_URL for the compilation, then
    restores the original value to avoid colliding with the marquez_client
    fixture (which uses MARQUEZ_URL as the base URL for reads).

    Args:
        otel_tracer_provider: OTel TracerProvider fixture (ensures tracing active).
        marquez_client: Marquez HTTP client (ensures Marquez is ready).

    Raises:
        pytest.Failed: If seeding fails (compilation error).
    """
    old_marquez = os.environ.get("MARQUEZ_URL")
    # compile_pipeline posts events directly to this URL
    os.environ["MARQUEZ_URL"] = "http://localhost:5000/api/v1/lineage"

    try:
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.telemetry.initialization import ensure_telemetry_initialized

        ensure_telemetry_initialized()

        root = Path(__file__).parent.parent.parent
        spec_path = root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = root / "demo" / "manifest.yaml"

        compile_pipeline(spec_path, manifest_path)

        # Flush OTel spans to ensure they reach Jaeger
        otel_tracer_provider.force_flush(timeout_millis=5000)
    except Exception as exc:
        pytest.fail(f"Observability seeding failed (compile_pipeline): {exc}")
    finally:
        if old_marquez is None:
            os.environ.pop("MARQUEZ_URL", None)
        else:
            os.environ["MARQUEZ_URL"] = old_marquez


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

    Writes E2E ``profiles.yml`` files to each demo project directory,
    backing up the originals as ``profiles.yml.bak``.  The
    The ``run_dbt()`` helper in ``dbt_utils.py`` passes
    ``--profiles-dir`` pointing to the project directory, so profiles
    must live there.

    Credentials are sourced from environment variables, consistent with
    the ``polaris_client`` fixture.

    Yields:
        Dict mapping demo product directory names to their written
        ``profiles.yml`` paths.

    Note:
        Originals are restored on session teardown.
    """
    # --- Resolve credentials from environment and publish as env vars ---
    # dbt profiles use {{ env_var(...) }} Jinja references (FR-014),
    # so credentials are resolved at runtime, never written to disk.
    polaris_url = os.environ.get("POLARIS_URL", "http://localhost:8181")
    minio_url = os.environ.get("MINIO_URL", "http://localhost:9000")
    default_cred = "demo-admin:demo-secret"  # pragma: allowlist secret
    cred = os.environ.get("POLARIS_CREDENTIAL", default_cred)
    parts = cred.split(":", 1)
    if len(parts) != 2:
        pytest.fail(f"POLARIS_CREDENTIAL must be 'client_id:client_secret', got: {cred!r}")
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

    backups: dict[str, str | None] = {}
    profile_paths: dict[str, Path] = {}

    def _restore_backups() -> None:
        """Restore original profiles and remove backups."""
        for prod_dir, orig_content in backups.items():
            proj_dir = project_root / "demo" / prod_dir
            prof_path = proj_dir / "profiles.yml"
            bak_path = proj_dir / "profiles.yml.bak"

            if orig_content is not None:
                prof_path.write_text(orig_content)
            elif prof_path.exists():
                prof_path.unlink()

            bak_path.unlink(missing_ok=True)

    try:
        for product_dir, profile_name in _DBT_DEMO_PRODUCTS.items():
            project_dir = project_root / "demo" / product_dir
            profile_path = project_dir / "profiles.yml"
            backup_path = project_dir / "profiles.yml.bak"

            # Back up original
            if profile_path.exists():
                original_content = profile_path.read_text()
                backups[product_dir] = original_content
                backup_path.write_text(original_content)
            else:
                backups[product_dir] = None

            # Write E2E profile (credentials via env_var, not plaintext)
            e2e_content = _build_dbt_iceberg_profile(
                profile_name=profile_name,
                warehouse=warehouse,
            )
            profile_path.write_text(e2e_content)
            profile_paths[product_dir] = profile_path
    except Exception:
        # Setup failed mid-loop — restore any profiles already backed up
        _restore_backups()
        raise

    yield profile_paths

    _restore_backups()
    # Clean up env vars set for dbt env_var() resolution
    for var_name in _e2e_env_vars:
        os.environ.pop(var_name, None)
    # Restore AWS vars to their pre-fixture state
    for var_name, prior_value in _aws_vars_prior.items():
        if prior_value is None:
            os.environ.pop(var_name, None)
        else:
            os.environ[var_name] = prior_value
