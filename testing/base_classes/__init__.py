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
    BasePluginMetadataTests: Base class for plugin metadata validation tests
    BasePluginLifecycleTests: Base class for plugin lifecycle hook tests
    BasePluginDiscoveryTests: Base class for plugin entry point discovery tests
    GoldenTestCase: Base class for golden test suites
    GoldenFixture: Represents a golden test fixture with metadata

Functions:
    capture_golden: Capture function output as a golden fixture
    assert_golden_match: Assert output matches a golden fixture
    golden_test: Decorator for creating golden tests

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
from testing.base_classes.base_secrets_plugin_tests import (
    AuditLogCapture,
    BaseSecretsPluginTests,
)

# Golden test utilities for behavior-preserving refactoring
from testing.base_classes.golden_test_utils import (
    GoldenFixture,
    GoldenTestCase,
    assert_golden_match,
    capture_golden,
    golden_test,
)
from testing.base_classes.integration_test_base import IntegrationTestBase

# Plugin metadata, lifecycle, and discovery validation base classes
from testing.base_classes.plugin_discovery_tests import BasePluginDiscoveryTests
from testing.base_classes.plugin_lifecycle_tests import BasePluginLifecycleTests
from testing.base_classes.plugin_metadata_tests import BasePluginMetadataTests
from testing.base_classes.plugin_test_base import PluginTestBase

__all__ = [
    "AdapterTestBase",
    "AuditLogCapture",
    "BaseCatalogPluginTests",
    "BaseIdentityPluginTests",
    "BasePluginDiscoveryTests",
    "BasePluginLifecycleTests",
    "BasePluginMetadataTests",
    "BaseSecretsPluginTests",
    "GoldenFixture",
    "GoldenTestCase",
    "IntegrationTestBase",
    "PluginTestBase",
    "assert_golden_match",
    "capture_golden",
    "golden_test",
]
