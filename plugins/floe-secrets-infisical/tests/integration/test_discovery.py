"""Integration tests for Infisical Secrets plugin entry point discovery.

Tests that the plugin can be discovered via the floe.secrets entry point.

Task: T043, T079
Phase: 7, 10 - US7 (Test Duplication Reduction)
Requirements: 7A-FR-004 (All plugins MUST inherit from PluginMetadata)

This module inherits from BasePluginDiscoveryTests to reduce test duplication
while adding Infisical-specific discovery tests.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, ClassVar

import pytest
from pydantic import SecretStr
from testing.base_classes import BasePluginDiscoveryTests


class TestInfisicalSecretsPluginDiscovery(BasePluginDiscoveryTests):
    """Tests for Infisical plugin entry point discovery.

    Inherits standard discovery tests from BasePluginDiscoveryTests:
    - test_entry_point_is_registered
    - test_exactly_one_entry_point
    - test_entry_point_module_path
    - test_plugin_loads_successfully
    - test_plugin_can_be_instantiated
    - test_instantiated_plugin_has_correct_name
    - test_plugin_has_required_metadata_attributes
    - test_plugin_metadata_values_not_none
    - test_plugin_inherits_from_expected_abc
    - test_plugin_instance_is_abc_instance
    - test_plugin_has_lifecycle_methods
    """

    entry_point_group: ClassVar[str] = "floe.secrets"
    expected_name: ClassVar[str] = "infisical"
    expected_module_prefix: ClassVar[str] = "floe_secrets_infisical"
    expected_class_name: ClassVar[str] = "InfisicalSecretsPlugin"

    @property
    def expected_plugin_abc(self) -> type[Any]:
        """Return the expected ABC for type checking."""
        from floe_core.plugins.secrets import SecretsPlugin

        return SecretsPlugin

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create Infisical plugin with required configuration.

        Args:
            plugin_class: The InfisicalSecretsPlugin class.

        Returns:
            Configured InfisicalSecretsPlugin instance.
        """
        from floe_secrets_infisical import InfisicalSecretsConfig

        config = InfisicalSecretsConfig(
            site_url="https://infisical.example.com",
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )
        return plugin_class(config=config)

    # =========================================================================
    # Secrets-Specific Method Tests
    # =========================================================================

    @pytest.mark.requirement("7A-FR-002")
    def test_plugin_has_secrets_specific_methods(self) -> None:
        """Test plugin has SecretsPlugin-specific methods beyond lifecycle."""
        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()

        # SecretsPlugin-specific methods (beyond standard lifecycle)
        secrets_methods = [
            "get_secret",
            "set_secret",
            "list_secrets",
        ]

        for method_name in secrets_methods:
            assert hasattr(
                plugin_class, method_name
            ), f"Plugin missing SecretsPlugin method: {method_name}"
            assert callable(getattr(plugin_class, method_name))

    @pytest.mark.requirement("7A-FR-021")
    def test_plugin_supports_universal_auth(self) -> None:
        """Test plugin config requires Universal Auth fields."""
        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()

        # Get the config schema
        config_schema = plugin_class.get_config_schema()

        # Config should require client_id and client_secret for Universal Auth
        assert config_schema is not None
        schema_json = config_schema.model_json_schema()
        required_fields = schema_json.get("required", [])

        assert "client_id" in required_fields
        assert "client_secret" in required_fields


class TestInfisicalSecretsPluginCoexistence:
    """Test plugin coexistence with other secrets plugins."""

    @pytest.mark.requirement("7A-FR-020")
    def test_multiple_secrets_plugins_coexist(self) -> None:
        """Test multiple secrets plugins can be discovered together."""
        eps = entry_points(group="floe.secrets")
        names = [ep.name for ep in eps]

        # Both k8s and infisical should be available
        assert "k8s" in names
        assert "infisical" in names

        # Each should be distinct
        assert len(names) == len(set(names)), "Duplicate entry point names found"
