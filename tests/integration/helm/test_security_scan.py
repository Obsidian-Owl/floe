"""Security scanning tests for Helm charts.

These tests validate that rendered Helm templates meet security best practices
using kubesec scoring.

Requirements:
- SC-007: Security scanning in CI
- 9b-FR-036: Pod Security Standards
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

# Minimum kubesec score required for all workloads
MIN_KUBESEC_SCORE = 7

# Workload kinds to scan
WORKLOAD_KINDS: set[str] = {
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "Pod",
    "Job",
    "CronJob",
}


def render_helm_templates(
    chart_path: Path, values_path: Path | None = None
) -> list[dict[str, Any]]:
    """Render Helm templates to YAML documents.

    Args:
        chart_path: Path to the Helm chart
        values_path: Optional path to values file

    Returns:
        List of parsed YAML documents
    """
    # NOTE: --skip-schema-validation required because Dagster subchart
    # references external JSON schema URL that returns 404
    cmd = [
        "helm",
        "template",
        "--skip-schema-validation",
        "test-release",
        str(chart_path),
    ]
    if values_path:
        cmd.extend(["--values", str(values_path)])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    documents: list[dict[str, Any]] = []
    for doc in yaml.safe_load_all(result.stdout):
        if doc and isinstance(doc, dict):
            documents.append(doc)

    return documents


def run_kubesec_scan(manifest: dict[str, Any]) -> dict[str, Any]:
    """Run kubesec scan on a single manifest.

    Args:
        manifest: Kubernetes manifest as dict

    Returns:
        Kubesec scan result
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(manifest, f)
        f.flush()

        try:
            result = subprocess.run(
                ["kubesec", "scan", f.name],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return {"score": 0, "error": result.stderr}

            return json.loads(result.stdout)[0]
        finally:
            Path(f.name).unlink(missing_ok=True)


def is_kubesec_available() -> bool:
    """Check if kubesec is installed."""
    try:
        subprocess.run(["kubesec", "version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def chart_root() -> Path:
    """Get the charts directory root."""
    # Find repo root by looking for charts directory
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "charts").is_dir():
            return current / "charts"
        current = current.parent
    pytest.fail("Could not find charts directory")


@pytest.fixture(scope="module")
def floe_platform_templates(chart_root: Path) -> list[dict[str, Any]]:
    """Render floe-platform templates."""
    chart_path = chart_root / "floe-platform"
    if not chart_path.exists():
        pytest.skip("floe-platform chart not found")

    # Update dependencies first
    subprocess.run(
        ["helm", "dependency", "update", str(chart_path)],
        capture_output=True,
        check=False,
    )

    return render_helm_templates(chart_path)


@pytest.fixture(scope="module")
def floe_jobs_templates(chart_root: Path) -> list[dict[str, Any]]:
    """Render floe-jobs templates."""
    chart_path = chart_root / "floe-jobs"
    if not chart_path.exists():
        pytest.skip("floe-jobs chart not found")

    return render_helm_templates(chart_path)


@pytest.mark.requirement("SC-007")
class TestKubesecScanning:
    """Kubesec security scanning tests."""

    @pytest.fixture(autouse=True)
    def check_kubesec(self) -> None:
        """Skip tests if kubesec is not available."""
        if not is_kubesec_available():
            pytest.fail(
                "kubesec not installed. Install with: "
                "curl -sSL https://github.com/controlplaneio/kubesec/"
                "releases/download/v2.14.0/"
                "kubesec_linux_amd64.tar.gz"
                " | tar xz && sudo mv kubesec /usr/local/bin/"
            )

    @pytest.mark.requirement("SC-007")
    def test_floe_platform_security_score(
        self, floe_platform_templates: list[dict[str, Any]]
    ) -> None:
        """Test that floe-platform workloads meet minimum kubesec score.

        Validates that all Deployments, StatefulSets, DaemonSets, and Pods
        in the rendered templates score at least MIN_KUBESEC_SCORE.
        """
        workloads = [
            doc for doc in floe_platform_templates if doc.get("kind") in WORKLOAD_KINDS
        ]

        if not workloads:
            pytest.skip("No workloads found in floe-platform chart")

        failures: list[str] = []
        for workload in workloads:
            kind = workload.get("kind", "Unknown")
            name = workload.get("metadata", {}).get("name", "unknown")

            result = run_kubesec_scan(workload)
            score = result.get("score", 0)

            if score < MIN_KUBESEC_SCORE:
                critical = result.get("scoring", {}).get("critical", [])
                advise = result.get("scoring", {}).get("advise", [])

                failure_msg = f"{kind}/{name}: score={score} (min={MIN_KUBESEC_SCORE})"
                if critical:
                    failure_msg += (
                        f"\n  Critical: {[c.get('selector') for c in critical]}"
                    )
                if advise:
                    failure_msg += (
                        f"\n  Advise: {[a.get('selector') for a in advise[:3]]}"
                    )

                failures.append(failure_msg)

        if failures:
            pytest.fail(
                f"Security scan failed for {len(failures)} workload(s):\n"
                + "\n".join(failures)
            )

    @pytest.mark.requirement("SC-007")
    def test_floe_jobs_security_score(
        self, floe_jobs_templates: list[dict[str, Any]]
    ) -> None:
        """Test that floe-jobs workloads meet minimum kubesec score."""
        workloads = [
            doc for doc in floe_jobs_templates if doc.get("kind") in WORKLOAD_KINDS
        ]

        if not workloads:
            pytest.skip("No workloads found in floe-jobs chart")

        failures: list[str] = []
        for workload in workloads:
            kind = workload.get("kind", "Unknown")
            name = workload.get("metadata", {}).get("name", "unknown")

            result = run_kubesec_scan(workload)
            score = result.get("score", 0)

            if score < MIN_KUBESEC_SCORE:
                failures.append(f"{kind}/{name}: score={score}")

        if failures:
            pytest.fail(
                f"Security scan failed for {len(failures)} workload(s): {failures}"
            )


@pytest.mark.requirement("9b-FR-036")
class TestPodSecurityStandards:
    """Pod Security Standards compliance tests."""

    @pytest.mark.requirement("9b-FR-036")
    def test_containers_run_as_non_root(
        self, floe_platform_templates: list[dict[str, Any]]
    ) -> None:
        """Test that all containers run as non-root user.

        Validates runAsNonRoot=true or runAsUser > 0 in security contexts.
        """
        violations: list[str] = []

        for doc in floe_platform_templates:
            if doc.get("kind") not in WORKLOAD_KINDS:
                continue

            name = doc.get("metadata", {}).get("name", "unknown")
            spec = doc.get("spec", {})

            # Get pod spec (handle different workload types)
            pod_spec = spec.get("template", {}).get("spec", spec)

            # Check pod security context
            pod_security = pod_spec.get("securityContext", {})
            run_as_non_root = pod_security.get("runAsNonRoot", False)
            run_as_user = pod_security.get("runAsUser", 0)

            # Check each container
            for container in pod_spec.get("containers", []):
                container_name = container.get("name", "unknown")
                container_security = container.get("securityContext", {})

                container_non_root = container_security.get(
                    "runAsNonRoot", run_as_non_root
                )
                container_user = container_security.get("runAsUser", run_as_user)

                if not container_non_root and container_user == 0:
                    violations.append(f"{name}/{container_name}: runs as root")

        if violations:
            pytest.fail(
                f"Found {len(violations)} container(s) running as root:\n"
                + "\n".join(violations)
            )

    @pytest.mark.requirement("9b-FR-036")
    def test_containers_drop_all_capabilities(
        self, floe_platform_templates: list[dict[str, Any]]
    ) -> None:
        """Test that all containers drop all capabilities.

        Validates that capabilities.drop includes 'ALL'.
        """
        violations: list[str] = []

        for doc in floe_platform_templates:
            if doc.get("kind") not in WORKLOAD_KINDS:
                continue

            name = doc.get("metadata", {}).get("name", "unknown")
            spec = doc.get("spec", {})
            pod_spec = spec.get("template", {}).get("spec", spec)

            for container in pod_spec.get("containers", []):
                container_name = container.get("name", "unknown")
                security_context = container.get("securityContext", {})
                capabilities = security_context.get("capabilities", {})
                drop = capabilities.get("drop", [])

                if "ALL" not in drop:
                    violations.append(
                        f"{name}/{container_name}: does not drop ALL capabilities"
                    )

        if violations:
            pytest.fail(
                f"Found {len(violations)} container(s) not dropping ALL capabilities:\n"
                + "\n".join(violations)
            )

    @pytest.mark.requirement("9b-FR-036")
    def test_containers_read_only_root_filesystem(
        self, floe_platform_templates: list[dict[str, Any]]
    ) -> None:
        """Test that containers use read-only root filesystem where possible.

        Note: Some containers may legitimately need writable filesystems.
        This test warns rather than fails for violations.
        """
        violations: list[str] = []

        for doc in floe_platform_templates:
            if doc.get("kind") not in WORKLOAD_KINDS:
                continue

            name = doc.get("metadata", {}).get("name", "unknown")
            spec = doc.get("spec", {})
            pod_spec = spec.get("template", {}).get("spec", spec)

            for container in pod_spec.get("containers", []):
                container_name = container.get("name", "unknown")
                security_context = container.get("securityContext", {})

                if not security_context.get("readOnlyRootFilesystem", False):
                    violations.append(f"{name}/{container_name}")

        if violations:
            # Log warning but don't fail - some containers need writable fs
            import warnings

            warnings.warn(
                f"Containers without readOnlyRootFilesystem=true: {violations}",
                UserWarning,
                stacklevel=1,
            )
