"""E2E workflow tests for Helm-based deployment.

These tests validate the complete workflow:
1. Deploy platform via Helm
2. Register code location (Dagster)
3. Trigger dbt Job
4. Validate output exists

Requirements:
- E2E-001: Platform deployment validation
- E2E-002: Code location registration
- E2E-003: Job execution validation
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from testing.fixtures.polling import wait_for_condition

if TYPE_CHECKING:
    from collections.abc import Generator


def _run_command(
    cmd: list[str],
    timeout: int = 900,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command with timeout.

    Args:
        cmd: Command and arguments
        timeout: Command timeout in seconds
        check: Whether to raise on non-zero exit

    Returns:
        Completed process result
    """
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def _helm(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
    """Run a helm command."""
    return _run_command(["helm"] + args, timeout=timeout)


def _kubectl(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run a kubectl command."""
    return _run_command(["kubectl"] + args, timeout=timeout)


def _wait_for_pods_ready(
    namespace: str,
    label_selector: str,
    timeout: int = 300,
    interval: int = 10,
) -> bool:
    """Wait for pods matching selector to be ready.

    Args:
        namespace: Kubernetes namespace
        label_selector: Label selector for pods
        timeout: Total timeout in seconds
        interval: Check interval in seconds

    Returns:
        True if all pods ready, False otherwise
    """

    def check_pods_ready() -> bool:
        result = _kubectl(
            [
                "get",
                "pods",
                "-n",
                namespace,
                "-l",
                label_selector,
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )
        if result.returncode == 0:
            phases = result.stdout.strip().split()
            return bool(phases and all(p == "Running" for p in phases))
        return False

    return wait_for_condition(
        check_pods_ready,
        timeout=float(timeout),
        interval=float(interval),
        description=f"pods with selector {label_selector} to be ready",
        raise_on_timeout=False,
    )


@pytest.fixture(scope="module")
def chart_root() -> Path:
    """Get the charts directory root."""
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "charts").is_dir():
            return current / "charts"
        current = current.parent
    pytest.fail("Could not find charts directory")


@pytest.fixture(scope="module")
def e2e_namespace() -> Generator[str, None, None]:
    """Create and manage E2E test namespace."""
    namespace = "floe-e2e-helm"

    # Create namespace
    _kubectl(["create", "namespace", namespace])

    yield namespace

    # Cleanup
    _helm(["uninstall", "floe-e2e", "-n", namespace])
    _kubectl(["delete", "namespace", namespace, "--ignore-not-found", "--wait=false"])


@pytest.fixture(scope="module")
def deployed_platform(
    chart_root: Path,
    e2e_namespace: str,
) -> Generator[str, None, None]:
    """Deploy floe-platform and yield release name."""
    release_name = "floe-e2e"
    platform_chart = chart_root / "floe-platform"

    # Update dependencies
    result = _helm(["dependency", "update", str(platform_chart)])
    if result.returncode != 0:
        pytest.fail(f"Failed to update dependencies: {result.stderr}")

    # Install platform with test values (includes test credentials)
    # values-test.yaml contains pre-configured credentials suitable for E2E testing
    result = _helm(
        [
            "upgrade",
            "--install",
            release_name,
            str(platform_chart),
            "--namespace",
            e2e_namespace,
            "--values",
            str(platform_chart / "values-test.yaml"),
            "--set",
            "postgresql.enabled=true",
            "--set",
            "polaris.enabled=true",
            "--set",
            "polaris.service.type=ClusterIP",  # Avoid NodePort conflict with main release
            "--set",
            "dagster.enabled=false",  # Skip dagster for basic test
            "--set",
            "otel.enabled=false",
            "--set",
            "minio.enabled=false",
            "--set",
            "polaris.bootstrap.enabled=false",  # Bootstrap requires MinIO
            "--wait",
            "--timeout",
            "10m",
        ]
    )

    if result.returncode != 0:
        pytest.fail(f"Platform deployment failed: {result.stderr}")

    yield release_name


@pytest.mark.e2e
@pytest.mark.requirement("E2E-001")
@pytest.mark.timeout(900)
class TestHelmWorkflow:
    """E2E tests for Helm-based platform deployment workflow."""

    @pytest.fixture(autouse=True)
    def check_cluster(self) -> None:
        """Verify kubectl access to cluster."""
        result = _kubectl(["cluster-info"])
        if result.returncode != 0:
            pytest.fail("Kubernetes cluster not available.\nStart cluster with: make kind-up")

    @pytest.mark.requirement("E2E-001")
    def test_platform_deployed(
        self,
        deployed_platform: str,
        e2e_namespace: str,
    ) -> None:
        """Test that platform services are deployed and running."""
        # Check helm release status
        result = _helm(
            [
                "status",
                deployed_platform,
                "--namespace",
                e2e_namespace,
            ]
        )
        assert result.returncode == 0, f"Helm status failed: {result.stderr}"
        assert "deployed" in result.stdout.lower(), "Release not in deployed state"

    @pytest.mark.requirement("E2E-001")
    def test_polaris_accessible(
        self,
        deployed_platform: str,  # noqa: ARG002 - fixture required for ordering
        e2e_namespace: str,
    ) -> None:
        """Test that Polaris service is accessible."""
        # Wait for Polaris pods
        ready = _wait_for_pods_ready(
            e2e_namespace,
            "app.kubernetes.io/component=polaris",
            timeout=120,
        )
        assert ready, "Polaris pods not ready"

        # Check Polaris service exists (Helm chart names: {release}-floe-platform-polaris)
        result = _kubectl(
            [
                "get",
                "service",
                "-n",
                e2e_namespace,
                "-l",
                "app.kubernetes.io/component=polaris",
            ]
        )
        assert result.returncode == 0, f"Polaris service not found: {result.stderr}"
        assert "polaris" in result.stdout, f"No Polaris service in output: {result.stdout}"

    @pytest.mark.requirement("E2E-001")
    def test_postgresql_accessible(
        self,
        deployed_platform: str,  # noqa: ARG002 - fixture required for ordering
        e2e_namespace: str,
    ) -> None:
        """Test that PostgreSQL is accessible."""
        # Check PostgreSQL StatefulSet
        result = _kubectl(
            [
                "get",
                "statefulset",
                "-n",
                e2e_namespace,
                "-l",
                "app.kubernetes.io/component=postgresql",
            ]
        )
        # PostgreSQL might be a StatefulSet or managed by parent chart
        if result.returncode != 0:
            # Fallback: check for postgresql pods by component label
            result = _kubectl(
                [
                    "get",
                    "pods",
                    "-n",
                    e2e_namespace,
                    "-l",
                    "app.kubernetes.io/component=postgresql",
                ]
            )

        assert result.returncode == 0, f"PostgreSQL not found: {result.stderr}"


@pytest.mark.e2e
@pytest.mark.requirement("E2E-002")
@pytest.mark.timeout(900)
class TestCodeLocationRegistration:
    """Tests for Dagster code location registration.

    Note: These tests are skipped when Dagster is disabled.
    """

    @pytest.mark.requirement("E2E-002")
    def test_dagster_workspace_configmap(
        self,
        deployed_platform: str,
        e2e_namespace: str,
    ) -> None:
        """Test that Dagster workspace ConfigMap is created."""
        _ = deployed_platform  # Used for fixture ordering
        # This test is only valid when Dagster is enabled
        result = _kubectl(
            [
                "get",
                "configmap",
                "-n",
                e2e_namespace,
                "-l",
                "app.kubernetes.io/component=workspace",
            ]
        )
        # Fail if no workspace configmap (Dagster disabled)
        if result.returncode != 0:
            pytest.fail(
                "Dagster workspace not configured.\n"
                "The Helm chart must configure Dagster workspace for E2E tests.\n"
                "Track: Epic 13 - Helm deployment integration"
            )


@pytest.mark.e2e
@pytest.mark.requirement("E2E-003")
@pytest.mark.timeout(900)
class TestJobExecution:
    """Tests for job execution after Helm deployment.

    Note: Full job execution requires Dagster and dbt configuration.
    """

    @pytest.mark.requirement("E2E-003")
    def test_job_template_rendered(
        self,
        deployed_platform: str,
        chart_root: Path,
    ) -> None:
        _ = deployed_platform  # Used for fixture ordering
        """Test that job templates render correctly."""
        jobs_chart = chart_root / "floe-jobs"

        result = _helm(
            [
                "template",
                "test-jobs",
                str(jobs_chart),
                "--set",
                "dbt.enabled=true",
            ]
        )

        assert result.returncode == 0, f"Template rendering failed: {result.stderr}"
        assert "kind: Job" in result.stdout or "kind: CronJob" in result.stdout, (
            "No Job or CronJob in rendered output"
        )


@pytest.mark.requirement("AC-32.1")
def test_minio_persistence_enabled_in_test_values() -> None:
    """Test that values-test.yaml configures MinIO with persistent storage.

    AC-32.1 requires minio.persistence.enabled=true with size=1Gi in
    the test values file. Without persistence, MinIO data is lost on
    pod restart, causing flaky E2E tests when Iceberg metadata or
    warehouse data disappears mid-suite.

    Validates:
        - minio.persistence.enabled is exactly True (boolean, not string)
        - minio.persistence.size is exactly "1Gi"
        - minio section exists and is a dict (not accidentally deleted)
        - persistence sub-key exists (not missing entirely)
    """
    import yaml

    values_path = Path(__file__).parent.parent.parent / "charts" / "floe-platform" / "values-test.yaml"
    assert values_path.exists(), (
        f"values-test.yaml not found at {values_path}. "
        "Chart directory structure may have changed."
    )

    raw_content = values_path.read_text()
    values = yaml.safe_load(raw_content)

    assert isinstance(values, dict), (
        f"values-test.yaml did not parse as a dict, got {type(values).__name__}"
    )

    # Verify minio section exists and is a dict
    assert "minio" in values, (
        "values-test.yaml is missing the 'minio' top-level key entirely"
    )
    minio_config = values["minio"]
    assert isinstance(minio_config, dict), (
        f"minio config should be a dict, got {type(minio_config).__name__}"
    )

    # Verify persistence sub-section exists
    assert "persistence" in minio_config, (
        "minio.persistence key is missing from values-test.yaml. "
        "Expected persistence configuration with enabled=true and size=1Gi."
    )
    persistence_config = minio_config["persistence"]
    assert isinstance(persistence_config, dict), (
        f"minio.persistence should be a dict, got {type(persistence_config).__name__}"
    )

    # Verify persistence.enabled is exactly True (boolean)
    assert "enabled" in persistence_config, (
        "minio.persistence.enabled key is missing"
    )
    assert persistence_config["enabled"] is True, (
        f"minio.persistence.enabled must be true, got {persistence_config['enabled']!r}. "
        "Without persistence, MinIO data is lost on pod restart."
    )

    # Verify persistence.size is exactly "1Gi"
    assert "size" in persistence_config, (
        "minio.persistence.size key is missing. "
        "Expected size: '1Gi' for test environment."
    )
    assert persistence_config["size"] == "1Gi", (
        f"minio.persistence.size must be '1Gi', got {persistence_config['size']!r}"
    )
