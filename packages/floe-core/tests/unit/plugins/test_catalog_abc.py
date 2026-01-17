"""Unit tests for CatalogPlugin ABC in floe-core.

These tests verify CatalogPlugin ABC instantiation and behavior at the
package level. Package-specific tests focus on internal implementation
details that don't affect external consumers.

For cross-package contract tests, see tests/contract/test_catalog_plugin_abc.py

Requirements Covered:
- FR-001: CatalogPlugin ABC with connect() method
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core import CatalogPlugin, HealthState, HealthStatus
from floe_core.plugins.catalog import Catalog


class TestCatalogPluginABCInstantiation:
    """Unit tests for CatalogPlugin ABC instantiation."""

    @pytest.mark.requirement("FR-001")
    def test_cannot_instantiate_catalog_plugin_directly(self) -> None:
        """Verify CatalogPlugin cannot be instantiated directly.

        The ABC enforces that concrete implementations must be created.
        """
        with pytest.raises(TypeError, match="abstract"):
            CatalogPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-001")
    def test_mock_catalog_plugin_instantiation(self) -> None:
        """Verify a complete mock implementation can be instantiated."""

        class MockCatalogPlugin(CatalogPlugin):
            """Complete mock implementation for testing."""

            @property
            def name(self) -> str:
                return "mock-catalog"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def connect(self, config: dict[str, Any]) -> Catalog:
                _ = config
                # Return a mock that satisfies Catalog protocol
                return _create_mock_catalog()

            def create_namespace(
                self,
                namespace: str,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = namespace, properties

            def list_namespaces(self, parent: str | None = None) -> list[str]:
                _ = parent
                return ["bronze", "silver", "gold"]

            def delete_namespace(self, namespace: str) -> None:
                _ = namespace

            def create_table(
                self,
                identifier: str,
                schema: dict[str, Any],
                location: str | None = None,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = identifier, schema, location, properties

            def list_tables(self, namespace: str) -> list[str]:
                _ = namespace
                return ["table1", "table2"]

            def drop_table(self, identifier: str, purge: bool = False) -> None:
                _ = identifier, purge

            def vend_credentials(
                self,
                table_path: str,
                operations: list[str],
            ) -> dict[str, Any]:
                _ = table_path, operations
                return {"access_key": "mock", "secret_key": "mock"}

        plugin = MockCatalogPlugin()

        assert plugin.name == "mock-catalog"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "1.0"


class TestCatalogPluginDefaultImplementations:
    """Unit tests for CatalogPlugin default method implementations."""

    @pytest.mark.requirement("FR-001")
    def test_health_check_default_returns_unhealthy(self) -> None:
        """Verify default health_check() returns unhealthy status.

        The default implementation returns unhealthy to signal that
        concrete implementations should override with real health checks.
        """

        class MinimalCatalogPlugin(CatalogPlugin):
            """Plugin with only required methods to test defaults."""

            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def connect(self, config: dict[str, Any]) -> Catalog:
                _ = config
                return _create_mock_catalog()

            def create_namespace(
                self,
                namespace: str,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = namespace, properties

            def list_namespaces(self, parent: str | None = None) -> list[str]:
                _ = parent
                return []

            def delete_namespace(self, namespace: str) -> None:
                _ = namespace

            def create_table(
                self,
                identifier: str,
                schema: dict[str, Any],
                location: str | None = None,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = identifier, schema, location, properties

            def list_tables(self, namespace: str) -> list[str]:
                _ = namespace
                return []

            def drop_table(self, identifier: str, purge: bool = False) -> None:
                _ = identifier, purge

            def vend_credentials(
                self,
                table_path: str,
                operations: list[str],
            ) -> dict[str, Any]:
                _ = table_path, operations
                return {}

        plugin = MinimalCatalogPlugin()
        health = plugin.health_check()

        assert isinstance(health, HealthStatus)
        assert health.state == HealthState.UNHEALTHY
        assert "not implemented" in health.message.lower()

    @pytest.mark.requirement("FR-001")
    def test_health_check_accepts_timeout_parameter(self) -> None:
        """Verify health_check() accepts timeout parameter."""

        class MinimalCatalogPlugin(CatalogPlugin):
            """Plugin with only required methods."""

            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def connect(self, config: dict[str, Any]) -> Catalog:
                _ = config
                return _create_mock_catalog()

            def create_namespace(
                self,
                namespace: str,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = namespace, properties

            def list_namespaces(self, parent: str | None = None) -> list[str]:
                _ = parent
                return []

            def delete_namespace(self, namespace: str) -> None:
                _ = namespace

            def create_table(
                self,
                identifier: str,
                schema: dict[str, Any],
                location: str | None = None,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = identifier, schema, location, properties

            def list_tables(self, namespace: str) -> list[str]:
                _ = namespace
                return []

            def drop_table(self, identifier: str, purge: bool = False) -> None:
                _ = identifier, purge

            def vend_credentials(
                self,
                table_path: str,
                operations: list[str],
            ) -> dict[str, Any]:
                _ = table_path, operations
                return {}

        plugin = MinimalCatalogPlugin()

        # Custom timeout
        health = plugin.health_check(timeout=5.0)
        assert health.details is not None
        assert health.details.get("timeout") == pytest.approx(5.0)

        # Default timeout
        health = plugin.health_check()
        assert health.details is not None
        assert health.details.get("timeout") == pytest.approx(1.0)


class TestCatalogPluginInheritance:
    """Unit tests for CatalogPlugin inheritance chain."""

    @pytest.mark.requirement("FR-001")
    def test_inherits_from_plugin_metadata(self) -> None:
        """Verify CatalogPlugin inherits from PluginMetadata."""
        from floe_core import PluginMetadata

        assert issubclass(CatalogPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-001")
    def test_inherited_lifecycle_methods_work(self) -> None:
        """Verify inherited lifecycle methods (startup, shutdown) work."""

        class LifecycleTestPlugin(CatalogPlugin):
            """Plugin to test lifecycle methods."""

            startup_called = False
            shutdown_called = False

            @property
            def name(self) -> str:
                return "lifecycle"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def connect(self, config: dict[str, Any]) -> Catalog:
                _ = config
                return _create_mock_catalog()

            def create_namespace(
                self,
                namespace: str,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = namespace, properties

            def list_namespaces(self, parent: str | None = None) -> list[str]:
                _ = parent
                return []

            def delete_namespace(self, namespace: str) -> None:
                _ = namespace

            def create_table(
                self,
                identifier: str,
                schema: dict[str, Any],
                location: str | None = None,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = identifier, schema, location, properties

            def list_tables(self, namespace: str) -> list[str]:
                _ = namespace
                return []

            def drop_table(self, identifier: str, purge: bool = False) -> None:
                _ = identifier, purge

            def vend_credentials(
                self,
                table_path: str,
                operations: list[str],
            ) -> dict[str, Any]:
                _ = table_path, operations
                return {}

            def startup(self) -> None:
                LifecycleTestPlugin.startup_called = True

            def shutdown(self) -> None:
                LifecycleTestPlugin.shutdown_called = True

        plugin = LifecycleTestPlugin()

        # Lifecycle methods should be callable
        plugin.startup()
        assert LifecycleTestPlugin.startup_called

        plugin.shutdown()
        assert LifecycleTestPlugin.shutdown_called


class TestCatalogPluginMethods:
    """Unit tests for CatalogPlugin method behaviors."""

    @pytest.mark.requirement("FR-001")
    def test_connect_returns_catalog_protocol(self) -> None:
        """Verify connect() returns object satisfying Catalog protocol."""

        class CatalogTestPlugin(CatalogPlugin):
            """Plugin that returns a Catalog-compatible object."""

            @property
            def name(self) -> str:
                return "catalog-test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def connect(self, config: dict[str, Any]) -> Catalog:
                _ = config
                return _create_mock_catalog()

            def create_namespace(
                self,
                namespace: str,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = namespace, properties

            def list_namespaces(self, parent: str | None = None) -> list[str]:
                _ = parent
                return []

            def delete_namespace(self, namespace: str) -> None:
                _ = namespace

            def create_table(
                self,
                identifier: str,
                schema: dict[str, Any],
                location: str | None = None,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = identifier, schema, location, properties

            def list_tables(self, namespace: str) -> list[str]:
                _ = namespace
                return []

            def drop_table(self, identifier: str, purge: bool = False) -> None:
                _ = identifier, purge

            def vend_credentials(
                self,
                table_path: str,
                operations: list[str],
            ) -> dict[str, Any]:
                _ = table_path, operations
                return {}

        plugin = CatalogTestPlugin()
        catalog = plugin.connect({"uri": "http://test"})

        # Verify it's a Catalog (runtime_checkable protocol)
        assert isinstance(catalog, Catalog)
        assert hasattr(catalog, "list_namespaces")
        assert hasattr(catalog, "list_tables")
        assert hasattr(catalog, "load_table")


def _create_mock_catalog() -> Catalog:
    """Create a mock object that satisfies the Catalog protocol.

    Returns:
        An object that implements the Catalog protocol methods.
    """

    class MockCatalog:
        """Mock catalog for testing."""

        def list_namespaces(self) -> list[tuple[str, ...]]:
            return [("bronze",), ("silver",), ("gold",)]

        def list_tables(self, namespace: str) -> list[str]:
            _ = namespace
            return ["table1", "table2"]

        def load_table(self, identifier: str) -> Any:
            _ = identifier
            return {"mock": "table"}

    return MockCatalog()
