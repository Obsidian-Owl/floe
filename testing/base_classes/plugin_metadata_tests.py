"""Base class for plugin metadata tests.

This module provides reusable test cases for validating plugin metadata.
Plugin test files can inherit from this class to get standard metadata
validation tests without duplicating code.

Task ID: T045
Phase: 7 - US7 (Reduce Test Duplication)
User Story: US7 - Reduce Test Duplication

Requirements tested:
    CR-001: Plugin declares floe_api_version
    FR-004: Plugin metadata (name, version, floe_api_version)

Example:
    from testing.base_classes.plugin_metadata_tests import BasePluginMetadataTests

    class TestMyPluginMetadata(BasePluginMetadataTests):
        plugin_class = MyPlugin
        expected_name = "my_plugin"
        expected_entry_point_group = "floe.computes"

        @pytest.fixture
        def plugin_instance(self):
            return MyPlugin(config=MyPluginConfig())
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

if TYPE_CHECKING:
    pass


class BasePluginMetadataTests(ABC):
    """Base class providing reusable plugin metadata test cases.

    Subclasses must define:
        - plugin_class: The plugin class being tested
        - expected_name: Expected plugin name
        - expected_entry_point_group: Entry point group (e.g., "floe.computes")
        - plugin_instance fixture: Returns an instantiated plugin for testing

    Provides standard tests for:
        - Plugin name validation
        - Version format (semver)
        - floe_api_version presence
        - Description validation
        - Entry point registration
        - Config schema validation

    Example:
        class TestDuckDBPluginMetadata(BasePluginMetadataTests):
            plugin_class = DuckDBComputePlugin
            expected_name = "duckdb"
            expected_entry_point_group = "floe.computes"

            @pytest.fixture
            def plugin_instance(self) -> DuckDBComputePlugin:
                return DuckDBComputePlugin()
    """

    # Subclasses must define these
    plugin_class: ClassVar[type[Any]]
    expected_name: ClassVar[str]
    expected_entry_point_group: ClassVar[str]

    # Optional: Override in subclass if different
    expected_floe_api_version: ClassVar[str] = "1.0"

    # Semver pattern for version validation
    SEMVER_PATTERN: ClassVar[str] = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"

    @pytest.fixture
    @abstractmethod
    def plugin_instance(self) -> Any:
        """Return an instantiated plugin for testing.

        Subclasses MUST implement this fixture to provide a configured
        plugin instance.

        Returns:
            An instantiated plugin object.
        """
        ...

    # =========================================================================
    # Name Tests
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_name_property(self, plugin_instance: Any) -> None:
        """Test plugin has a name property."""
        assert hasattr(plugin_instance, "name")
        assert isinstance(plugin_instance.name, str)
        assert len(plugin_instance.name) > 0

    @pytest.mark.requirement("FR-004")
    def test_plugin_name_matches_expected(self, plugin_instance: Any) -> None:
        """Test plugin name matches expected value."""
        assert plugin_instance.name == self.expected_name

    # =========================================================================
    # Version Tests
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_version_property(self, plugin_instance: Any) -> None:
        """Test plugin has a version property."""
        assert hasattr(plugin_instance, "version")
        assert isinstance(plugin_instance.version, str)
        assert len(plugin_instance.version) > 0

    @pytest.mark.requirement("FR-004")
    def test_plugin_version_is_semver(self, plugin_instance: Any) -> None:
        """Test plugin version follows semantic versioning format."""
        version = plugin_instance.version
        assert re.match(self.SEMVER_PATTERN, version), (
            f"Version '{version}' does not follow semver format (X.Y.Z)"
        )

    # =========================================================================
    # API Version Tests
    # =========================================================================

    @pytest.mark.requirement("CR-001")
    def test_plugin_has_floe_api_version(self, plugin_instance: Any) -> None:
        """Test plugin declares floe_api_version."""
        assert hasattr(plugin_instance, "floe_api_version")
        assert isinstance(plugin_instance.floe_api_version, str)
        assert len(plugin_instance.floe_api_version) > 0

    @pytest.mark.requirement("CR-001")
    def test_floe_api_version_matches_expected(self, plugin_instance: Any) -> None:
        """Test floe_api_version matches expected value."""
        assert plugin_instance.floe_api_version == self.expected_floe_api_version

    # =========================================================================
    # Description Tests
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_description(self, plugin_instance: Any) -> None:
        """Test plugin has a description property."""
        assert hasattr(plugin_instance, "description")
        assert isinstance(plugin_instance.description, str)

    @pytest.mark.requirement("FR-004")
    def test_plugin_description_not_empty(self, plugin_instance: Any) -> None:
        """Test plugin description is not empty."""
        assert len(plugin_instance.description) > 0

    # =========================================================================
    # Config Schema Tests
    # =========================================================================

    @pytest.mark.requirement("CR-003")
    def test_plugin_has_get_config_schema(self, plugin_instance: Any) -> None:
        """Test plugin has get_config_schema method."""
        assert hasattr(plugin_instance, "get_config_schema")
        assert callable(plugin_instance.get_config_schema)

    @pytest.mark.requirement("CR-003")
    def test_config_schema_returns_type(self, plugin_instance: Any) -> None:
        """Test get_config_schema returns a type (class)."""
        schema = plugin_instance.get_config_schema()
        assert schema is not None
        assert isinstance(schema, type)

    # =========================================================================
    # Entry Point Tests
    # =========================================================================

    @pytest.mark.requirement("FR-006")
    def test_plugin_entry_point_registered(self) -> None:
        """Test plugin is registered via entry points."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.expected_entry_point_group)
        plugin_names = [ep.name for ep in eps]

        assert self.expected_name in plugin_names, (
            f"Plugin '{self.expected_name}' not found in entry point group "
            f"'{self.expected_entry_point_group}'. Found: {plugin_names}"
        )

    @pytest.mark.requirement("FR-006")
    def test_plugin_loadable_via_entry_point(self) -> None:
        """Test plugin can be loaded via entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.expected_entry_point_group)
        matching_eps = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching_eps) == 1, (
            f"Expected exactly one entry point for '{self.expected_name}'"
        )

        # Load the plugin class
        loaded_class = matching_eps[0].load()

        # Verify it's the expected class
        assert loaded_class is self.plugin_class

    # =========================================================================
    # Lifecycle Method Tests
    # =========================================================================

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_startup_method(self, plugin_instance: Any) -> None:
        """Test plugin has startup() lifecycle method."""
        assert hasattr(plugin_instance, "startup")
        assert callable(plugin_instance.startup)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_shutdown_method(self, plugin_instance: Any) -> None:
        """Test plugin has shutdown() lifecycle method."""
        assert hasattr(plugin_instance, "shutdown")
        assert callable(plugin_instance.shutdown)


# Module exports
__all__ = ["BasePluginMetadataTests"]
