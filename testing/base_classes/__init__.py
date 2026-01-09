"""Test base classes for K8s-native integration testing.

This module provides base classes that handle common integration test setup,
including service availability checks, namespace isolation, and resource cleanup.

Classes:
    IntegrationTestBase: Base class for K8s-native integration tests
    PluginTestBase: Base class for plugin compliance testing
    AdapterTestBase: Base class for adapter testing

Example:
    from testing.base_classes import IntegrationTestBase

    class TestPolarisCatalog(IntegrationTestBase):
        required_services = [("polaris", 8181)]

        def test_create_namespace(self) -> None:
            namespace = self.generate_unique_namespace("test")
            # Test implementation...
"""

from __future__ import annotations

# Exports will be added as classes are implemented in Phase 4
__all__: list[str] = []
