"""Test base classes for K8s-native integration testing.

This module provides base classes that handle common integration test setup,
including service availability checks, namespace isolation, and resource cleanup.

Classes:
    IntegrationTestBase: Base class for K8s-native integration tests
    PluginTestBase: Base class for plugin compliance testing
    AdapterTestBase: Base class for adapter testing
    BaseCatalogPluginTests: Base class for CatalogPlugin ABC compliance testing
    BaseSecretsPluginTests: Base class for SecretsPlugin ABC compliance testing
    BaseIdentityPluginTests: Base class for IdentityPlugin ABC compliance testing

Example:
    from testing.base_classes import IntegrationTestBase

    class TestPolarisCatalog(IntegrationTestBase):
        required_services = [("polaris", 8181)]

        def test_create_namespace(self) -> None:
            namespace = self.generate_unique_namespace("test")
            # Test implementation...

Example (Plugin Compliance):
    from testing.base_classes import BaseCatalogPluginTests

    class TestMyPlugin(BaseCatalogPluginTests):
        @pytest.fixture
        def catalog_plugin(self):
            return MyPlugin(config={...})

Example (Secrets Plugin Compliance):
    from testing.base_classes import BaseSecretsPluginTests

    class TestK8sSecretsPlugin(BaseSecretsPluginTests):
        @pytest.fixture
        def secrets_plugin(self):
            return K8sSecretsPlugin(config={...})

Example (Identity Plugin Compliance):
    from testing.base_classes import BaseIdentityPluginTests

    class TestKeycloakPlugin(BaseIdentityPluginTests):
        @pytest.fixture
        def identity_plugin(self):
            return KeycloakIdentityPlugin(config={...})
"""

from __future__ import annotations

# Phase 4 exports - Base classes for integration testing
from testing.base_classes.adapter_test_base import AdapterTestBase
from testing.base_classes.base_catalog_plugin_tests import BaseCatalogPluginTests
from testing.base_classes.base_identity_plugin_tests import BaseIdentityPluginTests
from testing.base_classes.base_secrets_plugin_tests import BaseSecretsPluginTests
from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.base_classes.plugin_test_base import PluginTestBase

__all__ = [
    "AdapterTestBase",
    "BaseCatalogPluginTests",
    "BaseIdentityPluginTests",
    "BaseSecretsPluginTests",
    "IntegrationTestBase",
    "PluginTestBase",
]
