"""Regression tests for DevContainer Flux tooling parity."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SH = REPO_ROOT / "testing" / "ci" / "common.sh"
DEVCONTAINER_DOCKERFILE = REPO_ROOT / ".devcontainer" / "Dockerfile"
DEVCONTAINER_CONFIGS = [
    REPO_ROOT / ".devcontainer" / "devcontainer.json",
    REPO_ROOT / ".devcontainer" / "hetzner" / "devcontainer.json",
]


def _flux_version() -> str:
    content = COMMON_SH.read_text()
    match = re.search(r'FLUX_VERSION[=:].*"?(\d+\.\d+\.\d+)"?', content)
    assert match is not None, "FLUX_VERSION not found in testing/ci/common.sh"
    return match.group(1)


@pytest.mark.requirement("test-infra-drift-elimination-AC-5")
def test_devcontainer_dockerfile_installs_flux_cli() -> None:
    """The shared DevContainer image must install the pinned Flux CLI."""
    content = DEVCONTAINER_DOCKERFILE.read_text()
    version = _flux_version()

    assert f"ARG FLUX_VERSION={version}" in content
    assert "flux_${FLUX_VERSION}_linux_${ARCH}.tar.gz" in content
    assert "/usr/local/bin/flux" in content


@pytest.mark.requirement("test-infra-drift-elimination-AC-5")
def test_devcontainer_configs_forward_flux_version_build_arg() -> None:
    """Both local and Hetzner DevContainer configs must pass FLUX_VERSION."""
    version = _flux_version()

    for config_path in DEVCONTAINER_CONFIGS:
        config = json.loads(config_path.read_text())
        assert config["build"]["args"]["FLUX_VERSION"] == version, (
            f"{config_path.relative_to(REPO_ROOT)} must pass FLUX_VERSION={version}"
        )
