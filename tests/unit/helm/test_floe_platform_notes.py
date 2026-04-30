"""Unit-level checks for floe-platform Helm NOTES output."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOTES_PATH = _REPO_ROOT / "charts" / "floe-platform" / "templates" / "NOTES.txt"
_SITE_CONFIG_PATH = _REPO_ROOT / "docs-site" / "site-config.mjs"


def _canonical_docs_site() -> str:
    """Read the canonical docs URL from docs-site configuration."""
    match = re.search(
        r"export const docsSite = '([^']+)';",
        _SITE_CONFIG_PATH.read_text(),
    )
    assert match is not None, "docs-site/site-config.mjs must export docsSite"
    return match.group(1)


def _render_notes() -> str:
    """Render Helm install output including NOTES."""
    result = subprocess.run(
        [
            "helm",
            "install",
            "floe",
            "./charts/floe-platform",
            "--dry-run",
            "--debug",
        ],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return f"{result.stdout}\n{result.stderr}"


@pytest.mark.requirement("alpha-docs")
def test_notes_docs_links_use_current_starlight_routes() -> None:
    """Helm NOTES must not emit stale public docs URLs."""
    content = _NOTES_PATH.read_text()
    docs_site = _canonical_docs_site()

    assert "floe.dev" not in content
    assert "/docs/deployment/helm" not in content
    assert "/docs/troubleshooting" not in content
    assert f"{docs_site}/" in content
    assert f"{docs_site}/guides/deployment/kubernetes-helm" in content
    assert f"{docs_site}/contributing/troubleshooting" in content


@pytest.mark.requirement("alpha-docs")
def test_rendered_notes_keep_troubleshooting_numbering_on_new_lines() -> None:
    """Rendered Helm NOTES must keep troubleshooting items separated from headings."""
    rendered_notes = _render_notes()
    docs_site = _canonical_docs_site()

    assert "issues:1." not in rendered_notes
    assert "issues:3." not in rendered_notes
    assert "check these common issues:\n\n1. Schema validation error" in rendered_notes
    assert f"{docs_site}/guides/deployment/kubernetes-helm" in rendered_notes
