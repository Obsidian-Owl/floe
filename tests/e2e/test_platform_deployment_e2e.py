"""E2E test: Full Platform Deployment Verification (AC-2.1).

Validates that the floe-platform Helm chart deploys correctly and all services
are healthy and accessible via their real health endpoints.

This test uses the port-forward pattern (AD-2) — services are accessed via
localhost URLs set up by `make test-e2e`. No IntegrationTestBase, no dual-mode
networking, no custom TCP health checks.

Workflow:
    helm install floe-platform → wait for pods → verify all services healthy

Prerequisites:
    - Kind cluster running: make kind-up
    - Platform deployed: make helm-install-test
    - Port-forwards active: make test-e2e (manages lifecycle)

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.1
    - charts/floe-platform/values-test.yaml: Service configuration
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import httpx
import pytest

from tests.e2e.conftest import run_helm, run_kubectl

if TYPE_CHECKING:
    from collections.abc import Callable


# K8s namespace — set by test-e2e.sh or default to floe-test
NAMESPACE = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")

# Expected core services that MUST be deployed
EXPECTED_COMPONENTS = frozenset(
    {
        "postgresql",
        "polaris",
        "dagster",
        "minio",
        "otel",
    }
)


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.1")
class TestPlatformDeployment:
    """Full platform deployment verification.

    Validates that all floe-platform services are deployed, running, and
    healthy. Uses real kubectl/helm commands and real HTTP health endpoints
    — zero mocks, zero custom infrastructure.
    """

    @pytest.mark.requirement("AC-2.1")
    def test_helm_release_deployed(self) -> None:
        """Verify floe-platform Helm release is in 'deployed' state.

        Checks that the Helm release exists and is successfully deployed,
        not in a failed or pending state.
        """
        result = run_helm(["status", "floe-platform", "-n", NAMESPACE, "-o", "json"])
        assert result.returncode == 0, (
            f"Helm release 'floe-platform' not found in namespace {NAMESPACE}.\n"
            f"stderr: {result.stderr}\n"
            f"Deploy with: make helm-install-test"
        )

        status = json.loads(result.stdout)
        release_status = status.get("info", {}).get("status", "")
        assert release_status == "deployed", (
            f"Helm release status is '{release_status}', expected 'deployed'.\n"
            f"Check: helm status floe-platform -n {NAMESPACE}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_all_pods_running(self) -> None:
        """Verify all pods in the platform namespace are Running.

        Queries real pod status via kubectl jsonpath. Asserts that every pod
        has reached the Running phase, not just that pods exist.
        """
        result = run_kubectl(
            ["get", "pods", "-o", "json"],
            namespace=NAMESPACE,
        )
        assert result.returncode == 0, (
            f"kubectl get pods failed: {result.stderr}\n"
            f"Ensure cluster is accessible: kubectl cluster-info"
        )

        pods = json.loads(result.stdout)
        pod_items = pods.get("items", [])
        assert len(pod_items) > 0, (
            f"No pods found in namespace {NAMESPACE}.\nDeploy with: make helm-install-test"
        )

        not_running: list[str] = []
        for pod in pod_items:
            name = pod["metadata"]["name"]
            phase = pod.get("status", {}).get("phase", "Unknown")
            # Completed jobs are acceptable
            if phase not in ("Running", "Succeeded"):
                not_running.append(f"  {name}: {phase}")

        assert not not_running, (
            "Pods not in Running/Succeeded state:\n"
            + "\n".join(not_running)
            + f"\nCheck: kubectl get pods -n {NAMESPACE}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_all_pods_ready(self) -> None:
        """Verify all Running pods have Ready condition = True.

        A pod can be Running but not Ready (e.g., failing readiness probes).
        This catches that case.
        """
        result = run_kubectl(
            ["get", "pods", "-o", "json"],
            namespace=NAMESPACE,
        )
        assert result.returncode == 0, f"kubectl failed: {result.stderr}"

        pods = json.loads(result.stdout)
        not_ready: list[str] = []

        for pod in pods.get("items", []):
            name = pod["metadata"]["name"]
            phase = pod.get("status", {}).get("phase", "Unknown")

            # Skip completed jobs
            if phase == "Succeeded":
                continue

            conditions = pod.get("status", {}).get("conditions", [])
            ready_condition = next(
                (c for c in conditions if c.get("type") == "Ready"),
                None,
            )
            if not ready_condition or ready_condition.get("status") != "True":
                reason = (ready_condition or {}).get("reason", "Unknown")
                not_ready.append(f"  {name}: Ready={reason}")

        assert not not_ready, (
            "Pods not Ready:\n"
            + "\n".join(not_ready)
            + f"\nCheck: kubectl describe pods -n {NAMESPACE}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_expected_components_deployed(self) -> None:
        """Verify all expected platform components have at least one pod.

        Checks that postgresql, polaris, dagster, minio, and otel components
        are all represented in the running pods.
        """
        result = run_kubectl(
            [
                "get",
                "pods",
                "-o",
                "jsonpath={.items[*].metadata.labels}",
            ],
            namespace=NAMESPACE,
        )
        assert result.returncode == 0, f"kubectl failed: {result.stderr}"

        # Re-query with JSON for reliable label parsing
        result = run_kubectl(
            ["get", "pods", "-o", "json"],
            namespace=NAMESPACE,
        )
        pods = json.loads(result.stdout)

        deployed_components: set[str] = set()
        for pod in pods.get("items", []):
            labels = pod.get("metadata", {}).get("labels", {})
            component = labels.get("app.kubernetes.io/component", "")
            name = labels.get("app.kubernetes.io/name", "")
            deployed_components.add(component)
            deployed_components.add(name)

        missing = EXPECTED_COMPONENTS - deployed_components
        assert not missing, (
            f"Missing platform components: {missing}\n"
            f"Deployed: {deployed_components}\n"
            f"All core services must be deployed for platform to function."
        )

    @pytest.mark.requirement("AC-2.1")
    def test_dagster_health(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Verify Dagster webserver responds at /server_info.

        Validates that Dagster is not just running but functionally healthy:
        returns a valid JSON response with dagster_version field.
        """
        dagster_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")
        wait_for_service(
            f"{dagster_url}/server_info",
            timeout=60,
            description="Dagster webserver",
        )

        response = httpx.get(f"{dagster_url}/server_info", timeout=10.0)
        assert response.status_code == 200, f"Dagster /server_info returned {response.status_code}"

        info = response.json()
        assert "dagster_version" in info, (
            f"Dagster /server_info missing dagster_version: {info}\n"
            "Dagster may not have connected to its PostgreSQL database."
        )
        assert isinstance(info["dagster_version"], str), (
            f"dagster_version should be string, got {type(info['dagster_version'])}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_polaris_health(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Verify Polaris catalog responds at health endpoint.

        Validates that Polaris REST catalog is accepting connections and
        can serve its configuration endpoint.
        """
        polaris_url = os.environ.get("POLARIS_URL", "http://localhost:8181")
        wait_for_service(
            f"{polaris_url}/api/catalog/v1/config",
            timeout=90,
            description="Polaris catalog",
        )

        # Verify catalog config endpoint returns valid JSON
        response = httpx.get(
            f"{polaris_url}/api/catalog/v1/config",
            timeout=10.0,
        )
        assert response.status_code == 200, (
            f"Polaris /api/catalog/v1/config returned {response.status_code}"
        )
        config = response.json()
        assert "defaults" in config or "overrides" in config, (
            f"Polaris config response missing expected keys: {config}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_minio_health(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Verify MinIO responds at /minio/health/ready.

        Validates that MinIO S3-compatible storage is ready to accept
        read/write operations, not just listening on the port.
        """
        minio_url = os.environ.get("MINIO_URL", "http://localhost:9000")
        wait_for_service(
            f"{minio_url}/minio/health/ready",
            timeout=60,
            description="MinIO S3 storage",
        )

        response = httpx.get(f"{minio_url}/minio/health/ready", timeout=10.0)
        assert response.status_code == 200, (
            f"MinIO /minio/health/ready returned {response.status_code}\n"
            "MinIO is not ready to accept operations."
        )

    @pytest.mark.requirement("AC-2.1")
    def test_marquez_health(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Verify Marquez responds at /api/v1/namespaces.

        Validates that the OpenLineage lineage service is functional and
        can serve namespace queries.
        """
        marquez_url = os.environ.get("MARQUEZ_URL", "http://localhost:5000")
        wait_for_service(
            f"{marquez_url}/api/v1/namespaces",
            timeout=90,
            description="Marquez lineage API",
        )

        response = httpx.get(f"{marquez_url}/api/v1/namespaces", timeout=10.0)
        assert response.status_code == 200, (
            f"Marquez /api/v1/namespaces returned {response.status_code}"
        )
        data = response.json()
        assert "namespaces" in data, f"Marquez response missing 'namespaces' key: {data}"

    @pytest.mark.requirement("AC-2.1")
    def test_jaeger_health(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Verify Jaeger responds at /api/services.

        Validates that the distributed tracing backend is functional and
        can serve service queries.
        """
        jaeger_url = os.environ.get("JAEGER_URL", "http://localhost:16686")
        wait_for_service(
            f"{jaeger_url}/api/services",
            timeout=60,
            description="Jaeger query API",
        )

        response = httpx.get(f"{jaeger_url}/api/services", timeout=10.0)
        assert response.status_code == 200, f"Jaeger /api/services returned {response.status_code}"
        data = response.json()
        assert "data" in data, f"Jaeger response missing 'data' key: {data}"
        assert isinstance(data["data"], list), (
            f"Jaeger services data should be a list, got {type(data['data'])}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_all_services_have_endpoints(self) -> None:
        """Verify all core K8s Services have at least one endpoint.

        A Service can exist without endpoints if no pods match its selector.
        This catches selector mismatches between Service and Deployment.
        """
        # Core services that must have endpoints
        core_services = [
            "floe-platform-postgresql",
            "floe-platform-polaris",
            "floe-platform-minio",
        ]

        services_without_endpoints: list[str] = []

        for svc_name in core_services:
            result = run_kubectl(
                [
                    "get",
                    "endpoints",
                    svc_name,
                    "-o",
                    "jsonpath={.subsets[*].addresses[*].ip}",
                ],
                namespace=NAMESPACE,
            )

            if result.returncode != 0:
                services_without_endpoints.append(f"  {svc_name}: not found")
            elif not result.stdout.strip():
                services_without_endpoints.append(f"  {svc_name}: no endpoints")

        assert not services_without_endpoints, (
            "Services without endpoints (selector mismatch?):\n"
            + "\n".join(services_without_endpoints)
            + f"\nCheck: kubectl get endpoints -n {NAMESPACE}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_dagster_graphql_operational(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Verify Dagster GraphQL API can execute queries.

        Goes beyond HTTP 200 — actually executes a GraphQL query to verify
        the API is functionally correct, not just listening.
        """
        dagster_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")
        wait_for_service(
            f"{dagster_url}/server_info",
            timeout=60,
            description="Dagster webserver",
        )

        response = httpx.post(
            f"{dagster_url}/graphql",
            json={"query": "{ version }"},
            timeout=10.0,
        )
        assert response.status_code == 200, f"Dagster GraphQL returned {response.status_code}"

        data = response.json()
        assert "data" in data, f"GraphQL response missing 'data': {data}"
        assert "version" in data["data"], f"GraphQL version query returned no version: {data}"
        version = data["data"]["version"]
        assert isinstance(version, str) and len(version) > 0, (
            f"Dagster version should be non-empty string, got: {version!r}"
        )

    @pytest.mark.requirement("WU2-AC5")
    def test_cube_store_pod_running(self) -> None:
        """Verify Cube Store StatefulSet has a running pod.

        This test validates that the multi-arch Cube Store image was
        successfully pulled and the pod is running.
        """
        result = run_kubectl(
            [
                "get",
                "pods",
                "-l",
                "app.kubernetes.io/component=cube-store",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            namespace=NAMESPACE,
        )
        assert result.returncode == 0, f"kubectl failed: {result.stderr}"

        phases = result.stdout.strip()
        assert phases, (
            "No Cube Store pods found. "
            "Ensure cube.cubeStore.enabled=true in values-test.yaml "
            "and the multi-arch image is available at ghcr.io/obsidian-owl/cube-store"
        )
        assert "Running" in phases, (
            f"Cube Store pod not running. Phase(s): {phases}. "
            "Check: kubectl get pods -l app.kubernetes.io/component=cube-store "
            f"-n {NAMESPACE}"
        )

    @pytest.mark.requirement("WU2-AC5")
    def test_cube_store_ready(self) -> None:
        """Verify Cube Store pod has Ready condition.

        Goes beyond Running phase — validates the pod's readiness probe
        is passing, meaning Cube Store is accepting connections.
        """
        result = run_kubectl(
            [
                "get",
                "pods",
                "-l",
                "app.kubernetes.io/component=cube-store",
                "-o",
                "json",
            ],
            namespace=NAMESPACE,
        )
        assert result.returncode == 0, f"kubectl failed: {result.stderr}"

        pods = json.loads(result.stdout)
        pod_items = pods.get("items", [])
        assert len(pod_items) > 0, "No Cube Store pods found"

        pod = pod_items[0]
        conditions = pod.get("status", {}).get("conditions", [])
        ready = next(
            (c for c in conditions if c.get("type") == "Ready"),
            None,
        )
        assert ready is not None and ready.get("status") == "True", (
            f"Cube Store pod not Ready. Conditions: {conditions}"
        )

    @pytest.mark.requirement("AC-2.1")
    def test_postgresql_functional(self) -> None:
        """Verify PostgreSQL accepts queries via kubectl exec.

        Executes a real SQL query inside the PostgreSQL pod to verify the
        database is not just running but accepting connections and queries.
        """
        # Find PostgreSQL pod
        result = run_kubectl(
            [
                "get",
                "pods",
                "-l",
                "app.kubernetes.io/component=postgresql",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            ],
            namespace=NAMESPACE,
        )
        assert result.returncode == 0 and result.stdout.strip(), (
            f"PostgreSQL pod not found: {result.stderr}\n"
            f"Check: kubectl get pods -n {NAMESPACE} -l app.kubernetes.io/component=postgresql"
        )

        pg_pod = result.stdout.strip()
        pg_user = os.environ.get("POSTGRES_USER", "floe")

        # Execute SELECT 1 to verify database connectivity
        query_result = run_kubectl(
            [
                "exec",
                pg_pod,
                "--",
                "psql",
                "-U",
                pg_user,
                "-c",
                "SELECT 1 as connected;",
            ],
            namespace=NAMESPACE,
            timeout=30,
        )
        assert query_result.returncode == 0, (
            f"PostgreSQL not accepting queries: {query_result.stderr}\n"
            f"User: {pg_user}, Pod: {pg_pod}"
        )
        assert "1" in query_result.stdout, (
            f"PostgreSQL SELECT 1 returned unexpected result: {query_result.stdout}"
        )
