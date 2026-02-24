"""E2E test: Service Failure Resilience (AC-2.7).

Validates graceful error handling when a service pod is killed mid-operation.

Workflow:
    Start operation → kill a service pod → verify graceful error (not silent failure)

NOTE: persistence.enabled=false in values-test.yaml — data does NOT survive
pod restart. This test verifies ERROR HANDLING ONLY, not retry-after-restore.

Prerequisites:
    - Kind cluster: make kind-up
    - Port-forwards active: make test-e2e

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.7
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from testing.fixtures.polling import wait_for_condition
from tests.e2e.conftest import run_kubectl

# K8s namespace
NAMESPACE = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.7")
class TestServiceFailureResilience:
    """Service failure resilience: kill pod → graceful error.

    Tests that the platform handles service failures gracefully with
    descriptive errors rather than silent failures or hangs.
    """

    @pytest.mark.requirement("AC-2.7")
    def test_minio_pod_restart_detected(self) -> None:
        """Verify MinIO health endpoint fails when pod is deleted.

        Deletes the MinIO pod and verifies that:
        1. The health endpoint returns an error (not silent success)
        2. K8s restarts the pod (Deployment controller)
        3. Service becomes healthy again after restart

        This validates error detection, NOT data recovery.
        """
        minio_url = os.environ.get("MINIO_URL", "http://localhost:9000")

        # Verify MinIO is healthy before the test
        response = httpx.get(f"{minio_url}/minio/health/ready", timeout=5.0)
        assert response.status_code == 200, (
            "MinIO not healthy before test — cannot test failure resilience"
        )

        # Delete the MinIO pod (K8s will restart it)
        result = run_kubectl(
            [
                "delete",
                "pod",
                "-l",
                "app.kubernetes.io/name=minio",
                "--grace-period=0",
                "--force",
            ],
            namespace=NAMESPACE,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to delete MinIO pod: {result.stderr}"

        # Verify the service becomes unavailable (error, not silent)
        # Port-forward may break when pod restarts — that's expected
        service_down = False
        for _ in range(5):
            try:
                response = httpx.get(
                    f"{minio_url}/minio/health/ready",
                    timeout=2.0,
                )
                if response.status_code >= 500:
                    service_down = True
                    break
            except (httpx.HTTPError, OSError):
                service_down = True
                break

        assert service_down, (
            "MinIO should have been unavailable after pod deletion.\n"
            "Expected: connection error or HTTP 5xx\n"
            "Got: service still responding normally"
        )

        # Wait for K8s to restart the pod
        pod_ready = wait_for_condition(
            lambda: _check_pod_ready("app.kubernetes.io/name=minio"),
            timeout=120.0,
            interval=5.0,
            description="MinIO pod to restart and become Ready",
            raise_on_timeout=False,
        )

        assert pod_ready, (
            f"MinIO pod did not restart within 120s.\n"
            f"Check: kubectl get pods -n {NAMESPACE} -l app.kubernetes.io/name=minio"
        )

    @pytest.mark.requirement("AC-2.7")
    def test_polaris_pod_restart_detected(self) -> None:
        """Verify Polaris health fails when pod is deleted, then recovers.

        Similar to MinIO test but for the Polaris catalog service.
        """
        polaris_health_url = os.environ.get("POLARIS_HEALTH_URL", "http://localhost:8182")

        # Verify Polaris is healthy (management endpoint, no OAuth needed)
        response = httpx.get(
            f"{polaris_health_url}/q/health/ready",
            timeout=5.0,
        )
        assert response.status_code == 200, "Polaris not healthy before test"

        # Delete Polaris pod
        result = run_kubectl(
            [
                "delete",
                "pod",
                "-l",
                "app.kubernetes.io/component=polaris",
                "--grace-period=0",
                "--force",
            ],
            namespace=NAMESPACE,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to delete Polaris pod: {result.stderr}"

        # Verify service disruption
        service_down = False
        for _ in range(5):
            try:
                response = httpx.get(
                    f"{polaris_health_url}/q/health/ready",
                    timeout=2.0,
                )
                if response.status_code >= 500:
                    service_down = True
                    break
            except (httpx.HTTPError, OSError):
                service_down = True
                break

        assert service_down, "Polaris should have been unavailable after pod deletion"

        # Wait for recovery
        pod_ready = wait_for_condition(
            lambda: _check_pod_ready("app.kubernetes.io/component=polaris"),
            timeout=120.0,
            interval=5.0,
            description="Polaris pod to restart and become Ready",
            raise_on_timeout=False,
        )

        assert pod_ready, (
            f"Polaris pod did not restart within 120s.\n"
            f"Check: kubectl get pods -n {NAMESPACE} -l app.kubernetes.io/component=polaris"
        )

    @pytest.mark.requirement("AC-2.7")
    def test_compilation_during_service_outage(
        self,
        project_root: Path,
    ) -> None:
        """Verify compilation handles service outage gracefully.

        Restarts a service pod, then immediately attempts compilation.
        Compilation should either succeed (if it doesn't need the downed
        service) or fail with a descriptive error containing the service name.

        This validates pipeline-aware failure handling without requiring
        Dagster pipeline infrastructure — compilation is a Python process.
        """
        from floe_core.compilation.stages import compile_pipeline

        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Restart Polaris pod to create transient outage
        result = run_kubectl(
            [
                "delete",
                "pod",
                "-l",
                "app.kubernetes.io/component=polaris",
                "--grace-period=0",
                "--force",
            ],
            namespace=NAMESPACE,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to delete Polaris pod: {result.stderr}"

        # Immediately attempt compilation during the outage window
        try:
            artifacts = compile_pipeline(spec_path, manifest_path)
            # Compilation succeeded — it doesn't depend on Polaris at compile time
            assert artifacts.version, "Compilation returned empty artifacts during service outage"
        except Exception as e:
            # Compilation failed — verify the error is descriptive
            error_msg = str(e).lower()
            assert (
                "polaris" in error_msg
                or "catalog" in error_msg
                or "connection" in error_msg
                or "timeout" in error_msg
                or "service" in error_msg
            ), (
                f"Compilation failed with non-descriptive error during outage: {e}\n"
                "Errors during service outage should mention the affected service."
            )

        # Wait for Polaris to recover (cleanup for other tests)
        pod_ready = wait_for_condition(
            lambda: _check_pod_ready("app.kubernetes.io/component=polaris"),
            timeout=120.0,
            interval=5.0,
            description="Polaris pod to restart after compilation test",
            raise_on_timeout=False,
        )
        assert pod_ready, (
            f"Polaris pod did not recover within 120s.\n"
            f"Check: kubectl get pods -n {NAMESPACE} -l app.kubernetes.io/component=polaris"
        )


def _check_pod_ready(label_selector: str) -> bool:
    """Check if pods matching selector are Ready.

    Args:
        label_selector: K8s label selector string.

    Returns:
        True if all matching pods are Ready.
    """
    result = run_kubectl(
        [
            "get",
            "pods",
            "-l",
            label_selector,
            "-o",
            "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}",
        ],
        namespace=NAMESPACE,
    )
    if result.returncode != 0:
        return False
    statuses = result.stdout.strip().split()
    return bool(statuses and all(s == "True" for s in statuses))
