"""Contract tests for OrchestratorPlugin ABC compliance.

These tests validate that the OrchestratorPlugin abstract base class defines
the correct interface for orchestrator plugins. They ensure:
- All required abstract methods are defined with correct signatures
- Concrete implementations must implement all abstract methods
- Type hints are present and accurate
- Dagster plugin correctly implements the ABC

This is a contract test (tests/contract/) because it validates the interface
that plugin packages depend on. Changes to OrchestratorPlugin ABC can break
downstream implementations.

Requirements Covered:
- FR-002: OrchestratorPlugin ABC with 7 abstract methods
- FR-003: Plugin metadata requirements (name, version, floe_api_version)
- FR-004: Plugin inherits from OrchestratorPlugin and PluginMetadata
- SC-001: Plugin passes all abstract method compliance tests
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import Any
from uuid import UUID, uuid4

import pytest
from floe_core.lineage import LineageDataset, RunState


class TestOrchestratorPluginABCDefinition:
    """Contract tests for OrchestratorPlugin ABC structure.

    These tests verify that OrchestratorPlugin defines the correct abstract
    methods with proper signatures.
    """

    @pytest.mark.requirement("FR-002")
    def test_orchestrator_plugin_is_abstract_class(self) -> None:
        """Verify OrchestratorPlugin is an abstract base class.

        OrchestratorPlugin must be abstract to enforce method implementation
        in concrete plugins.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        # Must be a class
        assert isinstance(OrchestratorPlugin, type)

        # Must inherit from ABC (via PluginMetadata)
        assert issubclass(OrchestratorPlugin, ABC)

    @pytest.mark.requirement("FR-002")
    def test_create_definitions_method_is_abstract(self) -> None:
        """Verify create_definitions() is an abstract method with correct signature.

        FR-002: OrchestratorPlugin must define create_definitions() that
        generates platform-specific definitions from CompiledArtifacts.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        # Method must exist
        assert hasattr(OrchestratorPlugin, "create_definitions")

        # Must be abstract
        method = OrchestratorPlugin.create_definitions
        assert getattr(method, "__isabstractmethod__", False), (
            "create_definitions() must be abstract"
        )

        # Check signature
        sig = inspect.signature(OrchestratorPlugin.create_definitions)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "artifacts" in params

    @pytest.mark.requirement("FR-002")
    def test_create_assets_from_transforms_method_is_abstract(self) -> None:
        """Verify create_assets_from_transforms() is an abstract method.

        FR-002: OrchestratorPlugin must define create_assets_from_transforms()
        for generating orchestrator assets from dbt transforms.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "create_assets_from_transforms")

        method = OrchestratorPlugin.create_assets_from_transforms
        assert getattr(method, "__isabstractmethod__", False), (
            "create_assets_from_transforms() must be abstract"
        )

        sig = inspect.signature(OrchestratorPlugin.create_assets_from_transforms)
        params = list(sig.parameters.keys())
        assert "transforms" in params

    @pytest.mark.requirement("FR-002")
    def test_get_helm_values_method_is_abstract(self) -> None:
        """Verify get_helm_values() is an abstract method.

        FR-002: OrchestratorPlugin must define get_helm_values() for
        providing Helm chart configuration.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "get_helm_values")

        method = OrchestratorPlugin.get_helm_values
        assert getattr(method, "__isabstractmethod__", False), "get_helm_values() must be abstract"

    @pytest.mark.requirement("FR-002")
    def test_validate_connection_method_is_abstract(self) -> None:
        """Verify validate_connection() is an abstract method.

        FR-002: OrchestratorPlugin must define validate_connection() for
        testing connectivity to the orchestration service.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "validate_connection")

        method = OrchestratorPlugin.validate_connection
        assert getattr(method, "__isabstractmethod__", False), (
            "validate_connection() must be abstract"
        )

    @pytest.mark.requirement("FR-002")
    def test_get_resource_requirements_method_is_abstract(self) -> None:
        """Verify get_resource_requirements() is an abstract method.

        FR-002: OrchestratorPlugin must define get_resource_requirements()
        for K8s resource specifications.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "get_resource_requirements")

        method = OrchestratorPlugin.get_resource_requirements
        assert getattr(method, "__isabstractmethod__", False), (
            "get_resource_requirements() must be abstract"
        )

        sig = inspect.signature(OrchestratorPlugin.get_resource_requirements)
        params = list(sig.parameters.keys())
        assert "workload_size" in params

    @pytest.mark.requirement("FR-002")
    def test_emit_lineage_event_method_is_abstract(self) -> None:
        """Verify emit_lineage_event() is an abstract method.

        FR-002: OrchestratorPlugin must define emit_lineage_event() for
        OpenLineage event emission.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "emit_lineage_event")

        method = OrchestratorPlugin.emit_lineage_event
        assert getattr(method, "__isabstractmethod__", False), (
            "emit_lineage_event() must be abstract"
        )

        sig = inspect.signature(OrchestratorPlugin.emit_lineage_event)
        params = list(sig.parameters.keys())
        assert "event_type" in params
        assert "job_name" in params
        assert "inputs" in params
        assert "outputs" in params

    @pytest.mark.requirement("FR-002")
    def test_schedule_job_method_is_abstract(self) -> None:
        """Verify schedule_job() is an abstract method.

        FR-002: OrchestratorPlugin must define schedule_job() for
        job scheduling with cron expressions.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "schedule_job")

        method = OrchestratorPlugin.schedule_job
        assert getattr(method, "__isabstractmethod__", False), "schedule_job() must be abstract"

        sig = inspect.signature(OrchestratorPlugin.schedule_job)
        params = list(sig.parameters.keys())
        assert "job_name" in params
        assert "cron" in params
        assert "timezone" in params


class TestOrchestratorPluginMetadataRequirements:
    """Contract tests for plugin metadata requirements.

    FR-003: All OrchestratorPlugin implementations must provide plugin metadata.
    """

    @pytest.mark.requirement("FR-003")
    def test_orchestrator_plugin_inherits_plugin_metadata(self) -> None:
        """Verify OrchestratorPlugin inherits from PluginMetadata.

        This ensures all orchestrator plugins have required metadata properties.
        """
        from floe_core.plugin_metadata import PluginMetadata
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert issubclass(OrchestratorPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-003")
    def test_name_property_is_required(self) -> None:
        """Verify name property is required (abstract).

        All plugins must have a unique name.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        # name comes from PluginMetadata and is abstract
        assert hasattr(OrchestratorPlugin, "name")

    @pytest.mark.requirement("FR-003")
    def test_version_property_is_required(self) -> None:
        """Verify version property is required (abstract).

        All plugins must declare their version.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "version")

    @pytest.mark.requirement("FR-003")
    def test_floe_api_version_property_is_required(self) -> None:
        """Verify floe_api_version property is required (abstract).

        All plugins must declare compatible API version.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "floe_api_version")

    @pytest.mark.requirement("FR-003")
    def test_description_property_is_required(self) -> None:
        """Verify description property is required (abstract).

        All plugins must have a human-readable description.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert hasattr(OrchestratorPlugin, "description")


class TestOrchestratorPluginInstantiationContract:
    """Contract tests for OrchestratorPlugin instantiation.

    These tests verify that:
    - OrchestratorPlugin cannot be instantiated directly (abstract)
    - Incomplete implementations cannot be instantiated
    - Complete implementations can be instantiated
    """

    @pytest.mark.requirement("FR-002")
    def test_cannot_instantiate_abstract_orchestrator_plugin(self) -> None:
        """Verify OrchestratorPlugin cannot be instantiated directly.

        Direct instantiation must fail because abstract methods are not implemented.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        with pytest.raises(TypeError, match="abstract"):
            OrchestratorPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-002")
    def test_incomplete_implementation_fails(self) -> None:
        """Verify incomplete OrchestratorPlugin implementation fails.

        A class that only implements some abstract methods should not
        be instantiable.
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        class IncompletePlugin(OrchestratorPlugin):
            """Plugin missing most abstract methods."""

            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def description(self) -> str:
                return "Incomplete plugin"

            def create_definitions(self, artifacts: dict[str, Any]) -> Any:
                _ = artifacts
                return None

            # Missing: create_assets_from_transforms, get_helm_values,
            #          validate_connection, get_resource_requirements,
            #          emit_lineage_event, schedule_job

        with pytest.raises(TypeError, match="abstract"):
            IncompletePlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-002")
    @pytest.mark.requirement("FR-003")
    @pytest.mark.requirement("SC-001")
    def test_complete_implementation_succeeds(self) -> None:
        """Verify complete OrchestratorPlugin implementation can be instantiated.

        A class implementing all abstract methods should be instantiable.
        """
        from floe_core.plugins.orchestrator import (
            OrchestratorPlugin,
            ResourceSpec,
            TransformConfig,
            ValidationResult,
        )

        class CompleteMockPlugin(OrchestratorPlugin):
            """Complete mock plugin implementation for testing."""

            @property
            def name(self) -> str:
                return "mock-orchestrator"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def description(self) -> str:
                return "Mock orchestrator plugin for testing"

            def create_definitions(self, artifacts: dict[str, Any]) -> Any:
                _ = artifacts
                return {"mock": "definitions"}

            def create_assets_from_transforms(self, transforms: list[TransformConfig]) -> list[Any]:
                _ = transforms
                return []

            def get_helm_values(self) -> dict[str, Any]:
                return {"mock-orchestrator": {"enabled": True}}

            def validate_connection(self, **kwargs: Any) -> ValidationResult:
                _ = kwargs
                return ValidationResult(success=True, message="Mock connection OK")

            def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
                _ = workload_size
                return ResourceSpec()

            def emit_lineage_event(
                self,
                event_type: RunState,
                job_name: str,
                job_namespace: str | None = None,
                run_id: UUID | None = None,
                inputs: list[LineageDataset] | None = None,
                outputs: list[LineageDataset] | None = None,
                run_facets: dict[str, Any] | None = None,
                job_facets: dict[str, Any] | None = None,
                producer: str | None = None,
            ) -> UUID:
                _ = (
                    event_type,
                    job_name,
                    job_namespace,
                    run_id,
                    inputs,
                    outputs,
                    run_facets,
                    job_facets,
                    producer,
                )
                return uuid4()

            def schedule_job(self, job_name: str, cron: str, timezone: str) -> None:
                _ = job_name, cron, timezone

        # Should not raise
        plugin = CompleteMockPlugin()

        # Verify metadata is accessible
        assert plugin.name == "mock-orchestrator"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "1.0"
        assert plugin.description == "Mock orchestrator plugin for testing"


class TestOrchestratorPluginTypeHints:
    """Contract tests for OrchestratorPlugin method type hints.

    Type hints are part of the public contract and must be stable.
    """

    @pytest.mark.requirement("FR-002")
    def test_create_definitions_return_type_hint(self) -> None:
        """Verify create_definitions() has Any return type hint.

        Returns platform-specific definitions (Dagster Definitions, Airflow DAG).
        """
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        sig = inspect.signature(OrchestratorPlugin.create_definitions)
        return_annotation = sig.return_annotation

        # Should be annotated with Any (may be string due to future annotations)
        assert return_annotation is Any or return_annotation == "Any"

    @pytest.mark.requirement("FR-002")
    def test_create_assets_from_transforms_return_type_hint(self) -> None:
        """Verify create_assets_from_transforms() returns list[Any]."""
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        sig = inspect.signature(OrchestratorPlugin.create_assets_from_transforms)
        return_annotation = sig.return_annotation

        # Should return list[Any]
        assert "list" in str(return_annotation).lower()

    @pytest.mark.requirement("FR-002")
    def test_get_helm_values_return_type_hint(self) -> None:
        """Verify get_helm_values() returns dict[str, Any]."""
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        sig = inspect.signature(OrchestratorPlugin.get_helm_values)
        return_annotation = sig.return_annotation

        # Should return dict
        assert "dict" in str(return_annotation).lower()

    @pytest.mark.requirement("FR-002")
    def test_validate_connection_return_type_hint(self) -> None:
        """Verify validate_connection() returns ValidationResult."""
        from floe_core.plugins.orchestrator import OrchestratorPlugin, ValidationResult

        sig = inspect.signature(OrchestratorPlugin.validate_connection)
        return_annotation = sig.return_annotation

        # Should return ValidationResult (may be string due to future annotations)
        assert return_annotation is ValidationResult or return_annotation == "ValidationResult"

    @pytest.mark.requirement("FR-002")
    def test_get_resource_requirements_return_type_hint(self) -> None:
        """Verify get_resource_requirements() returns ResourceSpec."""
        from floe_core.plugins.orchestrator import OrchestratorPlugin, ResourceSpec

        sig = inspect.signature(OrchestratorPlugin.get_resource_requirements)
        return_annotation = sig.return_annotation

        # Should return ResourceSpec (may be string due to future annotations)
        assert return_annotation is ResourceSpec or return_annotation == "ResourceSpec"


class TestDagsterPluginImplementsABC:
    """Contract tests verifying DagsterOrchestratorPlugin implements the ABC.

    These tests verify that the actual Dagster plugin correctly implements
    all abstract methods from OrchestratorPlugin.
    """

    @pytest.mark.requirement("FR-004")
    @pytest.mark.requirement("SC-001")
    def test_dagster_plugin_inherits_from_orchestrator_plugin(self) -> None:
        """Verify DagsterOrchestratorPlugin inherits from OrchestratorPlugin."""
        from floe_core.plugins.orchestrator import OrchestratorPlugin
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        assert issubclass(DagsterOrchestratorPlugin, OrchestratorPlugin)

    @pytest.mark.requirement("SC-001")
    def test_dagster_plugin_can_be_instantiated(self) -> None:
        """Verify DagsterOrchestratorPlugin can be instantiated.

        This proves all abstract methods are implemented.
        """
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        assert plugin is not None

    @pytest.mark.requirement("FR-003")
    def test_dagster_plugin_has_required_metadata(self) -> None:
        """Verify DagsterOrchestratorPlugin has all required metadata."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()

        # All metadata properties must be present and valid
        assert plugin.name == "dagster"
        assert len(plugin.version.split(".")) == 3  # Semver format
        assert plugin.floe_api_version == "1.0"
        assert "dagster" in plugin.description.lower()

    @pytest.mark.requirement("SC-001")
    def test_dagster_plugin_implements_all_abstract_methods(self) -> None:
        """Verify DagsterOrchestratorPlugin implements all 7 abstract methods."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()

        # All 7 abstract methods must be callable
        assert callable(plugin.create_definitions)
        assert callable(plugin.create_assets_from_transforms)
        assert callable(plugin.get_helm_values)
        assert callable(plugin.validate_connection)
        assert callable(plugin.get_resource_requirements)
        assert callable(plugin.emit_lineage_event)
        assert callable(plugin.schedule_job)
