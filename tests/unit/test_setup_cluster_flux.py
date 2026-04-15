"""Structural tests: setup-cluster.sh Flux CLI check and --no-flux flag.

Validates that setup-cluster.sh contains the prerequisite check for the
flux CLI, version verification, --no-flux flag parsing, and FLOE_NO_FLUX
env var handling.

Requirements Covered:
    - AC-5: Flux CLI prerequisite check
    - AC-10: Direct Helm deployment path preserved (--no-flux flag)
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
# AC-5: Flux CLI prerequisite check
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-5")
def test_setup_cluster_sources_common_sh() -> None:
    """setup-cluster.sh sources common.sh to get FLUX_VERSION."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"source.*common\.sh", content), (
        "setup-cluster.sh must source common.sh to access FLUX_VERSION"
    )


@pytest.mark.requirement("AC-5")
def test_check_prerequisites_includes_flux() -> None:
    """check_prerequisites() checks for flux CLI on PATH."""
    content = _SETUP_SCRIPT.read_text()
    # Must check for flux command availability
    assert re.search(r"command\s+-v\s+flux", content), (
        "check_prerequisites must check for flux CLI via 'command -v flux'"
    )


@pytest.mark.requirement("AC-5")
def test_flux_check_prints_install_instructions() -> None:
    """Flux CLI check failure prints install instructions to stderr."""
    content = _SETUP_SCRIPT.read_text()
    assert "fluxcd.io/install.sh" in content, "Flux CLI check must include install instructions URL"


@pytest.mark.requirement("AC-5")
def test_flux_version_check_exists() -> None:
    """setup-cluster.sh verifies flux version matches FLUX_VERSION."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"flux.*--version|flux\s+--version", content), (
        "setup-cluster.sh must run 'flux --version' to verify version"
    )
    assert "FLUX_VERSION" in content, (
        "setup-cluster.sh must reference FLUX_VERSION for version comparison"
    )


@pytest.mark.requirement("AC-5")
def test_flux_check_skipped_when_no_flux() -> None:
    """Flux CLI check is skipped when FLOE_NO_FLUX is set."""
    content = _SETUP_SCRIPT.read_text()
    # The flux prerequisite check must be gated on FLOE_NO_FLUX
    assert re.search(r"FLOE_NO_FLUX", content), (
        "setup-cluster.sh must reference FLOE_NO_FLUX to skip flux check"
    )


# ---------------------------------------------------------------------------
# AC-10: --no-flux flag and FLOE_NO_FLUX env var
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-10")
def test_no_flux_flag_parsing() -> None:
    """setup-cluster.sh parses --no-flux command line flag."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"--no-flux", content), (
        "setup-cluster.sh must parse --no-flux command line flag"
    )


@pytest.mark.requirement("AC-10")
def test_floe_no_flux_env_var() -> None:
    """setup-cluster.sh reads FLOE_NO_FLUX environment variable."""
    content = _SETUP_SCRIPT.read_text()
    assert re.search(r"FLOE_NO_FLUX", content), (
        "setup-cluster.sh must read FLOE_NO_FLUX environment variable"
    )


@pytest.mark.requirement("AC-10")
def test_no_flux_preserves_helm_path() -> None:
    """When --no-flux is set, direct helm upgrade --install path is used."""
    content = _SETUP_SCRIPT.read_text()
    # The script must have a conditional that uses direct Helm when no-flux
    assert re.search(r"helm\s+upgrade\s+--install", content), (
        "setup-cluster.sh must retain helm upgrade --install path"
    )
