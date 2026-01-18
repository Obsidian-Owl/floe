"""Base test class for IdentityPlugin compliance testing.

This module provides BaseIdentityPluginTests, an abstract test class that
validates IdentityPlugin implementations meet all interface requirements.

Plugin implementations MUST pass all tests in this class to be considered
compliant with the IdentityPlugin ABC.

Usage:
    1. Create a test class that inherits from BaseIdentityPluginTests
    2. Implement the identity_plugin fixture to return your plugin instance
    3. Implement the valid_credentials fixture for authentication testing
    4. Run pytest - all base tests will be executed automatically

Example:
    >>> import pytest
    >>> from testing.base_classes import BaseIdentityPluginTests
    >>> from my_plugin import MyIdentityPlugin
    >>>
    >>> class TestMyIdentityPlugin(BaseIdentityPluginTests):
    ...     @pytest.fixture
    ...     def identity_plugin(self) -> MyIdentityPlugin:
    ...         return MyIdentityPlugin(config={...})
    ...
    ...     @pytest.fixture
    ...     def valid_credentials(self) -> dict:
    ...         return {"client_id": "...", "client_secret": "..."}

Requirements Covered:
    - 7A-FR-001: IdentityPlugin ABC implementation
    - 7A-FR-030: Token validation
    - 7A-FR-031: OIDC configuration
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.plugins.identity import IdentityPlugin


class BaseIdentityPluginTests(ABC):
    """Abstract base test class for IdentityPlugin implementations.

    Subclasses must implement the identity_plugin fixture to provide
    an instance of their IdentityPlugin implementation.

    All tests use @pytest.mark.requirement() for traceability.

    Attributes:
        identity_plugin: Fixture that returns the plugin under test.
        valid_credentials: Fixture that returns credentials for authentication.

    Example:
        >>> class TestKeycloakIdentityPlugin(BaseIdentityPluginTests):
        ...     @pytest.fixture
        ...     def identity_plugin(self):
        ...         return KeycloakIdentityPlugin(config)
        ...
        ...     @pytest.fixture
        ...     def valid_credentials(self):
        ...         return {"client_id": "test", "client_secret": "secret"}
    """

    @pytest.fixture
    @abstractmethod
    def identity_plugin(self) -> IdentityPlugin:
        """Return an instance of the IdentityPlugin to test.

        Subclasses MUST implement this fixture to provide their
        concrete plugin implementation.

        Returns:
            A configured IdentityPlugin instance ready for testing.
        """
        ...

    @pytest.fixture
    @abstractmethod
    def valid_credentials(self) -> dict[str, Any]:
        """Return valid credentials for authentication testing.

        Subclasses MUST implement this fixture to provide credentials
        that will successfully authenticate with their identity provider.

        Returns:
            Dictionary with authentication credentials.
        """
        ...

    # =========================================================================
    # Plugin Metadata Tests (7A-FR-001)
    # =========================================================================

    @pytest.mark.requirement("7A-FR-001")
    def test_has_name_property(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has a name property.

        All plugins must have a unique name identifier.
        """
        assert hasattr(identity_plugin, "name")
        assert isinstance(identity_plugin.name, str)
        assert len(identity_plugin.name) > 0

    @pytest.mark.requirement("7A-FR-001")
    def test_has_version_property(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has a version property.

        Plugin version should follow semantic versioning.
        """
        assert hasattr(identity_plugin, "version")
        assert isinstance(identity_plugin.version, str)
        assert len(identity_plugin.version) > 0

    @pytest.mark.requirement("7A-FR-001")
    def test_has_floe_api_version_property(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin declares compatible floe API version.

        This is used to check plugin compatibility with the platform.
        """
        assert hasattr(identity_plugin, "floe_api_version")
        assert isinstance(identity_plugin.floe_api_version, str)
        assert len(identity_plugin.floe_api_version) > 0

    # =========================================================================
    # Core Method Tests (7A-FR-001)
    # =========================================================================

    @pytest.mark.requirement("7A-FR-001")
    def test_has_authenticate_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has authenticate() method."""
        assert hasattr(identity_plugin, "authenticate")
        assert callable(identity_plugin.authenticate)

    @pytest.mark.requirement("7A-FR-001")
    def test_has_get_user_info_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has get_user_info() method."""
        assert hasattr(identity_plugin, "get_user_info")
        assert callable(identity_plugin.get_user_info)

    @pytest.mark.requirement("7A-FR-001")
    def test_has_validate_token_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has validate_token() method."""
        assert hasattr(identity_plugin, "validate_token")
        assert callable(identity_plugin.validate_token)

    @pytest.mark.requirement("7A-FR-001")
    def test_authenticate_returns_token_or_none(
        self, identity_plugin: IdentityPlugin
    ) -> None:
        """Verify authenticate() returns str or None for invalid creds.

        Per contract: Return None for failed authentication, not raise exception.
        """
        invalid_credentials = {"username": "invalid", "password": "invalid"}
        result = identity_plugin.authenticate(invalid_credentials)
        assert result is None

    @pytest.mark.requirement("7A-FR-001")
    def test_validate_token_returns_result(
        self, identity_plugin: IdentityPlugin
    ) -> None:
        """Verify validate_token() always returns TokenValidationResult.

        Even for invalid tokens, should return result with valid=False.
        """
        from floe_core.plugins.identity import TokenValidationResult

        result = identity_plugin.validate_token("invalid-token")

        assert isinstance(result, TokenValidationResult)
        assert hasattr(result, "valid")
        assert hasattr(result, "error")

    @pytest.mark.requirement("7A-FR-001")
    def test_invalid_token_returns_invalid_result(
        self, identity_plugin: IdentityPlugin
    ) -> None:
        """Verify invalid tokens return valid=False in result."""
        result = identity_plugin.validate_token("definitely-not-a-valid-token")
        assert result.valid is False
        # Should have error message
        assert result.error != ""

    @pytest.mark.requirement("7A-FR-001")
    def test_get_user_info_returns_userinfo_or_none(
        self, identity_plugin: IdentityPlugin
    ) -> None:
        """Verify get_user_info() returns UserInfo or None.

        For invalid tokens, should return None.
        """
        result = identity_plugin.get_user_info("invalid-token")
        assert result is None

    # =========================================================================
    # OIDC Configuration Tests (7A-FR-031)
    # =========================================================================

    @pytest.mark.requirement("7A-FR-031")
    def test_has_get_oidc_config_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has get_oidc_config() method."""
        assert hasattr(identity_plugin, "get_oidc_config")
        assert callable(identity_plugin.get_oidc_config)

    # =========================================================================
    # Lifecycle Tests
    # =========================================================================

    @pytest.mark.requirement("7A-FR-001")
    def test_has_health_check_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has health_check() method."""
        assert hasattr(identity_plugin, "health_check")
        assert callable(identity_plugin.health_check)

    @pytest.mark.requirement("7A-FR-001")
    def test_health_check_returns_health_status(self, identity_plugin: IdentityPlugin) -> None:
        """Verify health_check() returns a HealthStatus object."""
        from floe_core.plugin_metadata import HealthStatus

        health = identity_plugin.health_check()
        assert isinstance(health, HealthStatus)
        assert hasattr(health, "state")

    @pytest.mark.requirement("7A-FR-001")
    def test_has_startup_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has startup() lifecycle method."""
        assert hasattr(identity_plugin, "startup")
        assert callable(identity_plugin.startup)

    @pytest.mark.requirement("7A-FR-001")
    def test_has_shutdown_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has shutdown() lifecycle method."""
        assert hasattr(identity_plugin, "shutdown")
        assert callable(identity_plugin.shutdown)

    # =========================================================================
    # Config Schema Tests
    # =========================================================================

    @pytest.mark.requirement("7A-FR-001")
    def test_has_get_config_schema_method(self, identity_plugin: IdentityPlugin) -> None:
        """Verify plugin has get_config_schema() method."""
        assert hasattr(identity_plugin, "get_config_schema")
        assert callable(identity_plugin.get_config_schema)

    @pytest.mark.requirement("7A-FR-001")
    def test_config_schema_returns_valid_type(self, identity_plugin: IdentityPlugin) -> None:
        """Verify get_config_schema() returns None or a BaseModel class."""
        schema = identity_plugin.get_config_schema()

        if schema is not None:
            from pydantic import BaseModel

            assert isinstance(schema, type)
            assert issubclass(schema, BaseModel)


# Module exports
__all__ = ["BaseIdentityPluginTests"]
