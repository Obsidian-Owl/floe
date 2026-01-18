"""Unit tests for floe-secrets-infisical error classes.

Tests for all exception classes and their message formatting.

Task: Coverage improvement for 7a-identity-secrets
Requirements: CR-004
"""

from __future__ import annotations

import pytest

from floe_secrets_infisical.errors import (
    InfisicalAccessDeniedError,
    InfisicalAuthError,
    InfisicalBackendUnavailableError,
    InfisicalPluginError,
    InfisicalSecretNotFoundError,
    InfisicalValidationError,
)


class TestInfisicalPluginError:
    """Tests for InfisicalPluginError base class."""

    @pytest.mark.requirement("CR-004")
    def test_basic_message(self) -> None:
        """Test basic error message."""
        error = InfisicalPluginError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"

    @pytest.mark.requirement("CR-004")
    def test_is_exception(self) -> None:
        """Test that it inherits from Exception."""
        error = InfisicalPluginError("test")
        assert isinstance(error, Exception)


class TestInfisicalAuthError:
    """Tests for InfisicalAuthError."""

    @pytest.mark.requirement("CR-004")
    def test_with_reason(self) -> None:
        """Test auth error with reason."""
        error = InfisicalAuthError("Invalid client credentials")
        assert "Invalid client credentials" in str(error)
        assert "authentication failed" in str(error).lower()
        assert error.reason == "Invalid client credentials"

    @pytest.mark.requirement("CR-004")
    def test_without_reason(self) -> None:
        """Test auth error without reason."""
        error = InfisicalAuthError()
        assert "authentication failed" in str(error).lower()
        assert error.reason == ""

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_plugin_error(self) -> None:
        """Test that it inherits from InfisicalPluginError."""
        error = InfisicalAuthError("test")
        assert isinstance(error, InfisicalPluginError)


class TestInfisicalSecretNotFoundError:
    """Tests for InfisicalSecretNotFoundError."""

    @pytest.mark.requirement("CR-004")
    def test_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = InfisicalSecretNotFoundError(
            "db-password",
            path="/floe/secrets",
            environment="production",
        )
        assert "db-password" in str(error)
        assert "/floe/secrets" in str(error)
        assert "production" in str(error)
        assert error.secret_key == "db-password"
        assert error.path == "/floe/secrets"
        assert error.environment == "production"

    @pytest.mark.requirement("CR-004")
    def test_with_defaults(self) -> None:
        """Test error with default path and environment."""
        error = InfisicalSecretNotFoundError("my-secret")
        assert "my-secret" in str(error)
        assert error.path == "/"
        assert error.environment == "dev"

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_plugin_error(self) -> None:
        """Test that it inherits from InfisicalPluginError."""
        error = InfisicalSecretNotFoundError("test")
        assert isinstance(error, InfisicalPluginError)


class TestInfisicalAccessDeniedError:
    """Tests for InfisicalAccessDeniedError."""

    @pytest.mark.requirement("CR-004")
    def test_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = InfisicalAccessDeniedError(
            secret_key="admin-secret",
            project_id="proj-123",
            reason="Insufficient permissions",
        )
        assert "admin-secret" in str(error)
        assert "proj-123" in str(error)
        assert "Insufficient permissions" in str(error)
        assert error.secret_key == "admin-secret"
        assert error.project_id == "proj-123"
        assert error.reason == "Insufficient permissions"

    @pytest.mark.requirement("CR-004")
    def test_with_secret_only(self) -> None:
        """Test error with secret key only."""
        error = InfisicalAccessDeniedError(secret_key="my-secret")
        assert "my-secret" in str(error)
        assert "access denied" in str(error).lower()

    @pytest.mark.requirement("CR-004")
    def test_with_project_only(self) -> None:
        """Test error with project only."""
        error = InfisicalAccessDeniedError(project_id="proj-456")
        assert "proj-456" in str(error)

    @pytest.mark.requirement("CR-004")
    def test_with_reason_only(self) -> None:
        """Test error with reason only."""
        error = InfisicalAccessDeniedError(reason="Token expired")
        assert "Token expired" in str(error)

    @pytest.mark.requirement("CR-004")
    def test_with_no_params(self) -> None:
        """Test error with no parameters."""
        error = InfisicalAccessDeniedError()
        assert "access denied" in str(error).lower()
        assert error.secret_key == ""
        assert error.project_id == ""
        assert error.reason == ""

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_permission_error(self) -> None:
        """Test that it inherits from PermissionError."""
        error = InfisicalAccessDeniedError()
        assert isinstance(error, PermissionError)
        assert isinstance(error, InfisicalPluginError)


class TestInfisicalBackendUnavailableError:
    """Tests for InfisicalBackendUnavailableError."""

    @pytest.mark.requirement("CR-004")
    def test_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = InfisicalBackendUnavailableError(
            site_url="https://app.infisical.com",
            reason="Connection timed out",
        )
        assert "https://app.infisical.com" in str(error)
        assert "Connection timed out" in str(error)
        assert error.site_url == "https://app.infisical.com"
        assert error.reason == "Connection timed out"

    @pytest.mark.requirement("CR-004")
    def test_with_site_only(self) -> None:
        """Test error with site URL only."""
        error = InfisicalBackendUnavailableError(site_url="https://infisical.local")
        assert "https://infisical.local" in str(error)

    @pytest.mark.requirement("CR-004")
    def test_with_reason_only(self) -> None:
        """Test error with reason only."""
        error = InfisicalBackendUnavailableError(reason="DNS lookup failed")
        assert "DNS lookup failed" in str(error)

    @pytest.mark.requirement("CR-004")
    def test_with_no_params(self) -> None:
        """Test error with no parameters."""
        error = InfisicalBackendUnavailableError()
        assert "unavailable" in str(error).lower()
        assert error.site_url == ""
        assert error.reason == ""

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_connection_error(self) -> None:
        """Test that it inherits from ConnectionError."""
        error = InfisicalBackendUnavailableError()
        assert isinstance(error, ConnectionError)
        assert isinstance(error, InfisicalPluginError)


class TestInfisicalValidationError:
    """Tests for InfisicalValidationError."""

    @pytest.mark.requirement("CR-004")
    def test_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = InfisicalValidationError(
            field="secret_key",
            reason="Key must not contain special characters",
        )
        assert "secret_key" in str(error)
        assert "Key must not contain special characters" in str(error)
        assert error.field == "secret_key"
        assert error.reason == "Key must not contain special characters"

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_value_error(self) -> None:
        """Test that it inherits from ValueError."""
        error = InfisicalValidationError(field="test", reason="invalid")
        assert isinstance(error, ValueError)
        assert isinstance(error, InfisicalPluginError)


class TestExceptionHierarchy:
    """Tests for exception hierarchy and catching."""

    @pytest.mark.requirement("CR-004")
    def test_catch_all_plugin_errors(self) -> None:
        """Test that all errors can be caught as InfisicalPluginError."""
        errors = [
            InfisicalAuthError("test"),
            InfisicalSecretNotFoundError("test"),
            InfisicalAccessDeniedError(),
            InfisicalBackendUnavailableError(),
            InfisicalValidationError(field="test", reason="test"),
        ]

        for error in errors:
            assert isinstance(error, InfisicalPluginError)

    @pytest.mark.requirement("CR-004")
    def test_catch_permission_error(self) -> None:
        """Test that AccessDeniedError can be caught as PermissionError."""
        error = InfisicalAccessDeniedError()

        with pytest.raises(PermissionError):
            raise error

    @pytest.mark.requirement("CR-004")
    def test_catch_connection_error(self) -> None:
        """Test that BackendUnavailableError can be caught as ConnectionError."""
        error = InfisicalBackendUnavailableError()

        with pytest.raises(ConnectionError):
            raise error
