from pathlib import Path

import pytest


@pytest.mark.requirement("197")
def test_makefile_does_not_hardcode_floe_workspace_kubeconfig() -> None:
    """Demo and Devpod targets derive kubeconfig from DEVPOD_WORKSPACE."""
    text = Path("Makefile").read_text()

    assert "devpod-floe.config" not in text
    assert "DEVPOD_KUBECONFIG ?=" in text
    assert "devpod-$(DEVPOD_WORKSPACE).config" in text
