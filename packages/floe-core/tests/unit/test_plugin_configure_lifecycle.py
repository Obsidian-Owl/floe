"""Unit tests for PluginMetadata configure() lifecycle.

Tests the configure(), is_configured property, and _config initialization
added to the PluginMetadata ABC to close the unsafe config window (ARC-001).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from floe_core.plugin_metadata import PluginMetadata


class SampleConfig(BaseModel):
    """Test config model."""

    host: str = "localhost"
    port: int = 8080


class ConcretePlugin(PluginMetadata):
    """Minimal concrete plugin for testing ABC lifecycle."""

    @property
    def name(self) -> str:
        return "test-concrete"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def get_config_schema(self) -> type[BaseModel]:
        return SampleConfig


@pytest.mark.requirement("ARC-001")
def test_freshly_instantiated_plugin_is_not_configured() -> None:
    """Test that a new plugin starts in unconfigured state.

    AC-1 condition 4: A freshly instantiated plugin has is_configured == False.
    """
    plugin = ConcretePlugin()
    assert plugin.is_configured is False


@pytest.mark.requirement("ARC-001")
def test_plugin_has_config_none_after_init() -> None:
    """Test that _config is None after instantiation.

    AC-1 condition 1: PluginMetadata.__init__ sets self._config = None.
    """
    plugin = ConcretePlugin()
    assert plugin._config is None


@pytest.mark.requirement("ARC-001")
def test_configure_sets_config() -> None:
    """Test that configure() sets _config and is_configured.

    AC-1 condition 5: After plugin.configure(SomeConfig(...)), is_configured == True.
    """
    plugin = ConcretePlugin()
    config = SampleConfig(host="example.com", port=9090)
    plugin.configure(config)
    assert plugin.is_configured is True
    assert plugin._config is config


@pytest.mark.requirement("ARC-001")
def test_configure_none_clears_config() -> None:
    """Test that configure(None) resets to unconfigured state.

    AC-1 condition 6: After plugin.configure(None), is_configured == False.
    """
    plugin = ConcretePlugin()
    config = SampleConfig()
    plugin.configure(config)
    assert plugin.is_configured is True

    plugin.configure(None)
    assert plugin.is_configured is False
    assert plugin._config is None


@pytest.mark.requirement("ARC-001")
def test_configure_is_concrete_not_abstract() -> None:
    """Test that configure() is a concrete method, not abstract.

    AC-1 condition 2: configure() is a concrete method.
    """
    plugin = ConcretePlugin()
    # Should be callable without override
    plugin.configure(SampleConfig())
    assert plugin.is_configured is True


@pytest.mark.requirement("ARC-001")
def test_is_configured_returns_bool() -> None:
    """Test that is_configured is a property returning bool.

    AC-1 condition 3: is_configured is a property that returns bool.
    """
    plugin = ConcretePlugin()
    result = plugin.is_configured
    assert isinstance(result, bool)
    assert result is False

    plugin.configure(SampleConfig())
    result = plugin.is_configured
    assert isinstance(result, bool)
    assert result is True


@pytest.mark.requirement("ARC-001")
def test_configure_overwrites_previous_config() -> None:
    """Test that calling configure() twice uses last-write-wins.

    Validates the precedence rule from AC-3: configure() always wins.
    """
    plugin = ConcretePlugin()
    config1 = SampleConfig(host="first")
    config2 = SampleConfig(host="second")

    plugin.configure(config1)
    assert plugin._config is config1

    plugin.configure(config2)
    assert plugin._config is config2
