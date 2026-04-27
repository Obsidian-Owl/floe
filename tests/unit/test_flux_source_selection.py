"""Tests for Flux source branch selection in the Kind setup script."""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

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


@pytest.mark.requirement("AC-2")
def test_resolve_flux_git_branch_uses_explicit_flux_branch(tmp_path: Path) -> None:
    """FLOE_REQUIRED_FLUX_GIT_BRANCH guards but does not select the branch."""
    result = _run_setup_function("resolve_flux_git_branch", tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "feature-worktree"


@pytest.mark.requirement("AC-2")
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


@pytest.mark.requirement("AC-2")
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


@pytest.mark.requirement("AC-2")
def test_render_flux_manifests_injects_demo_image_without_python_yaml(
    tmp_path: Path,
) -> None:
    """Flux image overrides must not depend on system Python packages.

    The Hetzner DevPod bootstrap environment has Python but not necessarily
    PyYAML. If rendering relies on ``import yaml``, the image override is
    skipped and Flux deploys the stale ``floe-dagster-demo:latest`` value.
    """
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python3"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'python3 must not be required for Flux image injection' >&2\n"
        "exit 127\n"
    )
    fake_python.chmod(0o755)

    result = _run_setup_function(
        textwrap.dedent(
            f"""\
            export PATH="{fake_bin}:$PATH"
            FLOE_FLUX_FIXTURE_DIR="{_REPO_ROOT / "testing" / "k8s" / "flux"}"

            rendered_dir="$(render_flux_manifests "feature-worktree")"
            trap 'rm -rf "$rendered_dir"' EXIT

            grep -q 'tag: "local"' "$rendered_dir/helmrelease-platform.yaml"
            grep -q 'repository: "floe-dagster-demo"' "$rendered_dir/helmrelease-platform.yaml"
            if grep -q 'python3 must not be required' \\
                "$rendered_dir/helmrelease-platform.yaml"; then
                exit 99
            fi
            """
        ),
        tmp_path,
        required_branch="feature-worktree",
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.requirement("AC-2")
def test_render_flux_manifests_merges_demo_image_into_existing_values(
    tmp_path: Path,
) -> None:
    """Image overrides must merge into an existing HelmRelease spec.values map."""
    flux_fixture_dir = tmp_path / "flux-fixture"
    flux_fixture_dir.mkdir()
    (flux_fixture_dir / "gitrepository.yaml").write_text(
        (_REPO_ROOT / "testing" / "k8s" / "flux" / "gitrepository.yaml").read_text()
    )
    (flux_fixture_dir / "helmrelease-platform.yaml").write_text(
        textwrap.dedent(
            """\
            apiVersion: helm.toolkit.fluxcd.io/v2
            kind: HelmRelease
            metadata:
              name: floe-platform
              namespace: floe-test
            spec:
              interval: 30m
              chart:
                spec:
                  chart: ./charts/floe-platform/flux-artifacts/floe-platform.tgz
                  sourceRef:
                    kind: GitRepository
                    name: floe
                    namespace: flux-system
              values:
                existingConfig:
                  enabled: true
            """
        )
    )

    result = _run_setup_function(
        textwrap.dedent(
            f"""\
            FLOE_FLUX_FIXTURE_DIR="{flux_fixture_dir}"

            rendered_dir="$(render_flux_manifests "feature-worktree")"
            printf '%s\\n' "$rendered_dir"
            """
        ),
        tmp_path,
        required_branch="feature-worktree",
    )

    assert result.returncode == 0, result.stderr
    rendered_dir = Path(result.stdout.strip().splitlines()[-1])
    rendered_helmrelease = rendered_dir / "helmrelease-platform.yaml"
    rendered_content = rendered_helmrelease.read_text()

    assert rendered_content.count("\n  values:\n") == 1
    assert "existingConfig:" in rendered_content
    assert 'repository: "floe-dagster-demo"' in rendered_content
    assert 'tag: "local"' in rendered_content
