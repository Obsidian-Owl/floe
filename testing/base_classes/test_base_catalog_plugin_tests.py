"""Tests for BaseCatalogPluginTests base class.

This module verifies that BaseCatalogPluginTests works correctly
with a mock CatalogPlugin implementation.
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core import CatalogPlugin, HealthState, HealthStatus
from floe_core.plugins.catalog import Catalog
from testing.base_classes import BaseCatalogPluginTests


class MockCatalog:
    """Mock catalog for testing."""

    def list_namespaces(self) -> list[tuple[str, ...]]:
        return [("bronze",), ("silver",)]

    def list_tables(self, namespace: str) -> list[str]:
        _ = namespace
        return ["table1"]

    def load_table(self, identifier: str) -> Any:
        _ = identifier
        return {"mock": "table"}


class MockCatalogPlugin(CatalogPlugin):
    """Mock CatalogPlugin for testing BaseCatalogPluginTests."""

    @property
    def name(self) -> str:
        return "mock-catalog"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "0.1"

    @property
    def description(self) -> str:
        return "Mock catalog for testing"

    def connect(self, config: dict[str, Any]) -> Catalog:
        _ = config
        return MockCatalog()

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        _ = namespace, properties

    def list_namespaces(self, parent: str | None = None) -> list[str]:
        _ = parent
        return ["bronze", "silver"]

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

    def health_check(self, timeout: float = 1.0) -> HealthStatus:
        _ = timeout
        return HealthStatus(
            state=HealthState.HEALTHY,
            message="Mock catalog healthy",
        )


class TestMockCatalogPlugin(BaseCatalogPluginTests):
    """Test BaseCatalogPluginTests with MockCatalogPlugin.

    This verifies that the base test class works correctly
    and that a complete CatalogPlugin implementation passes all tests.
    """

    @pytest.fixture
    def catalog_plugin(self) -> MockCatalogPlugin:
        """Provide mock plugin for testing."""
        return MockCatalogPlugin()
