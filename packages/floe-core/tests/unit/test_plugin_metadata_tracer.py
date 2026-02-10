"""Unit tests for PluginMetadata tracer_name property.

Tests the optional tracer_name property used by the instrumentation audit system.
"""

from __future__ import annotations

import pytest

from floe_core.plugin_metadata import PluginMetadata


class UninstrumentedPlugin(PluginMetadata):
    """Test plugin without tracer_name override."""

    @property
    def name(self) -> str:
        return "test-uninstrumented"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"


class InstrumentedPlugin(PluginMetadata):
    """Test plugin with tracer_name override."""

    @property
    def name(self) -> str:
        return "test-instrumented"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    @property
    def tracer_name(self) -> str | None:
        return "floe.test.instrumented"


class AnotherInstrumentedPlugin(PluginMetadata):
    """Another test plugin with different tracer_name."""

    @property
    def name(self) -> str:
        return "test-another"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    @property
    def tracer_name(self) -> str | None:
        return "floe.test.another"


@pytest.mark.requirement("6C-FR-015")
def test_default_tracer_name_returns_none() -> None:
    """Test that default tracer_name returns None.

    A concrete PluginMetadata subclass without tracer_name override
    should return None, indicating no instrumentation.
    """
    plugin = UninstrumentedPlugin()
    assert plugin.tracer_name is None


@pytest.mark.requirement("6C-FR-015")
def test_tracer_name_override_returns_correct_name() -> None:
    """Test that tracer_name override returns expected string.

    A subclass that overrides tracer_name should return the string
    configured by the plugin.
    """
    plugin = InstrumentedPlugin()
    assert plugin.tracer_name == "floe.test.instrumented"


@pytest.mark.requirement("6C-FR-015")
def test_multiple_plugins_unique_tracer_names() -> None:
    """Test that different plugins have distinct tracer_names.

    Two instrumented plugins with different tracer_names should
    return their respective names independently.
    """
    plugin1 = InstrumentedPlugin()
    plugin2 = AnotherInstrumentedPlugin()

    assert plugin1.tracer_name == "floe.test.instrumented"
    assert plugin2.tracer_name == "floe.test.another"
    assert plugin1.tracer_name != plugin2.tracer_name
