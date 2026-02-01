"""Helm chart installation tests for floe-jobs chart.

These tests validate the floe-jobs Helm chart can be installed
and uninstalled in a Kind cluster.

Requirements tested:
- 9b-FR-082: Chart installation validation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def jobs_chart_path() -> Path:
    """Return path to floe-jobs chart."""
    return Path(__file__).parents[3] / "charts" / "floe-jobs"


class TestJobsChartInstall:
    """Test floe-jobs chart installation."""

    @pytest.mark.slow
    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.usefixtures("helm_available", "kind_cluster")
    def test_chart_install_dry_run(
        self, jobs_chart_path: Path, test_namespace: str
    ) -> None:
        """Test chart installation with dry-run."""
        result = subprocess.run(
            [
                "helm",
                "install",
                "test-jobs",
                str(jobs_chart_path),
                "--namespace",
                test_namespace,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Dry-run failed: {result.stderr}"

    @pytest.mark.slow
    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.usefixtures("helm_available", "kind_cluster")
    def test_chart_install_with_dbt_job(
        self, jobs_chart_path: Path, test_namespace: str
    ) -> None:
        """Test chart installation with dbt job enabled."""
        release_name = "test-jobs-dbt"

        try:
            # Install chart
            install_result = subprocess.run(
                [
                    "helm",
                    "install",
                    release_name,
                    str(jobs_chart_path),
                    "--namespace",
                    test_namespace,
                    "--set",
                    "dbt.enabled=true",
                    "--wait",
                    "--timeout",
                    "60s",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            # Job will fail because there's no actual dbt project,
            # but the chart should install successfully
            assert install_result.returncode == 0, (
                f"Install failed: {install_result.stderr}"
            )

            # Verify job was created
            get_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "job",
                    f"{release_name}-floe-jobs-dbt",
                    "-n",
                    test_namespace,
                    "-o",
                    "name",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert "job" in get_result.stdout.lower()

        finally:
            # Cleanup
            subprocess.run(
                [
                    "helm",
                    "uninstall",
                    release_name,
                    "--namespace",
                    test_namespace,
                ],
                capture_output=True,
                check=False,
            )

    @pytest.mark.slow
    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.usefixtures("helm_available", "kind_cluster")
    def test_chart_install_with_cronjob(
        self, jobs_chart_path: Path, test_namespace: str
    ) -> None:
        """Test chart installation with CronJob."""
        release_name = "test-jobs-cron"

        try:
            # Install chart
            install_result = subprocess.run(
                [
                    "helm",
                    "install",
                    release_name,
                    str(jobs_chart_path),
                    "--namespace",
                    test_namespace,
                    "--set",
                    "dbt.enabled=true",
                    "--set",
                    "dbt.schedule=0 * * * *",
                    "--wait",
                    "--timeout",
                    "60s",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert install_result.returncode == 0, (
                f"Install failed: {install_result.stderr}"
            )

            # Verify cronjob was created
            get_result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "cronjob",
                    f"{release_name}-floe-jobs-dbt",
                    "-n",
                    test_namespace,
                    "-o",
                    "name",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert "cronjob" in get_result.stdout.lower()

        finally:
            # Cleanup
            subprocess.run(
                [
                    "helm",
                    "uninstall",
                    release_name,
                    "--namespace",
                    test_namespace,
                ],
                capture_output=True,
                check=False,
            )

    @pytest.mark.slow
    @pytest.mark.requirement("9b-FR-082")
    @pytest.mark.usefixtures("helm_available", "kind_cluster")
    def test_chart_upgrade(
        self, jobs_chart_path: Path, test_namespace: str
    ) -> None:
        """Test chart upgrade works correctly."""
        release_name = "test-jobs-upgrade"

        try:
            # Initial install
            subprocess.run(
                [
                    "helm",
                    "install",
                    release_name,
                    str(jobs_chart_path),
                    "--namespace",
                    test_namespace,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Upgrade with different values
            upgrade_result = subprocess.run(
                [
                    "helm",
                    "upgrade",
                    release_name,
                    str(jobs_chart_path),
                    "--namespace",
                    test_namespace,
                    "--set",
                    "dbt.enabled=true",
                    "--set",
                    "dbt.schedule=0 */2 * * *",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert upgrade_result.returncode == 0, (
                f"Upgrade failed: {upgrade_result.stderr}"
            )

        finally:
            # Cleanup
            subprocess.run(
                [
                    "helm",
                    "uninstall",
                    release_name,
                    "--namespace",
                    test_namespace,
                ],
                capture_output=True,
                check=False,
            )
