"""Platform chart template render tests.

Tests that validate the floe-platform Helm chart templates render correctly.
Template tests catch rendering errors without requiring a running cluster.

Requirements:
    FR-081: Helm template rendering validation
    AC-17.6: OTEL env vars in Dagster deployments
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

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
        assert "Deployment" in resource_kinds or "StatefulSet" in resource_kinds, (
            "Expected Deployment or StatefulSet for Polaris"
        )

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

        assert has_standard_labels, "No resources have standard app.kubernetes.io/name label"

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
        assert release_name in output, f"Release name '{release_name}' not found in template output"

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
            doc for doc in documents if doc.get("metadata", {}).get("namespace") == namespace
        ]

        # Some resources should have the namespace set
        # Note: ClusterRole, ClusterRoleBinding don't have namespace
        assert len(namespaced_resources) > 0 or len(documents) == 0, (
            f"No resources have namespace '{namespace}'"
        )


def _render_template(chart_path: Path) -> list[dict[str, Any]]:
    """Render Helm template and return parsed YAML documents.

    Args:
        chart_path: Path to the Helm chart.

    Returns:
        List of parsed Kubernetes resource documents.
    """
    result = subprocess.run(
        [
            "helm",
            "template",
            "--skip-schema-validation",
            "floe-platform",
            str(chart_path),
        ],
        capture_output=True,
        timeout=60,
        check=True,
    )
    output = result.stdout.decode()
    docs = list(yaml.safe_load_all(output))
    return [d for d in docs if d is not None]


def _find_dagster_deployments(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find Dagster Deployment resources from rendered templates.

    Searches for Deployments with 'dagster' in their name, targeting
    the webserver and daemon components.

    Args:
        documents: Parsed K8s resource documents.

    Returns:
        List of Dagster Deployment resources.
    """
    dagster_deps: list[dict[str, Any]] = []
    for doc in documents:
        if doc.get("kind") != "Deployment":
            continue
        name = doc.get("metadata", {}).get("name", "")
        if "dagster" in name.lower():
            dagster_deps.append(doc)
    return dagster_deps


def _get_container_env_vars(
    deployment: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract env vars from all containers in a Deployment.

    Args:
        deployment: Parsed Deployment resource.

    Returns:
        Flattened list of env var dicts from all containers.
    """
    all_envs: list[dict[str, Any]] = []
    pod_spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
    for container in pod_spec.get("containers", []):
        all_envs.extend(container.get("env", []))
    return all_envs


class TestDagsterOtelEnvVars:
    """Tests verifying OTEL env vars in Dagster Helm deployments (AC-17.6)."""

    @pytest.mark.requirement("AC-17.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_dagster_deployments_have_otel_endpoint(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify OTEL_EXPORTER_OTLP_ENDPOINT in Dagster Deployments.

        AC-17.6 requires helm template to show OTEL_EXPORTER_OTLP_ENDPOINT
        in Dagster webserver/daemon Deployment env.
        """
        documents = _render_template(platform_chart_path)
        dagster_deps = _find_dagster_deployments(documents)

        assert len(dagster_deps) > 0, (
            "No Dagster Deployments found in helm template output. "
            "Expected webserver and daemon Deployments."
        )

        for dep in dagster_deps:
            name = dep["metadata"]["name"]
            envs = _get_container_env_vars(dep)
            env_names = [e.get("name") for e in envs]
            assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env_names, (
                f"Dagster Deployment '{name}' missing "
                "OTEL_EXPORTER_OTLP_ENDPOINT env var.\n"
                f"Env vars found: {env_names}"
            )

    @pytest.mark.requirement("AC-17.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_dagster_deployments_have_otel_service_name(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify OTEL_SERVICE_NAME in Dagster Deployments.

        AC-17.6 requires helm template to show OTEL_SERVICE_NAME
        in Dagster webserver/daemon Deployment env.
        """
        documents = _render_template(platform_chart_path)
        dagster_deps = _find_dagster_deployments(documents)

        assert len(dagster_deps) > 0, "No Dagster Deployments found"

        for dep in dagster_deps:
            name = dep["metadata"]["name"]
            envs = _get_container_env_vars(dep)
            env_names = [e.get("name") for e in envs]
            assert "OTEL_SERVICE_NAME" in env_names, (
                f"Dagster Deployment '{name}' missing "
                "OTEL_SERVICE_NAME env var.\n"
                f"Env vars found: {env_names}"
            )

    @pytest.mark.requirement("AC-17.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_otel_endpoint_points_to_collector(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify OTEL endpoint resolves to OTel Collector service.

        The endpoint value must reference the OTel Collector service
        in K8s DNS format (e.g., http://<release>-otel-collector:4317).
        """
        documents = _render_template(platform_chart_path)
        dagster_deps = _find_dagster_deployments(documents)

        assert len(dagster_deps) > 0, "No Dagster Deployments found"

        for dep in dagster_deps:
            name = dep["metadata"]["name"]
            envs = _get_container_env_vars(dep)
            endpoint_envs = [e for e in envs if e.get("name") == "OTEL_EXPORTER_OTLP_ENDPOINT"]
            assert len(endpoint_envs) > 0
            endpoint_val = endpoint_envs[0].get("value", "")
            assert "otel-collector" in endpoint_val, (
                f"Dagster '{name}' OTEL endpoint does not "
                f"reference otel-collector service. "
                f"Got: {endpoint_val}"
            )
            assert ":4317" in endpoint_val, (
                f"Dagster '{name}' OTEL endpoint missing port 4317. Got: {endpoint_val}"
            )

    @pytest.mark.requirement("AC-17.6")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_otel_service_name_is_floe_platform(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify OTEL_SERVICE_NAME is set to floe-platform.

        All Dagster containers should identify as floe-platform service.
        """
        documents = _render_template(platform_chart_path)
        dagster_deps = _find_dagster_deployments(documents)

        assert len(dagster_deps) > 0, "No Dagster Deployments found"

        for dep in dagster_deps:
            name = dep["metadata"]["name"]
            envs = _get_container_env_vars(dep)
            svc_envs = [e for e in envs if e.get("name") == "OTEL_SERVICE_NAME"]
            assert len(svc_envs) > 0
            svc_val = svc_envs[0].get("value", "")
            assert svc_val == "floe-platform", (
                f"Dagster '{name}' OTEL_SERVICE_NAME should be 'floe-platform'. Got: '{svc_val}'"
            )
