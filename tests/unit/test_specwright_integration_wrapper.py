"""Regression tests for the Specwright integration dispatcher."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _REPO_ROOT / ".specwright" / "config.json"
_SCRIPT_PATH = _REPO_ROOT / "testing" / "ci" / "test-specwright-integration.sh"


def _run_wrapper(*, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the wrapper with a controlled environment."""
    return _run_wrapper_in_repo(_REPO_ROOT, env=env)


def _run_wrapper_in_repo(
    repo_root: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the wrapper from an arbitrary repository root."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", str(repo_root / "testing" / "ci" / "test-specwright-integration.sh")],
        cwd=repo_root,
        env=merged_env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.mark.requirement("AC-5")
def test_specwright_config_uses_integration_dispatcher() -> None:
    """Specwright config points build/verify at the generic integration wrapper."""
    config = json.loads(_CONFIG_PATH.read_text())
    assert config["commands"]["test:integration"] == "./testing/ci/test-specwright-integration.sh"


@pytest.mark.requirement("AC-5")
def test_dispatcher_noop_profile_exits_zero() -> None:
    """The explicit no-op profile should skip cleanly for structural units."""
    result = _run_wrapper(env={"SPECWRIGHT_INTEGRATION_PROFILE": "none"})
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "No targeted Specwright integration suite matched" in result.stdout


@pytest.mark.requirement("AC-5")
def test_dispatcher_unit_c_profile_dry_run_reports_remote_boundary_command() -> None:
    """The Unit C profile should expose the existing remote boundary proof command."""
    result = _run_wrapper(
        env={
            "SPECWRIGHT_INTEGRATION_PROFILE": "unit-c-devpod-boundary",
            "SPECWRIGHT_INTEGRATION_DRY_RUN": "1",
        }
    )
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "Selected profile: unit-c-devpod-boundary" in result.stdout
    assert "tests/integration/test_unit_c_devpod_flux_boundary.py" in result.stdout


@pytest.mark.requirement("AC-5")
@pytest.mark.parametrize(
    "changed_file",
    [
        "testing/ci/common.sh",
        "testing/ci/test-e2e-cluster.sh",
        "testing/ci/test-unit-c-boundary.sh",
        "testing/k8s/setup-cluster.sh",
        "testing/k8s/flux/gitrepository.yaml",
        "charts/floe-platform/values-test.yaml",
        "charts/floe-platform/templates/_helpers.tpl",
        "charts/floe-platform/templates/tests/_test-job.tpl",
        "charts/floe-platform/templates/tests/job-e2e.yaml",
        "charts/floe-platform/templates/tests/pvc-artifacts.yaml",
        "charts/floe-platform/templates/tests/rbac-standard.yaml",
        "tests/integration/test_unit_c_devpod_flux_boundary.py",
        "tests/unit/test_unit_c_boundary_wrapper.py",
        "scripts/devpod-ensure-ready.sh",
        ".devcontainer/hetzner/postStartCommand.sh",
    ],
)
def test_dispatcher_auto_detects_unit_c_profile_from_changed_files(
    changed_file: str,
) -> None:
    """The wrapper should detect Unit C's direct runtime dependencies."""
    result = _run_wrapper(
        env={
            "SPECWRIGHT_CHANGED_FILES": changed_file,
            "SPECWRIGHT_INTEGRATION_DRY_RUN": "1",
        }
    )
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "Selected profile: unit-c-devpod-boundary" in result.stdout


@pytest.mark.requirement("AC-5")
def test_dispatcher_rejects_unknown_profile() -> None:
    """Unknown profiles must fail closed with exit code 2."""
    result = _run_wrapper(env={"SPECWRIGHT_INTEGRATION_PROFILE": "bogus-profile"})
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 2, combined
    assert "Unknown Specwright integration profile" in result.stderr


@pytest.mark.requirement("AC-5")
def test_dispatcher_uses_reachable_branch_history_without_main_refs(
    tmp_path: Path,
) -> None:
    """Shallow single-branch clones should still see earlier PR-triggering commits."""
    origin_repo = tmp_path / "origin"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(origin_repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Specwright Tests"],
        cwd=origin_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "specwright@example.com"],
        cwd=origin_repo,
        check=True,
        capture_output=True,
        text=True,
    )

    (origin_repo / "testing" / "ci").mkdir(parents=True)
    (origin_repo / "testing" / "k8s").mkdir(parents=True)
    (origin_repo / "testing" / "ci" / "common.sh").write_text(
        (_REPO_ROOT / "testing" / "ci" / "common.sh").read_text()
    )
    (origin_repo / "testing" / "ci" / "test-specwright-integration.sh").write_text(
        _SCRIPT_PATH.read_text()
    )
    (origin_repo / "testing" / "k8s" / "setup-cluster.sh").write_text("base\n")
    (origin_repo / "README.md").write_text("base\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=origin_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=origin_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", "feature"],
        cwd=origin_repo,
        check=True,
        capture_output=True,
        text=True,
    )

    (origin_repo / "testing" / "k8s" / "setup-cluster.sh").write_text("trigger\n")
    subprocess.run(
        ["git", "commit", "-am", "trigger unit c"],
        cwd=origin_repo,
        check=True,
        capture_output=True,
        text=True,
    )

    (origin_repo / "README.md").write_text("unrelated\n")
    subprocess.run(
        ["git", "commit", "-am", "unrelated follow-up"],
        cwd=origin_repo,
        check=True,
        capture_output=True,
        text=True,
    )

    shallow_clone = tmp_path / "shallow-clone"
    subprocess.run(
        [
            "git",
            "clone",
            "--depth=2",
            "--branch",
            "feature",
            "--single-branch",
            origin_repo.as_uri(),
            str(shallow_clone),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    missing_main_ref = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=shallow_clone,
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing_main_ref.returncode != 0

    result = _run_wrapper_in_repo(
        shallow_clone,
        env={"SPECWRIGHT_INTEGRATION_DRY_RUN": "1"},
    )
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "Selected profile: unit-c-devpod-boundary" in result.stdout
