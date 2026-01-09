"""Plugin test base class for floe plugin testing.

This module provides the PluginTestBase class for testing floe plugins.
It extends IntegrationTestBase with plugin-specific functionality.

Example:
    from testing.base_classes.plugin_test_base import PluginTestBase

    class TestComputePlugin(PluginTestBase):
        plugin_type = "compute"
        plugin_name = "duckdb"

        def test_plugin_registration(self) -> None:
            assert self.plugin_is_registered()
"""

from __future__ import annotations

from typing import ClassVar

from testing.base_classes.integration_test_base import IntegrationTestBase


class PluginTestBase(IntegrationTestBase):
    """Base class for plugin integration tests.

    Extends IntegrationTestBase with plugin-specific functionality:
    - Plugin discovery verification
    - Plugin metadata validation
    - Plugin lifecycle testing helpers

    Class Attributes:
        plugin_type: The type of plugin being tested (e.g., "compute", "catalog").
        plugin_name: The name of the specific plugin (e.g., "duckdb", "polaris").

    Usage:
        class TestDuckDBPlugin(PluginTestBase):
            plugin_type = "compute"
            plugin_name = "duckdb"

            @pytest.mark.requirement("plugin-FR-001")
            def test_plugin_discovery(self) -> None:
                assert self.plugin_is_registered()
                metadata = self.get_plugin_metadata()
                assert metadata.name == "duckdb"
    """

    plugin_type: ClassVar[str] = ""
    plugin_name: ClassVar[str] = ""

    def setup_method(self) -> None:
        """Set up plugin test fixtures.

        Extends parent setup to verify plugin configuration is valid.
        """
        super().setup_method()
        # Validate plugin configuration
        if not self.plugin_type:
            raise ValueError(
                f"{self.__class__.__name__} must define plugin_type class attribute"
            )
        if not self.plugin_name:
            raise ValueError(
                f"{self.__class__.__name__} must define plugin_name class attribute"
            )

    def plugin_is_registered(self) -> bool:
        """Check if the plugin is registered in the plugin registry.

        Returns:
            True if plugin is registered, False otherwise.

        Note:
            This is a placeholder implementation. Override or implement
            once the plugin registry is available.
        """
        # Placeholder - will use actual plugin registry when available
        return True

    def get_plugin_metadata(self) -> dict[str, str]:
        """Get metadata for the plugin being tested.

        Returns:
            Dictionary with plugin metadata (name, version, etc.).

        Note:
            This is a placeholder implementation. Override or implement
            once the plugin registry is available.
        """
        # Placeholder - will use actual plugin registry when available
        return {
            "name": self.plugin_name,
            "type": self.plugin_type,
            "version": "0.0.0",
        }

    def get_entry_point_group(self) -> str:
        """Get the entry point group for this plugin type.

        Returns:
            Entry point group string (e.g., "floe.computes").
        """
        return f"floe.{self.plugin_type}s"


# Module exports
__all__ = ["PluginTestBase"]
