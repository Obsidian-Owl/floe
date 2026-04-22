"""Structural tests: internal Flux fixture manifests and shared constants.

Validates that the HelmRelease and GitRepository CRD manifests in
``testing/k8s/flux/`` have the correct structure, API versions, and field
values for Flux v2 GA. Also validates that shared Flux constants are defined
in ``testing/ci/common.sh`` and not hardcoded elsewhere.

Requirements Covered:
    - AC-1: Flux version constant in common.sh
    - AC-2: HelmRelease CRD for floe-platform
    - AC-3: HelmRelease CRD for floe-jobs-test
    - AC-4: GitRepository source CRD
"""

from __future__ import annotations

import re
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FLUX_DIR = _REPO_ROOT / "testing" / "k8s" / "flux"
_COMMON_SH = _REPO_ROOT / "testing" / "ci" / "common.sh"
_PLATFORM_CHART_DIR = _REPO_ROOT / "charts" / "floe-platform"
_PACKAGED_PLATFORM_CHART = _PLATFORM_CHART_DIR / "flux-artifacts" / "floe-platform.tgz"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return the parsed dict."""
    assert path.exists(), f"File not found: {path}"
    content = path.read_text()
    docs = list(yaml.safe_load_all(content))
    assert len(docs) >= 1, f"No YAML documents in {path}"
    return docs[0]


def _load_packaged_chart_yaml(package_path: Path, member_name: str) -> dict[str, Any]:
    """Load a YAML member from a packaged Helm chart."""
    assert package_path.exists(), f"Packaged chart not found: {package_path}"
    with tarfile.open(package_path, "r:gz") as archive:
        member = archive.extractfile(member_name)
        assert member is not None, f"Packaged chart is missing {member_name}"
        return yaml.safe_load(member.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# AC-1: Flux version constant in common.sh
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-1")
def test_flux_version_defined_in_common_sh() -> None:
    """FLUX_VERSION is defined and exported in testing/ci/common.sh."""
    content = _COMMON_SH.read_text()
    # Must define FLUX_VERSION as a pinned version string
    match = re.search(r'FLUX_VERSION[=:].*"?(\d+\.\d+\.\d+)"?', content)
    assert match is not None, (
        "FLUX_VERSION not found in testing/ci/common.sh. "
        'Expected a pinned version like FLUX_VERSION="2.5.1"'
    )
    # Must be exported
    assert "FLUX_VERSION" in content, "FLUX_VERSION must be present in common.sh"
    assert re.search(r"export\s+.*FLUX_VERSION", content), (
        "FLUX_VERSION must be exported in common.sh"
    )


@pytest.mark.requirement("AC-1")
def test_flux_fixture_dir_defined_in_common_sh() -> None:
    """FLOE_FLUX_FIXTURE_DIR is defined and exported in testing/ci/common.sh."""
    content = _COMMON_SH.read_text()
    match = re.search(r'FLOE_FLUX_FIXTURE_DIR:=([^"\n]+|"[^"]+")', content)
    assert match is not None, "FLOE_FLUX_FIXTURE_DIR must be defined in common.sh"
    assert "testing/k8s/flux" in match.group(0), (
        "FLOE_FLUX_FIXTURE_DIR must default to testing/k8s/flux"
    )
    assert re.search(r"export\s+.*FLOE_FLUX_FIXTURE_DIR", content), (
        "FLOE_FLUX_FIXTURE_DIR must be exported in common.sh"
    )


@pytest.mark.requirement("AC-1")
def test_flux_version_not_hardcoded_elsewhere() -> None:
    """No other file hardcodes a Flux version in flux install commands."""
    # Read the pinned version from common.sh
    content = _COMMON_SH.read_text()
    match = re.search(r"FLUX_VERSION.*?(\d+\.\d+\.\d+)", content)
    assert match is not None, "FLUX_VERSION not found in common.sh"
    version = match.group(1)

    # Search for hardcoded version in flux install/version commands elsewhere
    result = subprocess.run(
        [
            "grep",
            "-rn",
            "--include=*.sh",
            "--include=*.yaml",
            "--include=*.yml",
            f"flux.*{version}",
            str(_REPO_ROOT / "testing"),
        ],
        capture_output=True,
        text=True,
    )
    # Filter out common.sh itself from matches
    matches = [
        line
        for line in result.stdout.strip().split("\n")
        if line and "common.sh" not in line and "test_flux_manifests" not in line
    ]
    assert len(matches) == 0, (
        f"Flux version {version} is hardcoded in files other than common.sh:\n" + "\n".join(matches)
    )


# ---------------------------------------------------------------------------
# AC-2: HelmRelease CRD for floe-platform
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-2")
def test_helmrelease_platform_api_version() -> None:
    """HelmRelease for floe-platform uses GA v2 API (not v2beta2)."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-platform.yaml")
    assert doc["apiVersion"] == "helm.toolkit.fluxcd.io/v2", (
        f"Expected GA v2 API, got {doc['apiVersion']}"
    )


@pytest.mark.requirement("AC-2")
def test_helmrelease_platform_metadata() -> None:
    """HelmRelease for floe-platform has correct name and namespace."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-platform.yaml")
    assert doc["metadata"]["name"] == "floe-platform"
    assert doc["metadata"]["namespace"] == "floe-test"


@pytest.mark.requirement("AC-2")
def test_helmrelease_platform_chart_source() -> None:
    """HelmRelease references a packaged chart artifact from GitRepository."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-platform.yaml")
    chart_spec = doc["spec"]["chart"]["spec"]
    assert chart_spec["chart"] == "./charts/floe-platform/flux-artifacts/floe-platform.tgz"
    assert chart_spec["reconcileStrategy"] == "Revision"
    source_ref = chart_spec["sourceRef"]
    assert source_ref["kind"] == "GitRepository"
    assert source_ref["name"] == "floe"
    assert source_ref["namespace"] == "flux-system"


@pytest.mark.requirement("AC-2")
def test_helmrelease_platform_remediation() -> None:
    """HelmRelease for floe-platform has strategy: uninstall with 3 retries."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-platform.yaml")
    spec = doc["spec"]

    # Install remediation
    install_rem = spec["install"]["remediation"]
    assert install_rem["retries"] == 3

    # Upgrade remediation
    upgrade_rem = spec["upgrade"]["remediation"]
    assert upgrade_rem["retries"] == 3
    assert upgrade_rem["strategy"] == "uninstall"
    assert upgrade_rem["remediateLastFailure"] is True

    # Cleanup on fail
    assert spec["upgrade"]["cleanupOnFail"] is True


@pytest.mark.requirement("AC-2")
def test_helmrelease_platform_timeouts() -> None:
    """HelmRelease for floe-platform has 10m install and upgrade timeouts."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-platform.yaml")
    spec = doc["spec"]
    assert spec["install"]["timeout"] == "10m"
    assert spec["upgrade"]["timeout"] == "10m"


@pytest.mark.requirement("AC-2")
def test_helmrelease_platform_interval() -> None:
    """HelmRelease for floe-platform has 30m reconciliation interval."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-platform.yaml")
    assert doc["spec"]["interval"] == "30m"


@pytest.mark.requirement("AC-2")
def test_helmrelease_platform_values_files() -> None:
    """HelmRelease for floe-platform layers base and test values files."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-platform.yaml")
    values_files = doc["spec"]["chart"]["spec"].get("valuesFiles", [])
    assert values_files == [
        "./charts/floe-platform/values.yaml",
        "./charts/floe-platform/values-test.yaml",
    ], (
        "HelmRelease must layer base values.yaml before values-test.yaml so "
        "Flux sees the same defaults as direct Helm installs."
    )


@pytest.mark.requirement("AC-2")
def test_packaged_platform_chart_exists() -> None:
    """Flux fixture ships a packaged floe-platform chart artifact in-repo."""
    assert _PACKAGED_PLATFORM_CHART.exists(), (
        "The Flux fixture must point at a committed packaged chart artifact so "
        "source-controller does not have to rebuild the Bitnami MinIO dependency."
    )


@pytest.mark.requirement("AC-2")
def test_packaged_platform_chart_matches_source_chart_metadata() -> None:
    """Packaged floe-platform chart preserves the source chart name and version."""
    source_chart = _load_yaml(_PLATFORM_CHART_DIR / "Chart.yaml")
    packaged_chart = _load_packaged_chart_yaml(
        _PACKAGED_PLATFORM_CHART,
        "floe-platform/Chart.yaml",
    )
    assert packaged_chart["name"] == source_chart["name"]
    assert packaged_chart["version"] == source_chart["version"]


@pytest.mark.requirement("AC-2")
def test_packaged_platform_chart_vendors_minio_dependency() -> None:
    """Packaged floe-platform chart includes the MinIO dependency content."""
    with tarfile.open(_PACKAGED_PLATFORM_CHART, "r:gz") as archive:
        members = archive.getnames()
    assert "floe-platform/charts/minio/Chart.yaml" in members, (
        "The packaged chart must vendor the MinIO dependency so Flux does not "
        "attempt OCI-backed dependency resolution during GitRepository packaging."
    )


# ---------------------------------------------------------------------------
# AC-3: HelmRelease CRD for floe-jobs-test
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-3")
def test_helmrelease_jobs_api_version() -> None:
    """HelmRelease for floe-jobs-test uses GA v2 API."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-jobs.yaml")
    assert doc["apiVersion"] == "helm.toolkit.fluxcd.io/v2"


@pytest.mark.requirement("AC-3")
def test_helmrelease_jobs_metadata() -> None:
    """HelmRelease for floe-jobs-test has correct name and namespace."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-jobs.yaml")
    assert doc["metadata"]["name"] == "floe-jobs-test"
    assert doc["metadata"]["namespace"] == "floe-test"


@pytest.mark.requirement("AC-3")
def test_helmrelease_jobs_source_ref() -> None:
    """HelmRelease for floe-jobs-test references GitRepository source."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-jobs.yaml")
    chart_spec = doc["spec"]["chart"]["spec"]
    assert chart_spec["reconcileStrategy"] == "Revision"
    source_ref = chart_spec["sourceRef"]
    assert source_ref["kind"] == "GitRepository"
    assert source_ref["name"] == "floe"
    assert source_ref["namespace"] == "flux-system"


@pytest.mark.requirement("AC-3")
def test_helmrelease_jobs_depends_on_platform() -> None:
    """HelmRelease for floe-jobs-test depends on floe-platform."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-jobs.yaml")
    depends_on = doc["spec"]["dependsOn"]
    names = [dep["name"] for dep in depends_on]
    assert "floe-platform" in names


@pytest.mark.requirement("AC-3")
def test_helmrelease_jobs_values_files() -> None:
    """HelmRelease for floe-jobs-test layers base and test values files."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-jobs.yaml")
    values_files = doc["spec"]["chart"]["spec"].get("valuesFiles", [])
    assert values_files == [
        "./charts/floe-jobs/values.yaml",
        "./charts/floe-jobs/values-test.yaml",
    ], (
        "HelmRelease must layer base values.yaml before values-test.yaml so "
        "Flux sees the same defaults as direct Helm installs."
    )


@pytest.mark.requirement("AC-3")
def test_helmrelease_jobs_remediation() -> None:
    """HelmRelease for floe-jobs-test has strategy: uninstall with 2 retries."""
    doc = _load_yaml(_FLUX_DIR / "helmrelease-jobs.yaml")
    spec = doc["spec"]

    install_rem = spec["install"]["remediation"]
    assert install_rem["retries"] == 2

    upgrade_rem = spec["upgrade"]["remediation"]
    assert upgrade_rem["retries"] == 2
    assert upgrade_rem["strategy"] == "uninstall"


# ---------------------------------------------------------------------------
# AC-4: GitRepository source CRD
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-4")
def test_gitrepository_api_version() -> None:
    """GitRepository uses GA v1 API."""
    doc = _load_yaml(_FLUX_DIR / "gitrepository.yaml")
    assert doc["apiVersion"] == "source.toolkit.fluxcd.io/v1"


@pytest.mark.requirement("AC-4")
def test_gitrepository_metadata() -> None:
    """GitRepository has correct name and namespace."""
    doc = _load_yaml(_FLUX_DIR / "gitrepository.yaml")
    assert doc["metadata"]["name"] == "floe"
    assert doc["metadata"]["namespace"] == "flux-system"


@pytest.mark.requirement("AC-4")
def test_gitrepository_spec() -> None:
    """GitRepository points to Obsidian-Owl/floe repo via HTTPS with main branch."""
    doc = _load_yaml(_FLUX_DIR / "gitrepository.yaml")
    spec = doc["spec"]
    assert spec["interval"] == "1m"
    assert spec["url"] == "https://github.com/Obsidian-Owl/floe", (
        f"Expected exact repo URL https://github.com/Obsidian-Owl/floe, got {spec['url']}"
    )
    assert spec["ref"]["branch"] == "main"
