from pathlib import Path

import pytest

PORTABILITY_FILES = (
    Path(".mcp.json"),
    Path("Makefile"),
    Path("demo/README.md"),
    Path("TESTING.md"),
    Path("scripts/devpod-ensure-ready.sh"),
    Path("scripts/devpod-test.sh"),
    Path("scripts/devpod-sync-kubeconfig.sh"),
)


@pytest.mark.requirement("197")
def test_makefile_does_not_hardcode_floe_workspace_kubeconfig() -> None:
    """Demo and Devpod targets derive kubeconfig from DEVPOD_WORKSPACE."""
    text = Path("Makefile").read_text()

    assert "devpod-floe.config" not in text
    assert "DEVPOD_KUBECONFIG ?=" in text
    assert "devpod-$(DEVPOD_WORKSPACE).config" in text


@pytest.mark.requirement("197")
def test_user_facing_docs_do_not_hardcode_floe_workspace_kubeconfig() -> None:
    """User-facing docs keep DevPod kubeconfig paths workspace-portable."""
    for path in PORTABILITY_FILES:
        assert "devpod-floe.config" not in path.read_text(), str(path)


@pytest.mark.requirement("197")
def test_devpod_scripts_honor_devpod_kubeconfig_override() -> None:
    """DevPod sync/readiness scripts honor DEVPOD_KUBECONFIG overrides."""
    sync_script = Path("scripts/devpod-sync-kubeconfig.sh").read_text()
    ready_script = Path("scripts/devpod-ensure-ready.sh").read_text()
    test_script = Path("scripts/devpod-test.sh").read_text()

    assert 'LOCAL_KUBECONFIG="${DEVPOD_KUBECONFIG:-' in sync_script
    assert 'KUBECONFIG_PATH="${DEVPOD_KUBECONFIG:-' in ready_script
    assert 'KUBECONFIG_PATH="${DEVPOD_KUBECONFIG:-' in test_script


@pytest.mark.requirement("197")
def test_devpod_sync_parses_kubeconfig_with_kubectl_not_yaml_regex() -> None:
    """DevPod kubeconfig sync uses kubeconfig-aware parsing for the API server."""
    sync_script = Path("scripts/devpod-sync-kubeconfig.sh").read_text()

    assert "kubectl config view" in sync_script
    assert "urlparse" in sync_script
    assert "sed -nE" not in sync_script
    assert "config set-cluster" in sync_script


@pytest.mark.requirement("197")
def test_devpod_sync_waits_for_tunnel_readiness_before_returning() -> None:
    """DevPod kubeconfig sync must not return while the SSH tunnel is still starting."""
    sync_script = Path("scripts/devpod-sync-kubeconfig.sh").read_text()
    env_example = Path(".env.example").read_text()

    assert 'TUNNEL_TIMEOUT="${DEVPOD_TUNNEL_TIMEOUT:-120}"' in sync_script
    assert 'TUNNEL_INTERVAL="${DEVPOD_TUNNEL_INTERVAL:-2}"' in sync_script
    assert "while (( SECONDS < tunnel_deadline )); do" in sync_script
    assert 'kubectl --kubeconfig "${LOCAL_KUBECONFIG}" cluster-info' in sync_script
    assert 'kill -0 "${TUNNEL_PID}"' in sync_script
    assert "SSH tunnel process exited before Kubernetes became reachable" in sync_script
    assert "DEVPOD_TUNNEL_TIMEOUT=120" in env_example
