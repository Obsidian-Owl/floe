"""Platform upgrade tests for Helm charts.

These tests validate that rolling upgrades work correctly
for the floe-platform chart.

Requirements:
- SC-008: Rolling update support
- E2E-001: Platform upgrade validation
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


def _run_helm_command(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run a helm command with timeout.

    Args:
        args: Helm command arguments
        timeout: Command timeout in seconds

    Returns:
        Completed process result
    """
    cmd = ["helm"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _run_kubectl_command(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run a kubectl command with timeout.

    Args:
        args: kubectl command arguments
        timeout: Command timeout in seconds

    Returns:
        Completed process result
    """
    cmd = ["kubectl"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def wait_for_deployment(
    name: str,
    namespace: str,
    timeout: int = 300,
    interval: int = 10,
) -> bool:
    """Wait for a deployment to be ready.

    Args:
        name: Deployment name
        namespace: Namespace
        timeout: Total timeout in seconds
        interval: Check interval in seconds

    Returns:
        True if deployment is ready, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        result = _run_kubectl_command([
            "get", "deployment", name,
            "-n", namespace,
            "-o", "jsonpath={.status.readyReplicas}",
        ])
        if result.returncode == 0 and result.stdout.strip():
            try:
                ready = int(result.stdout.strip())
                if ready > 0:
                    return True
            except ValueError:
                pass
        time.sleep(interval)
    return False


# Export for use in other test modules
__all__ = ["wait_for_deployment"]


@pytest.fixture(scope="module")
def chart_path() -> Path:
    """Get the path to the floe-platform chart."""
    current = Path(__file__).parent
    while current != current.parent:
        chart = current / "charts" / "floe-platform"
        if chart.exists():
            return chart
        current = current.parent
    pytest.fail("Could not find charts/floe-platform directory")


@pytest.fixture(scope="module")
def test_namespace() -> Generator[str, None, None]:
    """Create and clean up test namespace."""
    namespace = "floe-upgrade-test"

    # Create namespace
    _run_kubectl_command(["create", "namespace", namespace])

    yield namespace

    # Cleanup
    _run_kubectl_command(["delete", "namespace", namespace, "--ignore-not-found"])


@pytest.mark.requirement("SC-008")
@pytest.mark.requirement("E2E-001")
class TestPlatformUpgrade:
    """Tests for platform rolling upgrades."""

    @pytest.fixture(autouse=True)
    def check_cluster(self) -> None:
        """Verify kubectl access to cluster."""
        result = _run_kubectl_command(["cluster-info"])
        if result.returncode != 0:
            pytest.fail(
                "Kubernetes cluster not available.\n"
                "Start cluster with: make kind-up"
            )

    @pytest.mark.requirement("SC-008")
    def test_initial_install(
        self,
        chart_path: Path,
        test_namespace: str,
    ) -> None:
        """Test initial chart installation succeeds."""
        # Update dependencies
        result = _run_helm_command([
            "dependency", "update", str(chart_path),
        ])
        if result.returncode != 0:
            pytest.fail(f"Failed to update dependencies: {result.stderr}")

        # Install chart
        result = _run_helm_command([
            "upgrade", "--install", "floe-test",
            str(chart_path),
            "--namespace", test_namespace,
            "--values", str(chart_path / "values.yaml"),
            "--set", "dagster.enabled=false",  # Skip dagster for faster test
            "--set", "otel.enabled=false",
            "--set", "minio.enabled=false",
            "--wait",
            "--timeout", "5m",
        ])

        assert result.returncode == 0, f"Initial install failed: {result.stderr}"

    @pytest.mark.requirement("SC-008")
    def test_upgrade_with_config_change(
        self,
        chart_path: Path,
        test_namespace: str,
    ) -> None:
        """Test upgrade with configuration change succeeds."""
        # Upgrade with changed replica count
        result = _run_helm_command([
            "upgrade", "floe-test",
            str(chart_path),
            "--namespace", test_namespace,
            "--values", str(chart_path / "values.yaml"),
            "--set", "dagster.enabled=false",
            "--set", "otel.enabled=false",
            "--set", "minio.enabled=false",
            "--set", "polaris.replicaCount=2",
            "--wait",
            "--timeout", "5m",
        ])

        assert result.returncode == 0, f"Upgrade failed: {result.stderr}"

    @pytest.mark.requirement("SC-008")
    def test_rollback(
        self,
        test_namespace: str,
    ) -> None:
        """Test rollback to previous revision succeeds."""
        # Get current revision
        result = _run_helm_command([
            "history", "floe-test",
            "--namespace", test_namespace,
            "--max", "1",
            "-o", "json",
        ])

        if result.returncode != 0:
            pytest.skip("No previous revision to rollback to")

        # Rollback to previous revision
        result = _run_helm_command([
            "rollback", "floe-test", "1",
            "--namespace", test_namespace,
            "--wait",
            "--timeout", "5m",
        ])

        assert result.returncode == 0, f"Rollback failed: {result.stderr}"

    @pytest.mark.requirement("SC-008")
    def test_cleanup(
        self,
        test_namespace: str,
    ) -> None:
        """Clean up test release."""
        result = _run_helm_command([
            "uninstall", "floe-test",
            "--namespace", test_namespace,
        ])

        # Allow failure if already uninstalled
        if result.returncode != 0 and "not found" not in result.stderr:
            pytest.fail(f"Cleanup failed: {result.stderr}")
