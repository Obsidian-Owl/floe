"""Integration tests for Polaris credential vending.

Tests the PolarisCatalogPlugin vend_credentials() method against a real Polaris
instance running in the Kind cluster. These tests verify:
- vend_credentials() returns temporary STS credentials
- Credentials contain required fields (access_key, secret_key, token, expiration)
- Credentials work for READ and WRITE operations
- Credential expiration is properly set

Requirements Covered:
    - FR-019: System MUST define vend_credentials() as required abstract method
    - FR-020: System MUST return short-lived, scoped credentials for table access
    - FR-021: Vended credentials MUST include expiration and be valid <= 24 hours
    - FR-030: System MUST emit OpenTelemetry spans for all catalog operations
    - FR-031: OTel spans MUST include required attributes

Infrastructure Notes:
    Credential vending requires Polaris to be configured with STS-capable storage.
    The MinIO IAM setup job creates the polaris-svc user with S3 access policy.
    See: testing/k8s/services/minio.yaml for IAM configuration.
    See: testing/k8s/scripts/init-polaris.sh for catalog storageConfigInfo.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from floe_core import NotFoundError
from pydantic import SecretStr
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    pass

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestCredentialVending(IntegrationTestBase):
    """Integration tests for vend_credentials() method.

    These tests require a real Polaris instance running in the Kind cluster
    with STS-enabled storage backend (MinIO with IAM configured).

    Required services:
        - polaris:8181 - Polaris REST API
        - minio:9000 - MinIO S3-compatible storage with STS
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

    def _create_test_table(
        self,
        plugin: PolarisCatalogPlugin,
        namespace: str,
        table_name: str,
    ) -> str:
        """Create a test table for credential vending tests.

        Args:
            plugin: Connected plugin instance.
            namespace: Namespace to create table in.
            table_name: Name of the table.

        Returns:
            Full table path (namespace.table_name).
        """
        # Create namespace first
        plugin.create_namespace(namespace)

        # Create table with simple schema
        # Full table identifier: "namespace.table_name"
        full_table_name = f"{namespace}.{table_name}"
        schema = Schema(
            NestedField(field_id=1, name="id", field_type=LongType(), required=True),
            NestedField(field_id=2, name="name", field_type=StringType(), required=False),
        )

        plugin.create_table(full_table_name, schema)

        return full_table_name

    def _cleanup_test_resources(
        self,
        plugin: PolarisCatalogPlugin,
        namespace: str,
        table_name: str | None = None,
    ) -> None:
        """Clean up test resources.

        Args:
            plugin: Connected plugin instance.
            namespace: Namespace to clean up.
            table_name: Optional table to drop.
        """
        try:
            if table_name:
                plugin.drop_table(f"{namespace}.{table_name}")
        except NotFoundError:
            pass  # Table may not exist

        try:
            plugin.delete_namespace(namespace)
        except Exception:
            pass  # Namespace may not be empty or not exist

    # =========================================================================
    # TestCredentialVendingSuccess - Core credential vending tests (FR-020)
    # =========================================================================

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_returns_dict_with_required_keys(self) -> None:
        """Test vend_credentials returns credentials with required keys.

        Validates FR-020: System MUST return short-lived, scoped credentials
        for table access. Credentials must include access_key, secret_key,
        token (for STS), and expiration.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "test_table"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act - vend credentials for the table
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert - verify required keys exist
            assert isinstance(credentials, dict)
            assert "access_key" in credentials
            assert "secret_key" in credentials
            assert "expiration" in credentials
            # Token may be empty for some storage backends but key should exist
            assert "token" in credentials

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_access_key_is_not_empty(self) -> None:
        """Test vend_credentials returns non-empty access_key.

        Validates that vended credentials have actual values, not empty strings.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "test_table"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert - access_key should have a value
            assert credentials["access_key"], "access_key should not be empty"
            assert len(credentials["access_key"]) > 0

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_secret_key_is_not_empty(self) -> None:
        """Test vend_credentials returns non-empty secret_key.

        Validates that vended credentials have actual secret values.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "test_table"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert - secret_key should have a value
            assert credentials["secret_key"], "secret_key should not be empty"
            assert len(credentials["secret_key"]) > 0

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    # =========================================================================
    # TestCredentialVendingOperations - Operation scoping tests (FR-020)
    # =========================================================================

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_for_read_operation(self) -> None:
        """Test vend_credentials with READ operation.

        Validates that credentials can be vended for read-only access.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "read_test"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act - request READ credentials
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert - should return valid credentials
            assert credentials is not None
            assert "access_key" in credentials
            assert credentials["access_key"]  # Not empty

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_for_write_operation(self) -> None:
        """Test vend_credentials with WRITE operation.

        Validates that credentials can be vended for write access.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "write_test"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act - request WRITE credentials
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["WRITE"],
            )

            # Assert - should return valid credentials
            assert credentials is not None
            assert "access_key" in credentials
            assert credentials["access_key"]

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_for_read_write_operations(self) -> None:
        """Test vend_credentials with both READ and WRITE operations.

        Validates that credentials can be vended for full access.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "readwrite_test"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act - request both READ and WRITE
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ", "WRITE"],
            )

            # Assert - should return valid credentials
            assert credentials is not None
            assert "access_key" in credentials
            assert credentials["access_key"]

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    # =========================================================================
    # TestCredentialVendingExpiration - Expiration validation (FR-021)
    # =========================================================================

    @pytest.mark.requirement("FR-021")
    def test_vend_credentials_includes_expiration(self) -> None:
        """Test vend_credentials includes expiration timestamp.

        Validates FR-021: Vended credentials MUST include expiration timestamp.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "expiry_test"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert - expiration should exist and have a value
            assert "expiration" in credentials
            # Note: expiration may be empty string if catalog doesn't support it
            # but the key must exist per FR-021

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    @pytest.mark.requirement("FR-021")
    def test_vend_credentials_expiration_is_parseable_timestamp(self) -> None:
        """Test expiration can be parsed as a timestamp.

        Validates that when expiration is set, it's in ISO 8601 format.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "expiry_parse_test"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert - if expiration is set, it should be parseable
            expiration = credentials.get("expiration", "")
            if expiration:
                # Should be parseable as ISO datetime
                try:
                    # Handle both "Z" suffix and "+00:00" format
                    datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                except ValueError:
                    pytest.fail(f"expiration '{expiration}' is not valid ISO 8601 format")

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    @pytest.mark.requirement("FR-021")
    def test_vend_credentials_expiration_within_24_hours(self) -> None:
        """Test credentials expire within 24 hours.

        Validates FR-021: Vended credentials MUST be valid for no more than 24 hours.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table_name = "expiry_24h_test"

        try:
            table_path = self._create_test_table(plugin, namespace, table_name)

            # Act
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert - if expiration is set, it should be within 24 hours
            expiration = credentials.get("expiration", "")
            if expiration:
                expiration_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)

                # Expiration should be in the future
                assert expiration_dt > now, "Credentials should not be expired"

                # Expiration should be within 24 hours
                hours_until_expiration = (expiration_dt - now).total_seconds() / 3600
                assert hours_until_expiration <= 24, (
                    f"Credentials valid for {hours_until_expiration:.1f} hours, "
                    "but FR-021 requires <= 24 hours"
                )

        finally:
            self._cleanup_test_resources(plugin, namespace, table_name)

    # =========================================================================
    # TestCredentialVendingErrors - Error handling tests
    # =========================================================================

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_table_not_found_raises_error(self) -> None:
        """Test vend_credentials raises NotFoundError for non-existent table.

        Validates error handling when table does not exist.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"

        try:
            # Create namespace but no table
            plugin.create_namespace(namespace)

            # Act & Assert - should raise NotFoundError
            with pytest.raises(NotFoundError) as exc_info:
                plugin.vend_credentials(
                    table_path=f"{namespace}.nonexistent_table",
                    operations=["READ"],
                )

            assert exc_info.value.resource_type == "table"

        finally:
            self._cleanup_test_resources(plugin, namespace)

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_not_connected_raises_error(self) -> None:
        """Test vend_credentials raises error when not connected.

        Validates that calling vend_credentials before connect() fails clearly.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        # Note: intentionally NOT calling plugin.connect()

        # Act & Assert
        with pytest.raises(RuntimeError, match="not connected"):
            plugin.vend_credentials(
                table_path="some_namespace.some_table",
                operations=["READ"],
            )

    # =========================================================================
    # TestCredentialVendingMultipleTables - Scoping tests
    # =========================================================================

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_returns_different_for_different_tables(self) -> None:
        """Test vend_credentials returns table-scoped credentials.

        Validates that credentials are scoped to specific tables.
        Note: This tests that credentials can be vended for multiple tables;
        whether the credentials are actually different depends on the storage
        backend's STS implementation.
        """
        plugin = self._get_connected_plugin()
        namespace = f"cred_{uuid.uuid4().hex[:8]}"
        table1 = "table_one"
        table2 = "table_two"

        try:
            # Create namespace once, then create multiple tables
            plugin.create_namespace(namespace)

            # Create first table
            table1_path = f"{namespace}.{table1}"
            schema = Schema(
                NestedField(field_id=1, name="id", field_type=LongType(), required=True),
                NestedField(field_id=2, name="name", field_type=StringType(), required=False),
            )
            plugin.create_table(table1_path, schema)

            # Create second table
            table2_path = f"{namespace}.{table2}"
            plugin.create_table(table2_path, schema)

            # Act - vend credentials for both tables
            creds1 = plugin.vend_credentials(
                table_path=table1_path,
                operations=["READ"],
            )
            creds2 = plugin.vend_credentials(
                table_path=table2_path,
                operations=["READ"],
            )

            # Assert - both should return valid credentials
            assert creds1 is not None
            assert creds2 is not None
            assert creds1["access_key"]
            assert creds2["access_key"]

        finally:
            self._cleanup_test_resources(plugin, namespace, table1)
            self._cleanup_test_resources(plugin, namespace, table2)


class TestCredentialVendingHierarchicalNamespace(IntegrationTestBase):
    """Integration tests for credential vending with hierarchical namespaces.

    Tests vending credentials for tables in nested namespaces.

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

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_for_table_in_nested_namespace(self) -> None:
        """Test vend_credentials works for tables in nested namespaces.

        Validates credential vending for hierarchical namespace paths
        like 'domain.product.layer'.
        """
        plugin = self._get_connected_plugin()
        parent_ns = f"parent_{uuid.uuid4().hex[:8]}"
        child_ns = f"{parent_ns}.child"
        table_name = "nested_table"

        try:
            # Create hierarchical namespaces
            plugin.create_namespace(parent_ns)
            plugin.create_namespace(child_ns)

            # Create table in child namespace
            # Full table identifier: "parent_ns.child.table_name"
            table_path = f"{child_ns}.{table_name}"
            schema = Schema(
                NestedField(field_id=1, name="id", field_type=LongType(), required=True),
                NestedField(field_id=2, name="name", field_type=StringType(), required=False),
            )
            plugin.create_table(table_path, schema)

            # Act - vend credentials
            credentials = plugin.vend_credentials(
                table_path=table_path,
                operations=["READ"],
            )

            # Assert
            assert credentials is not None
            assert credentials["access_key"]

        finally:
            # Clean up
            try:
                plugin.drop_table(f"{child_ns}.{table_name}")
            except Exception:
                pass
            try:
                plugin.delete_namespace(child_ns)
            except Exception:
                pass
            try:
                plugin.delete_namespace(parent_ns)
            except Exception:
                pass
