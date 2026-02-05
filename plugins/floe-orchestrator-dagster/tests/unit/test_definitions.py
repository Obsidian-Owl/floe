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
    """Test create_definitions with valid CompiledArtifacts inputs.

    Validates FR-005: System MUST generate valid Dagster Definitions
    object from CompiledArtifacts.
    """

    def test_create_definitions_returns_definitions_object(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test create_definitions returns a Dagster Definitions object."""
        from dagster import Definitions

        result = dagster_plugin.create_definitions(valid_compiled_artifacts)

        assert isinstance(result, Definitions)

    def test_create_definitions_creates_assets_from_models(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts_with_models: dict[str, Any],
    ) -> None:
        """Test create_definitions creates assets for all models."""
        from dagster import Definitions

        result = dagster_plugin.create_definitions(valid_compiled_artifacts_with_models)

        assert isinstance(result, Definitions)
        assert len(result.assets) > 0

    def test_create_definitions_preserves_model_count(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts_with_models: dict[str, Any],
    ) -> None:
        """Test create_definitions creates correct number of assets."""
        from dagster import Definitions

        result = dagster_plugin.create_definitions(valid_compiled_artifacts_with_models)

        # Fixture has 3 models - verify assets were created
        assert isinstance(result, Definitions)
        assert len(result.assets) == 3


class TestCreateDefinitionsWithEmptyTransforms:
    """Test create_definitions with empty or missing transforms.

    Validates FR-005: System returns empty Definitions when no transforms exist.
    """

    def test_create_definitions_with_no_transforms_field(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test create_definitions handles missing transforms field."""
        from dagster import Definitions

        # Remove transforms to trigger empty path (but keep valid structure)
        artifacts = deepcopy(valid_compiled_artifacts)
        artifacts["transforms"] = None

        result = dagster_plugin.create_definitions(artifacts)

        assert isinstance(result, Definitions)

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

    def test_create_definitions_rejects_empty_dict(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test create_definitions raises ValueError for empty dict."""
        with pytest.raises(ValueError, match="CompiledArtifacts validation failed"):
            dagster_plugin.create_definitions({})

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

    def test_error_message_is_actionable(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test validation error includes actionable guidance."""
        with pytest.raises(ValueError, match="Ensure you are passing output from 'floe compile'"):
            dagster_plugin.create_definitions({})


class TestCreateDefinitionsEdgeCases:
    """Test create_definitions edge cases.

    Tests edge cases like circular dependencies and duplicate transform names.
    """

    def test_circular_dependencies_are_accepted(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test that circular dependencies in models are accepted.

        Note: Dagster (not the plugin) handles circular dependency detection.
        The plugin should accept any valid CompiledArtifacts structure.
        dbt is responsible for detecting circular dependencies during compilation.
        """
        artifacts = deepcopy(valid_compiled_artifacts)
        # Create circular dependency: A -> B -> A
        artifacts["transforms"]["models"] = [
            {"name": "model_a", "compute": "duckdb", "depends_on": ["model_b"]},
            {"name": "model_b", "compute": "duckdb", "depends_on": ["model_a"]},
        ]

        # The plugin should accept this - Dagster will handle the circular deps
        # at materialize time, not at definition creation time
        from dagster import Definitions

        result = dagster_plugin.create_definitions(artifacts)
        assert isinstance(result, Definitions)
        assert len(result.assets) == 2

    def test_duplicate_transform_names_create_separate_assets(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test that duplicate transform names create separate asset objects.

        Note: Dagster creates separate asset definitions for each model,
        even if they have the same name. The duplicate would be detected
        at Dagster repository/code location load time, not at definition
        creation time. This is expected behavior - the plugin creates
        assets as requested, and Dagster handles validation later.
        """
        artifacts = deepcopy(valid_compiled_artifacts)
        # Create duplicate names
        artifacts["transforms"]["models"] = [
            {"name": "duplicate_model", "compute": "duckdb"},
            {"name": "duplicate_model", "compute": "duckdb"},
        ]

        # Plugin creates the assets - Dagster validates at load time
        from dagster import Definitions

        result = dagster_plugin.create_definitions(artifacts)
        assert isinstance(result, Definitions)
        # Both assets are created (validation happens at load time)
        assert len(result.assets) == 2

    def test_model_with_nonexistent_dependency_accepted(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test that models can reference dependencies not in the artifact.

        External dependencies (like sources) are valid - Dagster will resolve
        them at materialize time.
        """
        artifacts = deepcopy(valid_compiled_artifacts)
        artifacts["transforms"]["models"] = [
            {
                "name": "model_with_external_dep",
                "compute": "duckdb",
                "depends_on": ["external_source"],
            },
        ]

        # Should succeed - external deps are allowed
        from dagster import Definitions

        result = dagster_plugin.create_definitions(artifacts)
        assert isinstance(result, Definitions)
        assert len(result.assets) == 1

    def test_model_with_many_dependencies(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test model with many dependencies is handled correctly."""
        artifacts = deepcopy(valid_compiled_artifacts)
        # Create a model with many dependencies
        deps = [f"source_{i}" for i in range(10)]
        artifacts["transforms"]["models"] = [
            {"name": "model_with_many_deps", "compute": "duckdb", "depends_on": deps},
        ]

        from dagster import Definitions

        result = dagster_plugin.create_definitions(artifacts)
        assert isinstance(result, Definitions)
        assert len(result.assets) == 1

    def test_model_names_with_special_characters(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test model names with underscores are handled correctly."""
        artifacts = deepcopy(valid_compiled_artifacts)
        artifacts["transforms"]["models"] = [
            {"name": "stg_customers_v2", "compute": "duckdb"},
            {"name": "fct_orders_2024", "compute": "duckdb"},
        ]

        from dagster import Definitions

        result = dagster_plugin.create_definitions(artifacts)
        assert isinstance(result, Definitions)
        assert len(result.assets) == 2
