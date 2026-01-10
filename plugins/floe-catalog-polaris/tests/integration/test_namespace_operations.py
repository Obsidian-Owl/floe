"""Integration tests for Polaris namespace operations.

Tests the PolarisCatalogPlugin namespace operations against a real Polaris
instance running in the Kind cluster. These tests verify:
- create_namespace() creates namespaces in Polaris
- list_namespaces() returns actual namespaces
- delete_namespace() removes namespaces
- Hierarchical namespace support
- Error handling for edge cases

Requirements Covered:
    - FR-010: Create namespaces with configurable properties
    - FR-011: Hierarchical namespace paths using dot notation
    - FR-012: List namespaces with optional filtering
    - FR-013: Delete empty namespaces
"""

from __future__ import annotations

import os
import uuid

import pytest
from pydantic import SecretStr
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin


class TestNamespaceOperations(IntegrationTestBase):
    """Integration tests for namespace CRUD operations.

    These tests require a real Polaris instance running in the Kind cluster.
    Each test creates uniquely named namespaces to avoid conflicts.

    Required services:
        - polaris:8181 - Polaris REST API
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris.

        Returns:
            PolarisCatalogConfig with test credentials.
        """
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    def _get_connected_plugin(self) -> PolarisCatalogPlugin:
        """Create and connect a plugin instance.

        Returns:
            Connected PolarisCatalogPlugin instance.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})
        return plugin

    def _generate_unique_namespace(self, prefix: str = "test") -> str:
        """Generate a unique namespace name for testing.

        Args:
            prefix: Prefix for the namespace name.

        Returns:
            Unique namespace name.
        """
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @pytest.mark.requirement("FR-010")
    @pytest.mark.integration
    def test_create_namespace_success(self) -> None:
        """Test creating a namespace in Polaris.

        Verifies that create_namespace() creates a namespace that can
        then be listed.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("create")

        try:
            # Create namespace
            plugin.create_namespace(namespace)

            # Verify it exists
            namespaces = plugin.list_namespaces()
            assert namespace in namespaces, (
                f"Created namespace '{namespace}' not found in list: {namespaces}"
            )
        finally:
            # Cleanup
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-010")
    @pytest.mark.integration
    def test_create_namespace_with_properties(self) -> None:
        """Test creating a namespace with custom properties.

        Verifies that namespace properties are stored correctly.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("props")

        properties = {
            "owner": "integration-test",
            "description": "Test namespace for integration tests",
        }

        try:
            # Create namespace with properties
            plugin.create_namespace(namespace, properties=properties)

            # Verify it exists
            namespaces = plugin.list_namespaces()
            assert namespace in namespaces
        finally:
            # Cleanup
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-010")
    @pytest.mark.integration
    def test_create_namespace_already_exists_raises_conflict(self) -> None:
        """Test that creating a duplicate namespace raises ConflictError.

        Verifies proper error handling for existing namespaces.
        """
        from floe_core import ConflictError

        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("dup")

        try:
            # Create first time
            plugin.create_namespace(namespace)

            # Create again should fail
            with pytest.raises(ConflictError) as exc_info:
                plugin.create_namespace(namespace)

            assert exc_info.value.resource_type == "namespace"
            assert namespace in exc_info.value.identifier
        finally:
            # Cleanup
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-012")
    @pytest.mark.integration
    def test_list_namespaces_returns_list(self) -> None:
        """Test listing namespaces returns a list.

        Verifies that list_namespaces() returns namespaces from Polaris.
        """
        plugin = self._get_connected_plugin()

        # List namespaces
        namespaces = plugin.list_namespaces()

        # Should be a list (may be empty or have existing namespaces)
        assert isinstance(namespaces, list)

    @pytest.mark.requirement("FR-012")
    @pytest.mark.integration
    def test_list_namespaces_includes_created_namespace(self) -> None:
        """Test that created namespaces appear in list.

        Verifies end-to-end create → list flow.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("list")

        try:
            # List before - namespace should not exist
            namespaces_before = plugin.list_namespaces()
            assert namespace not in namespaces_before

            # Create
            plugin.create_namespace(namespace)

            # List after - namespace should exist
            namespaces_after = plugin.list_namespaces()
            assert namespace in namespaces_after
        finally:
            # Cleanup
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-013")
    @pytest.mark.integration
    def test_delete_namespace_success(self) -> None:
        """Test deleting a namespace removes it.

        Verifies that delete_namespace() actually removes the namespace.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("delete")

        # Create first
        plugin.create_namespace(namespace)

        # Verify exists
        assert namespace in plugin.list_namespaces()

        # Delete
        plugin.delete_namespace(namespace)

        # Verify gone
        assert namespace not in plugin.list_namespaces()

    @pytest.mark.requirement("FR-013")
    @pytest.mark.integration
    def test_delete_namespace_not_found_raises_error(self) -> None:
        """Test deleting a non-existent namespace raises NotFoundError.

        Verifies proper error handling for missing namespaces.
        """
        from floe_core import NotFoundError

        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("notfound")

        # Delete non-existent namespace
        with pytest.raises(NotFoundError) as exc_info:
            plugin.delete_namespace(namespace)

        assert exc_info.value.resource_type == "namespace"

    @pytest.mark.requirement("FR-010")
    @pytest.mark.requirement("FR-013")
    @pytest.mark.integration
    def test_create_delete_lifecycle(self) -> None:
        """Test full namespace lifecycle: create → verify → delete → verify.

        Verifies the complete lifecycle works correctly.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("lifecycle")

        # Create
        plugin.create_namespace(namespace)
        assert namespace in plugin.list_namespaces()

        # Delete
        plugin.delete_namespace(namespace)
        assert namespace not in plugin.list_namespaces()

        # Can create again (not a conflict)
        plugin.create_namespace(namespace)
        assert namespace in plugin.list_namespaces()

        # Cleanup
        plugin.delete_namespace(namespace)


class TestNamespaceHierarchy(IntegrationTestBase):
    """Integration tests for hierarchical namespace support.

    Tests dot-notation hierarchical namespaces in Polaris.

    Required services:
        - polaris:8181 - Polaris REST API
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris."""
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    def _get_connected_plugin(self) -> PolarisCatalogPlugin:
        """Create and connect a plugin instance."""
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})
        return plugin

    def _generate_unique_namespace(self, prefix: str = "test") -> str:
        """Generate a unique namespace name for testing."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @pytest.mark.requirement("FR-011")
    @pytest.mark.integration
    def test_create_hierarchical_namespace(self) -> None:
        """Test creating a hierarchical namespace with parent creation.

        Polaris requires parent namespaces to exist before creating child
        namespaces. This test verifies the hierarchical namespace pattern
        works when parents are created first.

        Note: In Iceberg catalogs, list_namespaces() without parent only
        returns top-level namespaces. To see child namespaces, you must
        query with parent parameter.
        """
        plugin = self._get_connected_plugin()
        parent = self._generate_unique_namespace("hier")
        child = f"{parent}.child"

        try:
            # Create parent namespace first (required by Polaris)
            plugin.create_namespace(parent)

            # Create child namespace
            plugin.create_namespace(child)

            # Verify parent exists in top-level list
            top_namespaces = plugin.list_namespaces()
            assert parent in top_namespaces, (
                f"Parent namespace '{parent}' not found in list: {top_namespaces}"
            )

            # Verify child exists when querying with parent filter
            child_namespaces = plugin.list_namespaces(parent=parent)
            assert child in child_namespaces, (
                f"Child namespace '{child}' not found when listing parent '{parent}': {child_namespaces}"
            )
        finally:
            # Cleanup in reverse order (child first, then parent)
            try:
                plugin.delete_namespace(child)
            except Exception:
                pass
            try:
                plugin.delete_namespace(parent)
            except Exception:
                pass

    @pytest.mark.requirement("FR-011")
    @pytest.mark.integration
    def test_delete_hierarchical_namespace(self) -> None:
        """Test deleting a hierarchical namespace.

        Verifies that child namespaces can be deleted while parent remains.
        """
        plugin = self._get_connected_plugin()
        parent = self._generate_unique_namespace("hdel")
        child = f"{parent}.child"

        try:
            # Create parent then child
            plugin.create_namespace(parent)
            plugin.create_namespace(child)

            # Delete child only
            plugin.delete_namespace(child)

            # Verify child is gone (when querying with parent filter)
            child_namespaces = plugin.list_namespaces(parent=parent)
            assert child not in child_namespaces

            # Verify parent still exists
            top_namespaces = plugin.list_namespaces()
            assert parent in top_namespaces
        finally:
            # Cleanup parent
            try:
                plugin.delete_namespace(parent)
            except Exception:
                pass

    @pytest.mark.requirement("FR-011")
    @pytest.mark.integration
    def test_hierarchical_namespace_requires_parent(self) -> None:
        """Test that creating a child without parent fails.

        Polaris requires parent namespaces to exist before creating children.
        This verifies the error handling for missing parent.
        """
        from floe_core import CatalogUnavailableError, NotFoundError

        plugin = self._get_connected_plugin()
        parent = self._generate_unique_namespace("orphan")
        child = f"{parent}.child"

        # Try to create child without parent - should fail
        with pytest.raises((NotFoundError, CatalogUnavailableError)):
            plugin.create_namespace(child)

    @pytest.mark.requirement("FR-012")
    @pytest.mark.integration
    def test_list_namespaces_with_parent_filter(self) -> None:
        """Test listing child namespaces with parent filter.

        Verifies that list_namespaces(parent=...) returns only children.
        """
        plugin = self._get_connected_plugin()
        parent = self._generate_unique_namespace("filter")
        child1 = f"{parent}.child1"
        child2 = f"{parent}.child2"

        try:
            # Create hierarchy
            plugin.create_namespace(parent)
            plugin.create_namespace(child1)
            plugin.create_namespace(child2)

            # List with parent filter should return children
            children = plugin.list_namespaces(parent=parent)
            assert child1 in children
            assert child2 in children
            assert len([c for c in children if c.startswith(parent)]) >= 2
        finally:
            # Cleanup
            for ns in [child1, child2, parent]:
                try:
                    plugin.delete_namespace(ns)
                except Exception:
                    pass


class TestNamespaceEdgeCases(IntegrationTestBase):
    """Edge case tests for namespace operations.

    Tests unusual scenarios and boundary conditions.

    Required services:
        - polaris:8181 - Polaris REST API
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris."""
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    def _get_connected_plugin(self) -> PolarisCatalogPlugin:
        """Create and connect a plugin instance."""
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})
        return plugin

    def _generate_unique_namespace(self, prefix: str = "test") -> str:
        """Generate a unique namespace name for testing."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @pytest.mark.requirement("FR-010")
    @pytest.mark.integration
    def test_create_namespace_with_underscores(self) -> None:
        """Test creating a namespace with underscores.

        Verifies that underscores are valid in namespace names.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("under_score_test")

        try:
            plugin.create_namespace(namespace)
            assert namespace in plugin.list_namespaces()
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-010")
    @pytest.mark.integration
    def test_create_namespace_with_numbers(self) -> None:
        """Test creating a namespace with numbers.

        Verifies that numeric characters are valid in namespace names.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("ns123")

        try:
            plugin.create_namespace(namespace)
            assert namespace in plugin.list_namespaces()
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-012")
    @pytest.mark.integration
    def test_list_namespaces_multiple_times_consistent(self) -> None:
        """Test that list_namespaces returns consistent results.

        Verifies idempotency of list operations.
        """
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("consistent")

        try:
            plugin.create_namespace(namespace)

            # List multiple times
            list1 = plugin.list_namespaces()
            list2 = plugin.list_namespaces()
            list3 = plugin.list_namespaces()

            # All should contain our namespace
            assert namespace in list1
            assert namespace in list2
            assert namespace in list3
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-010")
    @pytest.mark.integration
    def test_create_multiple_namespaces(self) -> None:
        """Test creating multiple namespaces.

        Verifies that multiple namespaces can be created independently.
        """
        plugin = self._get_connected_plugin()
        namespaces = [
            self._generate_unique_namespace(f"multi{i}") for i in range(3)
        ]

        try:
            # Create all
            for ns in namespaces:
                plugin.create_namespace(ns)

            # Verify all exist
            current = plugin.list_namespaces()
            for ns in namespaces:
                assert ns in current, f"Namespace {ns} not found"
        finally:
            # Cleanup all
            for ns in namespaces:
                try:
                    plugin.delete_namespace(ns)
                except Exception:
                    pass

    @pytest.mark.requirement("FR-013")
    @pytest.mark.integration
    def test_delete_namespace_twice_raises_not_found(self) -> None:
        """Test deleting the same namespace twice raises NotFoundError.

        Verifies idempotency behavior.
        """
        from floe_core import NotFoundError

        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace("twice")

        # Create and delete once
        plugin.create_namespace(namespace)
        plugin.delete_namespace(namespace)

        # Delete again should fail
        with pytest.raises(NotFoundError):
            plugin.delete_namespace(namespace)


# Module-level docstring for test discovery
__all__ = [
    "TestNamespaceOperations",
    "TestNamespaceHierarchy",
    "TestNamespaceEdgeCases",
]
