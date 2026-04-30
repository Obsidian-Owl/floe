from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.mark.requirement("alpha-docs")
def test_docs_site_config_sets_github_pages_base_path() -> None:
    """Astro config uses the repository subpath as the deployment base."""
    astro_config = Path("docs-site/astro.config.mjs").read_text()
    site_config = Path("docs-site/site-config.mjs").read_text()
    site_path = re.search(
        r"docsSite\s*=\s*['\"]https://obsidian-owl\.github\.io(?P<path>/floe)['\"]",
        site_config,
    )

    assert site_path is not None
    assert "base: docsBase" in astro_config
    assert "site: docsSite" in astro_config
    assert "docsBase = new URL(docsSite).pathname" in site_config
