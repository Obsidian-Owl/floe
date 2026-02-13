"""E2E test: Helm Upgrade (AC-2.9).

Validates the Helm upgrade path:
    Deploy v1 → modify values → helm upgrade → verify rolling update completes

NOTE: persistence.enabled=false in values-test.yaml — data does NOT survive
pod restart. This test validates the Helm upgrade MECHANISM (rolling update,
service continuity), NOT data durability.

Prerequisites:
    - Kind cluster: make kind-up
    - Port-forwards active: make test-e2e

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.9
"""

from __future__ import annotations

import json
import os

import pytest

from testing.fixtures.polling import wait_for_condition
from tests.e2e.conftest import run_helm, run_kubectl

# K8s namespace
NAMESPACE = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")
# Helm release name
HELM_RELEASE = "floe-platform"


def _recover_stuck_release(release: str, namespace: str) -> None:
    """Detect and recover from stuck Helm release states.

    Checks for pending-upgrade, pending-install, pending-rollback, and failed
    states and performs rollback to the last known good revision.

    Args:
        release: Helm release name.
        namespace: K8s namespace.

    Raises:
        AssertionError: If recovery fails.
    """
    status_result = run_helm(
        ["status", release, "-n", namespace, "-o", "json"],
    )
    if status_result.returncode != 0:
        return  # Release doesn't exist, nothing to recover

    import json as _json

    current = _json.loads(status_result.stdout)
    release_status = current.get("info", {}).get("status", "")

    stuck_states = ("pending-upgrade", "pending-install", "pending-rollback", "failed")
    if release_status not in stuck_states:
        return

    current_revision = current.get("version", 1)
    rollback_revision = max(1, current_revision - 1)
    print(
        f"WARNING: Helm release '{release}' in '{release_status}' state. "
        f"Rolling back to revision {rollback_revision}..."
    )

    rollback_result = run_helm(
        ["rollback", release, str(rollback_revision), "-n", namespace, "--wait", "--timeout", "3m"],
    )
    assert rollback_result.returncode == 0, (
        f"Helm rollback failed: {rollback_result.stderr}\n"
        f"Release stuck in '{release_status}'. Manual intervention required:\n"
        f"  helm rollback {release} {rollback_revision} -n {namespace}"
    )
    print(f"Recovery complete: rolled back to revision {rollback_revision}")


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.9")
class TestHelmUpgrade:
    """Helm upgrade: rolling update + service continuity.

    Validates that the floe-platform Helm chart can be upgraded in-place
    without causing CrashLoopBackOff or permanent service disruption.
    """

    @pytest.mark.requirement("AC-2.9")
    def test_helm_upgrade_succeeds(self) -> None:
        """Verify helm upgrade completes without error.

        Detects and recovers from stuck release states (pending-upgrade,
        pending-install, failed) before attempting the upgrade.
        Runs helm upgrade with a minor change (annotation bump) and
        verifies the release transitions to 'deployed' state.
        """
        # Recover from stuck release state if needed (RC-3)
        _recover_stuck_release(HELM_RELEASE, NAMESPACE)

        # Get current revision
        status_result = run_helm(
            ["status", HELM_RELEASE, "-n", NAMESPACE, "-o", "json"],
        )
        assert status_result.returncode == 0, (
            f"floe-platform release not found: {status_result.stderr}"
        )
        current = json.loads(status_result.stdout)
        current_revision = current.get("version", 0)

        # Upgrade with an annotation change (minimal modification)
        upgrade_result = run_helm(
            [
                "upgrade",
                HELM_RELEASE,
                "charts/floe-platform",
                "-n",
                NAMESPACE,
                "--reuse-values",
                "--set",
                "global.annotations.e2e-test-revision=upgrade-test",
                "--wait",
                "--timeout",
                "5m",
            ],
        )
        assert upgrade_result.returncode == 0, (
            f"Helm upgrade failed: {upgrade_result.stderr}\n"
            "Chart may have incompatible values or templates."
        )

        # Verify revision bumped
        new_status = run_helm(
            ["status", HELM_RELEASE, "-n", NAMESPACE, "-o", "json"],
        )
        assert new_status.returncode == 0
        new = json.loads(new_status.stdout)
        new_revision = new.get("version", 0)
        assert new_revision > current_revision, (
            f"Revision did not bump: {current_revision} → {new_revision}"
        )
        assert new["info"]["status"] == "deployed", (
            f"Release status after upgrade: {new['info']['status']}"
        )

    @pytest.mark.requirement("AC-2.9")
    def test_no_crashloopbackoff_after_upgrade(self) -> None:
        """Verify no pods are in CrashLoopBackOff after upgrade.

        CrashLoopBackOff during rolling updates indicates a chart
        configuration error (e.g., missing env var, wrong image tag).
        """
        result = run_kubectl(
            ["get", "pods", "-o", "json"],
            namespace=NAMESPACE,
        )
        assert result.returncode == 0, f"kubectl failed: {result.stderr}"

        pods = json.loads(result.stdout)
        crashloop_pods: list[str] = []

        for pod in pods.get("items", []):
            name = pod["metadata"]["name"]
            container_statuses = pod.get("status", {}).get("containerStatuses", [])
            for cs in container_statuses:
                waiting = cs.get("state", {}).get("waiting", {})
                if waiting.get("reason") == "CrashLoopBackOff":
                    crashloop_pods.append(f"  {name}: {cs.get('name')}")

        assert not crashloop_pods, (
            "Pods in CrashLoopBackOff after upgrade:\n"
            + "\n".join(crashloop_pods)
            + f"\nCheck: kubectl describe pods -n {NAMESPACE}"
        )

    @pytest.mark.requirement("AC-2.9")
    def test_services_healthy_after_upgrade(self) -> None:
        """Verify all pods are Ready after the upgrade completes.

        The --wait flag in helm upgrade should ensure this, but we verify
        independently to catch race conditions.
        """

        def all_pods_ready() -> bool:
            result = run_kubectl(
                ["get", "pods", "-o", "json"],
                namespace=NAMESPACE,
            )
            if result.returncode != 0:
                return False
            pods = json.loads(result.stdout)
            for pod in pods.get("items", []):
                phase = pod.get("status", {}).get("phase", "")
                if phase == "Succeeded":
                    continue
                conditions = pod.get("status", {}).get("conditions", [])
                ready = next(
                    (c for c in conditions if c.get("type") == "Ready"),
                    None,
                )
                if not ready or ready.get("status") != "True":
                    return False
            return True

        ready = wait_for_condition(
            all_pods_ready,
            timeout=120.0,
            interval=5.0,
            description="all pods to be Ready after upgrade",
            raise_on_timeout=False,
        )

        assert ready, f"Not all pods Ready after upgrade.\nCheck: kubectl get pods -n {NAMESPACE}"

    @pytest.mark.requirement("AC-2.9")
    def test_helm_history_shows_revisions(self) -> None:
        """Verify helm history shows at least 2 revisions.

        This confirms the upgrade actually created a new revision
        rather than being a no-op.
        """
        result = run_helm(
            ["history", HELM_RELEASE, "-n", NAMESPACE, "-o", "json"],
        )
        assert result.returncode == 0, f"helm history failed: {result.stderr}"

        history = json.loads(result.stdout)
        assert len(history) >= 2, (
            f"Expected at least 2 revisions (initial + upgrade), got {len(history)}"
        )

        # All revisions should be in deployed or superseded state
        for entry in history:
            status = entry.get("status", "")
            assert status in ("deployed", "superseded"), (
                f"Unexpected revision status: {status} for revision {entry.get('revision')}"
            )
