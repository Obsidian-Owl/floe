"""Contract tests for CatalogPlugin ABC compliance.

These tests validate that the CatalogPlugin abstract base class defines
the correct interface for catalog plugins. They ensure:
- All required abstract methods are defined with correct signatures
- Concrete implementations must implement all abstract methods
- Type hints are present and accurate
- Default implementations work correctly

This is a contract test (tests/contract/) because it validates the interface
that plugin packages depend on. Changes to CatalogPlugin ABC can break
downstream implementations.

Requirements Covered:
- FR-001: CatalogPlugin ABC with connect() method returning PyIceberg Catalog
- FR-002: Namespace management methods (create, list, delete)
- FR-003: Table operation methods (create, list, drop)
- FR-004: Plugin metadata requirements (name, version, floe_api_version)
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


class TestCatalogPluginABCDefinition:
    """Contract tests for CatalogPlugin ABC structure.

    These tests verify that CatalogPlugin defines the correct abstract
    methods with proper signatures.
    """

    @pytest.mark.requirement("FR-001")
    def test_catalog_plugin_is_abstract_class(self) -> None:
        """Verify CatalogPlugin is an abstract base class.

        CatalogPlugin must be abstract to enforce method implementation
        in concrete plugins.
        """
        from floe_core.plugins import CatalogPlugin

        # Must be a class
        assert isinstance(CatalogPlugin, type)

        # Must inherit from ABC (via PluginMetadata)
        assert issubclass(CatalogPlugin, ABC)

    @pytest.mark.requirement("FR-001")
    def test_connect_method_is_abstract(self) -> None:
        """Verify connect() is an abstract method with correct signature.

        FR-001: CatalogPlugin must define connect() that returns a
        PyIceberg-compatible Catalog instance.
        """
        from floe_core.plugins import CatalogPlugin

        # Method must exist
        assert hasattr(CatalogPlugin, "connect")

        # Must be abstract
        method = CatalogPlugin.connect
        assert getattr(method, "__isabstractmethod__", False), "connect() must be abstract"

        # Check signature
        sig = inspect.signature(CatalogPlugin.connect)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "config" in params

    @pytest.mark.requirement("FR-002")
    def test_create_namespace_method_is_abstract(self) -> None:
        """Verify create_namespace() is an abstract method.

        FR-002: CatalogPlugin must define create_namespace() for
        namespace management.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "create_namespace")

        method = CatalogPlugin.create_namespace
        assert getattr(method, "__isabstractmethod__", False), "create_namespace() must be abstract"

        sig = inspect.signature(CatalogPlugin.create_namespace)
        params = list(sig.parameters.keys())
        assert "namespace" in params
        assert "properties" in params

    @pytest.mark.requirement("FR-002")
    def test_list_namespaces_method_is_abstract(self) -> None:
        """Verify list_namespaces() is an abstract method.

        FR-002: CatalogPlugin must define list_namespaces() for
        namespace listing with optional parent filter.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "list_namespaces")

        method = CatalogPlugin.list_namespaces
        assert getattr(method, "__isabstractmethod__", False), "list_namespaces() must be abstract"

        sig = inspect.signature(CatalogPlugin.list_namespaces)
        params = list(sig.parameters.keys())
        assert "parent" in params

    @pytest.mark.requirement("FR-002")
    def test_delete_namespace_method_is_abstract(self) -> None:
        """Verify delete_namespace() is an abstract method.

        FR-002: CatalogPlugin must define delete_namespace() for
        namespace deletion.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "delete_namespace")

        method = CatalogPlugin.delete_namespace
        assert getattr(method, "__isabstractmethod__", False), "delete_namespace() must be abstract"

        sig = inspect.signature(CatalogPlugin.delete_namespace)
        params = list(sig.parameters.keys())
        assert "namespace" in params

    @pytest.mark.requirement("FR-003")
    def test_create_table_method_is_abstract(self) -> None:
        """Verify create_table() is an abstract method.

        FR-003: CatalogPlugin must define create_table() for
        table creation.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "create_table")

        method = CatalogPlugin.create_table
        assert getattr(method, "__isabstractmethod__", False), "create_table() must be abstract"

        sig = inspect.signature(CatalogPlugin.create_table)
        params = list(sig.parameters.keys())
        assert "identifier" in params
        assert "schema" in params

    @pytest.mark.requirement("FR-003")
    def test_list_tables_method_is_abstract(self) -> None:
        """Verify list_tables() is an abstract method.

        FR-003: CatalogPlugin must define list_tables() for
        table listing within a namespace.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "list_tables")

        method = CatalogPlugin.list_tables
        assert getattr(method, "__isabstractmethod__", False), "list_tables() must be abstract"

        sig = inspect.signature(CatalogPlugin.list_tables)
        params = list(sig.parameters.keys())
        assert "namespace" in params

    @pytest.mark.requirement("FR-003")
    def test_drop_table_method_is_abstract(self) -> None:
        """Verify drop_table() is an abstract method.

        FR-003: CatalogPlugin must define drop_table() for
        table removal.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "drop_table")

        method = CatalogPlugin.drop_table
        assert getattr(method, "__isabstractmethod__", False), "drop_table() must be abstract"

        sig = inspect.signature(CatalogPlugin.drop_table)
        params = list(sig.parameters.keys())
        assert "identifier" in params
        assert "purge" in params

    @pytest.mark.requirement("FR-001")
    def test_vend_credentials_method_is_abstract(self) -> None:
        """Verify vend_credentials() is an abstract method.

        Credential vending is required for secure table access.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "vend_credentials")

        method = CatalogPlugin.vend_credentials
        assert getattr(method, "__isabstractmethod__", False), "vend_credentials() must be abstract"

        sig = inspect.signature(CatalogPlugin.vend_credentials)
        params = list(sig.parameters.keys())
        assert "table_path" in params
        assert "operations" in params

    @pytest.mark.requirement("FR-004")
    def test_health_check_has_default_implementation(self) -> None:
        """Verify health_check() has a default implementation.

        health_check() is optional with a default that returns unhealthy.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "health_check")

        method = CatalogPlugin.health_check
        # health_check is NOT abstract - it has a default implementation
        assert not getattr(method, "__isabstractmethod__", False), (
            "health_check() should have default implementation, not be abstract"
        )

        sig = inspect.signature(CatalogPlugin.health_check)
        params = list(sig.parameters.keys())
        assert "timeout" in params


class TestCatalogPluginMetadataRequirements:
    """Contract tests for plugin metadata requirements.

    FR-004: All CatalogPlugin implementations must provide plugin metadata.
    """

    @pytest.mark.requirement("FR-004")
    def test_catalog_plugin_inherits_plugin_metadata(self) -> None:
        """Verify CatalogPlugin inherits from PluginMetadata.

        This ensures all catalog plugins have required metadata properties.
        """
        from floe_core import PluginMetadata
        from floe_core.plugins import CatalogPlugin

        assert issubclass(CatalogPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-004")
    def test_name_property_is_required(self) -> None:
        """Verify name property is required (abstract).

        All plugins must have a unique name.
        """
        from floe_core.plugins import CatalogPlugin

        # name comes from PluginMetadata and is abstract
        assert hasattr(CatalogPlugin, "name")

    @pytest.mark.requirement("FR-004")
    def test_version_property_is_required(self) -> None:
        """Verify version property is required (abstract).

        All plugins must declare their version.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "version")

    @pytest.mark.requirement("FR-004")
    def test_floe_api_version_property_is_required(self) -> None:
        """Verify floe_api_version property is required (abstract).

        All plugins must declare compatible API version.
        """
        from floe_core.plugins import CatalogPlugin

        assert hasattr(CatalogPlugin, "floe_api_version")


class TestCatalogPluginInstantiationContract:
    """Contract tests for CatalogPlugin instantiation.

    These tests verify that:
    - CatalogPlugin cannot be instantiated directly (abstract)
    - Incomplete implementations cannot be instantiated
    - Complete implementations can be instantiated
    """

    @pytest.mark.requirement("FR-001")
    def test_cannot_instantiate_abstract_catalog_plugin(self) -> None:
        """Verify CatalogPlugin cannot be instantiated directly.

        Direct instantiation must fail because abstract methods are not implemented.
        """
        from floe_core.plugins import CatalogPlugin

        with pytest.raises(TypeError, match="abstract"):
            CatalogPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-001")
    def test_incomplete_implementation_fails(self) -> None:
        """Verify incomplete CatalogPlugin implementation fails.

        A class that only implements some abstract methods should not
        be instantiable.
        """
        from floe_core.plugins import CatalogPlugin

        class IncompletePlugin(CatalogPlugin):
            """Plugin missing most abstract methods."""

            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            def connect(self, config: dict[str, Any]) -> Any:
                pass

            # Missing: create_namespace, list_namespaces, delete_namespace,
            #          create_table, list_tables, drop_table, vend_credentials

        with pytest.raises(TypeError, match="abstract"):
            IncompletePlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-001")
    @pytest.mark.requirement("FR-002")
    @pytest.mark.requirement("FR-003")
    @pytest.mark.requirement("FR-004")
    def test_complete_implementation_succeeds(self) -> None:
        """Verify complete CatalogPlugin implementation can be instantiated.

        A class implementing all abstract methods should be instantiable.
        """
        from floe_core.plugins import CatalogPlugin

        class CompleteMockPlugin(CatalogPlugin):
            """Complete mock plugin implementation for testing."""

            @property
            def name(self) -> str:
                return "mock-catalog"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            def connect(self, config: dict[str, Any]) -> Any:
                _ = config  # Suppress unused parameter warning
                return {"mock": "catalog"}

            def create_namespace(
                self,
                namespace: str,
                properties: dict[str, str] | None = None,
            ) -> None:
                _ = namespace, properties  # Suppress unused parameter warning

            def list_namespaces(self, parent: str | None = None) -> list[str]:
                _ = parent  # Suppress unused parameter warning
                return []

            def delete_namespace(self, namespace: str) -> None:
                _ = namespace  # Suppress unused parameter warning

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
                return {"access_key": "mock", "secret_key": "mock"}

        # Should not raise
        plugin = CompleteMockPlugin()

        # Verify metadata is accessible
        assert plugin.name == "mock-catalog"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "0.1"


class TestCatalogPluginTypeHints:
    """Contract tests for CatalogPlugin method type hints.

    Type hints are part of the public contract and must be stable.
    """

    @pytest.mark.requirement("FR-001")
    def test_connect_return_type_hint(self) -> None:
        """Verify connect() has Catalog return type hint.

        FR-001: connect() must return a PyIceberg-compatible Catalog.
        """
        from floe_core.plugins import CatalogPlugin
        from floe_core.plugins.catalog import Catalog

        sig = inspect.signature(CatalogPlugin.connect)
        return_annotation = sig.return_annotation

        # Should be annotated with Catalog protocol
        assert return_annotation is Catalog or return_annotation == "Catalog"

    @pytest.mark.requirement("FR-002")
    def test_list_namespaces_return_type_hint(self) -> None:
        """Verify list_namespaces() returns list[str]."""
        from floe_core.plugins import CatalogPlugin

        sig = inspect.signature(CatalogPlugin.list_namespaces)
        return_annotation = sig.return_annotation

        # Should return list[str]
        assert "list" in str(return_annotation).lower()

    @pytest.mark.requirement("FR-003")
    def test_list_tables_return_type_hint(self) -> None:
        """Verify list_tables() returns list[str]."""
        from floe_core.plugins import CatalogPlugin

        sig = inspect.signature(CatalogPlugin.list_tables)
        return_annotation = sig.return_annotation

        # Should return list[str]
        assert "list" in str(return_annotation).lower()

    @pytest.mark.requirement("FR-001")
    def test_vend_credentials_return_type_hint(self) -> None:
        """Verify vend_credentials() returns dict[str, Any]."""
        from floe_core.plugins import CatalogPlugin

        sig = inspect.signature(CatalogPlugin.vend_credentials)
        return_annotation = sig.return_annotation

        # Should return dict
        assert "dict" in str(return_annotation).lower()
