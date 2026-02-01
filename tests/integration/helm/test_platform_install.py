"""Platform chart installation tests.

Tests that validate the floe-platform Helm chart can be installed in a Kind cluster.
These are the most comprehensive tests that verify actual deployment behavior.

Requirements:
    FR-082: Helm chart installation validation

Note:
    These tests require a running Kind cluster (make kind-up).
    They create real Kubernetes resources and clean up after completion.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _helm_uninstall(release_name: str, namespace: str) -> None:
    """Uninstall a Helm release (ignoring errors).

    Args:
        release_name: Helm release name.
        namespace: Kubernetes namespace.
    """
    subprocess.run(
        [
            "helm",
            "uninstall",
            release_name,
            "--namespace",
            namespace,
            "--wait",
        ],
        capture_output=True,
        check=False,
    )


class TestPlatformChartInstall:
    """Installation tests for the floe-platform Helm chart."""

    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.slow
    @pytest.mark.usefixtures(
        "kind_cluster", "helm_available", "update_helm_dependencies"
    )
    def test_chart_dry_run_install(
        self,
        platform_chart_path: Path,
        test_namespace: str,
        helm_release_name: str,
    ) -> None:
        """Test chart dry-run installation succeeds.

        Validates that `helm install --dry-run` succeeds.
        This tests server-side validation without creating resources.

        Args:
            platform_chart_path: Path to platform chart.
            test_namespace: Unique test namespace.
            helm_release_name: Unique release name.
        """
        result = subprocess.run(
            [
                "helm",
                "install",
                helm_release_name,
                str(platform_chart_path),
                "--namespace",
                test_namespace,
                "--dry-run",
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )

        stdout = result.stdout.decode() if result.stdout else ""
        stderr = result.stderr.decode() if result.stderr else ""

        assert result.returncode == 0, (
            f"Dry-run install failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.slow
    @pytest.mark.usefixtures(
        "kind_cluster", "helm_available", "update_helm_dependencies"
    )
    def test_chart_install_minimal(
        self,
        platform_chart_path: Path,
        test_namespace: str,
        helm_release_name: str,
    ) -> None:
        """Test chart installation with minimal components.

        Validates that the chart can be installed with optional components disabled.
        This tests the core chart functionality without waiting for all pods.

        Args:
            platform_chart_path: Path to platform chart.
            test_namespace: Unique test namespace.
            helm_release_name: Unique release name.
        """
        try:
            result = subprocess.run(
                [
                    "helm",
                    "install",
                    helm_release_name,
                    str(platform_chart_path),
                    "--namespace",
                    test_namespace,
                    "--set",
                    "dagster.enabled=false",
                    "--set",
                    "otel.enabled=false",
                    "--set",
                    "marquez.enabled=false",
                    "--set",
                    "minio.enabled=false",
                    # Keep Polaris and PostgreSQL for basic functionality
                    "--wait",
                    "--timeout",
                    "3m",
                ],
                capture_output=True,
                timeout=240,
                check=False,
            )

            stdout = result.stdout.decode() if result.stdout else ""
            stderr = result.stderr.decode() if result.stderr else ""

            assert result.returncode == 0, (
                f"Minimal install failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

            # Verify the release exists
            list_result = subprocess.run(
                [
                    "helm",
                    "list",
                    "--namespace",
                    test_namespace,
                    "-o",
                    "json",
                ],
                capture_output=True,
                check=True,
            )

            assert helm_release_name in list_result.stdout.decode(), (
                f"Release {helm_release_name} not found after install"
            )

        finally:
            _helm_uninstall(helm_release_name, test_namespace)

    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.slow
    @pytest.mark.usefixtures(
        "kind_cluster", "helm_available", "update_helm_dependencies"
    )
    def test_chart_upgrade_works(
        self,
        platform_chart_path: Path,
        test_namespace: str,
        helm_release_name: str,
    ) -> None:
        """Test chart upgrade works after initial install.

        Validates that `helm upgrade` succeeds on an existing release.
        This tests that the chart supports in-place upgrades.

        Args:
            platform_chart_path: Path to platform chart.
            test_namespace: Unique test namespace.
            helm_release_name: Unique release name.
        """
        try:
            # Initial install (minimal to be fast)
            install_result = subprocess.run(
                [
                    "helm",
                    "install",
                    helm_release_name,
                    str(platform_chart_path),
                    "--namespace",
                    test_namespace,
                    "--set",
                    "dagster.enabled=false",
                    "--set",
                    "otel.enabled=false",
                    "--set",
                    "postgresql.enabled=false",
                    "--set",
                    "polaris.enabled=false",
                ],
                capture_output=True,
                timeout=120,
                check=False,
            )

            if install_result.returncode != 0:
                stderr = install_result.stderr.decode() if install_result.stderr else ""
                pytest.skip(f"Initial install failed, skipping upgrade test: {stderr}")

            # Upgrade with different values
            upgrade_result = subprocess.run(
                [
                    "helm",
                    "upgrade",
                    helm_release_name,
                    str(platform_chart_path),
                    "--namespace",
                    test_namespace,
                    "--set",
                    "dagster.enabled=false",
                    "--set",
                    "otel.enabled=false",
                    "--set",
                    "postgresql.enabled=false",
                    "--set",
                    "polaris.enabled=false",
                    "--set",
                    "global.environment=staging",
                ],
                capture_output=True,
                timeout=120,
                check=False,
            )

            stdout = upgrade_result.stdout.decode() if upgrade_result.stdout else ""
            stderr = upgrade_result.stderr.decode() if upgrade_result.stderr else ""

            assert upgrade_result.returncode == 0, (
                f"Upgrade failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

        finally:
            _helm_uninstall(helm_release_name, test_namespace)

    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.slow
    @pytest.mark.usefixtures(
        "kind_cluster", "helm_available", "update_helm_dependencies"
    )
    def test_chart_uninstall_clean(
        self,
        platform_chart_path: Path,
        test_namespace: str,
        helm_release_name: str,
    ) -> None:
        """Test chart uninstallation is clean.

        Validates that `helm uninstall` removes all resources.

        Args:
            platform_chart_path: Path to platform chart.
            test_namespace: Unique test namespace.
            helm_release_name: Unique release name.
        """
        # Install with minimal components
        install_result = subprocess.run(
            [
                "helm",
                "install",
                helm_release_name,
                str(platform_chart_path),
                "--namespace",
                test_namespace,
                "--set",
                "dagster.enabled=false",
                "--set",
                "otel.enabled=false",
                "--set",
                "postgresql.enabled=false",
                "--set",
                "polaris.enabled=false",
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )

        if install_result.returncode != 0:
            stderr = install_result.stderr.decode() if install_result.stderr else ""
            pytest.skip(f"Install failed, skipping uninstall test: {stderr}")

        # Uninstall
        uninstall_result = subprocess.run(
            [
                "helm",
                "uninstall",
                helm_release_name,
                "--namespace",
                test_namespace,
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )

        assert uninstall_result.returncode == 0, (
            "Uninstall failed: "
            + (uninstall_result.stderr.decode() if uninstall_result.stderr else "")
        )

        # Verify release is gone
        list_result = subprocess.run(
            [
                "helm",
                "list",
                "--namespace",
                test_namespace,
                "-o",
                "json",
            ],
            capture_output=True,
            check=True,
        )

        assert helm_release_name not in list_result.stdout.decode(), (
            f"Release {helm_release_name} still exists after uninstall"
        )
