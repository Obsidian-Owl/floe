"""Tests for Flux source branch selection in the Kind setup script."""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETUP_SCRIPT = _REPO_ROOT / "testing" / "k8s" / "setup-cluster.sh"


def _run_setup_function(
    script: str,
    tmp_path: Path,
    *,
    flux_branch: str = "feature-worktree",
    required_branch: str = "release-alpha",
) -> subprocess.CompletedProcess[str]:
    """Source setup-cluster.sh without running main, then execute a Bash snippet."""
    script_dir = tmp_path / "testing" / "k8s"
    script_dir.mkdir(parents=True)
    common_dir = tmp_path / "testing" / "ci"
    common_dir.mkdir(parents=True)

    (common_dir / "common.sh").write_text((_REPO_ROOT / "testing" / "ci" / "common.sh").read_text())
    sourceable_script = script_dir / "setup-cluster.sh"
    setup_source = _SETUP_SCRIPT.read_text()
    sourceable_script.write_text(setup_source.replace('\nmain "$@"\n', "\n"))

    bash_script = tmp_path / "run.sh"
    bash_script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            source "{sourceable_script}"
            {script}
            """
        )
    )

    env = os.environ.copy()
    env["FLOE_REQUIRED_FLUX_GIT_BRANCH"] = required_branch
    env["FLOE_FLUX_GIT_BRANCH"] = flux_branch
    env["FLOE_DEMO_IMAGE_REPOSITORY"] = "floe-dagster-demo"
    env["FLOE_DEMO_IMAGE_TAG"] = "local"
    env["FLOE_DEMO_IMAGE"] = "floe-dagster-demo:local"

    return subprocess.run(
        ["bash", str(bash_script)],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def test_resolve_flux_git_branch_uses_explicit_flux_branch(tmp_path: Path) -> None:
    """FLOE_REQUIRED_FLUX_GIT_BRANCH guards but does not select the branch."""
    result = _run_setup_function("resolve_flux_git_branch", tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "feature-worktree"


def test_deploy_via_flux_rejects_explicit_branch_mismatch(tmp_path: Path) -> None:
    """Remote validation fails before deploy when Flux branch drifts."""
    result = _run_setup_function(
        textwrap.dedent(
            """\
            kubectl() {
                echo "kubectl should not be called before branch validation" >&2
                return 99
            }

            deploy_via_flux
            """
        ),
        tmp_path,
    )

    assert result.returncode != 0
    assert "Flux branch mismatch" in result.stderr
    assert "expected release-alpha" in result.stderr
    assert "got feature-worktree" in result.stderr
    assert "kubectl should not be called" not in result.stderr


def test_deploy_via_flux_accepts_explicit_branch_match(tmp_path: Path) -> None:
    """Matching selected and required branches render Flux manifests normally."""
    result = _run_setup_function(
        textwrap.dedent(
            """\
            rendered_branch_file="${TMPDIR:-/tmp}/floe-rendered-branch.$$"
            kubectl() {
                if [[ "${1:-}" == "wait" ]]; then
                    return 0
                fi
                cat >/dev/null
                return 0
            }
            render_flux_manifests() {
                printf '%s\\n' "$1" > "${rendered_branch_file}"
                local manifest_dir
                manifest_dir=$(mktemp -d)
                touch "${manifest_dir}/gitrepository.yaml"
                printf '%s\\n' "${manifest_dir}"
            }

            deploy_via_flux
            printf 'rendered_branch=%s\\n' "$(cat "${rendered_branch_file}")"
            rm -f "${rendered_branch_file}"
            """
        ),
        tmp_path,
        required_branch="feature-worktree",
    )

    assert result.returncode == 0, result.stderr
    assert "rendered_branch=feature-worktree" in result.stdout
