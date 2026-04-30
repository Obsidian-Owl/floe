"""Consistency checks between plugin implementation truth and public docs."""

from __future__ import annotations

from pathlib import Path

import pytest
from floe_core.plugin_types import PluginType

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.requirement("alpha-docs")
def test_plugin_catalog_mentions_current_plugin_category_count() -> None:
    """Plugin catalog states the category count derived from the PluginType enum."""
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()
    count = len(list(PluginType))

    assert f"{count} plugin categories" in text


@pytest.mark.requirement("alpha-docs")
def test_plugin_catalog_documents_required_table_columns() -> None:
    """Plugin catalog exposes the columns users need to understand ownership."""
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()

    assert "| Category | Entry point group | Current alpha status | Owner |" in text


@pytest.mark.requirement("alpha-docs")
def test_plugin_catalog_lists_every_plugin_type_entry_point() -> None:
    """Plugin catalog lists every implemented plugin type and entry point group."""
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()

    for plugin_type in PluginType:
        assert plugin_type.name in text
        assert plugin_type.entry_point_group in text


@pytest.mark.requirement("alpha-docs")
def test_plugin_catalog_documents_lineage_alias() -> None:
    """Plugin catalog explains that LINEAGE is an enum alias, not another category."""
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()

    assert "PluginType.LINEAGE" in text
    assert "LINEAGE_BACKEND" in text
    assert "not an extra category" in text


@pytest.mark.requirement("alpha-docs")
def test_owned_public_docs_do_not_use_stale_plugin_counts() -> None:
    """Owned public docs avoid stale plugin type counts that confuse users."""
    count = len(list(PluginType))
    stale_phrases = {
        "11 plugin interfaces",
        "11 plugin types",
        "12 plugin interfaces",
        "12 plugin types",
        "13 plugin interfaces",
        "13 plugin types",
    }
    paths = [
        ROOT / "README.md",
        ROOT / "docs" / "architecture" / "plugin-system" / "index.md",
        ROOT / "docs" / "architecture" / "interfaces" / "index.md",
        ROOT / "docs" / "architecture" / "ARCHITECTURE-SUMMARY.md",
        ROOT / "docs" / "contracts" / "glossary.md",
        ROOT / "docs" / "reference" / "plugin-catalog.md",
    ]

    for path in paths:
        text = path.read_text()
        for phrase in stale_phrases:
            assert phrase not in text, (
                f"{path} uses stale phrase {phrase!r}; "
                f"use {count} plugin categories or avoid counts"
            )
