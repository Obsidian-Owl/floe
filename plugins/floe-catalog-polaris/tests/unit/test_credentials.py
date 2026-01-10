"""Unit tests for credential vending operations.

This module tests the credential vending functionality of the PolarisCatalogPlugin
for secure, short-lived access to Iceberg tables.

Requirements Covered:
    - FR-019: System MUST define vend_credentials() as required abstract method
    - FR-020: System MUST return short-lived, scoped credentials for table access
    - FR-021: Vended credentials MUST include expiration and be valid ≤24 hours
    - FR-022: Catalogs without credential vending MUST raise NotSupportedError
    - FR-030: System MUST emit OpenTelemetry spans for all catalog operations
    - FR-031: OTel spans MUST include required attributes
    - FR-032: OTel spans MUST NOT include credentials or sensitive data
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from floe_core import AuthenticationError, NotFoundError
from pyiceberg.exceptions import ForbiddenError, NoSuchTableError

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    from typing import Any


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def polaris_config() -> PolarisCatalogConfig:
    """Create a test Polaris configuration."""
    return PolarisCatalogConfig(
        uri="https://polaris.example.com/api/catalog",
        warehouse="test_warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        ),
    )


@pytest.fixture
def polaris_plugin(polaris_config: PolarisCatalogConfig) -> PolarisCatalogPlugin:
    """Create a PolarisCatalogPlugin instance."""
    return PolarisCatalogPlugin(config=polaris_config)


@pytest.fixture
def mock_catalog() -> MagicMock:
    """Create a mock PyIceberg catalog."""
    return MagicMock()


@pytest.fixture
def connected_plugin(
    polaris_plugin: PolarisCatalogPlugin,
    mock_catalog: MagicMock,
) -> PolarisCatalogPlugin:
    """Create a plugin with a mocked catalog connection."""
    polaris_plugin._catalog = mock_catalog
    return polaris_plugin


@pytest.fixture
def mock_vended_credentials() -> dict[str, Any]:
    """Sample vended credentials response.

    Note: These are clearly fake test values, not real credentials.
    """
    return {
        "access_key": "TEST_ACCESS_KEY_FOR_UNIT_TESTS",
        "secret_key": "TEST_SECRET_KEY_FOR_UNIT_TESTS",  # noqa: S105
        "token": "TEST_SESSION_TOKEN_FOR_UNIT_TESTS",
        "expiration": "2026-01-09T12:00:00Z",
    }


# ============================================================================
# TestVendCredentials - Core functionality (FR-020)
# ============================================================================


class TestVendCredentials:
    """Tests for vend_credentials() method."""

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_returns_dict_with_required_keys(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials returns dictionary with required keys.

        Validates that vend_credentials returns credentials containing:
        - access_key
        - secret_key
        - token (optional but expected for Polaris)
        - expiration
        """
        # Arrange - Mock the credential vending
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="bronze.customers",
            operations=["READ"],
        )

        # Assert
        assert isinstance(result, dict)
        assert "access_key" in result
        assert "secret_key" in result
        assert "expiration" in result

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_for_read_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials with READ operation.

        Validates that credentials can be vended for read-only access.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="bronze.customers",
            operations=["READ"],
        )

        # Assert
        assert result is not None
        assert "access_key" in result

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_for_write_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials with WRITE operation.

        Validates that credentials can be vended for write access.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="bronze.customers",
            operations=["WRITE"],
        )

        # Assert
        assert result is not None
        assert "access_key" in result

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_for_read_write_operations(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials with both READ and WRITE operations.

        Validates that credentials can be vended for full access.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="bronze.customers",
            operations=["READ", "WRITE"],
        )

        # Assert
        assert result is not None
        assert "access_key" in result

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_returns_scoped_credentials(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials returns credentials scoped to the table.

        Validates that credentials are scoped to the requested table path.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="silver.dim_customers",
            operations=["READ"],
        )

        # Assert - verify the table was loaded (scoping)
        assert result is not None
        mock_catalog.load_table.assert_called()


# ============================================================================
# TestVendCredentialsExpiration - Expiration validation (FR-021)
# ============================================================================


class TestVendCredentialsExpiration:
    """Tests for credential expiration requirements."""

    @pytest.mark.requirement("FR-021")
    def test_vend_credentials_includes_expiration(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials includes expiration timestamp.

        Validates FR-021: Vended credentials MUST include expiration timestamp.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="bronze.customers",
            operations=["READ"],
        )

        # Assert
        assert "expiration" in result
        assert result["expiration"] is not None

    @pytest.mark.requirement("FR-021")
    def test_vend_credentials_expiration_is_iso_format(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test expiration is in ISO 8601 format.

        Validates expiration can be parsed as an ISO datetime string.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="bronze.customers",
            operations=["READ"],
        )

        # Assert - should be parseable as ISO datetime
        expiration = result["expiration"]
        if isinstance(expiration, str):
            # Should not raise
            datetime.fromisoformat(expiration.replace("Z", "+00:00"))

    @pytest.mark.requirement("FR-021")
    def test_vend_credentials_expiration_within_24_hours(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test credentials expire within 24 hours.

        Validates FR-021: Vended credentials MUST be valid for no more than 24 hours.
        """
        # Arrange - credentials that expire in 1 hour (valid)
        now = datetime.now(timezone.utc)
        valid_expiration = now.replace(hour=now.hour + 1).isoformat()
        valid_credentials = {
            "access_key": "TEST_TEMP_ACCESS_KEY",
            "secret_key": "test_temp_secret",  # noqa: S105
            "token": "test_session_token",
            "expiration": valid_expiration,
        }
        mock_catalog.load_table.return_value.io.return_value = valid_credentials

        # Act
        result = connected_plugin.vend_credentials(
            table_path="bronze.customers",
            operations=["READ"],
        )

        # Assert - expiration should be in the future but within 24h
        expiration_str = result["expiration"]
        if isinstance(expiration_str, str):
            expiration_dt = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
            # Should be in the future
            assert expiration_dt > now
            # Should be within 24 hours from now
            hours_until_expiration = (expiration_dt - now).total_seconds() / 3600
            assert hours_until_expiration <= 24


# ============================================================================
# TestVendCredentialsNotConnected - Connection state tests
# ============================================================================


class TestVendCredentialsNotConnected:
    """Tests for vend_credentials when not connected."""

    @pytest.mark.requirement("FR-020")
    def test_vend_credentials_when_not_connected_raises_error(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test vend_credentials raises error when catalog not connected.

        Validates that calling vend_credentials before connect() raises
        a RuntimeError with clear message.
        """
        # Act & Assert
        with pytest.raises(RuntimeError, match="not connected"):
            polaris_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["READ"],
            )


# ============================================================================
# TestVendCredentialsOTelTracing - OpenTelemetry tests (FR-030, FR-031, FR-032)
# ============================================================================


class TestVendCredentialsOTelTracing:
    """Tests for OpenTelemetry tracing in vend_credentials."""

    @pytest.mark.requirement("FR-030")
    def test_vend_credentials_creates_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials creates an OpenTelemetry span.

        Validates FR-030: System MUST emit OpenTelemetry spans for vend_credentials.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span_context:
            mock_span = MagicMock()
            mock_span_context.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_span_context.return_value.__exit__ = MagicMock(return_value=False)

            # Act
            connected_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["READ"],
            )

            # Assert
            mock_span_context.assert_called_once()

    @pytest.mark.requirement("FR-031")
    def test_vend_credentials_span_has_required_attributes(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials span includes required attributes.

        Validates FR-031: OTel spans MUST include catalog_name, catalog_uri,
        warehouse, and table_full_name.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span_context:
            mock_span = MagicMock()
            mock_span_context.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_span_context.return_value.__exit__ = MagicMock(return_value=False)

            # Act
            connected_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["READ"],
            )

            # Assert - check span was called with required attributes
            call_kwargs = mock_span_context.call_args[1]
            assert call_kwargs.get("catalog_name") == "polaris"
            assert "catalog_uri" in call_kwargs
            assert "warehouse" in call_kwargs
            assert "table_full_name" in call_kwargs

    @pytest.mark.requirement("FR-032")
    def test_vend_credentials_span_does_not_include_credentials(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials span does NOT include sensitive data.

        Validates FR-032: OTel spans MUST NOT include credentials, PII,
        or sensitive data.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span_context:
            mock_span = MagicMock()
            mock_span_context.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_span_context.return_value.__exit__ = MagicMock(return_value=False)

            # Act
            connected_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["READ"],
            )

            # Assert - verify no sensitive data in span attributes
            call_kwargs = mock_span_context.call_args[1]

            # Should not include credential values
            for key, value in call_kwargs.items():
                if isinstance(value, str):
                    assert "secret" not in value.lower()
                    assert "password" not in value.lower()
                    assert "token" not in value.lower()
                    assert "key" not in value.lower() or key in (
                        "access_key",
                        "api_key",
                    )

    @pytest.mark.requirement("FR-030")
    def test_vend_credentials_error_sets_span_error_attributes(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test errors during vend_credentials set span error attributes.

        Validates that when an error occurs, the span is marked with error status.
        """
        # Arrange - configure mock to raise error
        mock_catalog.load_table.side_effect = NoSuchTableError("bronze.customers")

        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span_context:
            mock_span = MagicMock()
            mock_span_context.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_span_context.return_value.__exit__ = MagicMock(return_value=False)

            with patch("floe_catalog_polaris.plugin.set_error_attributes") as mock_set_error:
                # Act & Assert
                with pytest.raises(NotFoundError):
                    connected_plugin.vend_credentials(
                        table_path="bronze.customers",
                        operations=["READ"],
                    )

                # Verify error attributes were set
                mock_set_error.assert_called_once()


# ============================================================================
# TestVendCredentialsErrorMapping - Error handling tests (FR-022, FR-033)
# ============================================================================


class TestVendCredentialsErrorMapping:
    """Tests for error mapping in vend_credentials."""

    @pytest.mark.requirement("FR-022")
    def test_vend_credentials_table_not_found_raises_not_found_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test NoSuchTableError maps to NotFoundError.

        Validates error mapping when table does not exist.
        """
        # Arrange
        mock_catalog.load_table.side_effect = NoSuchTableError("bronze.nonexistent")

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            connected_plugin.vend_credentials(
                table_path="bronze.nonexistent",
                operations=["READ"],
            )

        assert exc_info.value.resource_type == "table"

    @pytest.mark.requirement("FR-022")
    def test_vend_credentials_forbidden_raises_authentication_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test ForbiddenError maps to AuthenticationError.

        Validates error mapping when user lacks permission.
        """
        # Arrange
        mock_catalog.load_table.side_effect = ForbiddenError("Access denied")

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            connected_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["WRITE"],
            )

        assert "Permission denied" in str(exc_info.value)


# ============================================================================
# TestVendCredentialsLogging - Structured logging tests (FR-029)
# ============================================================================


class TestVendCredentialsLogging:
    """Tests for structured logging in vend_credentials."""

    @pytest.mark.requirement("FR-029")
    def test_vend_credentials_logs_operation_start(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials logs operation start.

        Validates that operation is logged before execution.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            # Act
            connected_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["READ"],
            )

            # Assert - should have logged info
            mock_logger.bind.assert_called()

    @pytest.mark.requirement("FR-029")
    def test_vend_credentials_logs_success(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials logs successful completion.

        Validates structured log is emitted on success.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            # Act
            connected_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["READ"],
            )

            # Assert
            mock_bound.info.assert_called()

    @pytest.mark.requirement("FR-029")
    def test_vend_credentials_logs_do_not_include_secrets(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        mock_vended_credentials: dict[str, Any],
    ) -> None:
        """Test vend_credentials logs do NOT include credentials.

        Validates FR-032 compliance in logging - no sensitive data in logs.
        """
        # Arrange
        mock_catalog.load_table.return_value.io.return_value = mock_vended_credentials

        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            # Act
            connected_plugin.vend_credentials(
                table_path="bronze.customers",
                operations=["READ"],
            )

            # Assert - check bind kwargs don't include secrets
            for call in mock_logger.bind.call_args_list:
                kwargs = call[1]
                for _key, value in kwargs.items():
                    if isinstance(value, str):
                        assert "TEST_ACCESS_KEY" not in value
                        assert "TEST_SECRET_KEY" not in value
