"""Structural tests for Git-backed DevPod source selection."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
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


def _run_source_helper(
    *,
    project_root: Path,
    remote: Path,
    ref: str,
) -> subprocess.CompletedProcess[str]:
    """Resolve a DevPod source using the real shell helper against a test remote."""
    script = (
        f"source {shlex.quote(str(_SOURCE_HELPER))}; "
        f"devpod_resolve_source {shlex.quote(str(project_root))}"
    )
    return subprocess.run(
        ["bash", "-lc", script],
        check=False,
        env={
            **os.environ,
            "DEVPOD_GIT_REMOTE": str(remote),
            "DEVPOD_GIT_REF": ref,
        },
        text=True,
        capture_output=True,
    )


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_source_helper_defaults_to_remote_git_branch() -> None:
    """DevPod source resolution must avoid local worktree upload by default."""
    helper = _read(_SOURCE_HELPER)

    assert "DEVPOD_SOURCE" in helper
    assert "DEVPOD_ALLOW_LOCAL_SOURCE" in helper
    assert "git ls-remote --exit-code" in helper
    assert "git ls-remote --exit-code --heads" not in helper
    assert "git:%s@%s" in helper
    assert "printf '%s\\n' \"${project_root}\"" in helper
    assert "Remote ref" in helper


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_source_helper_accepts_tag_refs(tmp_path: Path) -> None:
    """DEVPOD_GIT_REF must accept pushed tags for reproducible DevPod runs."""
    worktree = tmp_path / "worktree"
    remote = tmp_path / "remote.git"
    worktree.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True)
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "Test User"], check=True)
    (worktree / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(worktree), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", str(worktree), "tag", "v1.0.0"], check=True)
    subprocess.run(["git", "-C", str(worktree), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(
        ["git", "-C", str(worktree), "push", "origin", "HEAD:main", "v1.0.0"],
        check=True,
    )

    result = _run_source_helper(project_root=worktree, remote=remote, ref="v1.0.0")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"git:{str(remote).removesuffix('.git')}@v1.0.0"


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_source_helper_rejects_tail_pattern_ref_matches(tmp_path: Path) -> None:
    """Remote ref preflight must not accept suffix-pattern matches as exact refs."""
    worktree = tmp_path / "worktree"
    remote = tmp_path / "remote.git"
    worktree.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True)
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "Test User"], check=True)
    (worktree / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(worktree), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-m", "initial"], check=True)
    subprocess.run(
        ["git", "-C", str(worktree), "push", str(remote), "HEAD:refs/heads/feature/main"],
        check=True,
    )

    result = _run_source_helper(project_root=worktree, remote=remote, ref="main")

    assert result.returncode == 1
    assert "Remote ref 'main' is not available" in result.stderr


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_source_helper_rejects_missing_refs(tmp_path: Path) -> None:
    """Missing branch/tag refs must fail before provisioning Hetzner resources."""
    remote = tmp_path / "remote.git"
    project_root = tmp_path / "project"
    project_root.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)

    result = _run_source_helper(project_root=project_root, remote=remote, ref="missing-ref")

    assert result.returncode == 1
    assert "Remote ref 'missing-ref' is not available" in result.stderr


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
def test_workspace_running_rejects_not_running_status() -> None:
    """DevPod recovery must not treat 'Not running' as a healthy workspace."""
    script = _read(_DEVPOD_TEST)

    assert "[Rr]unning" not in script
    assert "not[[:space:]-]+running" in script


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_workspace_running_accepts_quoted_running_status() -> None:
    """DevPod recovery must accept the current CLI's quoted Running status."""
    script = _read(_DEVPOD_TEST)

    assert re.search(r"\[\^\[:alpha:\]\]\)running\(\[\^\[:alpha:\]\]\|\$\)", script), (
        "workspace_running must match DevPod status output such as "
        "\"Workspace 'floe' is 'Running'\". A whitespace-only boundary misses "
        "the quoted status and destroys a usable workspace after transport drops."
    )


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_full_lifecycle_skips_heavy_poststart_setup_during_provision() -> None:
    """Heavy Kind/E2E setup must run detached, not inside `devpod up`."""
    script = _read(_DEVPOD_TEST)
    post_start = _read(_REPO_ROOT / ".devcontainer" / "hetzner" / "postStartCommand.sh")

    assert "FLOE_DEVPOD_SKIP_POSTSTART_SETUP" in post_start, (
        "The Hetzner postStartCommand must expose an explicit skip control so "
        "the full lifecycle harness can keep `devpod up` lightweight."
    )
    provision_workspace = re.search(
        r"provision_workspace\(\) \{(.*?)recover_workspace_after_up_failure",
        script,
        re.DOTALL,
    )
    assert provision_workspace is not None, "provision_workspace function not found"
    provision_body = provision_workspace.group(1)
    assert 'if [[ "${DEVPOD_E2E_EXECUTION}" == "remote" ]]' in provision_body
    assert "workspace_env_args=(--workspace-env FLOE_DEVPOD_SKIP_POSTSTART_SETUP=1)" in (
        provision_body
    ), (
        "scripts/devpod-test.sh must skip heavyweight postStart setup only when "
        "remote E2E owns detached Kind/test execution."
    )
    assert '"${workspace_env_args[@]}"' in provision_body
    assert "--workspace-env FLOE_DEVPOD_SKIP_POSTSTART_SETUP=1 \\" not in provision_body
    env_example = _read(_ENV_EXAMPLE)
    assert "FLOE_DEVPOD_SKIP_POSTSTART_SETUP=0" in env_example, (
        ".env.example must document the postStart skip escape hatch for manual DevPod debugging."
    )
    assert "Set to 1 to skip automatic Kind/platform setup" in env_example


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
def test_remote_e2e_bootstraps_kind_before_running_tests() -> None:
    """Remote E2E owns Kind setup when provisioning skips postStart setup."""
    script = _read(_DEVPOD_TEST)

    assert "make kind-up" in script, (
        "The detached remote E2E script must create/deploy the Kind stack "
        "before running the in-cluster E2E Job."
    )
    assert script.index("make kind-up") < script.index("IMAGE_LOAD_METHOD=kind make test-e2e")


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_remote_e2e_skips_host_kubeconfig_health_gate() -> None:
    """Host kubeconfig sync must not run before remote Kind bootstrap exists."""
    script = _read(_DEVPOD_TEST)

    assert "Remote E2E owns Kind bootstrap; skipping host kubeconfig health gate" in script
    assert 'if [[ "${DEVPOD_E2E_EXECUTION}" == "remote" ]]; then' in script


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
def test_full_lifecycle_parses_remote_poll_payload_when_devpod_exits_nonzero() -> None:
    """DevPod can append tunnel errors after a valid remote poll payload."""
    script = _read(_DEVPOD_TEST)

    assert "poll_status=$?" in script
    assert "poll_state=" in script
    assert "grep -E '^(complete:[0-9]+|running|lost)$'" in script
    assert 'case "${poll_state}" in' in script
    assert "printf '%s\\n' \"${poll_state#complete:}\"" in script


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_remote_poll_stdout_is_reserved_for_exit_code() -> None:
    """Remote polling progress must not corrupt captured numeric exit code."""
    script = _read(_DEVPOD_TEST)
    poll_start = script.index("poll_remote_e2e_run() {")
    fetch_start = script.index("fetch_remote_e2e_artifacts()", poll_start)
    poll_function = script[poll_start:fetch_start]

    assert "echo \"[devpod-test] $(date '+%H:%M:%S') $*\" >&2" in script
    assert 'log "  Remote E2E still running' in poll_function
    assert "printf '%s\\n' \"${poll_state#complete:}\"" in poll_function


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_full_lifecycle_keeps_local_e2e_as_explicit_fallback() -> None:
    """The old host-driven E2E path must be opt-in, not the default path."""
    script = _read(_DEVPOD_TEST)

    assert "local)" in script
    assert 'make -C "${PROJECT_ROOT}" test-e2e KUBECONFIG="${KUBECONFIG_PATH}"' in script
    assert "DEVPOD_E2E_EXECUTION=local" in script


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_full_lifecycle_skips_tunnels_for_remote_e2e_by_default() -> None:
    """Remote E2E must not depend on host-side service SSH tunnels."""
    script = _read(_DEVPOD_TEST)

    assert 'DEVPOD_ENABLE_REMOTE_TUNNELS="${DEVPOD_ENABLE_REMOTE_TUNNELS:-0}"' in script
    assert "establish_service_tunnels()" in script
    assert "Skipping service port tunnels for remote E2E" in script
    assert 'if [[ "${DEVPOD_ENABLE_REMOTE_TUNNELS}" == "1" ]]; then' in script
    assert "Failed to establish optional remote SSH tunnels" in script


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_full_lifecycle_requires_tunnels_for_local_e2e() -> None:
    """Local E2E still requires tunnels because it runs from the host."""
    script = _read(_DEVPOD_TEST)

    local_case_start = script.index("local)")
    invalid_case_start = script.index("*)", local_case_start)
    local_case = script[local_case_start:invalid_case_start]

    assert 'bash "${SCRIPT_DIR}/devpod-tunnels.sh"' in local_case
    assert 'error "Failed to establish SSH tunnels"' in local_case
    assert "Skipping service port tunnels for remote E2E" not in local_case


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
        "DEVPOD_ENABLE_REMOTE_TUNNELS",
    ):
        assert variable in env_example
