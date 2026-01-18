"""Unit tests for floe-identity-keycloak package __init__.py.

Tests for lazy imports and module-level attributes.

Task: Coverage improvement for 7a-identity-secrets
"""

from __future__ import annotations

import pytest


class TestLazyImports:
    """Tests for lazy import functionality."""

    @pytest.mark.requirement("FR-034")
    def test_import_keycloak_identity_plugin(self) -> None:
        """Test lazy import of KeycloakIdentityPlugin."""
        from floe_identity_keycloak import KeycloakIdentityPlugin

        assert KeycloakIdentityPlugin is not None
        assert hasattr(KeycloakIdentityPlugin, "validate_token")

    @pytest.mark.requirement("FR-034")
    def test_import_keycloak_identity_config(self) -> None:
        """Test lazy import of KeycloakIdentityConfig."""
        from floe_identity_keycloak import KeycloakIdentityConfig

        assert KeycloakIdentityConfig is not None

    @pytest.mark.requirement("FR-034")
    def test_import_plugin_error(self) -> None:
        """Test lazy import of KeycloakPluginError."""
        from floe_identity_keycloak import KeycloakPluginError

        assert KeycloakPluginError is not None
        assert issubclass(KeycloakPluginError, Exception)

    @pytest.mark.requirement("FR-034")
    def test_import_config_error(self) -> None:
        """Test lazy import of KeycloakConfigError."""
        from floe_identity_keycloak import KeycloakConfigError

        assert KeycloakConfigError is not None
        assert issubclass(KeycloakConfigError, Exception)

    @pytest.mark.requirement("FR-034")
    def test_import_auth_error(self) -> None:
        """Test lazy import of KeycloakAuthError."""
        from floe_identity_keycloak import KeycloakAuthError

        assert KeycloakAuthError is not None
        assert issubclass(KeycloakAuthError, Exception)

    @pytest.mark.requirement("FR-034")
    def test_import_token_error(self) -> None:
        """Test lazy import of KeycloakTokenError."""
        from floe_identity_keycloak import KeycloakTokenError

        assert KeycloakTokenError is not None
        assert issubclass(KeycloakTokenError, Exception)

    @pytest.mark.requirement("FR-034")
    def test_import_unavailable_error(self) -> None:
        """Test lazy import of KeycloakUnavailableError."""
        from floe_identity_keycloak import KeycloakUnavailableError

        assert KeycloakUnavailableError is not None
        assert issubclass(KeycloakUnavailableError, Exception)

    @pytest.mark.requirement("FR-034")
    def test_invalid_attribute_raises_error(self) -> None:
        """Test that invalid attribute raises AttributeError."""
        import floe_identity_keycloak

        with pytest.raises(AttributeError) as exc_info:
            _ = floe_identity_keycloak.NonExistentAttribute  # type: ignore[attr-defined]

        assert "NonExistentAttribute" in str(exc_info.value)


class TestModuleAttributes:
    """Tests for module-level attributes."""

    @pytest.mark.requirement("FR-034")
    def test_version_attribute(self) -> None:
        """Test __version__ attribute."""
        import floe_identity_keycloak

        assert hasattr(floe_identity_keycloak, "__version__")
        assert isinstance(floe_identity_keycloak.__version__, str)

    @pytest.mark.requirement("FR-034")
    def test_all_attribute(self) -> None:
        """Test __all__ attribute contains expected exports."""
        import floe_identity_keycloak

        assert hasattr(floe_identity_keycloak, "__all__")
        expected = [
            "KeycloakIdentityPlugin",
            "KeycloakIdentityConfig",
            "KeycloakPluginError",
            "KeycloakConfigError",
            "KeycloakAuthError",
            "KeycloakTokenError",
            "KeycloakUnavailableError",
        ]
        for name in expected:
            assert name in floe_identity_keycloak.__all__
