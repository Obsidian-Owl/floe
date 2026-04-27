"""E2E test: Helm Upgrade (AC-2.9).

Validates the Helm upgrade path:
    Deploy v1 → modify values → helm upgrade → verify rolling update completes

NOTE: postgresql.persistence.enabled=false in values-test.yaml — PostgreSQL
uses emptyDir, data does NOT survive pod restart. This test validates the
Helm upgrade MECHANISM (rolling update, service continuity), NOT data durability.

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

from testing.fixtures.flux import flux_suspended  # noqa: F401 (pytest fixture import)
from testing.fixtures.polling import wait_for_condition
from tests.e2e.conftest import run_helm, run_kubectl

# K8s namespace
NAMESPACE = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")
# Helm release name
HELM_RELEASE = "floe-platform"

_DAGSTER_IMAGE_VALUE_PATHS = (
    "dagster.dagsterWebserver.image.repository",
    "dagster.dagsterWebserver.image.tag",
    "dagster.dagsterDaemon.image.repository",
    "dagster.dagsterDaemon.image.tag",
    "dagster.runLauncher.config.k8sRunLauncher.image.repository",
    "dagster.runLauncher.config.k8sRunLauncher.image.tag",
)


def _value_at_path(values: dict[str, object], path: str) -> object:
    """Return a nested Helm value by dotted path."""
    current: object = values
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def _current_dagster_image_overrides(release: str, namespace: str) -> list[str]:
    """Build Helm ``--set-string`` args for the current Dagster image values.

    The upgrade uses clean chart test values to avoid carrying stale release
    state, but the generated demo image tag is runtime-specific in Kind/DevPod.
    Preserve only those image coordinates from the active release.
    """
    values_result = run_helm(
        ["get", "values", release, "-n", namespace, "--all", "-o", "json"],
    )
    assert values_result.returncode == 0, (
        f"Unable to read current Helm values for {release}: {values_result.stderr}"
    )

    current_values = json.loads(values_result.stdout)
    overrides: list[str] = []
    missing_paths: list[str] = []
    for path in _DAGSTER_IMAGE_VALUE_PATHS:
        try:
            value = _value_at_path(current_values, path)
        except KeyError:
            missing_paths.append(path)
            continue
        overrides.extend(["--set-string", f"{path}={value}"])

    assert not missing_paths, (
        "Current Helm release is missing Dagster image values required for a "
        f"safe in-place upgrade: {', '.join(missing_paths)}"
    )
    return overrides


def _recover_stuck_release(release: str, namespace: str) -> None:
    """Detect and recover from stuck Helm release states.

    Delegates to the shared ``recover_stuck_helm_release`` utility.

    Args:
        release: Helm release name.
        namespace: K8s namespace.

    Raises:
        RuntimeError: If recovery fails.
        ValueError: If helm status output is not valid JSON.
    """
    from testing.fixtures.helm import recover_stuck_helm_release

    recover_stuck_helm_release(
        release,
        namespace,
        rollback_timeout="5m",
        helm_runner=run_helm,
    )


@pytest.mark.e2e
@pytest.mark.destructive
@pytest.mark.requirement("AC-2.9")
class TestHelmUpgrade:
    """Helm upgrade: rolling update + service continuity.

    Validates that the floe-platform Helm chart can be upgraded in-place
    without causing CrashLoopBackOff or permanent service disruption.
    """

    @pytest.mark.requirement("AC-2.9")
    @pytest.mark.timeout(1260)
    def test_helm_upgrade_succeeds(self, flux_suspended: None) -> None:  # noqa: F811
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
        image_overrides = _current_dagster_image_overrides(HELM_RELEASE, NAMESPACE)

        # Upgrade with an annotation change (minimal modification)
        # --rollback-on-failure auto-rollbacks on failure (prevents leaving
        # release in 'failed' state which cascades to downstream tests).
        # Replaces deprecated --atomic (removed in Helm v4).
        # --timeout 8m allows for the pg-pre-upgrade hook's
        # activeDeadlineSeconds: 300 plus scheduling latency.
        try:
            upgrade_result = run_helm(
                [
                    "upgrade",
                    HELM_RELEASE,
                    "charts/floe-platform",
                    "-n",
                    NAMESPACE,
                    "-f",
                    "charts/floe-platform/values-test.yaml",
                    "--set",
                    "global.annotations.e2e-test-revision=upgrade-test",
                    *image_overrides,
                    "--rollback-on-failure",
                    "--wait=legacy",
                    "--timeout",
                    "8m",
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
        finally:
            # Ensure release is in deployed state for downstream tests.
            # Wrap in try/except so recovery failure doesn't mask the
            # original test result.
            try:
                _recover_stuck_release(HELM_RELEASE, NAMESPACE)
            except Exception as exc:
                # Recovery is best-effort; log but don't mask the original error
                import logging

                logging.getLogger(__name__).warning("Post-upgrade release recovery failed: %s", exc)

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

        # Latest revision must be "deployed"; earlier revisions may be
        # "superseded" or "failed" (e.g., initial install timed out,
        # then recovered via rollback).
        latest_revision = history[-1].get("revision")
        for entry in history:
            status = entry.get("status", "")
            revision = entry.get("revision")
            if revision == latest_revision:
                assert status == "deployed", f"Latest revision {revision} not deployed: {status}"
            else:
                assert status in ("deployed", "superseded", "failed"), (
                    f"Unexpected revision status: {status} for revision {revision}"
                )
