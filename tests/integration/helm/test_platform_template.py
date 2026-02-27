"""Platform chart template render tests.

Tests that validate the floe-platform Helm chart templates render correctly.
Template tests catch rendering errors without requiring a running cluster.

Requirements:
    FR-081: Helm template rendering validation
    AC-17.6: OTEL env vars in Dagster deployments
    AC-19.1: Marquez stability root-cause (init container DB readiness)
    AC-19.2: Marquez probe configuration and resource sizing
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


def _find_marquez_deployment(
    documents: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find the Marquez Deployment resource from rendered templates.

    Searches for a Deployment with 'marquez' in its name and the
    app.kubernetes.io/component=marquez label.

    Args:
        documents: Parsed K8s resource documents.

    Returns:
        The Marquez Deployment resource, or None if not found.
    """
    for doc in documents:
        if doc.get("kind") != "Deployment":
            continue
        name = doc.get("metadata", {}).get("name", "")
        labels = doc.get("metadata", {}).get("labels", {})
        if "marquez" in name.lower() and labels.get("app.kubernetes.io/component") == "marquez":
            return doc
    return None


def _get_marquez_container(
    deployment: dict[str, Any],
) -> dict[str, Any] | None:
    """Extract the main marquez container from a Deployment.

    Args:
        deployment: Parsed Deployment resource.

    Returns:
        The marquez container spec, or None if not found.
    """
    pod_spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
    for container in pod_spec.get("containers", []):
        if container.get("name") == "marquez":
            return container
    return None


def _get_init_containers(
    deployment: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract init containers from a Deployment.

    Args:
        deployment: Parsed Deployment resource.

    Returns:
        List of init container specs.
    """
    pod_spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
    return pod_spec.get("initContainers", [])


def _parse_k8s_memory_to_mebibytes(memory_str: str) -> int:
    """Parse a Kubernetes memory string to mebibytes.

    Handles Mi, Gi, M, G suffixes. Returns integer mebibytes.

    Args:
        memory_str: Kubernetes memory string (e.g., '256Mi', '1Gi').

    Returns:
        Memory value in mebibytes.

    Raises:
        ValueError: If the memory string format is unrecognized.
    """
    memory_str = memory_str.strip()
    if memory_str.endswith("Gi"):
        return int(memory_str[:-2]) * 1024
    if memory_str.endswith("Mi"):
        return int(memory_str[:-2])
    if memory_str.endswith("G"):
        # Decimal GB to MiB (approximate)
        return int(float(memory_str[:-1]) * 1000)
    if memory_str.endswith("M"):
        # Decimal MB to MiB (approximate)
        return int(float(memory_str[:-1]))
    msg = f"Unrecognized memory format: {memory_str}"
    raise ValueError(msg)


class TestMarquezStability:
    """Tests verifying Marquez deployment stability configuration (WU-19 T40).

    Validates that the Marquez Helm deployment has proper probe
    configuration, init container database readiness checks, and
    adequate memory resources to prevent cold-start instability.

    Requirements:
        AC-19.1: Root-cause fix for init container DB readiness
        AC-19.2: Probe configuration and resource sizing
    """

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_deployment_exists(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez Deployment is rendered with default values.

        Precondition for all other Marquez stability tests. The Marquez
        deployment must be present in template output when marquez.enabled
        is true (the default).
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)

        assert marquez is not None, (
            "Marquez Deployment not found in rendered templates. "
            "Expected a Deployment with 'marquez' in name and "
            "app.kubernetes.io/component=marquez label."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_has_startup_probe(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez container has a startupProbe.

        AC-19.2 requires a startup probe with generous timeout for
        cold-start migrations. Without a startup probe, Kubernetes
        liveness checks can kill Marquez during initial DB migration,
        causing CrashLoopBackOff.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found in Deployment"

        startup_probe = container.get("startupProbe")
        assert startup_probe is not None, (
            "Marquez container is missing startupProbe. "
            "A startup probe is required to allow time for cold-start "
            "DB migrations without being killed by liveness checks."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_startup_probe_has_generous_timeout(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez startupProbe allows sufficient time for migrations.

        The startup probe must tolerate at least 180 seconds of startup
        time (failureThreshold * periodSeconds >= 180). Marquez Java
        process with Flyway migrations can take 60-120s on cold start.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        startup_probe = container.get("startupProbe")
        assert startup_probe is not None, "Marquez startupProbe missing"

        failure_threshold = startup_probe.get("failureThreshold", 3)
        period_seconds = startup_probe.get("periodSeconds", 10)
        total_tolerance = failure_threshold * period_seconds

        assert total_tolerance >= 180, (
            f"Marquez startupProbe total tolerance is {total_tolerance}s "
            f"(failureThreshold={failure_threshold} * periodSeconds={period_seconds}). "
            "Must be >= 180s to allow for cold-start DB migrations."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_startup_probe_checks_http_endpoint(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez startupProbe uses HTTP health check, not just TCP.

        The startup probe should check an HTTP endpoint to confirm
        Marquez is actually serving, not just that the port is open.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        startup_probe = container.get("startupProbe")
        assert startup_probe is not None, "Marquez startupProbe missing"

        http_get = startup_probe.get("httpGet")
        assert http_get is not None, (
            "Marquez startupProbe must use httpGet, not tcpSocket or exec. "
            f"Probe config: {startup_probe}"
        )

        path = http_get.get("path", "")
        assert path != "", (
            "Marquez startupProbe httpGet must specify a path."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_readiness_probe_timeout(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez readinessProbe timeoutSeconds >= 5.

        AC-19.2 requires readiness probe timeout of at least 5 seconds.
        The default Kubernetes timeout of 1 second is too aggressive for
        a Java service that may pause during GC.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        readiness_probe = container.get("readinessProbe")
        assert readiness_probe is not None, "Marquez readinessProbe missing"

        timeout_seconds = readiness_probe.get("timeoutSeconds", 1)
        assert timeout_seconds >= 5, (
            f"Marquez readinessProbe timeoutSeconds is {timeout_seconds}. "
            "Must be >= 5 to tolerate Java GC pauses. "
            "The default Kubernetes timeout of 1s causes false-negative "
            "readiness failures."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_liveness_probe_initial_delay(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez livenessProbe initialDelaySeconds >= 60.

        AC-19.2 requires liveness probe initial delay of at least 60
        seconds. Marquez is a Java application that needs substantial
        startup time for JVM warmup and DB migrations.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        liveness_probe = container.get("livenessProbe")
        assert liveness_probe is not None, "Marquez livenessProbe missing"

        initial_delay = liveness_probe.get("initialDelaySeconds", 0)
        assert initial_delay >= 60, (
            f"Marquez livenessProbe initialDelaySeconds is {initial_delay}. "
            "Must be >= 60 to avoid killing Marquez during startup. "
            "Current value of 30 causes CrashLoopBackOff when DB "
            "migrations run on first start."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_liveness_probe_timeout(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez livenessProbe timeoutSeconds >= 5.

        AC-19.2 requires liveness probe timeout of at least 5 seconds.
        The default Kubernetes timeout of 1 second is too aggressive for
        a Java service that may pause during GC.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        liveness_probe = container.get("livenessProbe")
        assert liveness_probe is not None, "Marquez livenessProbe missing"

        timeout_seconds = liveness_probe.get("timeoutSeconds", 1)
        assert timeout_seconds >= 5, (
            f"Marquez livenessProbe timeoutSeconds is {timeout_seconds}. "
            "Must be >= 5 to tolerate Java GC pauses. "
            "The default Kubernetes timeout of 1s causes false "
            "liveness failures under load."
        )

    @pytest.mark.requirement("AC-19.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_init_container_uses_pg_readiness_check(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify init container checks PostgreSQL query readiness, not just TCP.

        AC-19.1 requires the init container to verify PostgreSQL is ready
        for queries using pg_isready or 'SELECT 1', not just nc -z (TCP
        port check). TCP connectivity succeeds as soon as PostgreSQL binds
        the port, but the database may not be ready for queries (e.g.,
        still running recovery or not accepting connections).
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        init_containers = _get_init_containers(marquez)
        assert len(init_containers) > 0, (
            "Marquez Deployment has no init containers. "
            "Expected a wait-for-postgresql init container."
        )

        # Find the postgresql wait init container
        pg_init = None
        for ic in init_containers:
            name = ic.get("name", "")
            if "postgresql" in name.lower() or "postgres" in name.lower():
                pg_init = ic
                break

        assert pg_init is not None, (
            "No PostgreSQL wait init container found. "
            f"Init containers: {[ic.get('name') for ic in init_containers]}"
        )

        # Extract the command - it may be a list or a string
        command = pg_init.get("command", [])
        # Flatten command to a single string for analysis
        command_str = " ".join(command) if isinstance(command, list) else str(command)

        # Also check args if present (some init containers use command + args)
        args = pg_init.get("args", [])
        args_str = " ".join(args) if isinstance(args, list) else str(args)
        full_command = f"{command_str} {args_str}".strip()

        # The command must NOT use nc -z (TCP-only check)
        assert "nc -z" not in full_command, (
            "Init container uses 'nc -z' which only checks TCP connectivity, "
            "not PostgreSQL query readiness. Use pg_isready or 'SELECT 1' "
            f"instead. Current command: {full_command}"
        )

        # The command MUST use pg_isready or psql with SELECT
        uses_pg_isready = "pg_isready" in full_command
        uses_psql_select = "psql" in full_command and "select" in full_command.lower()
        assert uses_pg_isready or uses_psql_select, (
            "Init container must use pg_isready or psql with SELECT to "
            "verify PostgreSQL is ready for queries. "
            f"Current command: {full_command}"
        )

    @pytest.mark.requirement("AC-19.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_init_container_not_busybox(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify init container uses an image with PostgreSQL client tools.

        The busybox image only has nc for TCP checks. To use pg_isready
        or psql, the init container needs a PostgreSQL client image.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        init_containers = _get_init_containers(marquez)
        pg_init = None
        for ic in init_containers:
            name = ic.get("name", "")
            if "postgresql" in name.lower() or "postgres" in name.lower():
                pg_init = ic
                break

        assert pg_init is not None, "No PostgreSQL wait init container found"

        image = pg_init.get("image", "")
        assert "busybox" not in image.lower(), (
            f"Init container uses busybox image ({image}) which lacks "
            "PostgreSQL client tools (pg_isready, psql). Use a PostgreSQL "
            "client image (e.g., postgres:16-alpine or bitnami/postgresql)."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_memory_request_adequate(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez memory request is >= 384Mi.

        AC-19.2 requires memory request of at least 384Mi. Marquez is a
        Java application with JVM heap overhead. 256Mi is too tight and
        causes OOMKilled under load when Flyway migrations or large
        lineage graphs are processed.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        resources = container.get("resources", {})
        requests = resources.get("requests", {})
        memory_request = requests.get("memory", "0Mi")

        memory_mib = _parse_k8s_memory_to_mebibytes(str(memory_request))
        assert memory_mib >= 384, (
            f"Marquez memory request is {memory_request} ({memory_mib}Mi). "
            "Must be >= 384Mi. Marquez is a Java application and 256Mi "
            "is insufficient for JVM heap + Flyway migrations."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_memory_limit_adequate(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez memory limit is proportional to request.

        Memory limit should be at least 1.5x the request to allow for
        temporary spikes during migrations and lineage processing,
        and must be >= 512Mi absolute minimum.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        resources = container.get("resources", {})
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})

        memory_request_str = requests.get("memory", "0Mi")
        memory_limit_str = limits.get("memory", "0Mi")

        memory_request_mib = _parse_k8s_memory_to_mebibytes(str(memory_request_str))
        memory_limit_mib = _parse_k8s_memory_to_mebibytes(str(memory_limit_str))

        # Limit must be >= 512Mi absolute minimum
        assert memory_limit_mib >= 512, (
            f"Marquez memory limit is {memory_limit_str} ({memory_limit_mib}Mi). "
            "Must be >= 512Mi."
        )

        # Limit must be >= 1.5x request to allow headroom for spikes
        min_limit = int(memory_request_mib * 1.5)
        assert memory_limit_mib >= min_limit, (
            f"Marquez memory limit ({memory_limit_str} = {memory_limit_mib}Mi) "
            f"is less than 1.5x the request ({memory_request_str} = {memory_request_mib}Mi). "
            f"Limit should be >= {min_limit}Mi to allow headroom."
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_liveness_probe_uses_http(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez livenessProbe uses HTTP endpoint check.

        The liveness probe should verify Marquez HTTP API is responsive,
        not just that the process is alive.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        liveness_probe = container.get("livenessProbe")
        assert liveness_probe is not None, "Marquez livenessProbe missing"

        http_get = liveness_probe.get("httpGet")
        assert http_get is not None, (
            "Marquez livenessProbe must use httpGet. "
            f"Probe config: {liveness_probe}"
        )

    @pytest.mark.requirement("AC-19.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_marquez_readiness_probe_uses_http(
        self,
        platform_chart_path: Path,
    ) -> None:
        """Verify Marquez readinessProbe uses HTTP endpoint check.

        The readiness probe should verify Marquez HTTP API is ready to
        serve requests.
        """
        documents = _render_template(platform_chart_path)
        marquez = _find_marquez_deployment(documents)
        assert marquez is not None, "Marquez Deployment not found"

        container = _get_marquez_container(marquez)
        assert container is not None, "Marquez container not found"

        readiness_probe = container.get("readinessProbe")
        assert readiness_probe is not None, "Marquez readinessProbe missing"

        http_get = readiness_probe.get("httpGet")
        assert http_get is not None, (
            "Marquez readinessProbe must use httpGet. "
            f"Probe config: {readiness_probe}"
        )
