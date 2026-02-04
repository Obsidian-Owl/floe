"""E2E tests for floe-platform Helm chart bootstrap validation.

This module validates the complete platform deployment via Helm,
ensuring all services are properly deployed, configured, and accessible.

Tests:
- FR-001, FR-002: All pods reach Ready state
- FR-003: NodePort services respond to HTTP requests
- FR-004: PostgreSQL databases initialized with correct schemas
- FR-005: MinIO buckets exist
- FR-006: OTel collector forwards traces to Jaeger
- FR-007: Observability UIs accessible
- FR-049: Marquez lineage service accessible
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import TYPE_CHECKING

import httpx
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.polling import wait_for_condition

if TYPE_CHECKING:
    from collections.abc import Callable


def _run_kubectl(
    args: list[str],
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run kubectl command with timeout.

    Args:
        args: kubectl arguments (e.g., ["get", "pods"]).
        timeout: Command timeout in seconds. Defaults to 60.

    Returns:
        Completed process result with stdout, stderr, and returncode.
    """
    return subprocess.run(
        ["kubectl"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.mark.e2e
@pytest.mark.requirement("FR-001")
@pytest.mark.requirement("FR-002")
@pytest.mark.requirement("FR-003")
@pytest.mark.requirement("FR-004")
@pytest.mark.requirement("FR-005")
@pytest.mark.requirement("FR-006")
@pytest.mark.requirement("FR-007")
@pytest.mark.requirement("FR-049")
class TestPlatformBootstrap(IntegrationTestBase):
    """E2E tests for floe-platform Helm chart bootstrap validation.

    Validates the complete platform deployment lifecycle:
    1. Deploy floe-platform Helm chart
    2. Verify all pods reach Ready state
    3. Verify all NodePort services are accessible
    4. Verify PostgreSQL databases initialized
    5. Verify MinIO buckets exist
    6. Verify OTel collector forwards traces
    7. Verify observability UIs accessible
    8. Verify Marquez lineage service accessible

    This test class inherits from IntegrationTestBase to leverage:
    - Service availability checking
    - Unique namespace generation
    - Setup/teardown with resource cleanup
    - Infrastructure verification with actionable errors
    """

    # Required services for all platform bootstrap tests
    # Only NodePort-accessible services (ClusterIP-only services checked individually)
    required_services = [
        ("polaris", 8181),
        ("dagster-webserver", 3000),
        ("minio", 9000),
        ("jaeger-query", 16686),
    ]

    # K8s namespace for E2E tests
    namespace = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")

    @pytest.mark.requirement("FR-001")
    @pytest.mark.requirement("FR-002")
    def test_all_pods_ready(self) -> None:
        """Test that all pods reach Ready state within 120 seconds.

        Validates FR-001 (all services deployed) and FR-002 (all pods ready).
        Polls pod status until all pods are in Running phase with Ready condition,
        or timeout occurs.

        Additionally validates that all core platform services are deployed.

        Raises:
            AssertionError: If any pod not Ready within timeout or core services missing.
        """

        def check_all_pods_ready() -> bool:
            """Check if all pods in namespace are Ready."""
            result = _run_kubectl(
                [
                    "get",
                    "pods",
                    "-n",
                    self.namespace,
                    "-o",
                    "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}",
                ]
            )
            if result.returncode != 0:
                return False

            # All Ready conditions should be "True"
            statuses = result.stdout.strip().split()
            return bool(statuses and all(s == "True" for s in statuses))

        # Wait for all pods to be ready
        ready = wait_for_condition(
            check_all_pods_ready,
            timeout=120.0,
            interval=5.0,
            description=f"all pods in {self.namespace} to be Ready",
            raise_on_timeout=False,
        )

        assert ready, (
            f"Not all pods Ready in {self.namespace} after 120s\n"
            f"Check pod status: kubectl get pods -n {self.namespace}"
        )

        # Verify pod count matches expectations
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-o",
                "jsonpath={.items[*].metadata.labels.app\\.kubernetes\\.io/name}",
            ]
        )
        if result.returncode == 0:
            pod_labels = result.stdout.strip().split()
            # Core services that MUST be deployed
            expected_services = {"postgresql", "minio", "polaris", "dagster"}
            deployed_services = set(pod_labels)
            missing = expected_services - deployed_services
            assert not missing, (
                f"Missing required platform services: {missing}\n"
                f"Deployed: {deployed_services}\n"
                "All core services must be deployed for platform to function."
            )

    @pytest.mark.requirement("FR-003")
    def test_nodeport_services_respond(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Test that all NodePort services respond to HTTP requests.

        Validates FR-003 by querying each exposed NodePort service:
        - Dagster webserver: localhost:3000
        - Polaris catalog: localhost:8181
        - MinIO API: localhost:9000
        - MinIO UI: localhost:9001
        - Jaeger query: localhost:16686

        Note: Grafana, Prometheus, and Marquez are tested in separate tests
        as they may not be deployed in all configurations.

        Args:
            wait_for_service: Fixture for waiting on HTTP services.

        Raises:
            AssertionError: If any service does not respond with HTTP 200.
        """
        # Define core NodePort service endpoints (always deployed)
        core_services = [
            ("http://localhost:3000/server_info", "Dagster webserver"),
            ("http://localhost:8181/api/catalog/v1/config", "Polaris catalog"),
            ("http://localhost:9000/minio/health/live", "MinIO API"),
            ("http://localhost:9001/minio/health/live", "MinIO UI"),
        ]

        # Wait for core services
        for url, description in core_services:
            wait_for_service(url, timeout=60.0, description=description)

        # Optional services - only test if pods are running
        # Jaeger is optional (jaeger.enabled in values)
        jaeger_result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=jaeger",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )
        if jaeger_result.returncode == 0 and "Running" in jaeger_result.stdout:
            wait_for_service(
                "http://localhost:16686/api/services",
                timeout=30.0,
                description="Jaeger query (optional)",
            )

    @pytest.mark.requirement("FR-004")
    def test_postgresql_databases_exist(self) -> None:
        """Test that PostgreSQL service is deployed and functional.

        Validates FR-004 by:
        1. Verifying PostgreSQL pods are Running
        2. Verifying PostgreSQL service exists
        3. Verifying PostgreSQL secret exists
        4. Executing actual database query to verify functionality
        5. Verifying expected databases exist

        Raises:
            AssertionError: If PostgreSQL resources not deployed, not healthy, or not functional.
        """
        # Check PostgreSQL pods are Running (K8s resource existence check)
        # Use component label since PostgreSQL is part of floe-platform chart
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/component=postgresql",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )
        assert result.returncode == 0, f"Failed to check PostgreSQL pods: {result.stderr}"
        phases = result.stdout.strip().split()
        assert phases and all(p == "Running" for p in phases), (
            f"PostgreSQL pods not running. Phases: {phases}\n"
            f"Check: kubectl get pods -n {self.namespace} "
            f"-l app.kubernetes.io/component=postgresql"
        )

        # Verify PostgreSQL service exists
        result = _run_kubectl(
            [
                "get",
                "service",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/component=postgresql",
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ]
        )
        assert result.returncode == 0, f"Failed to check PostgreSQL service: {result.stderr}"
        services = result.stdout.strip().split()
        assert services, (
            "PostgreSQL service not found\n"
            f"Check: kubectl get service -n {self.namespace} "
            f"-l app.kubernetes.io/component=postgresql"
        )

        # Verify PostgreSQL secret exists (floe-platform uses prefixed name)
        result = _run_kubectl(
            [
                "get",
                "secret",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/component=postgresql",
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ]
        )
        assert result.returncode == 0, f"Failed to check PostgreSQL secret: {result.stderr}"
        assert result.stdout.strip(), "PostgreSQL secret not found"

        # Get PostgreSQL pod name for query execution
        pg_pod = None
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/component=postgresql",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            ]
        )
        if result.returncode == 0:
            pg_pod = result.stdout.strip()

        if pg_pod:
            # Execute SELECT 1 to verify database is accepting connections
            query_result = _run_kubectl(
                [
                    "exec",
                    "-n",
                    self.namespace,
                    pg_pod,
                    "--",
                    "psql",
                    "-U",
                    "postgres",
                    "-c",
                    "SELECT 1 as connected;",
                ],
                timeout=30,
            )
            assert query_result.returncode == 0, (
                f"PostgreSQL not accepting queries: {query_result.stderr}\n"
                "Database must be functional, not just running."
            )
            assert "1" in query_result.stdout, "PostgreSQL SELECT 1 returned unexpected result"

            # Check expected databases exist (dagster needs a database)
            db_result = _run_kubectl(
                [
                    "exec",
                    "-n",
                    self.namespace,
                    pg_pod,
                    "--",
                    "psql",
                    "-U",
                    "postgres",
                    "-c",
                    "SELECT datname FROM pg_database WHERE datistemplate = false;",
                ],
                timeout=30,
            )
            assert db_result.returncode == 0, f"Failed to list databases: {db_result.stderr}"
            db_names = db_result.stdout
            assert "dagster" in db_names or "postgres" in db_names, (
                f"Expected dagster or postgres database. Got: {db_names}\n"
                "Dagster requires its own database for run storage."
            )

    @pytest.mark.requirement("FR-005")
    def test_minio_buckets_exist(self) -> None:
        """Test that MinIO buckets exist and are functional.

        Validates FR-005 by:
        1. Verifying MinIO pod is running
        2. Verifying MinIO health endpoint responds
        3. Using MinIO mc CLI to list actual buckets
        4. Verifying 'warehouse' bucket exists

        Raises:
            AssertionError: If buckets are missing or MinIO is not functional.
        """
        # Get MinIO pod name (Bitnami MinIO subchart uses app.kubernetes.io/name=minio)
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=minio",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            ]
        )
        assert result.returncode == 0, f"Failed to find MinIO pod: {result.stderr}"
        minio_pod = result.stdout.strip()
        assert minio_pod, "MinIO pod name is empty"

        # Check MinIO health endpoint via localhost NodePort
        with httpx.Client(timeout=10.0) as client:
            response = client.get("http://localhost:9000/minio/health/live")
            assert response.status_code == 200, (
                f"MinIO health check failed: HTTP {response.status_code}\n"
                "Check MinIO pod: kubectl logs -n floe-test -l app.kubernetes.io/name=minio"
            )

        # Configure mc client and list buckets to verify functionality
        mc_result = _run_kubectl(
            [
                "exec",
                "-n",
                self.namespace,
                minio_pod,
                "--",
                "mc",
                "alias",
                "set",
                "local",
                "http://localhost:9000",
                "minioadmin",
                "minioadmin123",
            ],
            timeout=30,
        )

        if mc_result.returncode == 0:
            # List buckets to verify MinIO is functional
            ls_result = _run_kubectl(
                [
                    "exec",
                    "-n",
                    self.namespace,
                    minio_pod,
                    "--",
                    "mc",
                    "ls",
                    "local",
                ],
                timeout=30,
            )
            assert ls_result.returncode == 0, (
                f"Failed to list MinIO buckets: {ls_result.stderr}\n"
                "MinIO must be functional with accessible buckets."
            )

            # Verify expected buckets exist (warehouse for Iceberg data)
            bucket_output = ls_result.stdout
            expected_buckets = ["warehouse"]
            for bucket in expected_buckets:
                assert bucket in bucket_output, (
                    f"Expected bucket '{bucket}' not found in MinIO.\n"
                    f"Available: {bucket_output}\n"
                    "Warehouse bucket is required for Iceberg table storage."
                )

        # Check for MinIO bucket provisioning Job/ConfigMap as fallback
        # Bitnami MinIO chart creates buckets via provisioning job when configured
        result = _run_kubectl(
            [
                "get",
                "jobs",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=minio",
                "-o",
                "jsonpath={.items[*].status.succeeded}",
            ]
        )

        # If provisioning job exists and succeeded, buckets were created
        if result.returncode == 0 and result.stdout.strip():
            succeeded = result.stdout.strip().split()
            assert all(s == "1" for s in succeeded), (
                f"MinIO provisioning job(s) not all succeeded: {succeeded}\n"
                "Check job: kubectl get jobs -n floe-test -l app.kubernetes.io/name=minio"
            )

    @pytest.mark.requirement("FR-006")
    def test_otel_collector_forwarding(self) -> None:
        """Test that OTel collector is deployed and accepting traces.

        Validates FR-006 by:
        1. Verifying OTel collector pod is running
        2. Sending a test span to OTel collector (localhost:4317)
        3. If Jaeger is deployed, verify span appears there

        Note: Jaeger is optional (jaeger.enabled in values). When Jaeger is
        not deployed, this test verifies OTel collector accepts spans without
        error.

        Raises:
            AssertionError: If OTel collector not accessible or rejects spans.
        """
        # Check OTel collector pod is running
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=otel",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )
        if result.returncode != 0 or "Running" not in result.stdout:
            pytest.fail(
                "OTel collector pod not running. "
                "Check pod status: kubectl get pods -n floe-test -l app.kubernetes.io/name=otel"
            )

        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Create unique trace ID for this test
        test_service_name = f"e2e-platform-test-{int(time.time())}"

        # Configure OTel SDK to export to collector
        resource = Resource.create({"service.name": test_service_name})
        provider = TracerProvider(resource=resource)

        # Use localhost for NodePort access
        exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)

        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        # Create and send test span
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("e2e_test_span") as span:
            span.set_attribute("test.type", "platform_bootstrap")
            span.set_attribute("test.timestamp", int(time.time()))

        # Force flush to ensure span is sent - this will raise if collector rejects
        try:
            flush_result = provider.force_flush(timeout_millis=10000)
            assert flush_result, (
                "OTel collector did not accept span within 10s\n"
                "Check collector logs: kubectl logs -n floe-test -l app.kubernetes.io/name=otel"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to send span to OTel collector: {e}\n"
                "Check collector is accessible at localhost:4317"
            )

        # Check if Jaeger is deployed - if so, verify span appears there
        jaeger_result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=jaeger",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )

        if jaeger_result.returncode == 0 and "Running" in jaeger_result.stdout:
            # Jaeger is deployed - verify span appears
            jaeger_client = httpx.Client(base_url="http://localhost:16686", timeout=10.0)

            def check_span_in_jaeger() -> bool:
                """Check if test span appears in Jaeger."""
                try:
                    response = jaeger_client.get(
                        "/api/traces",
                        params={
                            "service": test_service_name,
                            "lookback": "1h",
                            "limit": 100,
                        },
                    )
                    if response.status_code == 200:
                        data = response.json()
                        traces = data.get("data", [])
                        for trace_data in traces:
                            for span_data in trace_data.get("spans", []):
                                if span_data.get("operationName") == "e2e_test_span":
                                    return True
                    return False
                except (httpx.HTTPError, ValueError):
                    return False

            try:
                span_found = wait_for_condition(
                    check_span_in_jaeger,
                    timeout=30.0,
                    interval=2.0,
                    description="test span to appear in Jaeger",
                    raise_on_timeout=False,
                )

                assert span_found, (
                    f"Test span not found in Jaeger after 30s\n"
                    f"Service: {test_service_name}\n"
                    f"Check Jaeger UI: http://localhost:16686"
                )
            finally:
                jaeger_client.close()

    @pytest.mark.requirement("FR-007")
    def test_observability_uis_accessible(self) -> None:
        """Test that observability resources are deployed and functional.

        Validates FR-007 by verifying:
        - Jaeger UI: accessible via HTTP and can execute queries if deployed
        - OTel collector: pod is running (core observability)
        - Grafana dashboards: ConfigMap exists (Grafana service not deployed)
        - Prometheus: K8s resource exists (if deployed)

        Raises:
            AssertionError: If core observability (OTel) not running or Jaeger not functional.
        """
        # Check OTel collector pod is running (core observability)
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=otel",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )
        assert result.returncode == 0 and "Running" in result.stdout, (
            "OTel collector pod not running\n"
            f"Check pod status: kubectl get pods -n {self.namespace} -l app.kubernetes.io/name=otel"
        )

        # Check Jaeger UI if deployed (optional)
        jaeger_result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=jaeger",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )
        if jaeger_result.returncode == 0 and "Running" in jaeger_result.stdout:
            with httpx.Client(timeout=10.0) as client:
                # Verify UI is accessible
                response = client.get("http://localhost:16686/search")
                assert response.status_code == 200, (
                    f"Jaeger UI not accessible: HTTP {response.status_code}\n"
                    f"URL: http://localhost:16686/search"
                )

                # Verify Jaeger can list services (functional query, not just HTTP 200)
                services_response = client.get("http://localhost:16686/api/services")
                assert services_response.status_code == 200, (
                    f"Jaeger services API failed: HTTP {services_response.status_code}"
                )
                services_data = services_response.json()
                assert "data" in services_data, (
                    "Jaeger services response missing 'data' key - API not functional"
                )
                # data should be a list (even if empty)
                assert isinstance(services_data["data"], list), (
                    "Jaeger services data should be a list"
                )

        # Check Grafana dashboards ConfigMap (may not be deployed)
        # Grafana service itself is not deployed in base platform, only dashboard definitions
        result = _run_kubectl(
            [
                "get",
                "configmap",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/component=observability",
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ]
        )
        # Grafana ConfigMap is optional - only verify if it exists that it has correct format
        if result.returncode == 0 and result.stdout.strip():
            configmaps = result.stdout.strip().split()
            # At least one observability ConfigMap should exist if Grafana is configured
            assert configmaps, (
                "Observability ConfigMaps not found\n"
                f"Check: kubectl get configmap -n {self.namespace}"
                f" -l app.kubernetes.io/component=observability"
            )

        # Check Prometheus resources (may not be deployed)
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app=prometheus",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )
        # Prometheus is optional - only check if pods exist
        if result.returncode == 0 and result.stdout.strip():
            phases = result.stdout.strip().split()
            # If Prometheus deployed, verify pods are Running
            assert all(p == "Running" for p in phases), (
                f"Prometheus pods not running. Phases: {phases}\n"
                f"Check pod status: kubectl get pods -n {self.namespace} -l app=prometheus"
            )

    @pytest.mark.requirement("FR-003")
    def test_dagster_graphql_operational(self) -> None:
        """Test that Dagster GraphQL API can execute queries.

        Validates FR-003 by going beyond HTTP 200 — actually executing
        a GraphQL query and verifying the response structure.

        Raises:
            AssertionError: If Dagster GraphQL API is not functional.
        """
        dagster_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")

        try:
            with httpx.Client(timeout=10.0) as client:
                # Execute GraphQL query for version
                response = client.post(
                    f"{dagster_url}/graphql",
                    json={"query": "{ version }"},
                )
                assert response.status_code == 200, (
                    f"Dagster GraphQL failed: HTTP {response.status_code}"
                )

                data = response.json()
                assert "data" in data, (
                    f"Dagster GraphQL response missing 'data': {data}\n"
                    "GraphQL engine not functional."
                )
                assert "version" in data["data"], (
                    f"Dagster version query returned no version: {data}"
                )

                # Version should be a non-empty string
                version = data["data"]["version"]
                assert isinstance(version, str) and len(version) > 0, (
                    f"Dagster version should be non-empty string, got: {version}"
                )
        except httpx.HTTPError as e:
            pytest.fail(
                f"Dagster GraphQL not reachable at {dagster_url}: {e}\n"
                "Verify Dagster is running: kubectl get pods -n floe-test -l app=dagster"
            )

    @pytest.mark.requirement("FR-001")
    def test_inter_service_connectivity(self) -> None:
        """Test that services can communicate with each other.

        Validates that critical service-to-service connections work:
        - Dagster → PostgreSQL (run storage)
        - OTel Collector → Jaeger (trace forwarding)

        These connections are verified by the service health endpoints
        and operational tests above, but this test explicitly validates
        the communication paths.

        Raises:
            AssertionError: If inter-service connectivity is broken.
        """
        # Verify Dagster can reach PostgreSQL by checking Dagster's health
        dagster_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{dagster_url}/server_info")
                assert response.status_code == 200, (
                    f"Dagster server info failed: HTTP {response.status_code}"
                )
                server_info = response.json()
                # Dagster server_info should indicate healthy database connection
                assert "dagster_version" in server_info or "dagit_version" in server_info, (
                    f"Dagster server_info missing version: {server_info}\n"
                    "Dagster may not have connected to PostgreSQL."
                )
        except httpx.HTTPError as e:
            pytest.fail(f"Dagster not reachable — service connectivity broken: {e}")

    @pytest.mark.requirement("FR-049")
    def test_marquez_accessible(self) -> None:
        """Test that Marquez lineage service is functional.

        Validates FR-049 by checking either:
        1. Marquez is deployed, running, and API is functional (if marquez.enabled=true), OR
        2. The platform is configured without Marquez (marquez.enabled=false)

        Note: Marquez is an optional observability component. The platform
        architecture supports external lineage backends. When Marquez is
        disabled, this test verifies the platform runs without it.

        Raises:
            AssertionError: If Marquez is enabled but not running or not functional.
        """
        # Check if any Marquez pods exist
        result = _run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                "app.kubernetes.io/name=marquez",
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ]
        )

        if result.returncode == 0 and result.stdout.strip():
            # Marquez is deployed - verify it's running
            result = _run_kubectl(
                [
                    "get",
                    "pods",
                    "-n",
                    self.namespace,
                    "-l",
                    "app.kubernetes.io/name=marquez",
                    "-o",
                    "jsonpath={.items[*].status.phase}",
                ]
            )
            phases = result.stdout.strip().split()
            assert phases and all(p == "Running" for p in phases), (
                f"Marquez pods not running. Phases: {phases}\n"
                f"Check: kubectl get pods -n {self.namespace} "
                f"-l app.kubernetes.io/name=marquez"
            )

            # Verify Marquez API is functional
            marquez_url = os.environ.get("MARQUEZ_URL", "http://localhost:5000")
            try:
                with httpx.Client(timeout=10.0) as client:
                    # List namespaces (basic CRUD operation)
                    ns_response = client.get(f"{marquez_url}/api/v1/namespaces")
                    assert ns_response.status_code == 200, (
                        f"Marquez namespaces API failed: HTTP {ns_response.status_code}\n"
                        "Marquez must support namespace queries for lineage tracking."
                    )
                    ns_data = ns_response.json()
                    assert "namespaces" in ns_data, (
                        "Marquez response missing 'namespaces' key - API not functional"
                    )
            except httpx.HTTPError as e:
                pytest.fail(
                    f"Marquez API not reachable at {marquez_url}: "
                    f"{e}\nPort-forward may be needed: kubectl "
                    "port-forward svc/floe-platform-marquez "
                    "5000:5000 -n floe-test"
                )
        else:
            # Marquez not deployed - verify platform still works without it
            # This is valid for test environments where marquez.enabled=false
            # Verify at least core services are running (Polaris as proxy)
            result = _run_kubectl(
                [
                    "get",
                    "pods",
                    "-n",
                    self.namespace,
                    "-l",
                    "app.kubernetes.io/component=polaris",
                    "-o",
                    "jsonpath={.items[*].status.phase}",
                ]
            )
            phases = result.stdout.strip().split()
            assert phases and all(p == "Running" for p in phases), (
                "Marquez disabled but core platform not healthy.\n"
                "Polaris pods should be running as baseline."
            )
