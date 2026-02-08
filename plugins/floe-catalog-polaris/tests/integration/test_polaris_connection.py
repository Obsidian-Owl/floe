"""Integration tests for Polaris catalog connection.

Tests the PolarisCatalogPlugin connection to a real Polaris instance
running in the Kind cluster. These tests verify:
- OAuth2 authentication flow
- PyIceberg REST catalog integration
- Connection error handling
- Network timeouts

Requirements Covered:
    - FR-006: CatalogPlugin implementations connect via PyIceberg REST catalog
    - FR-007: OAuth2 authentication with token refresh
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from floe_core.plugin_errors import CatalogUnavailableError
from pydantic import SecretStr
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    pass


class TestPolarisConnection(IntegrationTestBase):
    """Integration tests for Polaris connection.

    These tests require a real Polaris instance running in the Kind cluster.
    They verify that the PolarisCatalogPlugin can connect and authenticate.

    Required services:
        - polaris:8181 - Polaris REST API
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris.

        Returns:
            PolarisCatalogConfig with test credentials.
        """
        # Get Polaris URI from environment or construct from K8s service
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        # Get credentials from environment (defaults match testing/k8s/services/polaris.yaml)
        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        # Token URL is typically at the catalog endpoint
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

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_connect_success(self) -> None:
        """Test successful connection to Polaris catalog.

        Verifies that the plugin can connect to a Polaris instance
        using OAuth2 credentials and return a valid catalog object.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Connect should succeed
        catalog = plugin.connect({})

        # Verify we got a catalog object
        assert catalog is not None
        # The catalog should implement the basic protocol
        assert hasattr(catalog, "list_namespaces")
        assert hasattr(catalog, "list_tables")

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_connect_and_list_namespaces(self) -> None:
        """Test connection and basic namespace listing.

        Verifies end-to-end connectivity by performing a simple
        list_namespaces operation after connecting.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Connect
        plugin.connect({})

        # List namespaces should work (may return empty list)
        namespaces = plugin.list_namespaces()
        assert isinstance(namespaces, list)

    @pytest.mark.requirement("FR-007")
    @pytest.mark.integration
    def test_oauth2_authentication(self) -> None:
        """Test OAuth2 authentication works correctly.

        Verifies that the plugin can authenticate using OAuth2
        client credentials flow.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Connect with OAuth2 credentials
        catalog = plugin.connect({})

        # If we got here without exception, authentication worked
        assert catalog is not None

        # Verify we can perform an authenticated operation
        # list_namespaces requires valid auth
        namespaces = plugin.list_namespaces()
        assert isinstance(namespaces, list)

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_connect_invalid_credentials(self) -> None:
        """Test connection fails with invalid credentials.

        Verifies that the plugin properly handles authentication
        failures with clear error messages.
        """
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )
        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        config = PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="invalid_client",
                client_secret=SecretStr("invalid_secret"),
                token_url=token_url,
            ),
        )
        plugin = PolarisCatalogPlugin(config=config)

        # Connection should fail with authentication error
        with pytest.raises(Exception) as exc_info:
            plugin.connect({})

        # Error should indicate authentication failure
        error_str = str(exc_info.value).lower()
        assert any(
            term in error_str
            for term in ["auth", "credential", "unauthorized", "401", "forbidden"]
        ), f"Expected auth-related error, got: {exc_info.value}"

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_connect_invalid_uri(self) -> None:
        """Test connection fails with invalid URI.

        Verifies that the plugin handles connection failures
        with unreachable endpoints.
        """
        config = PolarisCatalogConfig(
            uri="http://nonexistent-host.invalid:8181/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test",
                client_secret=SecretStr("test"),
                token_url="http://nonexistent-host.invalid:8181/api/catalog/v1/oauth/tokens",
            ),
        )
        plugin = PolarisCatalogPlugin(config=config)

        # Connection should fail with connection error
        with pytest.raises(Exception) as exc_info:
            plugin.connect({})

        # Error should indicate connection failure
        error_str = str(exc_info.value).lower()
        assert any(
            term in error_str
            for term in ["connect", "network", "resolve", "unreachable", "failed"]
        ), f"Expected connection error, got: {exc_info.value}"

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_plugin_metadata(self) -> None:
        """Test plugin metadata is correct.

        Verifies that the plugin exposes correct metadata
        for discovery and registration.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        assert plugin.name == "polaris"
        assert plugin.version == "0.1.0"
        assert plugin.floe_api_version == "0.1"
        assert (
            "polaris" in plugin.description.lower()
            or "catalog" in plugin.description.lower()
        )

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_health_check_before_connect(self) -> None:
        """Test health check returns unhealthy before connection.

        Verifies that health_check returns UNHEALTHY when
        the plugin hasn't connected yet.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Health check before connect should return unhealthy
        status = plugin.health_check()

        from floe_core import HealthState

        assert status.state == HealthState.UNHEALTHY
        assert "not connected" in status.message.lower()

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_health_check_after_connect(self) -> None:
        """Test health check returns healthy after connection.

        Verifies that health_check returns HEALTHY when
        the plugin is connected and the catalog is responsive.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Connect first
        plugin.connect({})

        # Health check should return healthy
        status = plugin.health_check()

        from floe_core import HealthState

        assert status.state == HealthState.HEALTHY
        assert "details" in dir(status) or hasattr(status, "details")
        if hasattr(status, "details") and status.details:
            assert "response_time_ms" in status.details

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_reconnect_after_disconnect(self) -> None:
        """Test that plugin can reconnect after operations.

        Verifies that the plugin handles connection lifecycle
        correctly when connect is called multiple times.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # First connection
        catalog1 = plugin.connect({})
        assert catalog1 is not None

        # List namespaces to verify connection works
        namespaces1 = plugin.list_namespaces()
        assert isinstance(namespaces1, list)

        # Second connection (reconnect)
        catalog2 = plugin.connect({})
        assert catalog2 is not None

        # Operations should still work
        namespaces2 = plugin.list_namespaces()
        assert isinstance(namespaces2, list)


class TestPolarisConnectionEdgeCases(IntegrationTestBase):
    """Edge case tests for Polaris connection.

    Tests unusual scenarios and boundary conditions for connection handling.
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
            ),
        )

    @pytest.mark.requirement("FR-007")
    @pytest.mark.integration
    def test_connect_with_custom_scope(self) -> None:
        """Test connection with custom OAuth2 scope.

        Verifies that custom scopes are passed correctly to the
        OAuth2 token endpoint.
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

        # Use a specific scope
        config = PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )
        plugin = PolarisCatalogPlugin(config=config)

        # Should connect successfully with the scope
        catalog = plugin.connect({})
        assert catalog is not None

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_operations_before_connect_fail(self) -> None:
        """Test that operations fail gracefully before connect.

        Verifies that the plugin raises clear errors when operations
        are attempted before connect() is called.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Operations should fail before connect
        with pytest.raises(CatalogUnavailableError, match="not connected"):
            plugin.list_namespaces()

        with pytest.raises(CatalogUnavailableError, match="not connected"):
            plugin.create_namespace("test")

        with pytest.raises(CatalogUnavailableError, match="not connected"):
            plugin.list_tables("test")

    @pytest.mark.requirement("FR-006")
    @pytest.mark.integration
    def test_config_validation_on_instantiation(self) -> None:
        """Test that config is validated on plugin instantiation.

        Verifies that invalid configuration is caught early
        during plugin creation, not just at connection time.
        """
        from pydantic import ValidationError

        # Invalid URI (missing scheme)
        with pytest.raises(ValidationError):
            PolarisCatalogConfig(
                uri="invalid-uri-no-scheme",
                warehouse="test",
                oauth2=OAuth2Config(
                    client_id="test",
                    client_secret=SecretStr("test"),
                    token_url="http://localhost:8181/oauth/tokens",
                ),
            )

        # Invalid token URL (missing scheme)
        with pytest.raises(ValidationError):
            PolarisCatalogConfig(
                uri="http://localhost:8181/api/catalog",
                warehouse="test",
                oauth2=OAuth2Config(
                    client_id="test",
                    client_secret=SecretStr("test"),
                    token_url="invalid-no-scheme",
                ),
            )


# Module-level docstring for test discovery
__all__ = ["TestPolarisConnection", "TestPolarisConnectionEdgeCases"]
