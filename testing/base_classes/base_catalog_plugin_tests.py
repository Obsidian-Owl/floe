"""Base test class for CatalogPlugin compliance testing.

This module provides BaseCatalogPluginTests, an abstract test class that
validates CatalogPlugin implementations meet all interface requirements.

Plugin implementations MUST pass all tests in this class to be considered
compliant with the CatalogPlugin ABC.

Usage:
    1. Create a test class that inherits from BaseCatalogPluginTests
    2. Implement the catalog_plugin fixture to return your plugin instance
    3. Run pytest - all base tests will be executed automatically

Example:
    >>> import pytest
    >>> from testing.base_classes import BaseCatalogPluginTests
    >>> from my_plugin import MyCatalogPlugin
    >>>
    >>> class TestMyCatalogPlugin(BaseCatalogPluginTests):
    ...     @pytest.fixture
    ...     def catalog_plugin(self) -> MyCatalogPlugin:
    ...         return MyCatalogPlugin(config={...})

Requirements Covered:
    - FR-001: connect() method returning Catalog
    - FR-002: Namespace operations (create, list, delete)
    - FR-003: Table operations (create, list, drop)
    - FR-004: Plugin metadata (name, version, floe_api_version)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.plugins import CatalogPlugin


class BaseCatalogPluginTests(ABC):
    """Abstract base test class for CatalogPlugin implementations.

    Subclasses must implement the catalog_plugin fixture to provide
    an instance of their CatalogPlugin implementation.

    All tests use @pytest.mark.requirement() for traceability.

    Attributes:
        catalog_plugin: Fixture that returns the plugin under test.

    Example:
        >>> class TestPolarisPlugin(BaseCatalogPluginTests):
        ...     @pytest.fixture
        ...     def catalog_plugin(self):
        ...         return PolarisPlugin(config)
    """

    @pytest.fixture
    @abstractmethod
    def catalog_plugin(self) -> CatalogPlugin:
        """Return an instance of the CatalogPlugin to test.

        Subclasses MUST implement this fixture to provide their
        concrete plugin implementation.

        Returns:
            A configured CatalogPlugin instance ready for testing.

        Example:
            >>> @pytest.fixture
            ... def catalog_plugin(self):
            ...     config = {"uri": "http://localhost:8181"}
            ...     return MyCatalogPlugin(config)
        """
        ...

    # =========================================================================
    # Plugin Metadata Tests (FR-004)
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_has_name_property(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has a name property.

        All plugins must have a unique name identifier.
        """
        assert hasattr(catalog_plugin, "name")
        assert isinstance(catalog_plugin.name, str)
        assert len(catalog_plugin.name) > 0

    @pytest.mark.requirement("FR-004")
    def test_has_version_property(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has a version property.

        Plugin version should follow semantic versioning.
        """
        assert hasattr(catalog_plugin, "version")
        assert isinstance(catalog_plugin.version, str)
        assert len(catalog_plugin.version) > 0

    @pytest.mark.requirement("FR-004")
    def test_has_floe_api_version_property(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin declares compatible floe API version.

        This is used to check plugin compatibility with the platform.
        """
        assert hasattr(catalog_plugin, "floe_api_version")
        assert isinstance(catalog_plugin.floe_api_version, str)
        assert len(catalog_plugin.floe_api_version) > 0

    @pytest.mark.requirement("FR-004")
    def test_has_description_property(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has a description property.

        Description can be empty but must exist.
        """
        assert hasattr(catalog_plugin, "description")
        assert isinstance(catalog_plugin.description, str)

    @pytest.mark.requirement("FR-004")
    def test_has_dependencies_property(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has a dependencies property.

        Dependencies is a list of plugin names this plugin depends on.
        """
        assert hasattr(catalog_plugin, "dependencies")
        assert isinstance(catalog_plugin.dependencies, list)

    # =========================================================================
    # Method Existence Tests
    # =========================================================================

    @pytest.mark.requirement("FR-001")
    def test_has_connect_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has connect() method."""
        assert hasattr(catalog_plugin, "connect")
        assert callable(catalog_plugin.connect)

    @pytest.mark.requirement("FR-002")
    def test_has_create_namespace_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has create_namespace() method."""
        assert hasattr(catalog_plugin, "create_namespace")
        assert callable(catalog_plugin.create_namespace)

    @pytest.mark.requirement("FR-002")
    def test_has_list_namespaces_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has list_namespaces() method."""
        assert hasattr(catalog_plugin, "list_namespaces")
        assert callable(catalog_plugin.list_namespaces)

    @pytest.mark.requirement("FR-002")
    def test_has_delete_namespace_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has delete_namespace() method."""
        assert hasattr(catalog_plugin, "delete_namespace")
        assert callable(catalog_plugin.delete_namespace)

    @pytest.mark.requirement("FR-003")
    def test_has_create_table_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has create_table() method."""
        assert hasattr(catalog_plugin, "create_table")
        assert callable(catalog_plugin.create_table)

    @pytest.mark.requirement("FR-003")
    def test_has_list_tables_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has list_tables() method."""
        assert hasattr(catalog_plugin, "list_tables")
        assert callable(catalog_plugin.list_tables)

    @pytest.mark.requirement("FR-003")
    def test_has_drop_table_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has drop_table() method."""
        assert hasattr(catalog_plugin, "drop_table")
        assert callable(catalog_plugin.drop_table)

    @pytest.mark.requirement("FR-001")
    def test_has_vend_credentials_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has vend_credentials() method."""
        assert hasattr(catalog_plugin, "vend_credentials")
        assert callable(catalog_plugin.vend_credentials)

    @pytest.mark.requirement("FR-001")
    def test_has_health_check_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has health_check() method."""
        assert hasattr(catalog_plugin, "health_check")
        assert callable(catalog_plugin.health_check)

    # =========================================================================
    # Lifecycle Tests
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_has_startup_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has startup() lifecycle method."""
        assert hasattr(catalog_plugin, "startup")
        assert callable(catalog_plugin.startup)

    @pytest.mark.requirement("FR-004")
    def test_has_shutdown_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has shutdown() lifecycle method."""
        assert hasattr(catalog_plugin, "shutdown")
        assert callable(catalog_plugin.shutdown)

    @pytest.mark.requirement("FR-004")
    def test_startup_does_not_raise(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify startup() can be called without raising."""
        # Should not raise
        catalog_plugin.startup()

    @pytest.mark.requirement("FR-004")
    def test_shutdown_does_not_raise(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify shutdown() can be called without raising."""
        # Should not raise
        catalog_plugin.shutdown()

    # =========================================================================
    # Config Schema Tests
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_has_get_config_schema_method(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify plugin has get_config_schema() method."""
        assert hasattr(catalog_plugin, "get_config_schema")
        assert callable(catalog_plugin.get_config_schema)

    @pytest.mark.requirement("FR-004")
    def test_config_schema_returns_valid_type(
        self, catalog_plugin: CatalogPlugin
    ) -> None:
        """Verify get_config_schema() returns None or a BaseModel class.

        Plugins can either have no config schema (None) or return
        a Pydantic BaseModel subclass.
        """
        schema = catalog_plugin.get_config_schema()

        if schema is not None:
            from pydantic import BaseModel

            assert isinstance(schema, type)
            assert issubclass(schema, BaseModel)

    # =========================================================================
    # Health Check Tests
    # =========================================================================

    @pytest.mark.requirement("FR-001")
    def test_health_check_returns_health_status(
        self, catalog_plugin: CatalogPlugin
    ) -> None:
        """Verify health_check() returns a HealthStatus object."""
        from floe_core import HealthStatus

        health = catalog_plugin.health_check()

        assert isinstance(health, HealthStatus)
        assert hasattr(health, "state")
        assert hasattr(health, "message")

    @pytest.mark.requirement("FR-001")
    def test_health_check_accepts_timeout(self, catalog_plugin: CatalogPlugin) -> None:
        """Verify health_check() accepts timeout parameter."""
        from floe_core import HealthStatus

        # Should not raise
        health = catalog_plugin.health_check(timeout=5.0)
        assert isinstance(health, HealthStatus)
