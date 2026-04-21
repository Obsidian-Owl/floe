"""Structural tests for the DevPod path in test-e2e-cluster.sh."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "testing" / "ci" / "test-e2e-cluster.sh"
_COMMON_SH_PATH = _REPO_ROOT / "testing" / "ci" / "common.sh"
_ENV_EXAMPLE_PATH = _REPO_ROOT / ".env.example"


def _read_script() -> str:
    """Return the current test-e2e-cluster.sh contents."""
    return _SCRIPT_PATH.read_text()


def _read_common_sh() -> str:
    """Return the shared CI shell config."""
    return _COMMON_SH_PATH.read_text()


@pytest.mark.requirement("AC-1")
def test_devpod_mode_uses_devpod_ssh_for_docker_load() -> None:
    """DevPod mode must stream the image through the DevPod transport, not raw ssh."""
    script = _read_script()
    assert 'docker save "${image}" | devpod_remote_command "docker load"' in script, (
        "DevPod image loading must pipe docker save into the devpod transport "
        "so the caller does not depend on a local SSH alias."
    )


@pytest.mark.requirement("AC-1")
def test_devpod_mode_no_longer_uses_workspace_dot_devpod_alias() -> None:
    """The script must not assume `<workspace>.devpod` resolves locally."""
    script = _read_script()
    assert ".devpod" not in script, (
        "test-e2e-cluster.sh still depends on a `<workspace>.devpod` SSH alias. "
        "Use `devpod ssh` so the workspace transport matches the actual CLI."
    )


@pytest.mark.requirement("AC-2")
def test_devpod_mode_prepares_kubeconfig_via_helper_script() -> None:
    """DevPod mode must call the existing ensure-ready helper before cluster checks."""
    script = _read_script()
    assert "scripts/devpod-ensure-ready.sh" in script, (
        "The DevPod path must reuse scripts/devpod-ensure-ready.sh to sync "
        "kubeconfig and validate the remote Kind cluster."
    )
    assert 'KUBECONFIG="$(devpod_kubeconfig_path)"' in script, (
        "The DevPod path must export a workspace-specific kubeconfig path after "
        "running the ensure-ready helper."
    )
    assert script.index("ensure_devpod_ready") < script.index("floe_require_cluster"), (
        "DevPod readiness must be established before floe_require_cluster runs."
    )


@pytest.mark.requirement("AC-2")
def test_devpod_mode_uses_configurable_remote_workdir() -> None:
    """DevPod mode must expose the remote workspace path as config, not a literal."""
    script = _read_script()
    common = _read_common_sh()
    env_example = _ENV_EXAMPLE_PATH.read_text()
    assert "DEVPOD_REMOTE_WORKDIR:=/workspace" in common, (
        "common.sh must define a default DevPod remote workdir so callers "
        "have one documented place to override it."
    )
    assert "DEVPOD_REMOTE_WORKDIR" in env_example, (
        ".env.example must surface the DevPod remote workdir override for users."
    )
    assert '--workdir "${remote_workdir}"' in script, (
        "test-e2e-cluster.sh must pass a configurable workdir to `devpod ssh`."
    )
    assert "--workdir /workspace" not in script, (
        "test-e2e-cluster.sh still hardcodes the remote DevPod workdir."
    )


@pytest.mark.requirement("AC-3")
def test_load_image_scopes_devpod_transport_to_devpod_paths_only() -> None:
    """Kind and skip branches must not depend on DevPod transport helpers."""
    script = _read_script()
    match = re.search(r"load_image\(\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert match is not None, "load_image() function not found"
    body = match.group(1)

    kind_branch = re.search(r"kind\)(.*?)return 0", body, re.DOTALL)
    skip_branch = re.search(r"skip\)(.*?)return 0", body, re.DOTALL)
    devpod_branch = re.search(r"devpod\)(.*?)return 0", body, re.DOTALL)

    assert kind_branch is not None, "kind branch not found in load_image()"
    assert skip_branch is not None, "skip branch not found in load_image()"
    assert devpod_branch is not None, "devpod branch not found in load_image()"

    assert "devpod_remote_command" not in kind_branch.group(1), (
        "IMAGE_LOAD_METHOD=kind must not invoke DevPod transport helpers."
    )
    assert "devpod_remote_command" not in skip_branch.group(1), (
        "IMAGE_LOAD_METHOD=skip must not invoke DevPod transport helpers."
    )
    assert "devpod_remote_command" in devpod_branch.group(1), (
        "The explicit DevPod branch must use the shared DevPod transport helper."
    )
    assert 'if [[ -n "${DEVPOD_WORKSPACE:-}" ]]; then' in body, (
        "The auto branch must gate DevPod fallback on DEVPOD_WORKSPACE."
    )


@pytest.mark.requirement("AC-4")
def test_kind_load_calls_use_shared_kind_cluster_variable() -> None:
    """All Kind image loads in load_image() must use the shared kind_cluster value."""
    script = _read_script()
    match = re.search(r"load_image\(\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert match is not None, "load_image() function not found"
    body = match.group(1)

    assert 'local kind_cluster="${FLOE_KIND_CLUSTER}"' in body, (
        "load_image() must derive the Kind cluster name from FLOE_KIND_CLUSTER."
    )
    kind_load_lines = re.findall(r"kind load docker-image[^\n]+", body)
    assert len(kind_load_lines) == 4, (
        "load_image() should contain exactly four kind load docker-image calls "
        "(kind, devpod, auto-kind, and auto-devpod paths)."
    )
    assert all("${kind_cluster}" in line for line in kind_load_lines), (
        "Every kind load docker-image call in load_image() must use the shared "
        "${kind_cluster} variable."
    )
    assert '--name "floe-test"' not in body, (
        "load_image() still hardcodes the Kind cluster name in a load path."
    )
    assert "--name 'floe-test'" not in body, (
        "load_image() still hardcodes the Kind cluster name in a DevPod load path."
    )
