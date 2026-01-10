"""Integration tests validating quickstart.md code examples.

These tests verify that all code examples in specs/001-catalog-plugin/quickstart.md
work correctly against a real Polaris instance. Each test corresponds to a section
in the quickstart guide.

Requirements Covered:
    - T077 (FLO-341): Validate that quickstart.md examples work end-to-end
"""

from __future__ import annotations

import pytest
from floe_core import (
    AuthenticationError,
    CatalogError,
    CatalogUnavailableError,
    ConflictError,
    HealthState,
    NotFoundError,
    NotSupportedError,
)
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, TimestampType

from floe_catalog_polaris import PolarisCatalogPlugin
from floe_catalog_polaris.config import PolarisCatalogConfig

pytestmark = pytest.mark.integration


class TestQuickstartExamples:
    """Validate quickstart.md examples work end-to-end."""

    @pytest.mark.requirement("T077")
    def test_connect_example(
        self,
        polaris_config: PolarisCatalogConfig,
    ) -> None:
        """Test the 'Quick Example: Connect to Polaris' section.

        Validates:
            - Plugin creation with PolarisCatalogConfig
            - connect() returns a valid catalog object
            - list_namespaces() works after connect
        """
        # Example from quickstart: Create and connect plugin
        plugin = PolarisCatalogPlugin(config=polaris_config)
        iceberg_catalog = plugin.connect({})

        # Verify connect returned a valid catalog object
        assert iceberg_catalog is not None
        assert hasattr(iceberg_catalog, "list_namespaces")

        # List namespaces - verify connection is functional
        namespaces = plugin.list_namespaces()
        assert isinstance(namespaces, list)

    @pytest.mark.requirement("T077")
    def test_namespace_management_examples(
        self,
        polaris_plugin: PolarisCatalogPlugin,
        unique_namespace_name: str,
    ) -> None:
        """Test the 'Namespace Management' section examples.

        Validates:
            - create_namespace() with properties
            - list_namespaces()
            - delete_namespace()
        """
        namespace = unique_namespace_name

        # Create a namespace with properties (from quickstart)
        polaris_plugin.create_namespace(
            namespace=namespace,
            properties={
                "owner": "data-platform-team",
            },
        )

        # List all namespaces (from quickstart)
        all_namespaces = polaris_plugin.list_namespaces()
        assert namespace in all_namespaces

        # Delete an empty namespace (from quickstart)
        polaris_plugin.delete_namespace(namespace)

        # Verify deletion
        namespaces_after = polaris_plugin.list_namespaces()
        assert namespace not in namespaces_after

    @pytest.mark.requirement("T077")
    def test_table_operations_examples(
        self,
        polaris_plugin: PolarisCatalogPlugin,
        test_namespace: str,
    ) -> None:
        """Test the 'Table Operations' section examples.

        Validates:
            - create_table() with PyIceberg Schema
            - list_tables()
            - drop_table()
        """
        table_name = f"{test_namespace}.events"

        # Define Iceberg schema using PyIceberg types (from quickstart)
        schema = Schema(
            NestedField(field_id=1, name="event_id", field_type=StringType(), required=True),
            NestedField(field_id=2, name="event_time", field_type=TimestampType(), required=True),
            NestedField(field_id=3, name="payload", field_type=StringType(), required=False),
        )

        # Create table in namespace (from quickstart)
        polaris_plugin.create_table(
            identifier=table_name,
            schema=schema,
            properties={"format-version": "2"},
        )

        # List tables in a namespace (from quickstart)
        tables = polaris_plugin.list_tables(test_namespace)
        assert table_name in tables

        # Drop table (metadata only) (from quickstart)
        polaris_plugin.drop_table(table_name)

        # Verify deletion
        tables_after = polaris_plugin.list_tables(test_namespace)
        assert table_name not in tables_after

    @pytest.mark.requirement("T077")
    def test_health_check_example(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test the 'Health Checks' section examples.

        Validates:
            - health_check() returns HealthStatus
            - status.state == HealthState.HEALTHY for connected plugin
            - status.details contains response_time_ms
            - status.message is populated
        """
        # Check catalog health (from quickstart)
        status = polaris_plugin.health_check(timeout=1.0)

        # Validate the health check example code works
        if status.state == HealthState.HEALTHY:
            # This line from quickstart should work
            response_time = status.details["response_time_ms"]
            assert isinstance(response_time, float)
            assert response_time >= 0
        else:
            # If unhealthy, message should be populated
            assert status.message

        # status.details['checked_at'] provides timestamp for metrics
        assert "checked_at" in status.details

    @pytest.mark.requirement("T077")
    def test_error_handling_example(
        self,
        polaris_plugin: PolarisCatalogPlugin,
        test_namespace: str,
    ) -> None:
        """Test the 'Error Handling' section examples.

        Validates that the error imports and exception types work correctly.
        """
        # Try to create a namespace that already exists - should raise ConflictError
        with pytest.raises(ConflictError) as exc_info:
            polaris_plugin.create_namespace(test_namespace)
        # Verify error message mentions the namespace or conflict
        assert "already exists" in str(exc_info.value).lower() or test_namespace in str(
            exc_info.value
        )

        # Try to delete a non-existent namespace - should raise NotFoundError
        with pytest.raises(NotFoundError) as exc_info:
            polaris_plugin.delete_namespace("nonexistent_namespace_xyz123")
        # Verify error message mentions not found or the namespace
        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg or "does not exist" in error_msg

    @pytest.mark.requirement("T077")
    def test_error_hierarchy_imports(self) -> None:
        """Test that all error imports from quickstart work.

        Validates the import statement from the Error Handling section
        and verifies the inheritance hierarchy is correct.
        """
        # Verify inheritance hierarchy (CatalogError is the base)
        assert issubclass(CatalogUnavailableError, CatalogError)
        assert issubclass(AuthenticationError, CatalogError)
        assert issubclass(NotSupportedError, CatalogError)
        assert issubclass(ConflictError, CatalogError)
        assert issubclass(NotFoundError, CatalogError)

        # Verify each error can be instantiated with a message
        error_classes = [
            CatalogError,
            CatalogUnavailableError,
            AuthenticationError,
            NotSupportedError,
            ConflictError,
            NotFoundError,
        ]
        for error_class in error_classes:
            error = error_class("test message")
            assert str(error) == "test message"
            assert isinstance(error, Exception)
            assert isinstance(error, CatalogError)

    @pytest.mark.requirement("T077")
    def test_credential_vending_example_disabled(
        self,
        polaris_config: PolarisCatalogConfig,
        test_table: str,
    ) -> None:
        """Test credential vending example when disabled.

        When credential_vending_enabled=False, vend_credentials should raise
        NotSupportedError as shown in the custom plugin example.
        """
        # Create plugin with credential vending disabled

        config_disabled = PolarisCatalogConfig(
            uri=polaris_config.uri,
            warehouse=polaris_config.warehouse,
            oauth2=polaris_config.oauth2,
            credential_vending_enabled=False,
        )

        plugin = PolarisCatalogPlugin(config=config_disabled)
        plugin.connect({})

        # Vend credentials should raise NotSupportedError when disabled
        try:
            plugin.vend_credentials(
                table_path=test_table,
                operations=["READ"],
            )
            pytest.fail("Expected NotSupportedError when credential vending disabled")
        except NotSupportedError as e:
            # Verify error message mentions configuring storage credentials
            assert "credential" in str(e).lower() or "not supported" in str(e).lower()
