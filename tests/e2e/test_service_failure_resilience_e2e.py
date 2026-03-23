"""E2E test: Service Failure Resilience (AC-2.7).

Validates graceful error handling when a service pod is killed mid-operation.

Workflow:
    Start operation → kill a service pod → verify graceful error (not silent failure)

NOTE: postgresql.persistence.enabled=false in values-test.yaml — PostgreSQL
uses emptyDir, data does NOT survive pod restart. This test verifies ERROR
HANDLING ONLY, not retry-after-restore.

Prerequisites:
    - Kind cluster: make kind-up
    - Port-forwards active: make test-e2e

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.7
"""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

import httpx
import pytest

from testing.fixtures.kubernetes import (
    assert_pod_recovery,
    check_pod_ready,
    run_kubectl,
)
from testing.fixtures.polling import wait_for_condition
from testing.fixtures.services import ServiceEndpoint

logger = logging.getLogger(__name__)

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
        """Verify MinIO pod replacement via UID change after deletion.

        Deletes the MinIO pod and verifies that:
        1. K8s creates a replacement pod with a different UID
        2. Recovery completes within 30 seconds
        3. The replacement pod is Ready

        This validates pod replacement detection, NOT downtime observation.
        """
        minio_url = os.environ.get("MINIO_URL", ServiceEndpoint("minio").url)

        # Verify MinIO is healthy before the test
        response = httpx.get(f"{minio_url}/minio/health/ready", timeout=5.0)
        assert response.status_code == 200, (
            "MinIO not healthy before test — cannot test failure resilience"
        )

        # Delete pod and assert recovery via UID change
        result = assert_pod_recovery(
            "app.kubernetes.io/name=minio",
            "MinIO",
            namespace=NAMESPACE,
        )
        original_uid, new_uid, recovery_secs = result

        assert new_uid != original_uid, (
            f"MinIO pod UID did not change after deletion: {original_uid[:8]}"
        )
        assert recovery_secs < 30.0, f"MinIO recovery took {recovery_secs:.1f}s (limit: 30s)"

    @pytest.mark.requirement("AC-2.7")
    def test_polaris_pod_restart_detected(self) -> None:
        """Verify Polaris pod replacement via UID change after deletion.

        Similar to MinIO test but for the Polaris catalog service.
        """
        polaris_health_url = os.environ.get(
            "POLARIS_HEALTH_URL",
            ServiceEndpoint("polaris-management").url,
        )

        # Verify Polaris is healthy (management endpoint, no OAuth needed)
        response = httpx.get(
            f"{polaris_health_url}/q/health/ready",
            timeout=5.0,
        )
        assert response.status_code == 200, "Polaris not healthy before test"

        # Delete pod and assert recovery via UID change
        result = assert_pod_recovery(
            "app.kubernetes.io/component=polaris",
            "Polaris",
            namespace=NAMESPACE,
        )
        original_uid, new_uid, recovery_secs = result

        assert new_uid != original_uid, (
            f"Polaris pod UID did not change after deletion: {original_uid[:8]}"
        )
        assert recovery_secs < 30.0, f"Polaris recovery took {recovery_secs:.1f}s (limit: 30s)"

        # Wait for port-forward to reconnect (port 8182 management health)
        polaris_health_ready = wait_for_condition(
            lambda: _check_port_forward_health(f"{polaris_health_url}/q/health/ready"),
            timeout=60.0,
            interval=3.0,
            description="Polaris port-forward health (8182) to recover",
            raise_on_timeout=False,
        )
        if not polaris_health_ready:
            warnings.warn(
                "Polaris port-forward (8182) did not recover within 60s after pod restart. "
                "Subsequent tests using port 8182 may fail.",
                UserWarning,
                stacklevel=2,
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
        assert result.returncode == 0, (
            f"Failed to delete Polaris pod: {(result.stderr or '')[:500]}"
        )

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
            lambda: check_pod_ready("app.kubernetes.io/component=polaris", namespace=NAMESPACE),
            timeout=120.0,
            interval=5.0,
            description="Polaris pod to restart after compilation test",
            raise_on_timeout=False,
        )
        assert pod_ready, (
            f"Polaris pod did not recover within 120s.\n"
            f"Check: kubectl get pods -n {NAMESPACE} -l app.kubernetes.io/component=polaris"
        )


def _check_port_forward_health(url: str) -> bool:
    """Check if a port-forwarded health endpoint is reachable.

    Args:
        url: Full URL to health endpoint (e.g. http://localhost:8182/q/health/ready).

    Returns:
        True if endpoint returns HTTP 200.
    """
    try:
        response = httpx.get(url, timeout=3.0)
        return response.status_code == 200
    except (httpx.HTTPError, OSError):
        return False
