"""Unit tests for definition generation in DagsterOrchestratorPlugin.

These tests verify the create_definitions() method behavior with various
CompiledArtifacts inputs, including edge cases like empty transforms,
circular dependencies, and duplicate names.

Note: @pytest.mark.requirement markers are used for traceability to spec.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestCreateDefinitionsWithValidArtifacts:
    """Test direct create_definitions with valid CompiledArtifacts inputs.

    Direct plugin calls validate artifacts, then require the runtime loader
    path to supply project_dir before Definitions can be built.
    """

    @pytest.mark.requirement("FR-005")
    def test_create_definitions_requires_project_dir(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test direct create_definitions requires runtime project_dir."""
        with pytest.raises(ValueError, match="require project_dir"):
            dagster_plugin.create_definitions(valid_compiled_artifacts)

    @pytest.mark.requirement("FR-005")
    def test_create_definitions_with_models_requires_project_dir(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts_with_models: dict[str, Any],
    ) -> None:
        """Test direct create_definitions does not synthesize model assets."""
        with pytest.raises(ValueError, match="require project_dir"):
            dagster_plugin.create_definitions(valid_compiled_artifacts_with_models)

    @pytest.mark.requirement("FR-005")
    def test_create_definitions_with_multiple_models_requires_project_dir(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts_with_models: dict[str, Any],
    ) -> None:
        """Test direct create_definitions keeps the runtime-loader contract."""
        with pytest.raises(ValueError, match="require project_dir"):
            dagster_plugin.create_definitions(valid_compiled_artifacts_with_models)


class TestCreateDefinitionsWithEmptyTransforms:
    """Test create_definitions with empty or missing transforms.

    Validates FR-005: System returns empty Definitions when no transforms exist.
    """

    @pytest.mark.requirement("FR-005")
    def test_create_definitions_with_no_transforms_field(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test valid artifacts with no transforms still require project_dir."""
        # Remove transforms to trigger empty path (but keep valid structure)
        artifacts = deepcopy(valid_compiled_artifacts)
        artifacts["transforms"] = None

        with pytest.raises(ValueError, match="require project_dir"):
            dagster_plugin.create_definitions(artifacts)

    @pytest.mark.requirement("FR-005")
    def test_create_definitions_with_empty_models_list(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test create_definitions handles empty models list.

        Note: CompiledArtifacts schema requires at least 1 model in transforms.models,
        so this test validates that the schema enforcement works correctly.
        """
        artifacts = deepcopy(valid_compiled_artifacts)
        artifacts["transforms"]["models"] = []

        # Should fail validation (min_length=1 on models)
        with pytest.raises(ValueError, match="models"):
            dagster_plugin.create_definitions(artifacts)


class TestCreateDefinitionsWithInvalidArtifacts:
    """Test create_definitions with invalid CompiledArtifacts inputs.

    Validates FR-009: System MUST validate CompiledArtifacts schema
    before generating definitions.
    """

    @pytest.mark.requirement("FR-009")
    def test_create_definitions_rejects_empty_dict(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test create_definitions raises ValueError for empty dict."""
        with pytest.raises(ValueError, match="CompiledArtifacts validation failed"):
            dagster_plugin.create_definitions({})

    @pytest.mark.requirement("FR-009")
    def test_create_definitions_rejects_missing_required_fields(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test create_definitions raises ValueError for missing required fields."""
        artifacts = deepcopy(valid_compiled_artifacts)
        del artifacts["metadata"]

        with pytest.raises(ValueError, match="metadata"):
            dagster_plugin.create_definitions(artifacts)

    @pytest.mark.requirement("FR-009")
    def test_create_definitions_rejects_invalid_version(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test create_definitions raises ValueError for invalid version format."""
        artifacts = deepcopy(valid_compiled_artifacts)
        artifacts["version"] = "invalid"

        with pytest.raises(ValueError, match="version"):
            dagster_plugin.create_definitions(artifacts)

    @pytest.mark.requirement("FR-009")
    def test_error_message_is_actionable(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test validation error includes actionable guidance."""
        with pytest.raises(ValueError, match="Ensure you are passing output from 'floe compile'"):
            dagster_plugin.create_definitions({})


class TestCreateDefinitionsEdgeCases:
    """Test create_definitions edge cases.

    Tests edge cases like circular dependencies and duplicate transform names.
    """

    @pytest.mark.requirement("FR-007")
    def test_circular_dependencies_are_accepted(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test helper accepts circular dependencies.

        Note: Dagster (not the plugin) handles circular dependency detection.
        The helper should accept any valid transform structure.
        dbt is responsible for detecting circular dependencies during compilation.
        """
        from floe_core.plugins.orchestrator import TransformConfig

        transforms = [
            TransformConfig(name="model_a", compute="duckdb", depends_on=["model_b"]),
            TransformConfig(name="model_b", compute="duckdb", depends_on=["model_a"]),
        ]

        assets = dagster_plugin.create_assets_from_transforms(transforms)
        assert len(assets) == 2

    @pytest.mark.requirement("FR-005")
    def test_duplicate_transform_names_create_separate_assets(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test helper creates separate asset objects for duplicate names.

        Note: Dagster creates separate asset definitions for each model,
        even if they have the same name. The duplicate would be detected
        at Dagster repository/code location load time, not at definition
        creation time. This is expected behavior - the plugin creates
        assets as requested, and Dagster handles validation later.
        """
        from floe_core.plugins.orchestrator import TransformConfig

        transforms = [
            TransformConfig(name="duplicate_model", compute="duckdb"),
            TransformConfig(name="duplicate_model", compute="duckdb"),
        ]

        assets = dagster_plugin.create_assets_from_transforms(transforms)
        assert len(assets) == 2

    @pytest.mark.requirement("FR-007")
    def test_model_with_nonexistent_dependency_accepted(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test helper accepts dependencies not in the artifact.

        External dependencies (like sources) are valid - Dagster will resolve
        them at materialize time.
        """
        from floe_core.plugins.orchestrator import TransformConfig

        transforms = [
            TransformConfig(
                name="model_with_external_dep",
                compute="duckdb",
                depends_on=["external_source"],
            ),
        ]

        assets = dagster_plugin.create_assets_from_transforms(transforms)
        assert len(assets) == 1

    @pytest.mark.requirement("FR-007")
    def test_model_with_many_dependencies(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test helper handles a model with many dependencies."""
        from floe_core.plugins.orchestrator import TransformConfig

        deps = [f"source_{i}" for i in range(10)]
        transforms = [
            TransformConfig(
                name="model_with_many_deps",
                compute="duckdb",
                depends_on=deps,
            ),
        ]

        assets = dagster_plugin.create_assets_from_transforms(transforms)
        assert len(assets) == 1

    @pytest.mark.requirement("FR-006")
    def test_model_names_with_special_characters(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test helper handles model names with underscores."""
        from floe_core.plugins.orchestrator import TransformConfig

        transforms = [
            TransformConfig(name="stg_customers_v2", compute="duckdb"),
            TransformConfig(name="fct_orders_2024", compute="duckdb"),
        ]

        assets = dagster_plugin.create_assets_from_transforms(transforms)
        assert len(assets) == 2
