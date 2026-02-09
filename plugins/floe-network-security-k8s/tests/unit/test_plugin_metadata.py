"""Unit tests for K8sNetworkSecurityPlugin metadata.

Task: T087
Phase: 11 - Plugin Discovery (US7)
User Story: US7 - Plugin Architecture Standards
Requirement: FR-001
"""

from __future__ import annotations

import re

import pytest
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata

from floe_network_security_k8s import K8sNetworkSecurityPlugin


class TestPluginName:
    """Tests for plugin name property."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_name_property(self) -> None:
        """Test plugin has name property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "name")
        assert isinstance(plugin.name, str)

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_not_empty(self) -> None:
        """Test plugin name is not empty."""
        plugin = K8sNetworkSecurityPlugin()
        assert len(plugin.name) > 0

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_format(self) -> None:
        """Test plugin name follows naming convention (lowercase, hyphens allowed)."""
        plugin = K8sNetworkSecurityPlugin()
        # Name should be lowercase alphanumeric with hyphens
        pattern = r"^[a-z0-9-]+$"
        assert re.match(pattern, plugin.name), f"Name '{plugin.name}' doesn't match pattern"

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_no_spaces(self) -> None:
        """Test plugin name contains no spaces."""
        plugin = K8sNetworkSecurityPlugin()
        assert " " not in plugin.name

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_no_underscores(self) -> None:
        """Test plugin name uses hyphens, not underscores."""
        plugin = K8sNetworkSecurityPlugin()
        assert "_" not in plugin.name

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_is_consistent(self) -> None:
        """Test plugin name is consistent across multiple calls."""
        plugin = K8sNetworkSecurityPlugin()
        name1 = plugin.name
        name2 = plugin.name
        assert name1 == name2


class TestPluginVersion:
    """Tests for plugin version property."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_version_property(self) -> None:
        """Test plugin has version property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "version")
        assert isinstance(plugin.version, str)

    @pytest.mark.requirement("FR-001")
    def test_plugin_version_not_empty(self) -> None:
        """Test plugin version is not empty."""
        plugin = K8sNetworkSecurityPlugin()
        assert len(plugin.version) > 0

    @pytest.mark.requirement("FR-001")
    def test_version_follows_semver(self) -> None:
        """Test version follows semantic versioning (X.Y.Z)."""
        plugin = K8sNetworkSecurityPlugin()
        # Semver format: X.Y.Z or X.Y.Z-prerelease
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"
        assert re.match(pattern, plugin.version), f"Version '{plugin.version}' is not semver"

    @pytest.mark.requirement("FR-001")
    def test_version_has_three_parts(self) -> None:
        """Test version has three numeric parts (major.minor.patch)."""
        plugin = K8sNetworkSecurityPlugin()
        version = plugin.version
        # Split on first hyphen to remove prerelease
        base_version = version.split("-")[0]
        parts = base_version.split(".")
        assert len(parts) == 3, f"Version {version} doesn't have 3 parts"

    @pytest.mark.requirement("FR-001")
    def test_version_parts_are_numeric(self) -> None:
        """Test version parts are numeric."""
        plugin = K8sNetworkSecurityPlugin()
        version = plugin.version
        base_version = version.split("-")[0]
        parts = base_version.split(".")
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' is not numeric"

    @pytest.mark.requirement("FR-001")
    def test_version_is_consistent(self) -> None:
        """Test version is consistent across multiple calls."""
        plugin = K8sNetworkSecurityPlugin()
        version1 = plugin.version
        version2 = plugin.version
        assert version1 == version2

    @pytest.mark.requirement("FR-001")
    def test_version_no_leading_v(self) -> None:
        """Test version doesn't have leading 'v' character."""
        plugin = K8sNetworkSecurityPlugin()
        assert not plugin.version.startswith("v")


class TestFloeApiVersion:
    """Tests for floe_api_version property."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_floe_api_version_property(self) -> None:
        """Test plugin has floe_api_version property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "floe_api_version")
        assert isinstance(plugin.floe_api_version, str)

    @pytest.mark.requirement("FR-001")
    def test_floe_api_version_not_empty(self) -> None:
        """Test floe_api_version is not empty."""
        plugin = K8sNetworkSecurityPlugin()
        assert len(plugin.floe_api_version) > 0

    @pytest.mark.requirement("FR-001")
    def test_floe_api_version_format(self) -> None:
        """Test floe_api_version is in X.Y format."""
        plugin = K8sNetworkSecurityPlugin()
        api_version = plugin.floe_api_version
        # API version format: X.Y
        pattern = r"^\d+\.\d+$"
        assert re.match(pattern, api_version), f"API version '{api_version}' is not X.Y format"

    @pytest.mark.requirement("FR-001")
    def test_floe_api_version_has_two_parts(self) -> None:
        """Test floe_api_version has exactly two numeric parts."""
        plugin = K8sNetworkSecurityPlugin()
        api_version = plugin.floe_api_version
        parts = api_version.split(".")
        assert len(parts) == 2, f"API version {api_version} doesn't have 2 parts"

    @pytest.mark.requirement("FR-001")
    def test_floe_api_version_parts_are_numeric(self) -> None:
        """Test floe_api_version parts are numeric."""
        plugin = K8sNetworkSecurityPlugin()
        api_version = plugin.floe_api_version
        parts = api_version.split(".")
        for part in parts:
            assert part.isdigit(), f"API version part '{part}' is not numeric"

    @pytest.mark.requirement("FR-001")
    def test_floe_api_version_is_consistent(self) -> None:
        """Test floe_api_version is consistent across multiple calls."""
        plugin = K8sNetworkSecurityPlugin()
        version1 = plugin.floe_api_version
        version2 = plugin.floe_api_version
        assert version1 == version2

    @pytest.mark.requirement("FR-001")
    def test_floe_api_version_no_leading_v(self) -> None:
        """Test floe_api_version doesn't have leading 'v' character."""
        plugin = K8sNetworkSecurityPlugin()
        assert not plugin.floe_api_version.startswith("v")


class TestHealthCheck:
    """Tests for health_check() method."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_health_check_method(self) -> None:
        """Test plugin has health_check method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "health_check")
        assert callable(plugin.health_check)

    @pytest.mark.requirement("FR-001")
    def test_health_check_returns_health_status(self) -> None:
        """Test health_check returns HealthStatus instance."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.health_check()
        assert isinstance(result, HealthStatus)

    @pytest.mark.requirement("FR-001")
    def test_health_check_status_has_state(self) -> None:
        """Test health_check result has state attribute."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.health_check()
        assert hasattr(result, "state")
        assert result.state is not None

    @pytest.mark.requirement("FR-001")
    def test_health_check_state_is_health_state_enum(self) -> None:
        """Test health_check state is a HealthState enum value."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.health_check()
        assert isinstance(result.state, HealthState)

    @pytest.mark.requirement("FR-001")
    def test_health_check_state_is_valid_value(self) -> None:
        """Test health_check state is one of the valid HealthState values."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.health_check()
        valid_states = {
            HealthState.HEALTHY,
            HealthState.DEGRADED,
            HealthState.UNHEALTHY,
        }
        assert result.state in valid_states

    @pytest.mark.requirement("FR-001")
    def test_health_check_status_has_message(self) -> None:
        """Test health_check result has message attribute."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.health_check()
        assert hasattr(result, "message")
        assert isinstance(result.message, str)

    @pytest.mark.requirement("FR-001")
    def test_health_check_status_has_details(self) -> None:
        """Test health_check result has details attribute."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.health_check()
        assert hasattr(result, "details")
        assert isinstance(result.details, dict)

    @pytest.mark.requirement("FR-001")
    def test_health_check_is_repeatable(self) -> None:
        """Test health_check can be called multiple times."""
        plugin = K8sNetworkSecurityPlugin()
        result1 = plugin.health_check()
        result2 = plugin.health_check()
        assert isinstance(result1, HealthStatus)
        assert isinstance(result2, HealthStatus)

    @pytest.mark.requirement("FR-001")
    def test_health_check_default_is_healthy(self) -> None:
        """Test default health_check returns HEALTHY state."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.health_check()
        # Default implementation should return HEALTHY
        assert result.state == HealthState.HEALTHY


class TestPluginMetadataProtocol:
    """Tests for plugin implementing PluginMetadata protocol."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_is_plugin_metadata_instance(self) -> None:
        """Test plugin is instance of PluginMetadata."""
        plugin = K8sNetworkSecurityPlugin()
        assert isinstance(plugin, PluginMetadata)

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_description_property(self) -> None:
        """Test plugin has description property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "description")
        assert isinstance(plugin.description, str)

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_dependencies_property(self) -> None:
        """Test plugin has dependencies property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "dependencies")
        assert isinstance(plugin.dependencies, list)

    @pytest.mark.requirement("FR-001")
    def test_plugin_dependencies_are_strings(self) -> None:
        """Test plugin dependencies are all strings."""
        plugin = K8sNetworkSecurityPlugin()
        for dep in plugin.dependencies:
            assert isinstance(dep, str)

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_startup_method(self) -> None:
        """Test plugin has startup method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "startup")
        assert callable(plugin.startup)

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_shutdown_method(self) -> None:
        """Test plugin has shutdown method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "shutdown")
        assert callable(plugin.shutdown)

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_get_config_schema_method(self) -> None:
        """Test plugin has get_config_schema method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "get_config_schema")
        assert callable(plugin.get_config_schema)

    @pytest.mark.requirement("FR-001")
    def test_plugin_startup_is_callable(self) -> None:
        """Test plugin startup method can be called."""
        plugin = K8sNetworkSecurityPlugin()
        # Should not raise an exception
        plugin.startup()

    @pytest.mark.requirement("FR-001")
    def test_plugin_shutdown_is_callable(self) -> None:
        """Test plugin shutdown method can be called."""
        plugin = K8sNetworkSecurityPlugin()
        # Should not raise an exception
        plugin.shutdown()

    @pytest.mark.requirement("FR-001")
    def test_plugin_get_config_schema_returns_none_or_model(self) -> None:
        """Test get_config_schema returns None or Pydantic model."""
        plugin = K8sNetworkSecurityPlugin()
        schema = plugin.get_config_schema()
        # Should return None or a Pydantic model class
        assert schema is None or hasattr(schema, "__mro__")

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_properties_are_properties(self) -> None:
        """Test metadata properties are defined as properties."""
        for prop_name in [
            "name",
            "version",
            "floe_api_version",
            "description",
            "dependencies",
        ]:
            prop = getattr(K8sNetworkSecurityPlugin, prop_name)
            assert isinstance(prop, property), f"{prop_name} should be a property"

    @pytest.mark.requirement("FR-001")
    def test_plugin_all_metadata_accessible(self) -> None:
        """Test all metadata properties are accessible without errors."""
        plugin = K8sNetworkSecurityPlugin()
        # Should not raise any exceptions
        _ = plugin.name
        _ = plugin.version
        _ = plugin.floe_api_version
        _ = plugin.description
        _ = plugin.dependencies
        _ = plugin.health_check()
