"""Unit-level checks for floe-platform Helm NOTES output."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOTES_PATH = _REPO_ROOT / "charts" / "floe-platform" / "templates" / "NOTES.txt"


@pytest.mark.requirement("alpha-docs")
def test_notes_docs_links_use_current_starlight_routes() -> None:
    """Helm NOTES must not emit stale public docs URLs."""
    content = _NOTES_PATH.read_text()

    assert "/docs/deployment/helm" not in content
    assert "/docs/troubleshooting" not in content
    assert "https://floe.dev/guides/deployment/kubernetes-helm" in content
    assert "https://floe.dev/contributing/troubleshooting" in content
