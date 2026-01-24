"""Base class for plugin discovery tests.

This module provides reusable test cases for validating plugin entry point
discovery. Plugin test files can inherit from this class to get standard
discovery tests without duplicating code.

Task ID: T047
Phase: 7 - US7 (Reduce Test Duplication)
User Story: US7 - Reduce Test Duplication

Requirements tested:
    FR-004: All plugins MUST inherit from PluginMetadata
    FR-006: Plugin is discoverable via entry points
    FR-024: Entry point discovery mechanism

Example:
    from testing.base_classes.plugin_discovery_tests import BasePluginDiscoveryTests

    class TestMyPluginDiscovery(BasePluginDiscoveryTests):
        entry_point_group = "floe.computes"
        expected_name = "my_plugin"
        expected_module_prefix = "floe_my_plugin"
        expected_class_name = "MyPlugin"
"""

from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar

import pytest


class BasePluginDiscoveryTests(ABC):
    """Base class providing reusable plugin discovery test cases.

    Subclasses must define:
        - entry_point_group: The entry point group (e.g., "floe.computes")
        - expected_name: Expected plugin name in entry point
        - expected_module_prefix: Expected module prefix (e.g., "floe_compute_duckdb")
        - expected_class_name: Expected class name (e.g., "DuckDBComputePlugin")

    Optional class attributes:
        - expected_plugin_abc: The ABC the plugin should inherit from

    Provides standard tests for:
        - Entry point registration
        - Plugin loading
        - Metadata presence
        - ABC compliance

    Example:
        class TestDuckDBPluginDiscovery(BasePluginDiscoveryTests):
            entry_point_group = "floe.computes"
            expected_name = "duckdb"
            expected_module_prefix = "floe_compute_duckdb"
            expected_class_name = "DuckDBComputePlugin"
    """

    # Subclasses must define these
    entry_point_group: ClassVar[str]
    expected_name: ClassVar[str]
    expected_module_prefix: ClassVar[str]
    expected_class_name: ClassVar[str]

    # Optional: Subclasses can define the expected ABC
    expected_plugin_abc: ClassVar[type[Any] | None] = None

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create a plugin instance for testing.

        Override this method if your plugin requires configuration or
        arguments to instantiate. The default implementation assumes
        the plugin can be instantiated without arguments.

        Args:
            plugin_class: The plugin class loaded via entry point.

        Returns:
            An instantiated plugin object.

        Example:
            def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
                config = MyPluginConfig(...)
                return plugin_class(config=config)
        """
        return plugin_class()

    # =========================================================================
    # Entry Point Registration Tests
    # =========================================================================

    @pytest.mark.requirement("FR-024")
    def test_entry_point_is_registered(self) -> None:
        """Test plugin is registered under expected entry point group."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        names = [ep.name for ep in eps]

        assert self.expected_name in names, (
            f"Plugin '{self.expected_name}' not found in entry point group "
            f"'{self.entry_point_group}'. Found: {names}"
        )

    @pytest.mark.requirement("FR-024")
    def test_exactly_one_entry_point(self) -> None:
        """Test there is exactly one entry point with the expected name."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert (
            len(matching) == 1
        ), f"Expected exactly one '{self.expected_name}' entry point, found {len(matching)}"

    @pytest.mark.requirement("FR-024")
    def test_entry_point_module_path(self) -> None:
        """Test entry point references correct module."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        ep = matching[0]

        assert self.expected_module_prefix in ep.value, (
            f"Entry point value '{ep.value}' should contain module prefix "
            f"'{self.expected_module_prefix}'"
        )
        assert (
            self.expected_class_name in ep.value
        ), f"Entry point value '{ep.value}' should contain class name '{self.expected_class_name}'"

    # =========================================================================
    # Plugin Loading Tests
    # =========================================================================

    @pytest.mark.requirement("FR-006")
    def test_plugin_loads_successfully(self) -> None:
        """Test plugin class can be loaded via entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()

        assert plugin_class is not None
        assert plugin_class.__name__ == self.expected_class_name

    @pytest.mark.requirement("FR-006")
    def test_plugin_can_be_instantiated(self) -> None:
        """Test plugin can be instantiated after loading.

        Note: If your plugin requires configuration, override
        create_plugin_instance() to provide it.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        assert plugin is not None

    @pytest.mark.requirement("FR-006")
    def test_instantiated_plugin_has_correct_name(self) -> None:
        """Test instantiated plugin reports correct name."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        assert plugin.name == self.expected_name

    # =========================================================================
    # Metadata Tests
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_required_metadata_attributes(self) -> None:
        """Test plugin has all required PluginMetadata attributes."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        # Required PluginMetadata attributes
        assert hasattr(plugin, "name")
        assert hasattr(plugin, "version")
        assert hasattr(plugin, "floe_api_version")
        assert hasattr(plugin, "description")
        assert hasattr(plugin, "get_config_schema")

    @pytest.mark.requirement("FR-004")
    def test_plugin_metadata_values_not_none(self) -> None:
        """Test required plugin metadata values are not None.

        Note: get_config_schema() may return None for plugins that
        don't require additional configuration beyond ComputeConfig/etc.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        assert plugin.name is not None
        assert plugin.version is not None
        assert plugin.floe_api_version is not None
        assert plugin.description is not None
        # get_config_schema() may return None (valid for simple plugins)

    # =========================================================================
    # ABC Compliance Tests
    # =========================================================================

    @pytest.mark.requirement("FR-006")
    def test_plugin_inherits_from_expected_abc(self) -> None:
        """Test plugin inherits from expected ABC.

        This test only runs if expected_plugin_abc is defined.
        Subclasses that don't define expected_plugin_abc should override this test.
        """
        assert self.expected_plugin_abc is not None, (
            "expected_plugin_abc not defined for this test class. "
            "Either define expected_plugin_abc or override this test method."
        )

        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()

        assert issubclass(
            plugin_class, self.expected_plugin_abc
        ), f"{plugin_class.__name__} should inherit from {self.expected_plugin_abc.__name__}"

    @pytest.mark.requirement("FR-006")
    def test_plugin_instance_is_abc_instance(self) -> None:
        """Test plugin instance is instance of expected ABC.

        This test only runs if expected_plugin_abc is defined.
        Subclasses that don't define expected_plugin_abc should override this test.
        """
        assert self.expected_plugin_abc is not None, (
            "expected_plugin_abc not defined for this test class. "
            "Either define expected_plugin_abc or override this test method."
        )

        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        assert isinstance(
            plugin, self.expected_plugin_abc
        ), f"Plugin instance should be instance of {self.expected_plugin_abc.__name__}"

    # =========================================================================
    # Lifecycle Method Presence Tests
    # =========================================================================

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_lifecycle_methods(self) -> None:
        """Test plugin has required lifecycle methods."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        # Required lifecycle methods
        assert hasattr(plugin, "startup")
        assert hasattr(plugin, "shutdown")
        assert hasattr(plugin, "health_check")

        assert callable(plugin.startup)
        assert callable(plugin.shutdown)
        assert callable(plugin.health_check)


# Module exports
__all__ = ["BasePluginDiscoveryTests"]
