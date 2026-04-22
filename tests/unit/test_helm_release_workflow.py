"""Structural tests for the Helm release workflow signing alignment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "helm-release.yaml"


def _load_workflow() -> dict[str, Any]:
    """Load the Helm release workflow definition."""
    return yaml.safe_load(_WORKFLOW_PATH.read_text())


def _publish_oci_job() -> dict[str, Any]:
    """Return the publish-oci job configuration."""
    workflow = _load_workflow()
    return workflow["jobs"]["publish-oci"]


def _publish_oci_steps() -> list[dict[str, Any]]:
    """Return the publish-oci steps."""
    return _publish_oci_job()["steps"]


def _step_index(step_name: str) -> int:
    """Return the index of a named publish-oci step."""
    for index, step in enumerate(_publish_oci_steps()):
        if step.get("name") == step_name:
            return index
    raise AssertionError(f"publish-oci step not found: {step_name}")


def _step_named(step_name: str) -> dict[str, Any]:
    """Return a named publish-oci step."""
    return _publish_oci_steps()[_step_index(step_name)]


@pytest.mark.requirement("AC-1")
def test_publish_oci_job_grants_id_token_and_package_permissions() -> None:
    """publish-oci grants the OIDC and GHCR permissions needed for keyless signing."""
    permissions = _publish_oci_job()["permissions"]
    assert permissions["packages"] == "write"
    assert permissions["id-token"] == "write"


@pytest.mark.requirement("AC-2")
@pytest.mark.requirement("AC-5")
def test_publish_oci_installs_cosign_before_signing() -> None:
    """Cosign is installed before the workflow attempts to sign chart refs."""
    install_step = _step_named("Install Cosign")
    cosign_login_step = _step_named("Login Cosign to GHCR")
    assert (
        install_step["uses"] == "sigstore/cosign-installer@dc72c7d5c4d10cd6bcb8cf6e3fd625a9e5e537da"
    )
    assert (
        cosign_login_step["uses"] == "docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9"
    )
    assert cosign_login_step["with"]["registry"] == "ghcr.io"
    assert _step_index("Install Cosign") < _step_index("Sign OCI charts")
    assert _step_index("Login Cosign to GHCR") < _step_index("Sign OCI charts")


@pytest.mark.requirement("AC-3")
@pytest.mark.requirement("AC-4")
@pytest.mark.requirement("AC-5")
def test_publish_oci_signs_expected_chart_refs_after_push_as_best_effort() -> None:
    """Signing runs after helm push, uses the pushed refs, and stays best-effort."""
    sign_step = _step_named("Sign OCI charts")
    assert _step_index("Push charts to OCI registry") < _step_index("Sign OCI charts")
    assert sign_step["continue-on-error"] is True

    run_script = sign_step["run"]
    assert "${REGISTRY_PATH}/${chart_name}:${VERSION}" in run_script
    assert "floe-platform floe-jobs" in run_script
    assert 'echo "WARNING: Failed to sign ${chart_name}" >&2' in run_script
    assert "${REGISTRY}/${REGISTRY_PATH}" not in run_script
