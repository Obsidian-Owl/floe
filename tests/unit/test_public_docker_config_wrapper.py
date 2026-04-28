"""Tests for the public Docker config wrapper used by DevPod-safe pulls."""

from __future__ import annotations

import json
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
def test_public_docker_wrapper_defaults_to_isolated_helm_registry_config() -> None:
    """Helm OCI dependency pulls must not inherit stale Docker credential helpers."""
    result = _run_wrapper(
        "python",
        "-c",
        (
            "import os, pathlib; "
            "config = pathlib.Path(os.environ['HELM_REGISTRY_CONFIG']); "
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
def test_public_docker_wrapper_preserves_active_context_in_isolated_config(
    tmp_path: Path,
) -> None:
    """Isolated auth config must not discard non-default Docker contexts."""
    source_config = tmp_path / "source-docker-config"
    (source_config / "contexts").mkdir(parents=True)

    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1 $2" == "context show" ]]; then\n'
        "  printf 'orbstack\\n'\n"
        "  exit 0\n"
        "fi\n"
        "printf 'DOCKER_CONFIG=%s\\n' \"${DOCKER_CONFIG}\"\n"
        "printf 'CONFIG_JSON=%s\\n' \"$(tr -d '\\n' < \"${DOCKER_CONFIG}/config.json\")\"\n"
        'if [[ -e "${DOCKER_CONFIG}/contexts" ]]; then\n'
        "  printf 'CONTEXTS_PRESENT=1\\n'\n"
        "fi\n"
    )
    fake_docker.chmod(0o755)

    result = _run_wrapper(
        "docker",
        "build",
        env={
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "DOCKER_CONFIG": str(source_config),
        },
    )

    assert result.returncode == 0, result.stderr
    assert 'CONFIG_JSON={"auths":{},"currentContext":"orbstack"}' in result.stdout
    assert "CONTEXTS_PRESENT=1" in result.stdout


@pytest.mark.requirement("AC-2")
def test_public_docker_wrapper_json_escapes_active_context(tmp_path: Path) -> None:
    """Docker context names must be serialized as JSON, not interpolated text."""
    source_config = tmp_path / "source-docker-config"
    (source_config / "contexts").mkdir(parents=True)

    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1 $2" == "context show" ]]; then\n'
        "  printf 'orb\"stack\\\\prod\\n'\n"
        "  exit 0\n"
        "fi\n"
        "python - <<'PY'\n"
        "import json, os, pathlib\n"
        "config = pathlib.Path(os.environ['DOCKER_CONFIG']) / 'config.json'\n"
        "print(json.dumps(json.loads(config.read_text()), sort_keys=True))\n"
        "PY\n"
    )
    fake_docker.chmod(0o755)

    result = _run_wrapper(
        "docker",
        "build",
        env={
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "DOCKER_CONFIG": str(source_config),
        },
    )

    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout.strip())
    assert config == {"auths": {}, "currentContext": 'orb"stack\\prod'}


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
    assert (
        "scripts/with-public-docker-config.sh docker build -t "
        '"${IMAGE_NAME}" -f testing/Dockerfile .'
    ) in integration_script


@pytest.mark.requirement("AC-2")
def test_e2e_runner_resolves_chart_dependencies_before_image_build() -> None:
    """Clean remote E2E images must include Helm chart dependencies.

    The destructive E2E suite runs `helm upgrade charts/floe-platform` inside
    the test-runner pod. A clean Git checkout only has local subcharts; remote
    dependencies must be vendored before Docker copies `charts/` into the image.
    """
    e2e_script = (_REPO_ROOT / "testing" / "ci" / "test-e2e-cluster.sh").read_text()

    dependency_build = e2e_script.find("floe_ensure_chart_dependencies")
    image_build = e2e_script.find(
        'scripts/with-public-docker-config.sh docker build -t "${IMAGE_NAME}"'
    )

    assert dependency_build != -1, (
        "test-e2e-cluster.sh must explicitly vendor Helm chart dependencies "
        "before building the test-runner image."
    )
    assert image_build != -1, "test-e2e-cluster.sh must build the test-runner image."
    assert dependency_build < image_build, (
        "Helm chart dependencies must be resolved before Docker copies charts/ "
        "into floe-test-runner:latest."
    )


@pytest.mark.requirement("AC-2")
def test_chart_dependency_builds_use_public_registry_wrapper() -> None:
    """Helm OCI chart dependencies should bypass ambient DevPod credential helpers."""
    common_script = (_REPO_ROOT / "testing" / "ci" / "common.sh").read_text()

    assert "floe_public_registry_command()" in common_script
    assert 'floe_public_registry_command helm dependency build "${FLOE_CHART_DIR}"' in common_script


@pytest.mark.requirement("AC-2")
def test_bootstrap_helm_workflow_uses_public_registry_wrapper() -> None:
    """Bootstrap validation must not inherit stale DevPod Helm OCI credentials."""
    helm_workflow = (_REPO_ROOT / "tests" / "e2e" / "test_helm_workflow.py").read_text()

    assert "_PUBLIC_DOCKER_CONFIG_WRAPPER" in helm_workflow
    assert 'str(_PUBLIC_DOCKER_CONFIG_WRAPPER), "helm"' in helm_workflow


@pytest.mark.requirement("AC-2")
def test_env_example_documents_public_docker_config_controls() -> None:
    """The repo should surface the Docker helper override in documented config."""
    env_example = _ENV_EXAMPLE_PATH.read_text()
    assert "FLOE_PUBLIC_DOCKER_CONFIG_MODE=isolated" in env_example
    assert "FLOE_PUBLIC_DOCKER_CONFIG_DIR=" in env_example
    assert "FLOE_PUBLIC_DOCKER_BUILD_ENGINE=classic" in env_example
