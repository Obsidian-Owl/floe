"""Unit tests for error mapping utilities.

This module tests the mapping of PyIceberg exceptions to floe CatalogError
types for proper error handling and user feedback.

Requirements Covered:
    - FR-033: System MUST support error mapping for catalog operations
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from floe_core import (
    AuthenticationError,
    CatalogError,
    CatalogUnavailableError,
    ConflictError,
    NotFoundError,
    NotSupportedError,
)
from pyiceberg.exceptions import (
    AuthorizationExpiredError,
    BadRequestError,
    ForbiddenError,
    NamespaceAlreadyExistsError,
    NamespaceNotEmptyError,
    NoSuchIdentifierError,
    NoSuchNamespaceError,
    NoSuchTableError,
    NoSuchViewError,
    OAuthError,
    RESTError,
    ServerError,
    ServiceUnavailableError,
    TableAlreadyExistsError,
    UnauthorizedError,
    ValidationError,
)

from floe_catalog_polaris.errors import (
    PYICEBERG_EXCEPTION_TYPES,
    map_pyiceberg_error,
)


class TestMapPyicebergError:
    """Tests for map_pyiceberg_error function."""

    @pytest.mark.requirement("FR-033")
    def test_service_unavailable_maps_to_catalog_unavailable(self) -> None:
        """Test ServiceUnavailableError maps to CatalogUnavailableError."""
        error = ServiceUnavailableError("Service is down")

        result = map_pyiceberg_error(
            error,
            catalog_uri="http://polaris:8181",
            operation="connect",
        )

        assert isinstance(result, CatalogUnavailableError)
        assert result.catalog_uri == "http://polaris:8181"
        assert result.cause is error

    @pytest.mark.requirement("FR-033")
    def test_unauthorized_maps_to_authentication_error(self) -> None:
        """Test UnauthorizedError maps to AuthenticationError."""
        error = UnauthorizedError("Invalid credentials")

        result = map_pyiceberg_error(error, operation="connect")

        assert isinstance(result, AuthenticationError)
        assert "Invalid credentials" in str(result)
        assert result.operation == "connect"

    @pytest.mark.requirement("FR-033")
    def test_authorization_expired_maps_to_authentication_error(self) -> None:
        """Test AuthorizationExpiredError maps to AuthenticationError."""
        error = AuthorizationExpiredError("Token expired")

        result = map_pyiceberg_error(error, operation="list_namespaces")

        assert isinstance(result, AuthenticationError)
        assert "expired" in str(result).lower()
        assert result.operation == "list_namespaces"

    @pytest.mark.requirement("FR-033")
    def test_oauth_error_maps_to_authentication_error(self) -> None:
        """Test OAuthError maps to AuthenticationError."""
        error = OAuthError("Invalid client")

        result = map_pyiceberg_error(error, operation="connect")

        assert isinstance(result, AuthenticationError)
        assert "OAuth2" in str(result)
        assert result.operation == "connect"

    @pytest.mark.requirement("FR-033")
    def test_forbidden_maps_to_authentication_error(self) -> None:
        """Test ForbiddenError maps to AuthenticationError with permission denied."""
        error = ForbiddenError("Access denied")

        result = map_pyiceberg_error(error, operation="create_namespace")

        assert isinstance(result, AuthenticationError)
        assert "Permission denied" in str(result)
        assert result.operation == "create_namespace"

    @pytest.mark.requirement("FR-033")
    def test_namespace_already_exists_maps_to_conflict_error(self) -> None:
        """Test NamespaceAlreadyExistsError maps to ConflictError."""
        error = NamespaceAlreadyExistsError("bronze")

        result = map_pyiceberg_error(error)

        assert isinstance(result, ConflictError)
        assert result.resource_type == "namespace"
        assert "bronze" in result.identifier

    @pytest.mark.requirement("FR-033")
    def test_table_already_exists_maps_to_conflict_error(self) -> None:
        """Test TableAlreadyExistsError maps to ConflictError."""
        error = TableAlreadyExistsError("bronze.customers")

        result = map_pyiceberg_error(error)

        assert isinstance(result, ConflictError)
        assert result.resource_type == "table"
        assert "customers" in result.identifier or "bronze" in result.identifier

    @pytest.mark.requirement("FR-033")
    def test_no_such_namespace_maps_to_not_found_error(self) -> None:
        """Test NoSuchNamespaceError maps to NotFoundError."""
        error = NoSuchNamespaceError("silver")

        result = map_pyiceberg_error(error)

        assert isinstance(result, NotFoundError)
        assert result.resource_type == "namespace"
        assert "silver" in result.identifier

    @pytest.mark.requirement("FR-033")
    def test_no_such_table_maps_to_not_found_error(self) -> None:
        """Test NoSuchTableError maps to NotFoundError."""
        error = NoSuchTableError("bronze.orders")

        result = map_pyiceberg_error(error)

        assert isinstance(result, NotFoundError)
        assert result.resource_type == "table"
        assert "orders" in result.identifier or "bronze" in result.identifier

    @pytest.mark.requirement("FR-033")
    def test_no_such_view_maps_to_not_found_error(self) -> None:
        """Test NoSuchViewError maps to NotFoundError."""
        error = NoSuchViewError("silver.customer_view")

        result = map_pyiceberg_error(error)

        assert isinstance(result, NotFoundError)
        assert result.resource_type == "view"

    @pytest.mark.requirement("FR-033")
    def test_no_such_identifier_maps_to_not_found_error(self) -> None:
        """Test NoSuchIdentifierError maps to NotFoundError."""
        error = NoSuchIdentifierError("unknown.resource")

        result = map_pyiceberg_error(error)

        assert isinstance(result, NotFoundError)
        assert result.resource_type == "identifier"

    @pytest.mark.requirement("FR-033")
    def test_namespace_not_empty_maps_to_not_supported_error(self) -> None:
        """Test NamespaceNotEmptyError maps to NotSupportedError."""
        error = NamespaceNotEmptyError("bronze")

        result = map_pyiceberg_error(error, catalog_uri="http://polaris:8181")

        assert isinstance(result, NotSupportedError)
        assert result.operation == "delete_namespace"
        assert "not empty" in str(result).lower()

    @pytest.mark.requirement("FR-033")
    def test_validation_error_maps_to_not_supported_error(self) -> None:
        """Test ValidationError maps to NotSupportedError."""
        error = ValidationError("Invalid schema")

        result = map_pyiceberg_error(error, operation="create_table")

        assert isinstance(result, NotSupportedError)
        assert "Validation failed" in str(result)

    @pytest.mark.requirement("FR-033")
    def test_bad_request_maps_to_not_supported_error(self) -> None:
        """Test BadRequestError maps to NotSupportedError."""
        error = BadRequestError("Invalid request body")

        result = map_pyiceberg_error(error, operation="create_namespace")

        assert isinstance(result, NotSupportedError)
        assert "Invalid request" in str(result)

    @pytest.mark.requirement("FR-033")
    def test_server_error_maps_to_catalog_unavailable(self) -> None:
        """Test ServerError maps to CatalogUnavailableError."""
        error = ServerError("Internal server error")

        result = map_pyiceberg_error(
            error,
            catalog_uri="http://polaris:8181",
        )

        assert isinstance(result, CatalogUnavailableError)
        assert result.cause is error

    @pytest.mark.requirement("FR-033")
    def test_generic_rest_error_maps_to_catalog_unavailable(self) -> None:
        """Test RESTError maps to CatalogUnavailableError."""
        error = RESTError("Unknown REST error")

        result = map_pyiceberg_error(
            error,
            catalog_uri="http://polaris:8181",
        )

        assert isinstance(result, CatalogUnavailableError)
        assert result.cause is error

    @pytest.mark.requirement("FR-033")
    def test_unknown_exception_maps_to_catalog_error(self) -> None:
        """Test unknown exceptions map to generic CatalogError.

        Unknown exceptions are wrapped in CatalogError (not CatalogUnavailableError)
        because they may indicate logic errors rather than connectivity issues.
        """
        error = RuntimeError("Some unexpected error")

        result = map_pyiceberg_error(
            error,
            catalog_uri="http://polaris:8181",
            operation="test_operation",
        )

        assert isinstance(result, CatalogError)
        assert "unexpected" in str(result).lower()
        assert "test_operation" in str(result)

    @pytest.mark.requirement("FR-033")
    def test_map_with_no_context(self) -> None:
        """Test mapping works without optional context parameters."""
        error = NoSuchNamespaceError("test")

        result = map_pyiceberg_error(error)

        assert isinstance(result, NotFoundError)

    @pytest.mark.requirement("FR-033")
    def test_map_logs_errors_appropriately(self) -> None:
        """Test that error mapping logs errors with appropriate level."""
        error = ServiceUnavailableError("Catalog down")

        with patch("floe_catalog_polaris.errors.logger") as mock_logger:
            map_pyiceberg_error(
                error,
                catalog_uri="http://polaris:8181",
            )

            mock_logger.warning.assert_called_once()


class TestPyicebergExceptionTypes:
    """Tests for PYICEBERG_EXCEPTION_TYPES tuple."""

    @pytest.mark.requirement("FR-033")
    def test_exception_types_contains_service_unavailable(self) -> None:
        """Test ServiceUnavailableError is in exception types."""
        assert ServiceUnavailableError in PYICEBERG_EXCEPTION_TYPES

    @pytest.mark.requirement("FR-033")
    def test_exception_types_contains_unauthorized(self) -> None:
        """Test UnauthorizedError is in exception types."""
        assert UnauthorizedError in PYICEBERG_EXCEPTION_TYPES

    @pytest.mark.requirement("FR-033")
    def test_exception_types_contains_forbidden(self) -> None:
        """Test ForbiddenError is in exception types."""
        assert ForbiddenError in PYICEBERG_EXCEPTION_TYPES

    @pytest.mark.requirement("FR-033")
    def test_exception_types_contains_namespace_errors(self) -> None:
        """Test namespace-related errors are in exception types."""
        assert NamespaceAlreadyExistsError in PYICEBERG_EXCEPTION_TYPES
        assert NoSuchNamespaceError in PYICEBERG_EXCEPTION_TYPES
        assert NamespaceNotEmptyError in PYICEBERG_EXCEPTION_TYPES

    @pytest.mark.requirement("FR-033")
    def test_exception_types_contains_table_errors(self) -> None:
        """Test table-related errors are in exception types."""
        assert TableAlreadyExistsError in PYICEBERG_EXCEPTION_TYPES
        assert NoSuchTableError in PYICEBERG_EXCEPTION_TYPES

    @pytest.mark.requirement("FR-033")
    def test_exception_types_contains_rest_errors(self) -> None:
        """Test REST-related errors are in exception types."""
        assert RESTError in PYICEBERG_EXCEPTION_TYPES
        assert BadRequestError in PYICEBERG_EXCEPTION_TYPES
        assert ServerError in PYICEBERG_EXCEPTION_TYPES


class TestIdentifierExtraction:
    """Tests for identifier extraction from error messages."""

    @pytest.mark.requirement("FR-033")
    def test_extract_quoted_identifier(self) -> None:
        """Test extraction of single-quoted identifier from message."""
        # PyIceberg often uses messages like "Namespace 'bronze' already exists"
        error = NamespaceAlreadyExistsError("Namespace 'bronze' already exists")

        result = map_pyiceberg_error(error)

        assert isinstance(result, ConflictError)
        assert result.identifier == "bronze"

    @pytest.mark.requirement("FR-033")
    def test_extract_simple_identifier(self) -> None:
        """Test extraction when message is just the identifier."""
        # PyIceberg sometimes uses just the identifier as the message
        error = NoSuchNamespaceError("silver")

        result = map_pyiceberg_error(error)

        assert isinstance(result, NotFoundError)
        assert result.identifier == "silver"

    @pytest.mark.requirement("FR-033")
    def test_extract_empty_message_returns_unknown(self) -> None:
        """Test empty message returns 'unknown' as identifier."""
        error = NoSuchNamespaceError("")

        result = map_pyiceberg_error(error)

        assert isinstance(result, NotFoundError)
        assert result.identifier == "unknown"


class TestConnectWithErrorMapping:
    """Integration tests for connect() with error mapping."""

    @pytest.mark.requirement("FR-033")
    def test_connect_maps_service_unavailable_error(self) -> None:
        """Test connect() maps ServiceUnavailableError correctly."""
        from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            ),
        )
        plugin = PolarisCatalogPlugin(config=config)

        with patch(
            "floe_catalog_polaris.plugin.load_catalog",
            side_effect=ServiceUnavailableError("Catalog unavailable"),
        ):
            with pytest.raises(CatalogUnavailableError) as exc_info:
                plugin.connect({})

            assert (
                exc_info.value.catalog_uri == "https://polaris.example.com/api/catalog"
            )
            assert exc_info.value.cause is not None

    @pytest.mark.requirement("FR-033")
    def test_connect_maps_unauthorized_error(self) -> None:
        """Test connect() maps UnauthorizedError correctly."""
        from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            ),
        )
        plugin = PolarisCatalogPlugin(config=config)

        with patch(
            "floe_catalog_polaris.plugin.load_catalog",
            side_effect=UnauthorizedError("Invalid credentials"),
        ):
            with pytest.raises(AuthenticationError) as exc_info:
                plugin.connect({})

            assert exc_info.value.operation == "connect"

    @pytest.mark.requirement("FR-033")
    def test_connect_maps_forbidden_error(self) -> None:
        """Test connect() maps ForbiddenError correctly."""
        from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            ),
        )
        plugin = PolarisCatalogPlugin(config=config)

        with patch(
            "floe_catalog_polaris.plugin.load_catalog",
            side_effect=ForbiddenError("Access denied"),
        ):
            with pytest.raises(AuthenticationError) as exc_info:
                plugin.connect({})

            assert "Permission denied" in str(exc_info.value)
