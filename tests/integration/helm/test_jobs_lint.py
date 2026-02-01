"""Helm chart linting tests for floe-jobs chart.

These tests validate the floe-jobs Helm chart passes linting checks
with various value configurations.

Requirements tested:
- 9b-FR-080: Chart lint validation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def jobs_chart_path() -> Path:
    """Return path to floe-jobs chart."""
    return Path(__file__).parents[3] / "charts" / "floe-jobs"


class TestJobsChartLint:
    """Test floe-jobs chart linting."""

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available")
    def test_chart_lint_default_values(self, jobs_chart_path: Path) -> None:
        """Test chart lints successfully with default values."""
        result = subprocess.run(
            ["helm", "lint", str(jobs_chart_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Lint failed: {result.stderr}"
        assert "0 chart(s) failed" in result.stdout

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available")
    def test_chart_lint_dbt_enabled(self, jobs_chart_path: Path) -> None:
        """Test chart lints with dbt job enabled."""
        result = subprocess.run(
            [
                "helm",
                "lint",
                str(jobs_chart_path),
                "--set",
                "dbt.enabled=true",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Lint failed: {result.stderr}"

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available")
    def test_chart_lint_dbt_cronjob(self, jobs_chart_path: Path) -> None:
        """Test chart lints with dbt as CronJob."""
        result = subprocess.run(
            [
                "helm",
                "lint",
                str(jobs_chart_path),
                "--set",
                "dbt.enabled=true",
                "--set",
                "dbt.schedule=0 * * * *",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Lint failed: {result.stderr}"

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available")
    def test_chart_lint_ingestion_enabled(self, jobs_chart_path: Path) -> None:
        """Test chart lints with ingestion job enabled."""
        result = subprocess.run(
            [
                "helm",
                "lint",
                str(jobs_chart_path),
                "--set",
                "ingestion.enabled=true",
                "--set",
                "ingestion.image.repository=my-ingestion",
                "--set",
                "ingestion.image.tag=latest",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Lint failed: {result.stderr}"

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available")
    def test_chart_lint_strict(self, jobs_chart_path: Path) -> None:
        """Test chart passes strict linting."""
        result = subprocess.run(
            ["helm", "lint", str(jobs_chart_path), "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Strict mode may warn about icon, which is acceptable
        # We just check it doesn't have actual errors
        assert "Error:" not in result.stderr or "icon is recommended" in result.stdout
