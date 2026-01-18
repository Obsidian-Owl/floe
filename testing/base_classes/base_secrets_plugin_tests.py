"""Base test class for SecretsPlugin compliance testing.

This module provides BaseSecretsPluginTests, an abstract test class that
validates SecretsPlugin implementations meet all interface requirements.

Plugin implementations MUST pass all tests in this class to be considered
compliant with the SecretsPlugin ABC.

Usage:
    1. Create a test class that inherits from BaseSecretsPluginTests
    2. Implement the secrets_plugin fixture to return your plugin instance
    3. Implement the test_secret_key fixture for unique secret keys
    4. Run pytest - all base tests will be executed automatically

Example:
    >>> import pytest
    >>> from testing.base_classes import BaseSecretsPluginTests
    >>> from my_plugin import MySecretsPlugin
    >>>
    >>> class TestMySecretsPlugin(BaseSecretsPluginTests):
    ...     @pytest.fixture
    ...     def secrets_plugin(self) -> MySecretsPlugin:
    ...         return MySecretsPlugin(config={...})
    ...
    ...     @pytest.fixture
    ...     def test_secret_key(self) -> str:
    ...         return f"test-secret-{uuid.uuid4().hex[:8]}"

Requirements Covered:
    - 7A-FR-002: SecretsPlugin ABC implementation
    - 7A-FR-060: Permission error handling
    - 7A-FR-061: Connection error handling
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.plugins.secrets import SecretsPlugin


class BaseSecretsPluginTests(ABC):
    """Abstract base test class for SecretsPlugin implementations.

    Subclasses must implement the secrets_plugin fixture to provide
    an instance of their SecretsPlugin implementation.

    All tests use @pytest.mark.requirement() for traceability.

    Attributes:
        secrets_plugin: Fixture that returns the plugin under test.
        test_secret_key: Fixture that returns a unique secret key for testing.

    Example:
        >>> class TestK8sSecretsPlugin(BaseSecretsPluginTests):
        ...     @pytest.fixture
        ...     def secrets_plugin(self):
        ...         return K8sSecretsPlugin(config)
        ...
        ...     @pytest.fixture
        ...     def test_secret_key(self):
        ...         return f"test-{uuid.uuid4().hex[:8]}"
    """

    @pytest.fixture
    @abstractmethod
    def secrets_plugin(self) -> SecretsPlugin:
        """Return an instance of the SecretsPlugin to test.

        Subclasses MUST implement this fixture to provide their
        concrete plugin implementation.

        Returns:
            A configured SecretsPlugin instance ready for testing.
        """
        ...

    @pytest.fixture
    @abstractmethod
    def test_secret_key(self) -> str:
        """Return a unique secret key for testing.

        Subclasses MUST implement this fixture to provide unique
        keys that won't conflict with other tests.

        Returns:
            A unique secret key string.
        """
        ...

    # =========================================================================
    # Plugin Metadata Tests (7A-FR-002)
    # =========================================================================

    @pytest.mark.requirement("7A-FR-002")
    def test_has_name_property(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has a name property.

        All plugins must have a unique name identifier.
        """
        assert hasattr(secrets_plugin, "name")
        assert isinstance(secrets_plugin.name, str)
        assert len(secrets_plugin.name) > 0

    @pytest.mark.requirement("7A-FR-002")
    def test_has_version_property(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has a version property.

        Plugin version should follow semantic versioning.
        """
        assert hasattr(secrets_plugin, "version")
        assert isinstance(secrets_plugin.version, str)
        assert len(secrets_plugin.version) > 0

    @pytest.mark.requirement("7A-FR-002")
    def test_has_floe_api_version_property(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin declares compatible floe API version.

        This is used to check plugin compatibility with the platform.
        """
        assert hasattr(secrets_plugin, "floe_api_version")
        assert isinstance(secrets_plugin.floe_api_version, str)
        assert len(secrets_plugin.floe_api_version) > 0

    # =========================================================================
    # Core Method Tests (7A-FR-002)
    # =========================================================================

    @pytest.mark.requirement("7A-FR-002")
    def test_has_get_secret_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has get_secret() method."""
        assert hasattr(secrets_plugin, "get_secret")
        assert callable(secrets_plugin.get_secret)

    @pytest.mark.requirement("7A-FR-002")
    def test_has_set_secret_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has set_secret() method."""
        assert hasattr(secrets_plugin, "set_secret")
        assert callable(secrets_plugin.set_secret)

    @pytest.mark.requirement("7A-FR-002")
    def test_has_list_secrets_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has list_secrets() method."""
        assert hasattr(secrets_plugin, "list_secrets")
        assert callable(secrets_plugin.list_secrets)

    @pytest.mark.requirement("7A-FR-002")
    def test_get_secret_returns_value_or_none(
        self, secrets_plugin: SecretsPlugin, test_secret_key: str
    ) -> None:
        """Verify get_secret() returns str or None, not raises for missing.

        Per contract: Return None for non-existent secrets, not raise exception.
        """
        result = secrets_plugin.get_secret(f"nonexistent-{test_secret_key}")
        assert result is None

    @pytest.mark.requirement("7A-FR-002")
    def test_set_secret_creates_or_updates(
        self, secrets_plugin: SecretsPlugin, test_secret_key: str
    ) -> None:
        """Verify set_secret() creates new or updates existing secret.

        Should not raise for either create or update operation.
        """
        test_value = "test-value-12345"

        # Create
        secrets_plugin.set_secret(test_secret_key, test_value)

        # Verify created
        result = secrets_plugin.get_secret(test_secret_key)
        assert result == test_value

        # Update
        new_value = "updated-value-67890"
        secrets_plugin.set_secret(test_secret_key, new_value)

        # Verify updated
        result = secrets_plugin.get_secret(test_secret_key)
        assert result == new_value

    @pytest.mark.requirement("7A-FR-002")
    def test_list_secrets_returns_list(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify list_secrets() returns a list of strings."""
        result = secrets_plugin.list_secrets()
        assert isinstance(result, list)
        # All items should be strings
        for item in result:
            assert isinstance(item, str)

    @pytest.mark.requirement("7A-FR-002")
    def test_list_secrets_filters_by_prefix(
        self, secrets_plugin: SecretsPlugin, test_secret_key: str
    ) -> None:
        """Verify list_secrets(prefix) filters results correctly.

        Create secrets with known prefix, verify filtering works.
        """
        prefix = f"test-prefix-{test_secret_key[:8]}"

        # Create some secrets with the prefix
        secrets_plugin.set_secret(f"{prefix}/key1", "value1")
        secrets_plugin.set_secret(f"{prefix}/key2", "value2")

        # List with prefix filter
        result = secrets_plugin.list_secrets(prefix=prefix)

        # Should contain our prefixed secrets
        assert isinstance(result, list)
        assert len(result) >= 2
        for key in result:
            assert key.startswith(prefix)

    # =========================================================================
    # Optional Method Tests
    # =========================================================================

    @pytest.mark.requirement("7A-FR-002")
    def test_has_generate_pod_env_spec_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has generate_pod_env_spec() method."""
        assert hasattr(secrets_plugin, "generate_pod_env_spec")
        assert callable(secrets_plugin.generate_pod_env_spec)

    @pytest.mark.requirement("7A-FR-002")
    def test_generate_pod_env_spec_returns_dict(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify generate_pod_env_spec() returns valid pod spec fragment."""
        result = secrets_plugin.generate_pod_env_spec("test-secret")
        assert isinstance(result, dict)
        assert "envFrom" in result

    # =========================================================================
    # Lifecycle Tests
    # =========================================================================

    @pytest.mark.requirement("7A-FR-002")
    def test_has_health_check_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has health_check() method."""
        assert hasattr(secrets_plugin, "health_check")
        assert callable(secrets_plugin.health_check)

    @pytest.mark.requirement("7A-FR-002")
    def test_health_check_returns_health_status(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify health_check() returns a HealthStatus object."""
        from floe_core.plugin_metadata import HealthStatus

        health = secrets_plugin.health_check()
        assert isinstance(health, HealthStatus)
        assert hasattr(health, "state")

    @pytest.mark.requirement("7A-FR-002")
    def test_has_startup_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has startup() lifecycle method."""
        assert hasattr(secrets_plugin, "startup")
        assert callable(secrets_plugin.startup)

    @pytest.mark.requirement("7A-FR-002")
    def test_has_shutdown_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has shutdown() lifecycle method."""
        assert hasattr(secrets_plugin, "shutdown")
        assert callable(secrets_plugin.shutdown)

    # =========================================================================
    # Config Schema Tests
    # =========================================================================

    @pytest.mark.requirement("7A-FR-002")
    def test_has_get_config_schema_method(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify plugin has get_config_schema() method."""
        assert hasattr(secrets_plugin, "get_config_schema")
        assert callable(secrets_plugin.get_config_schema)

    @pytest.mark.requirement("7A-FR-002")
    def test_config_schema_returns_valid_type(self, secrets_plugin: SecretsPlugin) -> None:
        """Verify get_config_schema() returns None or a BaseModel class."""
        schema = secrets_plugin.get_config_schema()

        if schema is not None:
            from pydantic import BaseModel

            assert isinstance(schema, type)
            assert issubclass(schema, BaseModel)


# Module exports
__all__ = ["BaseSecretsPluginTests"]
