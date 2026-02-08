"""Unit tests for Keycloak plugin custom exceptions.

Task: T063
Requirements: 7A-CR-004 (Error handling requirements)
"""

from __future__ import annotations

import pytest


class TestKeycloakPluginError:
    """Tests for the base KeycloakPluginError exception."""

    @pytest.mark.requirement("7A-CR-004")
    def test_basic_error(self) -> None:
        """Test basic error with message only."""
        from floe_identity_keycloak.errors import KeycloakPluginError

        error = KeycloakPluginError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details is None

    @pytest.mark.requirement("7A-CR-004")
    def test_error_with_details(self) -> None:
        """Test error with details."""
        from floe_identity_keycloak.errors import KeycloakPluginError

        error = KeycloakPluginError("Failed", details="See server logs")

        assert str(error) == "Failed: See server logs"
        assert error.message == "Failed"
        assert error.details == "See server logs"

    @pytest.mark.requirement("7A-CR-004")
    def test_error_is_exception(self) -> None:
        """Test that KeycloakPluginError is an Exception."""
        from floe_identity_keycloak.errors import KeycloakPluginError

        error = KeycloakPluginError("Test")

        assert isinstance(error, Exception)


class TestKeycloakConfigError:
    """Tests for KeycloakConfigError exception."""

    @pytest.mark.requirement("7A-CR-004")
    def test_config_error_inheritance(self) -> None:
        """Test that KeycloakConfigError inherits from KeycloakPluginError."""
        from floe_identity_keycloak.errors import (
            KeycloakConfigError,
            KeycloakPluginError,
        )

        error = KeycloakConfigError("Invalid configuration")

        assert isinstance(error, KeycloakPluginError)
        assert isinstance(error, Exception)

    @pytest.mark.requirement("7A-CR-004")
    def test_config_error_message(self) -> None:
        """Test KeycloakConfigError message."""
        from floe_identity_keycloak.errors import KeycloakConfigError

        error = KeycloakConfigError(
            "Invalid server URL",
            details="URL must start with https://",
        )

        assert str(error) == "Invalid server URL: URL must start with https://"

    @pytest.mark.requirement("7A-CR-004")
    def test_catch_as_base_error(self) -> None:
        """Test that KeycloakConfigError can be caught as KeycloakPluginError."""
        from floe_identity_keycloak.errors import (
            KeycloakConfigError,
            KeycloakPluginError,
        )

        with pytest.raises(KeycloakPluginError):
            raise KeycloakConfigError("Config error")


class TestKeycloakAuthError:
    """Tests for KeycloakAuthError exception."""

    @pytest.mark.requirement("7A-CR-004")
    def test_auth_error_inheritance(self) -> None:
        """Test that KeycloakAuthError inherits from KeycloakPluginError."""
        from floe_identity_keycloak.errors import (
            KeycloakAuthError,
            KeycloakPluginError,
        )

        error = KeycloakAuthError("Authentication failed")

        assert isinstance(error, KeycloakPluginError)

    @pytest.mark.requirement("7A-CR-004")
    def test_auth_error_with_code(self) -> None:
        """Test KeycloakAuthError with error code."""
        from floe_identity_keycloak.errors import KeycloakAuthError

        error = KeycloakAuthError(
            "Authentication failed",
            error_code="invalid_grant",
            details="Invalid password",
        )

        assert str(error) == "Authentication failed: Invalid password (code: invalid_grant)"
        assert error.error_code == "invalid_grant"
        assert error.details == "Invalid password"

    @pytest.mark.requirement("7A-CR-004")
    def test_auth_error_without_code(self) -> None:
        """Test KeycloakAuthError without error code."""
        from floe_identity_keycloak.errors import KeycloakAuthError

        error = KeycloakAuthError("Failed")

        assert str(error) == "Failed"
        assert error.error_code is None

    @pytest.mark.requirement("7A-CR-004")
    def test_auth_error_code_only(self) -> None:
        """Test KeycloakAuthError with code but no details."""
        from floe_identity_keycloak.errors import KeycloakAuthError

        error = KeycloakAuthError("Failed", error_code="access_denied")

        assert str(error) == "Failed (code: access_denied)"


class TestKeycloakTokenError:
    """Tests for KeycloakTokenError exception."""

    @pytest.mark.requirement("7A-CR-004")
    def test_token_error_inheritance(self) -> None:
        """Test that KeycloakTokenError inherits from KeycloakPluginError."""
        from floe_identity_keycloak.errors import (
            KeycloakPluginError,
            KeycloakTokenError,
        )

        error = KeycloakTokenError("Token validation failed")

        assert isinstance(error, KeycloakPluginError)

    @pytest.mark.requirement("7A-CR-004")
    def test_token_error_with_reason(self) -> None:
        """Test KeycloakTokenError with reason."""
        from floe_identity_keycloak.errors import KeycloakTokenError

        error = KeycloakTokenError(
            "Token validation failed",
            reason="expired",
            details="Token expired at 2026-01-18T00:00:00Z",
        )

        assert str(error) == (
            "Token validation failed: Token expired at 2026-01-18T00:00:00Z (reason: expired)"
        )
        assert error.reason == "expired"

    @pytest.mark.requirement("7A-CR-004")
    def test_token_error_without_reason(self) -> None:
        """Test KeycloakTokenError without reason."""
        from floe_identity_keycloak.errors import KeycloakTokenError

        error = KeycloakTokenError("Invalid token")

        assert str(error) == "Invalid token"
        assert error.reason is None

    @pytest.mark.requirement("7A-CR-004")
    def test_token_error_reason_only(self) -> None:
        """Test KeycloakTokenError with reason but no details."""
        from floe_identity_keycloak.errors import KeycloakTokenError

        error = KeycloakTokenError("Failed", reason="invalid_signature")

        assert str(error) == "Failed (reason: invalid_signature)"


class TestKeycloakUnavailableError:
    """Tests for KeycloakUnavailableError exception."""

    @pytest.mark.requirement("7A-CR-004")
    def test_unavailable_error_inheritance(self) -> None:
        """Test that KeycloakUnavailableError inherits from KeycloakPluginError."""
        from floe_identity_keycloak.errors import (
            KeycloakPluginError,
            KeycloakUnavailableError,
        )

        error = KeycloakUnavailableError("Server unavailable")

        assert isinstance(error, KeycloakPluginError)

    @pytest.mark.requirement("7A-CR-004")
    def test_unavailable_error_with_original(self) -> None:
        """Test KeycloakUnavailableError with original exception."""
        from floe_identity_keycloak.errors import KeycloakUnavailableError

        original = ConnectionError("Connection refused")
        error = KeycloakUnavailableError(
            "Cannot connect to Keycloak",
            original_error=original,
        )

        assert str(error) == "Cannot connect to Keycloak (caused by: ConnectionError)"
        assert error.original_error is original

    @pytest.mark.requirement("7A-CR-004")
    def test_unavailable_error_without_original(self) -> None:
        """Test KeycloakUnavailableError without original exception."""
        from floe_identity_keycloak.errors import KeycloakUnavailableError

        error = KeycloakUnavailableError("Server timeout")

        assert str(error) == "Server timeout"
        assert error.original_error is None

    @pytest.mark.requirement("7A-CR-004")
    def test_unavailable_error_with_details_and_original(self) -> None:
        """Test KeycloakUnavailableError with both details and original."""
        from floe_identity_keycloak.errors import KeycloakUnavailableError

        original = TimeoutError("Timed out")
        error = KeycloakUnavailableError(
            "Connection failed",
            original_error=original,
            details="After 30 retries",
        )

        assert str(error) == "Connection failed: After 30 retries (caused by: TimeoutError)"


class TestExceptionImports:
    """Tests for exception imports from package root."""

    @pytest.mark.requirement("7A-CR-004")
    def test_import_from_package(self) -> None:
        """Test that exceptions can be imported from package root."""
        from floe_identity_keycloak import (
            KeycloakAuthError,
            KeycloakConfigError,
            KeycloakPluginError,
            KeycloakTokenError,
            KeycloakUnavailableError,
        )

        # Verify all can be instantiated
        assert KeycloakPluginError("test")
        assert KeycloakConfigError("test")
        assert KeycloakAuthError("test")
        assert KeycloakTokenError("test")
        assert KeycloakUnavailableError("test")

    @pytest.mark.requirement("7A-CR-004")
    def test_import_from_errors_module(self) -> None:
        """Test that exceptions can be imported from errors module."""
        from floe_identity_keycloak.errors import (
            KeycloakAuthError,
            KeycloakConfigError,
            KeycloakPluginError,
            KeycloakTokenError,
            KeycloakUnavailableError,
        )

        # Verify all can be instantiated
        assert KeycloakPluginError("test")
        assert KeycloakConfigError("test")
        assert KeycloakAuthError("test")
        assert KeycloakTokenError("test")
        assert KeycloakUnavailableError("test")
