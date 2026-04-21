"""Regression tests for the Unit C boundary wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BOUNDARY_SCRIPT = _REPO_ROOT / "testing" / "ci" / "test-unit-c-boundary.sh"


@pytest.mark.requirement("AC-2")
@pytest.mark.requirement("RAC-7")
def test_boundary_wrapper_reboots_platform_when_namespace_is_missing() -> None:
    """The wrapper should re-run the remote post-start bootstrap before giving up."""
    script = _BOUNDARY_SCRIPT.read_text()
    assert "rebootstrap_remote_platform()" in script
    assert 'kubectl get namespace "${FLOE_NAMESPACE}"' in script
    assert 'devpod_remote_command "bash .devcontainer/hetzner/postStartCommand.sh"' in script


@pytest.mark.requirement("RAC-7")
def test_boundary_wrapper_uses_longer_platform_ready_timeout_budget() -> None:
    """Recovering a stopped workspace needs more than the old 120s readiness budget."""
    script = _BOUNDARY_SCRIPT.read_text()
    assert 'PLATFORM_READY_TIMEOUT="${PLATFORM_READY_TIMEOUT:-900}"' in script


@pytest.mark.requirement("RAC-7")
def test_boundary_wrapper_restores_demo_image_before_waiting_for_flux() -> None:
    """The wrapper should repair the Dagster demo image contract before waiting."""
    script = _BOUNDARY_SCRIPT.read_text()
    assert "ensure_remote_demo_image_loaded()" in script
    assert "sync_devpod_checkout" in script
    assert "floe-dagster-demo:latest" in script
    assert "\"KIND_CLUSTER_NAME='${FLOE_KIND_CLUSTER}' make build-demo-image\"" in script
    assert "\"kind load docker-image '${demo_image}' --name '${FLOE_KIND_CLUSTER}'\"" in script


@pytest.mark.requirement("RAC-8")
def test_boundary_wrapper_restores_test_runner_image_before_startup_probe() -> None:
    """The startup probe should rebuild the remote test-runner image when needed."""
    script = _BOUNDARY_SCRIPT.read_text()
    assert "ensure_remote_test_runner_image_loaded()" in script
    assert '"make test-integration-image"' in script
    assert "Remote test-runner image '${test_runner_image}' is missing" in script


@pytest.mark.requirement("RAC-7")
@pytest.mark.requirement("RAC-8")
def test_boundary_wrapper_syncs_current_checkout_before_remote_rebuilds() -> None:
    """Remote image repairs must run against the current checkout, not stale workspace files."""
    script = _BOUNDARY_SCRIPT.read_text()
    assert "sync_devpod_checkout()" in script
    assert "--exclude='.git'" in script
    assert "--exclude='.venv'" in script
    assert '--command "tar -xf -"' in script
