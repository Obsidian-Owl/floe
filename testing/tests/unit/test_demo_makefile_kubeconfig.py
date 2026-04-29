from pathlib import Path

import pytest

PORTABILITY_FILES = (
    Path(".mcp.json"),
    Path("Makefile"),
    Path("demo/README.md"),
    Path("TESTING.md"),
    Path("scripts/devpod-ensure-ready.sh"),
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

    assert 'LOCAL_KUBECONFIG="${DEVPOD_KUBECONFIG:-' in sync_script
    assert 'KUBECONFIG_PATH="${DEVPOD_KUBECONFIG:-' in ready_script
