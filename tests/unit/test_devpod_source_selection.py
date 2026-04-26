"""Structural tests for Git-backed DevPod source selection."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SOURCE_HELPER = _REPO_ROOT / "scripts" / "devpod-source.sh"
_DEVPOD_TEST = _REPO_ROOT / "scripts" / "devpod-test.sh"
_DEVPOD_READY = _REPO_ROOT / "scripts" / "devpod-ensure-ready.sh"
_MAKEFILE = _REPO_ROOT / "Makefile"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"


def _read(path: Path) -> str:
    return path.read_text()


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_source_helper_defaults_to_remote_git_branch() -> None:
    """DevPod source resolution must avoid local worktree upload by default."""
    helper = _read(_SOURCE_HELPER)

    assert "DEVPOD_SOURCE" in helper
    assert "DEVPOD_ALLOW_LOCAL_SOURCE" in helper
    assert "git ls-remote --exit-code --heads" in helper
    assert "git:%s@%s" in helper
    assert "printf '%s\\n' \"${project_root}\"" in helper
    assert "Remote branch" in helper


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_full_lifecycle_uses_devpod_source_flag() -> None:
    """Full lifecycle validation must clone on Hetzner, not upload the repo."""
    script = _read(_DEVPOD_TEST)

    assert 'source "${SCRIPT_DIR}/devpod-source.sh"' in script
    assert 'devpod_resolve_source "${PROJECT_ROOT}"' in script
    assert "provision_workspace()" in script
    assert 'devpod up "${WORKSPACE}"' in script
    assert '--source "${DEVPOD_SOURCE_RESOLVED}"' in script
    assert 'devpod up "${PROJECT_ROOT}"' not in script


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_full_lifecycle_recovers_if_devpod_up_transport_drops() -> None:
    """A dropped `devpod up` channel must not immediately destroy a ready VM."""
    script = _read(_DEVPOD_TEST)

    assert "recover_workspace_after_up_failure()" in script
    assert 'DEVPOD_UP_RECOVERY_TIMEOUT="${DEVPOD_UP_RECOVERY_TIMEOUT:-600}"' in script
    assert "workspace_running && return 0" in script
    assert "recover_workspace_after_up_failure" in script
    assert 'error "Failed to provision workspace"' in script


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_full_lifecycle_provider_check_is_pipefail_safe() -> None:
    """DevPod provider preflight must not use grep -q under pipefail.

    Some CLI producers receive SIGPIPE when `grep -q` exits after its first
    match. With `set -o pipefail`, that turns a successful match into a failed
    preflight before the Hetzner workspace is even created.
    """
    script = _read(_DEVPOD_TEST)

    assert "provider_list=" in script
    assert "devpod provider list 2>/dev/null || true" in script
    assert 'grep -q "hetzner"' not in script


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_full_lifecycle_runs_e2e_inside_devpod_by_default() -> None:
    """Full lifecycle validation must not stream local E2E images by default."""
    script = _read(_DEVPOD_TEST)

    assert 'DEVPOD_E2E_EXECUTION="${DEVPOD_E2E_EXECUTION:-remote}"' in script
    assert 'case "${DEVPOD_E2E_EXECUTION}" in' in script
    assert "remote)" in script
    assert "run_remote_e2e_detached" in script
    assert "start_remote_e2e_run" in script
    assert "poll_remote_e2e_run" in script
    assert "fetch_remote_e2e_artifacts" in script
    assert '--workdir "${DEVPOD_REMOTE_WORKDIR}"' in script
    assert "IMAGE_LOAD_METHOD=kind make test-e2e" in script
    assert '--command "bash -lc ${escaped_script}"' in script


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_full_lifecycle_remote_e2e_is_detached_and_resumable() -> None:
    """Remote E2E must survive a dropped long-lived DevPod SSH command."""
    script = _read(_DEVPOD_TEST)

    assert 'nohup bash "\\${run_dir}/run.sh"' in script
    assert 'echo "\\${rc}" > "\\${FLOE_REMOTE_RUN_DIR}/exit-code"' in script
    assert "poll_failures=$((poll_failures + 1))" in script
    assert "DEVPOD_REMOTE_POLL_FAILURE_LIMIT" in script
    assert "DEVPOD_REMOTE_E2E_TIMEOUT" in script
    assert "test-artifacts/devpod-${REMOTE_RUN_ID}" in script


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_full_lifecycle_keeps_local_e2e_as_explicit_fallback() -> None:
    """The old host-driven E2E path must be opt-in, not the default path."""
    script = _read(_DEVPOD_TEST)

    assert "local)" in script
    assert 'make -C "${PROJECT_ROOT}" test-e2e KUBECONFIG="${KUBECONFIG_PATH}"' in script
    assert "DEVPOD_E2E_EXECUTION=local" in script


@pytest.mark.requirement("AC-DevPod-Health-Gate")
def test_full_lifecycle_health_gate_counts_captured_pod_rows() -> None:
    """Pod health arithmetic must operate on normalized numeric counts."""
    script = _read(_DEVPOD_TEST)

    assert 'POD_ROWS="$(kubectl --kubeconfig="${KUBECONFIG_PATH}" get pods' in script
    assert 'TOTAL="$(printf' in script
    assert "sed '/^[[:space:]]*$/d'" in script
    assert 'UNHEALTHY="$(printf' in script
    assert "wc -l | tr -d ' ' || echo \"0\"" not in script


@pytest.mark.requirement("AC-DevPod-Cleanup")
def test_full_lifecycle_cleanup_disarms_trap_before_deleting_workspace() -> None:
    """Signal-triggered cleanup must not run again via the EXIT trap."""
    script = _read(_DEVPOD_TEST)
    cleanup_start = script.index("cleanup() {")
    delete_start = script.index('if [[ "${WORKSPACE_CREATED}" == "true" ]]; then')

    assert "trap - EXIT INT TERM" in script[cleanup_start:delete_start]


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_readiness_restart_uses_same_source_selection() -> None:
    """Auto-started workspaces must use the same remote-source path."""
    script = _read(_DEVPOD_READY)

    assert 'source "${SCRIPT_DIR}/devpod-source.sh"' in script
    assert 'devpod_resolve_source "${PROJECT_ROOT}"' in script
    assert '--source "${DEVPOD_SOURCE_RESOLVED}"' in script
    assert 'devpod up "${PROJECT_ROOT}"' not in script


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_make_devpod_up_uses_source_helper() -> None:
    """Manual DevPod startup must not retain the local-folder upload path."""
    makefile = _read(_MAKEFILE)

    assert "source scripts/devpod-source.sh" in makefile
    assert '--source "$${source_resolved}"' in makefile
    assert "devpod up ." not in makefile


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_env_documents_remote_source_controls() -> None:
    """Source controls must be discoverable without reading shell internals."""
    env_example = _read(_ENV_EXAMPLE)

    for variable in (
        "DEVPOD_SOURCE",
        "DEVPOD_GIT_REF",
        "DEVPOD_ALLOW_LOCAL_SOURCE",
    ):
        assert variable in env_example
