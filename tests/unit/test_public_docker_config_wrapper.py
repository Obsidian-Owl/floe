"""Tests for the public Docker config wrapper used by DevPod-safe pulls."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "with-public-docker-config.sh"
_MAKEFILE_PATH = _REPO_ROOT / "Makefile"
_ENV_EXAMPLE_PATH = _REPO_ROOT / ".env.example"


def _run_wrapper(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the wrapper with a small subprocess payload."""
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(_SCRIPT_PATH), *args],
        cwd=_REPO_ROOT,
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.requirement("AC-2")
def test_public_docker_wrapper_defaults_to_isolated_config() -> None:
    """The wrapper should shield public pulls from ambient credential helpers."""
    result = _run_wrapper(
        "python",
        "-c",
        (
            "import os, pathlib; "
            "config = pathlib.Path(os.environ['DOCKER_CONFIG']) / 'config.json'; "
            "print(config.read_text().strip())"
        ),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '{"auths":{}}'


@pytest.mark.requirement("AC-2")
def test_public_docker_wrapper_can_inherit_existing_config() -> None:
    """Callers must be able to opt out when they intentionally need custom auth."""
    inherited_dir = _REPO_ROOT / ".tmp-test-docker-config"
    inherited_dir.mkdir(exist_ok=True)
    (inherited_dir / "config.json").write_text('{"auths":{"example.com":{}}}\n')
    try:
        result = _run_wrapper(
            "python",
            "-c",
            "import os; print(os.environ['DOCKER_CONFIG'])",
            env={
                "DOCKER_CONFIG": str(inherited_dir),
                "FLOE_PUBLIC_DOCKER_CONFIG_MODE": "inherit",
            },
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == str(inherited_dir)
    finally:
        (inherited_dir / "config.json").unlink(missing_ok=True)
        inherited_dir.rmdir()


@pytest.mark.requirement("AC-2")
def test_public_docker_wrapper_defaults_builds_to_classic_engine(tmp_path: Path) -> None:
    """Public docker builds should bypass the broken DevPod BuildKit auth path."""
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'DOCKER_BUILDKIT=%s\\n' \"${DOCKER_BUILDKIT:-}\" \n"
        'printf \'ARGS=%s %s\\n\' "$1" "$2"\n'
    )
    fake_docker.chmod(0o755)
    result = _run_wrapper(
        "docker",
        "build",
        env={"PATH": f"{tmp_path}:{os.environ['PATH']}"},
    )
    assert result.returncode == 0, result.stderr
    assert "DOCKER_BUILDKIT=0" in result.stdout
    assert "ARGS=build " in result.stdout


@pytest.mark.requirement("AC-2")
def test_build_demo_image_uses_public_docker_wrapper() -> None:
    """The demo image build must not depend on ambient Docker helper state."""
    makefile = _MAKEFILE_PATH.read_text()
    assert "scripts/with-public-docker-config.sh docker build" in makefile
    assert (
        "scripts/with-public-docker-config.sh docker run --rm -i ghcr.io/yannh/kubeconform:v0.6.7"
    ) in makefile
    assert (
        "scripts/with-public-docker-config.sh docker build -t floe-test-runner:latest "
        "-f testing/Dockerfile ."
    ) in makefile


@pytest.mark.requirement("AC-2")
def test_ci_test_runner_builds_use_public_docker_wrapper() -> None:
    """Remote-safe CI scripts should not build test-runner images with ambient auth."""
    e2e_script = (_REPO_ROOT / "testing" / "ci" / "test-e2e-cluster.sh").read_text()
    integration_script = (_REPO_ROOT / "testing" / "ci" / "test-integration.sh").read_text()

    assert (
        "scripts/with-public-docker-config.sh docker build -t "
        '"${IMAGE_NAME}" -f testing/Dockerfile .'
    ) in e2e_script
    assert "docker build" not in integration_script
    assert '"${SCRIPT_DIR}/test-e2e-cluster.sh"' in integration_script


@pytest.mark.requirement("AC-2")
def test_env_example_documents_public_docker_config_controls() -> None:
    """The repo should surface the Docker helper override in documented config."""
    env_example = _ENV_EXAMPLE_PATH.read_text()
    assert "FLOE_PUBLIC_DOCKER_CONFIG_MODE=isolated" in env_example
    assert "FLOE_PUBLIC_DOCKER_CONFIG_DIR=" in env_example
    assert "FLOE_PUBLIC_DOCKER_BUILD_ENGINE=classic" in env_example
