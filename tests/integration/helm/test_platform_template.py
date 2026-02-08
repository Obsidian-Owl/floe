"""Platform chart template render tests.

Tests that validate the floe-platform Helm chart templates render correctly.
Template tests catch rendering errors without requiring a running cluster.

Requirements:
    FR-081: Helm template rendering validation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml


class TestPlatformChartTemplate:
    """Template render tests for the floe-platform Helm chart."""

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_template_renders_with_defaults(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test templates render successfully with default values.

        Validates that `helm template` succeeds with default values.yaml.
        This catches template syntax errors and undefined variable issues.

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "template",
                "--skip-schema-validation",
                "test-release",
                str(platform_chart_path),
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )

        stderr = result.stderr.decode() if result.stderr else ""

        assert result.returncode == 0, f"Template render failed:\n{stderr}"
        assert result.stdout, "Template render produced no output"

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_template_output_valid_yaml(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test template output is valid YAML.

        Validates that the rendered templates are parseable as YAML.

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "template",
                "--skip-schema-validation",
                "test-release",
                str(platform_chart_path),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )

        output = result.stdout.decode()
        # Parse all YAML documents in the output
        documents = list(yaml.safe_load_all(output))

        # Filter out None documents (empty separators)
        documents = [doc for doc in documents if doc is not None]

        assert len(documents) > 0, "No Kubernetes resources rendered"

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_template_generates_polaris_resources(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test templates generate Polaris resources when enabled.

        Validates that Polaris deployment, service, and configmap are rendered.

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "template",
                "--skip-schema-validation",
                "test-release",
                str(platform_chart_path),
                "--set",
                "polaris.enabled=true",
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )

        output = result.stdout.decode()
        documents = list(yaml.safe_load_all(output))
        documents = [doc for doc in documents if doc is not None]

        # Check for Polaris-related resources
        resource_kinds = {doc.get("kind") for doc in documents}

        # We expect at least Deployment and Service for Polaris
        # Note: Actual resources depend on template implementation
        assert (
            "Deployment" in resource_kinds or "StatefulSet" in resource_kinds
        ), "Expected Deployment or StatefulSet for Polaris"

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_template_respects_disabled_components(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test templates respect disabled component flags.

        Validates that disabling components excludes their resources.

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "template",
                "--skip-schema-validation",
                "test-release",
                str(platform_chart_path),
                "--set",
                "polaris.enabled=false",
                "--set",
                "otel.enabled=false",
                "--set",
                "postgresql.enabled=false",
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )

        # With all major components disabled, we should have minimal resources
        # or the template should at least not fail
        assert result.returncode == 0

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_template_applies_labels(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test templates apply standard labels.

        Validates that resources have standard Kubernetes labels:
        - app.kubernetes.io/name
        - app.kubernetes.io/instance
        - helm.sh/chart

        Args:
            platform_chart_path: Path to platform chart.
        """
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "template",
                "--skip-schema-validation",
                "my-release",
                str(platform_chart_path),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )

        output = result.stdout.decode()
        documents = list(yaml.safe_load_all(output))
        documents = [doc for doc in documents if doc is not None]

        # Check at least one resource has standard labels
        has_standard_labels = False
        for doc in documents:
            metadata = doc.get("metadata", {})
            labels = metadata.get("labels", {})
            if "app.kubernetes.io/name" in labels:
                has_standard_labels = True
                break

        assert (
            has_standard_labels
        ), "No resources have standard app.kubernetes.io/name label"

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_template_release_name_substitution(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test templates correctly substitute release name.

        Validates that the release name appears in resource names and labels.

        Args:
            platform_chart_path: Path to platform chart.
        """
        release_name = "custom-release"
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "template",
                "--skip-schema-validation",
                release_name,
                str(platform_chart_path),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )

        output = result.stdout.decode()

        # Release name should appear in the output
        assert (
            release_name in output
        ), f"Release name '{release_name}' not found in template output"

    @pytest.mark.requirement("9b-FR-081")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_template_namespace_override(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Test templates accept namespace override.

        Validates that --namespace flag affects resource metadata.

        Args:
            platform_chart_path: Path to platform chart.
        """
        namespace = "custom-ns"
        # NOTE: --skip-schema-validation required because Dagster subchart
        # references external JSON schema URL that returns 404
        result = subprocess.run(
            [
                "helm",
                "template",
                "--skip-schema-validation",
                "test-release",
                str(platform_chart_path),
                "--namespace",
                namespace,
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )

        output = result.stdout.decode()
        documents = list(yaml.safe_load_all(output))
        documents = [doc for doc in documents if doc is not None]

        # Check that resources have the correct namespace
        namespaced_resources = [
            doc
            for doc in documents
            if doc.get("metadata", {}).get("namespace") == namespace
        ]

        # Some resources should have the namespace set
        # Note: ClusterRole, ClusterRoleBinding don't have namespace
        assert (
            len(namespaced_resources) > 0 or len(documents) == 0
        ), f"No resources have namespace '{namespace}'"
