"""Consistency checks between plugin implementation truth and public docs."""

from __future__ import annotations

from pathlib import Path

from floe_core.plugin_types import PluginType

ROOT = Path(__file__).resolve().parents[3]


def test_plugin_catalog_mentions_current_plugin_category_count() -> None:
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()
    count = len(list(PluginType))

    assert f"{count} plugin categories" in text


def test_plugin_catalog_documents_required_table_columns() -> None:
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()

    assert "| Category | Entry point group | Current alpha status | Owner |" in text


def test_plugin_catalog_lists_every_plugin_type_entry_point() -> None:
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()

    for plugin_type in PluginType:
        assert plugin_type.name in text
        assert plugin_type.entry_point_group in text


def test_plugin_catalog_documents_lineage_alias() -> None:
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()

    assert "PluginType.LINEAGE" in text
    assert "LINEAGE_BACKEND" in text
    assert "not an extra category" in text


def test_owned_public_docs_do_not_use_stale_plugin_counts() -> None:
    count = len(list(PluginType))
    stale_phrases = {"11 plugin types", "12 plugin types", "13 plugin types"}
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
