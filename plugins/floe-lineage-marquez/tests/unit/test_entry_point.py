"""Tests for entry point discovery of MarquezLineageBackendPlugin."""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest

from floe_lineage_marquez import MarquezLineageBackendPlugin


@pytest.mark.requirement("REQ-528")
def test_entry_point_registered() -> None:
    """Verify MarquezLineageBackendPlugin is discoverable via entry points."""
    eps = entry_points(group="floe.lineage_backends")
    ep_names = [ep.name for ep in eps]
    assert "marquez" in ep_names


@pytest.mark.requirement("REQ-528")
def test_entry_point_loads_correct_class() -> None:
    """Verify entry point loads MarquezLineageBackendPlugin."""
    eps = entry_points(group="floe.lineage_backends")
    marquez_ep = next(ep for ep in eps if ep.name == "marquez")
    plugin_class = marquez_ep.load()
    assert plugin_class is MarquezLineageBackendPlugin


@pytest.mark.requirement("REQ-528")
def test_entry_point_instantiation() -> None:
    """Verify plugin loaded via entry point can be instantiated."""
    eps = entry_points(group="floe.lineage_backends")
    marquez_ep = next(ep for ep in eps if ep.name == "marquez")
    plugin_class = marquez_ep.load()
    plugin = plugin_class()
    assert plugin.name == "marquez"
