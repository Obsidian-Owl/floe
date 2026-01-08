"""Contract tests for PluginMetadata ABC and PluginType enum stability.

These tests ensure the plugin system interfaces remain stable across versions.
Breaking changes to abstract methods, required properties, or enum values
should fail these tests.

Contract tests prevent accidental breaking changes to:
- Abstract properties (name, version, floe_api_version)
- Optional properties (description, dependencies)
- Lifecycle methods (startup, shutdown, health_check)
- Configuration method (get_config_schema)
- Supporting classes (HealthState, HealthStatus)
- PluginType enum values and entry point groups

Requirements Covered:
- FR-001: Plugin metadata schema stability
- FR-002: PluginType enum stability
- SC-001: Contract stability for plugin implementations
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from typing import get_type_hints

import pytest

from floe_core.plugin_metadata import (
    HealthState,
    HealthStatus,
    PluginMetadata,
)
from floe_core.plugin_types import PluginType


class TestHealthStateContract:
    """Contract tests for HealthState enum stability."""

    @pytest.mark.requirement("SC-001")
    def test_health_state_has_expected_values(self) -> None:
        """Verify HealthState enum has all required values.

        HealthState MUST have HEALTHY, DEGRADED, and UNHEALTHY values
        for plugins to report their operational status.
        """
        expected_values = {"HEALTHY", "DEGRADED", "UNHEALTHY"}
        actual_values = {member.name for member in HealthState}

        assert expected_values.issubset(actual_values), (
            f"HealthState missing required values: {expected_values - actual_values}"
        )

    @pytest.mark.requirement("SC-001")
    def test_health_state_string_values(self) -> None:
        """Verify HealthState enum values are lowercase strings.

        String values are used in serialization and must remain stable.
        """
        assert HealthState.HEALTHY.value == "healthy"
        assert HealthState.DEGRADED.value == "degraded"
        assert HealthState.UNHEALTHY.value == "unhealthy"


class TestHealthStatusContract:
    """Contract tests for HealthStatus dataclass stability."""

    @pytest.mark.requirement("SC-001")
    def test_health_status_has_required_fields(self) -> None:
        """Verify HealthStatus has all required fields.

        HealthStatus MUST have state, message, and details fields.
        """
        field_names = {f.name for f in fields(HealthStatus)}
        required_fields = {"state", "message", "details"}

        assert required_fields.issubset(field_names), (
            f"HealthStatus missing required fields: {required_fields - field_names}"
        )

    @pytest.mark.requirement("SC-001")
    def test_health_status_field_types(self) -> None:
        """Verify HealthStatus field type annotations are stable.

        Type annotations define the contract for health status data.
        Uses get_type_hints() to resolve forward references.
        """
        hints = get_type_hints(HealthStatus)

        assert hints.get("state") is HealthState
        assert hints.get("message") is str
        # dict[str, Any] is represented as different types, check it works
        assert "dict" in str(hints.get("details")).lower()

    @pytest.mark.requirement("SC-001")
    def test_health_status_defaults(self) -> None:
        """Verify HealthStatus has expected default values.

        Plugins should be able to create HealthStatus with just state.
        """
        status = HealthStatus(state=HealthState.HEALTHY)

        assert status.state == HealthState.HEALTHY
        assert status.message == ""
        assert status.details == {}


class TestPluginMetadataContract:
    """Contract tests for PluginMetadata ABC stability."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_is_abstract(self) -> None:
        """Verify PluginMetadata is an abstract base class.

        PluginMetadata MUST be abstract to enforce implementation.
        """
        assert inspect.isabstract(PluginMetadata)

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_has_abstract_properties(self) -> None:
        """Verify required abstract properties exist.

        These properties MUST be implemented by all plugins:
        - name: Plugin identifier
        - version: Plugin version (semver)
        - floe_api_version: Required floe API version
        """
        # Get abstract members
        abstract_members = set()
        for name, method in inspect.getmembers(PluginMetadata):
            if getattr(method, "__isabstractmethod__", False):
                abstract_members.add(name)

        required_abstract = {"name", "version", "floe_api_version"}

        assert required_abstract.issubset(abstract_members), (
            f"Missing abstract properties: {required_abstract - abstract_members}"
        )

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_abstract_properties_are_properties(self) -> None:
        """Verify abstract members are properties, not methods.

        Properties enforce read-only access to plugin metadata.
        """
        # Check that these are defined as properties
        for prop_name in ["name", "version", "floe_api_version"]:
            prop = getattr(PluginMetadata, prop_name)
            assert isinstance(prop, property), (
                f"{prop_name} should be a property, not {type(prop)}"
            )

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_has_optional_properties(self) -> None:
        """Verify optional properties exist with defaults.

        These properties have default implementations:
        - description: Human-readable description
        - dependencies: List of plugin names
        """
        # description property exists
        assert hasattr(PluginMetadata, "description")
        assert isinstance(
            inspect.getattr_static(PluginMetadata, "description"), property
        )

        # dependencies property exists
        assert hasattr(PluginMetadata, "dependencies")
        assert isinstance(
            inspect.getattr_static(PluginMetadata, "dependencies"), property
        )

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_has_lifecycle_methods(self) -> None:
        """Verify lifecycle methods exist.

        Lifecycle methods MUST exist for plugin activation:
        - startup(): Called when plugin is activated
        - shutdown(): Called when platform shuts down
        - health_check(): Returns current health status
        """
        lifecycle_methods = ["startup", "shutdown", "health_check"]

        for method_name in lifecycle_methods:
            method = getattr(PluginMetadata, method_name, None)
            assert method is not None, f"Missing lifecycle method: {method_name}"
            assert callable(method), f"{method_name} should be callable"

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_has_config_method(self) -> None:
        """Verify get_config_schema method exists.

        Plugins use this to provide Pydantic validation schemas.
        """
        method = getattr(PluginMetadata, "get_config_schema", None)
        assert method is not None, "Missing get_config_schema method"
        assert callable(method), "get_config_schema should be callable"

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_method_signatures(self) -> None:
        """Verify method signatures are stable.

        Method signatures define the contract for plugin implementations.
        Uses get_type_hints() to resolve forward references in return types.
        """
        # startup() -> None
        sig = inspect.signature(PluginMetadata.startup)
        assert sig.return_annotation in (None, "None", type(None))
        # Only self parameter
        params = list(sig.parameters.keys())
        assert params == ["self"], f"startup params should be ['self'], got {params}"

        # shutdown() -> None
        sig = inspect.signature(PluginMetadata.shutdown)
        assert sig.return_annotation in (None, "None", type(None))
        params = list(sig.parameters.keys())
        assert params == ["self"], f"shutdown params should be ['self'], got {params}"

        # health_check() -> HealthStatus
        # Use get_type_hints to resolve forward references
        hints = get_type_hints(PluginMetadata.health_check)
        assert hints.get("return") is HealthStatus
        sig = inspect.signature(PluginMetadata.health_check)
        params = list(sig.parameters.keys())
        assert params == ["self"], (
            f"health_check params should be ['self'], got {params}"
        )


class TestPluginMetadataImplementation:
    """Test that PluginMetadata can be properly implemented."""

    @pytest.mark.requirement("FR-001")
    def test_concrete_implementation_works(self) -> None:
        """Verify concrete implementations can instantiate.

        A minimal concrete plugin should work without errors.
        """

        class ConcretePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "test-plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        plugin = ConcretePlugin()

        # Abstract properties work
        assert plugin.name == "test-plugin"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "1.0"

        # Defaults work
        assert plugin.description == ""
        assert plugin.dependencies == []
        assert plugin.get_config_schema() is None

        # Lifecycle methods work
        plugin.startup()  # Should not raise
        plugin.shutdown()  # Should not raise

        # Health check returns expected type
        health = plugin.health_check()
        assert isinstance(health, HealthStatus)
        assert health.state == HealthState.HEALTHY

    @pytest.mark.requirement("FR-001")
    def test_incomplete_implementation_raises(self) -> None:
        """Verify incomplete implementations cannot instantiate.

        Missing abstract properties should raise TypeError.
        """

        class IncompletePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "incomplete"

            # Missing version and floe_api_version

        with pytest.raises(TypeError, match="abstract"):
            IncompletePlugin()  # type: ignore[abstract]


class TestPluginTypeContract:
    """Contract tests for PluginType enum stability.

    PluginType defines the 11 plugin categories and their entry point groups.
    Changes to this enum affect all plugin discovery and registration.
    """

    @pytest.mark.requirement("FR-002")
    def test_plugin_type_has_all_11_categories(self) -> None:
        """Verify PluginType has all 11 required categories.

        The floe platform MUST support exactly these 11 plugin types.
        Adding new types is allowed, but removing any breaks existing plugins.
        """
        required_types = {
            "COMPUTE",
            "ORCHESTRATOR",
            "CATALOG",
            "STORAGE",
            "TELEMETRY_BACKEND",
            "LINEAGE_BACKEND",
            "DBT",
            "SEMANTIC_LAYER",
            "INGESTION",
            "SECRETS",
            "IDENTITY",
        }
        actual_types = {member.name for member in PluginType}

        assert required_types.issubset(actual_types), (
            f"PluginType missing required types: {required_types - actual_types}"
        )

    @pytest.mark.requirement("FR-002")
    def test_plugin_type_entry_point_groups_are_stable(self) -> None:
        """Verify entry point group names are stable.

        Entry point groups are used in pyproject.toml and must not change.
        Changing these would break all existing plugin packages.
        """
        expected_groups = {
            "COMPUTE": "floe.computes",
            "ORCHESTRATOR": "floe.orchestrators",
            "CATALOG": "floe.catalogs",
            "STORAGE": "floe.storage",
            "TELEMETRY_BACKEND": "floe.telemetry_backends",
            "LINEAGE_BACKEND": "floe.lineage_backends",
            "DBT": "floe.dbt",
            "SEMANTIC_LAYER": "floe.semantic_layers",
            "INGESTION": "floe.ingestion",
            "SECRETS": "floe.secrets",
            "IDENTITY": "floe.identity",
        }

        for type_name, expected_group in expected_groups.items():
            plugin_type = PluginType[type_name]
            assert plugin_type.value == expected_group, (
                f"{type_name} entry point group changed from "
                f"'{expected_group}' to '{plugin_type.value}'"
            )

    @pytest.mark.requirement("FR-002")
    def test_plugin_type_has_entry_point_group_property(self) -> None:
        """Verify entry_point_group property exists and returns value.

        The entry_point_group property is the standard way to get the
        entry point group name for plugin discovery.
        """
        for plugin_type in PluginType:
            assert hasattr(plugin_type, "entry_point_group")
            assert plugin_type.entry_point_group == plugin_type.value

    @pytest.mark.requirement("FR-002")
    def test_plugin_type_has_all_entry_point_groups_method(self) -> None:
        """Verify all_entry_point_groups class method exists.

        This method is used to get all valid entry point groups at once.
        """
        assert hasattr(PluginType, "all_entry_point_groups")
        groups = PluginType.all_entry_point_groups()

        # Should return a list
        assert isinstance(groups, list)

        # Should have 11 groups (one per type)
        assert len(groups) >= 11

        # All should be strings
        assert all(isinstance(g, str) for g in groups)

        # All should start with 'floe.'
        assert all(g.startswith("floe.") for g in groups)

    @pytest.mark.requirement("FR-002")
    def test_plugin_type_from_entry_point_group_method(self) -> None:
        """Verify from_entry_point_group class method works.

        This method is used to convert entry point group names back to
        PluginType enum values during plugin discovery.
        """
        assert hasattr(PluginType, "from_entry_point_group")

        # Test roundtrip for all types
        for plugin_type in PluginType:
            group = plugin_type.entry_point_group
            recovered = PluginType.from_entry_point_group(group)
            assert recovered is plugin_type

    @pytest.mark.requirement("FR-002")
    def test_plugin_type_from_entry_point_group_invalid(self) -> None:
        """Verify from_entry_point_group raises ValueError for invalid groups.

        Invalid entry point groups should raise ValueError with a helpful
        message listing valid options.
        """
        with pytest.raises(ValueError, match="Unknown entry point group"):
            PluginType.from_entry_point_group("invalid.group")

        with pytest.raises(ValueError, match="floe.computes"):
            # Error message should list valid groups
            PluginType.from_entry_point_group("not.a.real.group")
