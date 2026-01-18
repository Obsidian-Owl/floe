"""Unit tests for floe-secrets-infisical package __init__.py.

Tests for lazy imports and module-level attributes.

Task: Coverage improvement for 7a-identity-secrets
"""

from __future__ import annotations

import pytest


class TestLazyImports:
    """Tests for lazy import functionality."""

    @pytest.mark.requirement("CR-004")
    def test_import_infisical_secrets_plugin(self) -> None:
        """Test lazy import of InfisicalSecretsPlugin."""
        from floe_secrets_infisical import InfisicalSecretsPlugin

        assert InfisicalSecretsPlugin is not None
        assert hasattr(InfisicalSecretsPlugin, "get_secret")

    @pytest.mark.requirement("CR-004")
    def test_import_infisical_secrets_config(self) -> None:
        """Test lazy import of InfisicalSecretsConfig."""
        from floe_secrets_infisical import InfisicalSecretsConfig

        assert InfisicalSecretsConfig is not None

    @pytest.mark.requirement("CR-004")
    def test_import_plugin_error(self) -> None:
        """Test lazy import of InfisicalPluginError."""
        from floe_secrets_infisical import InfisicalPluginError

        assert InfisicalPluginError is not None
        assert issubclass(InfisicalPluginError, Exception)

    @pytest.mark.requirement("CR-004")
    def test_import_auth_error(self) -> None:
        """Test lazy import of InfisicalAuthError."""
        from floe_secrets_infisical import InfisicalAuthError

        assert InfisicalAuthError is not None
        assert issubclass(InfisicalAuthError, Exception)

    @pytest.mark.requirement("CR-004")
    def test_import_secret_not_found_error(self) -> None:
        """Test lazy import of InfisicalSecretNotFoundError."""
        from floe_secrets_infisical import InfisicalSecretNotFoundError

        assert InfisicalSecretNotFoundError is not None
        assert issubclass(InfisicalSecretNotFoundError, Exception)

    @pytest.mark.requirement("CR-004")
    def test_import_access_denied_error(self) -> None:
        """Test lazy import of InfisicalAccessDeniedError."""
        from floe_secrets_infisical import InfisicalAccessDeniedError

        assert InfisicalAccessDeniedError is not None
        assert issubclass(InfisicalAccessDeniedError, PermissionError)

    @pytest.mark.requirement("CR-004")
    def test_import_backend_unavailable_error(self) -> None:
        """Test lazy import of InfisicalBackendUnavailableError."""
        from floe_secrets_infisical import InfisicalBackendUnavailableError

        assert InfisicalBackendUnavailableError is not None
        assert issubclass(InfisicalBackendUnavailableError, ConnectionError)

    @pytest.mark.requirement("CR-004")
    def test_import_validation_error(self) -> None:
        """Test lazy import of InfisicalValidationError."""
        from floe_secrets_infisical import InfisicalValidationError

        assert InfisicalValidationError is not None
        assert issubclass(InfisicalValidationError, ValueError)

    @pytest.mark.requirement("CR-004")
    def test_invalid_attribute_raises_error(self) -> None:
        """Test that invalid attribute raises AttributeError."""
        import floe_secrets_infisical

        with pytest.raises(AttributeError) as exc_info:
            _ = floe_secrets_infisical.NonExistentAttribute  # type: ignore[attr-defined]

        assert "NonExistentAttribute" in str(exc_info.value)


class TestModuleAttributes:
    """Tests for module-level attributes."""

    @pytest.mark.requirement("CR-004")
    def test_version_attribute(self) -> None:
        """Test __version__ attribute."""
        import floe_secrets_infisical

        assert hasattr(floe_secrets_infisical, "__version__")
        assert isinstance(floe_secrets_infisical.__version__, str)

    @pytest.mark.requirement("CR-004")
    def test_all_attribute(self) -> None:
        """Test __all__ attribute contains expected exports."""
        import floe_secrets_infisical

        assert hasattr(floe_secrets_infisical, "__all__")
        expected = [
            "InfisicalSecretsPlugin",
            "InfisicalSecretsConfig",
            "InfisicalPluginError",
            "InfisicalAuthError",
            "InfisicalSecretNotFoundError",
            "InfisicalAccessDeniedError",
            "InfisicalBackendUnavailableError",
            "InfisicalValidationError",
        ]
        for name in expected:
            assert name in floe_secrets_infisical.__all__
