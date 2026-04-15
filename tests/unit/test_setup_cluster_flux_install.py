"""Structural tests: setup-cluster.sh Flux install, cleanup, and readiness.

Validates that setup-cluster.sh contains the Flux controller installation,
pre-Flux cleanup for stuck Helm releases, HelmRelease CRD application,
readiness wait, diagnostics, and the --no-flux conditional structure.

Requirements Covered:
    - AC-6: Flux controller installation
    - AC-7: Pre-Flux cleanup for existing clusters
    - AC-8: HelmRelease application and readiness wait
    - AC-9: Flux install failure produces actionable diagnostics
    - AC-10: Direct Helm deployment path preserved
    - AC-11: Non-Flux path regression test
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SETUP_SCRIPT = _REPO_ROOT / "testing" / "k8s" / "setup-cluster.sh"


# ---------------------------------------------------------------------------
# AC-6: Flux controller installation
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-6")
def test_flux_install_command() -> None:
    """setup-cluster.sh runs flux install with pinned version and controllers."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(
        r"flux\s+install\s+--version.*--components.*source-controller.*helm-controller",
        content,
    ), "Must run 'flux install --version=... --components=source-controller,helm-controller'"


@pytest.mark.requirement("AC-6")
def test_flux_install_gated_on_no_flux() -> None:
    """Flux install only runs in the else branch of FLOE_NO_FLUX check."""
    content = _SETUP_SCRIPT.read_text()
    # The install_flux call must appear inside an else block following
    # the FLOE_NO_FLUX == "1" conditional (i.e., when FLOE_NO_FLUX is NOT set).
    # Match: if FLOE_NO_FLUX == "1" ... else ... install_flux
    pattern = (
        r'if\s+\[\[\s+"\$\{FLOE_NO_FLUX\}"\s*==\s*"1"\s*\]\].*?'
        r"else.*?install_flux"
    )
    assert re.search(pattern, content, re.DOTALL), (
        "install_flux must be called in the else branch of FLOE_NO_FLUX check"
    )


# ---------------------------------------------------------------------------
# AC-7: Pre-Flux cleanup for existing clusters
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-7")
def test_pre_flux_cleanup_checks_helm_status() -> None:
    """setup-cluster.sh checks existing Helm release status via helm status + jq."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"helm\s+status.*--output\s+json", content), (
        "Must check existing release status via 'helm status --output json'"
    )
    assert re.search(r"jq\s+-r", content), "Must parse helm status JSON with jq (not python3)"


@pytest.mark.requirement("AC-7")
def test_pre_flux_cleanup_skips_when_flux_installed() -> None:
    """Pre-Flux cleanup skips when flux-system namespace already exists."""
    content = _SETUP_SCRIPT.read_text()
    match = re.search(
        r"pre_flux_cleanup\(\)\s*\{(.*?)\n\}",
        content,
        re.DOTALL,
    )
    assert match is not None, "pre_flux_cleanup function must exist"
    func_body = match.group(1)
    assert "flux-system" in func_body, (
        "pre_flux_cleanup must check for existing flux-system namespace"
    )


@pytest.mark.requirement("AC-7")
def test_pre_flux_cleanup_detects_bad_states() -> None:
    """Pre-Flux cleanup detects failed/pending Helm release states."""
    content = _SETUP_SCRIPT.read_text()
    for state in ["failed", "pending-upgrade", "pending-install", "pending-rollback"]:
        assert state in content, f"Must detect Helm release state '{state}' for pre-Flux cleanup"


@pytest.mark.requirement("AC-7")
def test_pre_flux_cleanup_checks_both_releases() -> None:
    """Pre-Flux cleanup checks both floe-platform and floe-jobs-test releases."""
    content = _SETUP_SCRIPT.read_text()
    # Extract pre_flux_cleanup function body
    match = re.search(
        r"pre_flux_cleanup\(\)\s*\{(.*?)\n\}",
        content,
        re.DOTALL,
    )
    assert match is not None, "pre_flux_cleanup function must exist"
    func_body = match.group(1)
    assert "floe-jobs-test" in func_body, (
        "pre_flux_cleanup must check floe-jobs-test release (not just platform)"
    )


@pytest.mark.requirement("AC-7")
def test_pre_flux_cleanup_runs_helm_uninstall() -> None:
    """Pre-Flux cleanup runs helm uninstall with --wait and timeout."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"helm\s+uninstall.*--wait.*--timeout", content), (
        "Must run 'helm uninstall --wait --timeout' for stuck releases"
    )


# ---------------------------------------------------------------------------
# AC-8: HelmRelease application and readiness wait
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-8")
def test_flux_path_creates_namespace_before_apply() -> None:
    """deploy_via_flux creates the target namespace before applying CRDs."""
    content = _SETUP_SCRIPT.read_text()
    # Namespace creation must appear before kubectl apply in the function
    match = re.search(
        r"deploy_via_flux\(\)\s*\{(.*?)\n\}",
        content,
        re.DOTALL,
    )
    assert match is not None, "deploy_via_flux function must exist"
    func_body = match.group(1)
    ns_pos = func_body.find("kubectl create namespace")
    apply_pos = func_body.find("kubectl apply -f")
    assert ns_pos != -1, "Must create namespace before applying Flux CRDs"
    assert apply_pos != -1, "Must apply Flux CRDs"
    assert ns_pos < apply_pos, "Namespace creation must precede kubectl apply"


@pytest.mark.requirement("AC-8")
def test_kubectl_apply_flux_crds() -> None:
    """setup-cluster.sh applies CRD manifests from flux/ directory."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"kubectl\s+apply\s+-f.*flux", content), (
        "Must apply CRD manifests from charts/floe-platform/flux/ directory"
    )


@pytest.mark.requirement("AC-8")
def test_kubectl_wait_helmrelease_platform() -> None:
    """setup-cluster.sh waits for floe-platform HelmRelease readiness."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(
        r"kubectl\s+wait\s+helmrelease/floe-platform.*--for=condition=Ready.*--timeout=900s",
        content,
        re.DOTALL,
    ), "Must wait for floe-platform HelmRelease with 900s timeout"


@pytest.mark.requirement("AC-8")
def test_kubectl_wait_helmrelease_jobs() -> None:
    """setup-cluster.sh waits for floe-jobs-test HelmRelease readiness."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(
        r"kubectl\s+wait\s+helmrelease/floe-jobs-test.*--for=condition=Ready.*--timeout=600s",
        content,
        re.DOTALL,
    ), "Must wait for floe-jobs-test HelmRelease with 600s timeout"


# ---------------------------------------------------------------------------
# AC-9: Flux install failure diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-9")
def test_flux_install_failure_diagnostics() -> None:
    """Flux install failure outputs diagnostic information."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"kubectl\s+get\s+pods\s+-n\s+flux-system", content), (
        "Must output pod status in flux-system namespace on failure"
    )


@pytest.mark.requirement("AC-9")
def test_flux_failure_controller_wait() -> None:
    """setup-cluster.sh waits for controllers with kubectl wait and 120s timeout."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(
        r"kubectl\s+wait\s+--for=condition=Ready\s+pod.*flux-system.*--timeout=120s",
        content,
        re.DOTALL,
    ), "Must use 'kubectl wait --for=condition=Ready' with 120s timeout for controller readiness"


# ---------------------------------------------------------------------------
# AC-10: Direct Helm path preserved
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-10")
def test_no_flux_uses_direct_helm() -> None:
    """When FLOE_NO_FLUX=1, direct helm upgrade --install is used."""
    content = _SETUP_SCRIPT.read_text()
    # Must have a conditional that branches on FLOE_NO_FLUX
    # and contains helm upgrade --install in the non-Flux path
    assert re.search(r"FLOE_NO_FLUX", content), "Must reference FLOE_NO_FLUX for path selection"
    assert re.search(r"helm\s+upgrade\s+--install", content), (
        "Must retain direct helm upgrade --install path"
    )


# ---------------------------------------------------------------------------
# AC-11: Non-Flux path produces functional cluster
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-11")
def test_no_flux_path_deploys_both_charts() -> None:
    """Non-Flux path's deploy_services_helm installs both charts via helm upgrade."""
    content = _SETUP_SCRIPT.read_text()
    # Extract the deploy_services_helm function body
    match = re.search(
        r"deploy_services_helm\(\)\s*\{(.*?)\n\}",
        content,
        re.DOTALL,
    )
    assert match is not None, "deploy_services_helm function must exist"
    func_body = match.group(1)
    # Both charts must be installed via helm upgrade --install within this function
    assert re.search(r"helm\s+upgrade\s+--install\s+floe-platform", func_body), (
        "deploy_services_helm must run 'helm upgrade --install floe-platform'"
    )
    assert re.search(r"helm\s+upgrade\s+--install\s+floe-jobs", func_body), (
        "deploy_services_helm must run 'helm upgrade --install floe-jobs'"
    )


@pytest.mark.requirement("AC-8")
def test_flux_failure_shows_both_helmreleases() -> None:
    """On HelmRelease wait failure, diagnostic shows both HelmReleases."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"flux\s+get\s+helmrelease", content), (
        "Must show flux get helmrelease on failure for diagnostics"
    )


@pytest.mark.requirement("AC-8")
def test_flux_failure_shows_events() -> None:
    """On failure, diagnostic shows recent events."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"kubectl\s+get\s+events.*sort-by.*lastTimestamp", content), (
        "Must show recent events sorted by timestamp on failure"
    )
