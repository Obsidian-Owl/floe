"""Unit tests for DagsterOrchestratorPlugin.

These tests verify the Dagster orchestrator plugin implementation without
requiring external services.

Note: @pytest.mark.requirement markers are only used for integration tests.
Unit tests validate implementation correctness; integration tests validate requirements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from floe_core.plugins.orchestrator import OrchestratorPlugin

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestDagsterOrchestratorPluginMetadata:
    """Test plugin metadata properties.

    Validates FR-002, FR-003, FR-004 from spec:
    - FR-002: Implement all abstract methods from OrchestratorPlugin ABC
    - FR-003: Plugin declares name, version, floe_api_version
    - FR-004: Plugin inherits from OrchestratorPlugin and PluginMetadata
    """

    def test_plugin_name(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin name is 'dagster'."""
        assert dagster_plugin.name == "dagster"

    def test_plugin_version(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin version follows semver format."""
        version = dagster_plugin.version
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_floe_api_version(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test floe API version is specified."""
        api_version = dagster_plugin.floe_api_version
        assert api_version == "1.0"

    def test_plugin_description(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin has a meaningful description."""
        assert len(dagster_plugin.description) > 0
        assert "dagster" in dagster_plugin.description.lower()


class TestDagsterOrchestratorPluginABCCompliance:
    """Test ABC compliance verification.

    Validates SC-001: Plugin passes all 7 abstract method compliance tests
    defined in OrchestratorPlugin ABC.
    """

    def test_inherits_from_orchestrator_plugin(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin inherits from OrchestratorPlugin ABC."""
        assert isinstance(dagster_plugin, OrchestratorPlugin)

    def test_has_create_definitions_method(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements create_definitions method."""
        assert hasattr(dagster_plugin, "create_definitions")
        assert callable(dagster_plugin.create_definitions)

    def test_has_create_assets_from_transforms_method(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements create_assets_from_transforms method."""
        assert hasattr(dagster_plugin, "create_assets_from_transforms")
        assert callable(dagster_plugin.create_assets_from_transforms)

    def test_has_get_helm_values_method(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements get_helm_values method."""
        assert hasattr(dagster_plugin, "get_helm_values")
        assert callable(dagster_plugin.get_helm_values)

    def test_has_validate_connection_method(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements validate_connection method."""
        assert hasattr(dagster_plugin, "validate_connection")
        assert callable(dagster_plugin.validate_connection)

    def test_has_get_resource_requirements_method(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements get_resource_requirements method."""
        assert hasattr(dagster_plugin, "get_resource_requirements")
        assert callable(dagster_plugin.get_resource_requirements)

    def test_has_emit_lineage_event_method(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements emit_lineage_event method."""
        assert hasattr(dagster_plugin, "emit_lineage_event")
        assert callable(dagster_plugin.emit_lineage_event)

    def test_has_schedule_job_method(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements schedule_job method."""
        assert hasattr(dagster_plugin, "schedule_job")
        assert callable(dagster_plugin.schedule_job)


class TestDagsterOrchestratorPluginInstantiation:
    """Test plugin instantiation and basic operations."""

    def test_plugin_can_be_instantiated(self) -> None:
        """Test plugin can be instantiated without arguments."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        assert plugin is not None

    def test_plugin_can_be_imported_from_package(self) -> None:
        """Test plugin is exported from package __init__.py."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        assert DagsterOrchestratorPlugin is not None

    def test_version_exported_from_package(self) -> None:
        """Test __version__ is exported from package."""
        from floe_orchestrator_dagster import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)


class TestDagsterOrchestratorPluginSkeletonMethods:
    """Test skeleton methods raise NotImplementedError.

    These tests verify that placeholder methods correctly raise
    NotImplementedError until they are implemented in later tasks.
    """

    def test_create_definitions_not_implemented(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test create_definitions raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="T006"):
            dagster_plugin.create_definitions({})

    def test_create_assets_from_transforms_not_implemented(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test create_assets_from_transforms raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="T007"):
            dagster_plugin.create_assets_from_transforms([])

    def test_get_helm_values_not_implemented(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_helm_values raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="T012"):
            dagster_plugin.get_helm_values()

    def test_validate_connection_not_implemented(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="T024"):
            dagster_plugin.validate_connection()

    def test_get_resource_requirements_not_implemented(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_resource_requirements raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="T013"):
            dagster_plugin.get_resource_requirements("small")

    def test_emit_lineage_event_not_implemented(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test emit_lineage_event raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="T021"):
            dagster_plugin.emit_lineage_event("START", "job", [], [])

    def test_schedule_job_not_implemented(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test schedule_job raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="T017"):
            dagster_plugin.schedule_job("job", "0 8 * * *", "UTC")
