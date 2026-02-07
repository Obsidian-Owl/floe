"""Integration tests for Cube semantic layer plugin discovery.

Tests validate that the CubeSemanticPlugin is correctly registered via
entry points and discoverable through the floe plugin system.

Requirements Covered:
    - SC-001: SemanticLayerPlugin ABC defines complete interface
    - SC-003: Plugin is discoverable via entry points
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from floe_core.plugins.semantic import SemanticLayerPlugin
from testing.base_classes.plugin_discovery_tests import BasePluginDiscoveryTests

from floe_semantic_cube.config import CubeSemanticConfig


@pytest.mark.requirement("SC-001")
@pytest.mark.requirement("SC-003")
class TestCubeSemanticPluginDiscovery(BasePluginDiscoveryTests):
    """Integration tests for Cube plugin entry point discovery.

    Inherits standard discovery tests from BasePluginDiscoveryTests
    and configures them for the Cube semantic layer plugin.
    """

    entry_point_group: ClassVar[str] = "floe.semantic_layers"
    expected_name: ClassVar[str] = "cube"
    expected_module_prefix: ClassVar[str] = "floe_semantic_cube"
    expected_class_name: ClassVar[str] = "CubeSemanticPlugin"
    expected_plugin_abc: ClassVar[type[Any] | None] = SemanticLayerPlugin

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create a CubeSemanticPlugin instance for discovery testing.

        Args:
            plugin_class: The plugin class loaded via entry point.

        Returns:
            Instantiated CubeSemanticPlugin with test configuration.
        """
        config = CubeSemanticConfig(
            server_url="http://localhost:4000",
            api_secret="test-secret",
        )
        return plugin_class(config=config)
