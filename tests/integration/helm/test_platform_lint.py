"""Platform chart lint tests.

Tests that validate the floe-platform Helm chart passes linting checks.
Lint tests catch syntax errors, best practice violations, and common issues.

Requirements:
    FR-080: Helm chart linting and validation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestPlatformChartLint:
    """Lint tests for the floe-platform Helm chart."""

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_chart_lint_default_values(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test chart lints successfully with default values.

        Validates that the chart passes `helm lint` with default values.yaml.
        This catches syntax errors and common issues in templates.

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            ["helm", "lint", "--skip-schema-validation", str(platform_chart_path)],
            capture_output=True,
            timeout=60,
            check=False,
        )

        stdout = result.stdout.decode() if result.stdout else ""
        stderr = result.stderr.decode() if result.stderr else ""

        assert result.returncode == 0, f"Chart lint failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_chart_lint_strict_mode(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test chart lints successfully in strict mode.

        Validates that the chart passes `helm lint --strict`.
        Strict mode treats warnings as errors for higher quality.

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            ["helm", "lint", "--strict", "--skip-schema-validation", str(platform_chart_path)],
            capture_output=True,
            timeout=60,
            check=False,
        )

        stdout = result.stdout.decode() if result.stdout else ""
        stderr = result.stderr.decode() if result.stderr else ""

        assert result.returncode == 0, (
            f"Chart lint (strict) failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_chart_lint_with_values_override(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test chart lints with production-like values.

        Validates that the chart lints with production-like settings:
        - Higher replica counts
        - Enabled features
        - Resource limits

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "lint",
                "--skip-schema-validation",
                str(platform_chart_path),
                "--set",
                "global.environment=prod",
                "--set",
                "polaris.replicaCount=3",
                "--set",
                "ingress.enabled=true",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )

        stdout = result.stdout.decode() if result.stdout else ""
        stderr = result.stderr.decode() if result.stderr else ""

        assert result.returncode == 0, (
            f"Chart lint with overrides failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    @pytest.mark.requirement("9b-FR-080")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_chart_lint_disabled_components(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test chart lints with components disabled.

        Validates that disabling optional components doesn't break the chart.

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "lint",
                "--skip-schema-validation",
                str(platform_chart_path),
                "--set",
                "polaris.enabled=false",
                "--set",
                "otel.enabled=false",
                "--set",
                "marquez.enabled=false",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )

        stdout = result.stdout.decode() if result.stdout else ""
        stderr = result.stderr.decode() if result.stderr else ""

        assert result.returncode == 0, (
            f"Chart lint with disabled components failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    @pytest.mark.requirement("9b-FR-080")
    def test_chart_has_required_files(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test chart has all required files.

        Validates that the chart contains the minimum required files
        for a valid Helm chart.

        Args:
            platform_chart_path: Path to platform chart.
        """
        required_files = [
            "Chart.yaml",
            "values.yaml",
            "templates/_helpers.tpl",
        ]

        for filename in required_files:
            file_path = platform_chart_path / filename
            assert file_path.exists(), f"Required file missing: {filename}"

    @pytest.mark.requirement("9b-FR-080")
    def test_chart_yaml_valid(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test Chart.yaml contains required fields.

        Validates that Chart.yaml has the minimum required fields:
        - name
        - version
        - apiVersion

        Args:
            platform_chart_path: Path to platform chart.
        """
        import yaml

        chart_file = platform_chart_path / "Chart.yaml"
        with chart_file.open() as f:
            chart = yaml.safe_load(f)

        assert "name" in chart, "Chart.yaml missing 'name' field"
        assert "version" in chart, "Chart.yaml missing 'version' field"
        assert "apiVersion" in chart, "Chart.yaml missing 'apiVersion' field"
        assert chart["apiVersion"] == "v2", "Chart must use apiVersion v2"
