"""Structural coverage for DevPod-hosted live AWS provider validation."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEVPOD_SCRIPT_PATH = _REPO_ROOT / "scripts" / "devpod-test.sh"
_MAKEFILE_PATH = _REPO_ROOT / "Makefile"
_ENV_EXAMPLE_PATH = _REPO_ROOT / ".env.example"


def _read_devpod_script() -> str:
    """Return the DevPod validation wrapper contents."""
    return _DEVPOD_SCRIPT_PATH.read_text()


def _read_makefile() -> str:
    """Return the current Makefile contents."""
    return _MAKEFILE_PATH.read_text()


@pytest.mark.requirement("LIVE-VALIDATION")
def test_devpod_wrapper_uploads_allowlisted_remote_env_without_echoing_values() -> None:
    """Remote live provider runs must receive secrets through a private env file."""
    script = _read_devpod_script()

    assert "DEVPOD_REMOTE_ENV_ALLOWLIST" in script
    assert 'printf \'export %s=%q\\n\' "${env_name}" "${!env_name}"' in script
    assert 'devpod_remote_bash "umask 077 && cat > ${remote_env_q}' in script
    assert 'chmod 600 ${remote_env_q}" < "${LOCAL_REMOTE_ENV_FILE}"' in script
    assert 'REMOTE_ENV_FILE="${REMOTE_RUN_DIR}.remote-env.sh"' in script
    assert "FLOE_REMOTE_ENV_FILE=${remote_env_file_q}" in script
    assert 'source "\\${FLOE_REMOTE_ENV_FILE}"' in script
    assert 'source "\\${FLOE_REMOTE_RUN_DIR}/remote-env.sh"' not in script
    assert 'echo "${!env_name}"' not in script


@pytest.mark.requirement("LIVE-VALIDATION")
def test_devpod_wrapper_validates_remote_env_allowlist_names() -> None:
    """The env allowlist must reject shell metacharacters before any remote command."""
    script = _read_devpod_script()

    assert "for env_name in ${DEVPOD_REMOTE_ENV_ALLOWLIST}; do" in script
    assert '[[ ! "${env_name}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]' in script
    assert "Invalid DEVPOD_REMOTE_ENV_ALLOWLIST entry" in script


@pytest.mark.requirement("LIVE-VALIDATION")
def test_makefile_exposes_devpod_aws_provider_live_target() -> None:
    """AWS S3 + Glue live validation must be runnable from the DevPod lifecycle."""
    makefile = _read_makefile()

    assert ".PHONY: test-aws-provider-live" in makefile
    local_target = (
        "FLOE_RUN_LIVE_AWS_PROVIDER_TESTS=1 "
        "uv run pytest tests/integration/test_aws_provider_live.py -q"
    )
    assert local_target in makefile
    assert ".PHONY: devpod-test-aws-provider" in makefile
    target_env = "DEVPOD_REMOTE_E2E_MAKE_TARGET=" + "test-aws-provider-live"
    assert target_env in makefile
    assert "FLOE_RUN_LIVE_AWS_PROVIDER_TESTS=1" in makefile
    assert "AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN" in makefile


@pytest.mark.requirement("LIVE-VALIDATION")
def test_env_example_documents_remote_aws_live_validation_inputs() -> None:
    """Contributor setup must make the remote AWS live-test controls discoverable."""
    env_example = _ENV_EXAMPLE_PATH.read_text()

    assert "DEVPOD_REMOTE_ENV_ALLOWLIST=" in env_example
    assert "make devpod-test-aws-provider sets the AWS live-test allowlist" in env_example
    assert (
        "aws configure export-credentials --profile floe-aws-bootstrap --format env" in env_example
    )
    assert "FLOE_AWS_TEST_BUCKET=" in env_example
    assert "FLOE_AWS_GLUE_DATABASE_PREFIX=" in env_example
