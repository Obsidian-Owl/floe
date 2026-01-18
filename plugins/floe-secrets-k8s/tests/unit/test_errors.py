"""Unit tests for floe-secrets-k8s error classes.

Tests for all exception classes and their message formatting.

Task: Coverage improvement for 7a-identity-secrets
Requirements: CR-004
"""

from __future__ import annotations

import pytest

from floe_secrets_k8s.errors import (
    SecretAccessDeniedError,
    SecretBackendUnavailableError,
    SecretNotFoundError,
    SecretsPluginError,
    SecretValidationError,
)


class TestSecretsPluginError:
    """Tests for SecretsPluginError base class."""

    @pytest.mark.requirement("CR-004")
    def test_basic_message(self) -> None:
        """Test basic error message."""
        error = SecretsPluginError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"

    @pytest.mark.requirement("CR-004")
    def test_is_exception(self) -> None:
        """Test that it inherits from Exception."""
        error = SecretsPluginError("test")
        assert isinstance(error, Exception)


class TestSecretNotFoundError:
    """Tests for SecretNotFoundError."""

    @pytest.mark.requirement("CR-004")
    def test_with_namespace(self) -> None:
        """Test error with custom namespace."""
        error = SecretNotFoundError("db-password", namespace="production")
        assert "db-password" in str(error)
        assert "production" in str(error)
        assert error.secret_name == "db-password"
        assert error.namespace == "production"

    @pytest.mark.requirement("CR-004")
    def test_with_default_namespace(self) -> None:
        """Test error with default namespace."""
        error = SecretNotFoundError("my-secret")
        assert "my-secret" in str(error)
        assert "default" in str(error)
        assert error.namespace == "default"

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_plugin_error(self) -> None:
        """Test that it inherits from SecretsPluginError."""
        error = SecretNotFoundError("test")
        assert isinstance(error, SecretsPluginError)


class TestSecretAccessDeniedError:
    """Tests for SecretAccessDeniedError."""

    @pytest.mark.requirement("CR-004")
    def test_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = SecretAccessDeniedError(
            "admin-secret",
            namespace="kube-system",
            reason="ServiceAccount lacks 'get' permission",
        )
        assert "admin-secret" in str(error)
        assert "kube-system" in str(error)
        assert "ServiceAccount lacks 'get' permission" in str(error)
        assert error.secret_name == "admin-secret"
        assert error.namespace == "kube-system"
        assert error.reason == "ServiceAccount lacks 'get' permission"

    @pytest.mark.requirement("CR-004")
    def test_with_default_namespace(self) -> None:
        """Test error with default namespace."""
        error = SecretAccessDeniedError("my-secret")
        assert "my-secret" in str(error)
        assert "default" in str(error)
        assert error.namespace == "default"
        assert error.reason == ""

    @pytest.mark.requirement("CR-004")
    def test_without_reason(self) -> None:
        """Test error without reason."""
        error = SecretAccessDeniedError("test", namespace="prod")
        assert "Access denied" in str(error)
        assert error.reason == ""

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_permission_error(self) -> None:
        """Test that it inherits from PermissionError."""
        error = SecretAccessDeniedError("test")
        assert isinstance(error, PermissionError)
        assert isinstance(error, SecretsPluginError)


class TestSecretBackendUnavailableError:
    """Tests for SecretBackendUnavailableError."""

    @pytest.mark.requirement("CR-004")
    def test_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = SecretBackendUnavailableError(
            endpoint="https://kubernetes.default.svc",
            reason="Connection timed out",
        )
        assert "https://kubernetes.default.svc" in str(error)
        assert "Connection timed out" in str(error)
        assert error.endpoint == "https://kubernetes.default.svc"
        assert error.reason == "Connection timed out"

    @pytest.mark.requirement("CR-004")
    def test_with_endpoint_only(self) -> None:
        """Test error with endpoint only."""
        error = SecretBackendUnavailableError(endpoint="https://k8s.local")
        assert "https://k8s.local" in str(error)

    @pytest.mark.requirement("CR-004")
    def test_with_reason_only(self) -> None:
        """Test error with reason only."""
        error = SecretBackendUnavailableError(reason="SSL certificate expired")
        assert "SSL certificate expired" in str(error)

    @pytest.mark.requirement("CR-004")
    def test_with_no_params(self) -> None:
        """Test error with no parameters."""
        error = SecretBackendUnavailableError()
        assert "unavailable" in str(error).lower()
        assert error.endpoint == ""
        assert error.reason == ""

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_connection_error(self) -> None:
        """Test that it inherits from ConnectionError."""
        error = SecretBackendUnavailableError()
        assert isinstance(error, ConnectionError)
        assert isinstance(error, SecretsPluginError)


class TestSecretValidationError:
    """Tests for SecretValidationError."""

    @pytest.mark.requirement("CR-004")
    def test_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = SecretValidationError(
            field="secret_name",
            reason="Name must be lowercase alphanumeric",
        )
        assert "secret_name" in str(error)
        assert "Name must be lowercase alphanumeric" in str(error)
        assert error.field == "secret_name"
        assert error.reason == "Name must be lowercase alphanumeric"

    @pytest.mark.requirement("CR-004")
    def test_inherits_from_value_error(self) -> None:
        """Test that it inherits from ValueError."""
        error = SecretValidationError(field="test", reason="invalid")
        assert isinstance(error, ValueError)
        assert isinstance(error, SecretsPluginError)


class TestExceptionHierarchy:
    """Tests for exception hierarchy and catching."""

    @pytest.mark.requirement("CR-004")
    def test_catch_all_plugin_errors(self) -> None:
        """Test that all errors can be caught as SecretsPluginError."""
        errors = [
            SecretNotFoundError("test"),
            SecretAccessDeniedError("test"),
            SecretBackendUnavailableError(),
            SecretValidationError(field="test", reason="test"),
        ]

        for error in errors:
            assert isinstance(error, SecretsPluginError)

    @pytest.mark.requirement("CR-004")
    def test_catch_permission_error(self) -> None:
        """Test that AccessDeniedError can be caught as PermissionError."""
        error = SecretAccessDeniedError("test")

        with pytest.raises(PermissionError):
            raise error

    @pytest.mark.requirement("CR-004")
    def test_catch_connection_error(self) -> None:
        """Test that BackendUnavailableError can be caught as ConnectionError."""
        error = SecretBackendUnavailableError()

        with pytest.raises(ConnectionError):
            raise error
