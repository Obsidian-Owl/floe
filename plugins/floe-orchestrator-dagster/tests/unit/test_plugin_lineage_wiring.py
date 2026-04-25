"""Unit tests for lineage resource wiring in the Dagster runtime.

These tests verify that build_product_definitions() wires try_create_lineage_resource()
into the runtime Definitions resources dict, and that assets created by
_create_asset_for_transform() declare "lineage" in required_resource_keys.

Requirements Covered:
- AC-11: Lineage resource wiring into create_definitions()
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

_RUNTIME_MODULE = "floe_orchestrator_dagster.runtime"

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


def _write_runtime_project(tmp_path: Path, artifacts: dict[str, Any]) -> Path:
    """Write a minimal dbt project for runtime builder tests."""
    project_dir = tmp_path / "dbt_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "compiled_artifacts.json").write_text(json.dumps(artifacts))

    target_dir = project_dir / "target"
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
            "dbt_version": "1.7.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "invocation_id": "test-invocation",
        },
        "nodes": {},
        "sources": {},
        "exposures": {},
        "metrics": {},
        "groups": {},
        "selectors": {},
        "disabled": [],
        "parent_map": {},
        "child_map": {},
        "group_map": {},
        "semantic_models": {},
        "unit_tests": {},
        "saved_queries": {},
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest))
    return project_dir


def _build_runtime_definitions(artifacts: dict[str, Any], tmp_path: Path) -> Any:
    """Build runtime Definitions from validated artifacts and a real project_dir."""
    from floe_orchestrator_dagster.runtime import build_product_definitions

    validated = CompiledArtifacts.model_validate(artifacts)
    project_dir = _write_runtime_project(tmp_path, artifacts)
    return build_product_definitions(
        product_name=validated.metadata.product_name,
        artifacts=validated,
        project_dir=project_dir,
    )


class TestCreateDefinitionsIncludesLineageResource:
    """Test runtime builder includes lineage resource in Definitions.

    Validates AC-11: runtime building MUST call try_create_lineage_resource(plugins)
    and merge the result into the Definitions resources dict.
    """

    @pytest.mark.requirement("AC-11")
    def test_create_definitions_includes_lineage_resource(
        self,
        tmp_path: Path,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test runtime builder returns Definitions with 'lineage' key in resources.

        When runtime Definitions are built with valid artifacts, the returned
        Definitions MUST include a "lineage" key in its resources dict. This
        verifies the lineage resource is actually merged into the final
        Definitions object, not just created and discarded.
        """
        from dagster import Definitions

        mock_lineage_resource = MagicMock()

        with patch(f"{_RUNTIME_MODULE}.try_create_lineage_resource") as mock_try_create:
            mock_try_create.return_value = {"lineage": mock_lineage_resource}

            result = _build_runtime_definitions(valid_compiled_artifacts, tmp_path)

            assert isinstance(result, Definitions)
            assert isinstance(result.resources, dict)
            assert "lineage" in result.resources, (
                "Definitions.resources must contain 'lineage' key — "
                "build_product_definitions() must merge try_create_lineage_resource() "
                "result into the resources dict"
            )
            assert result.resources["lineage"] is mock_lineage_resource, (
                "The 'lineage' resource in Definitions must be the exact object "
                "returned by try_create_lineage_resource(), not a replacement"
            )


class TestCreateDefinitionsCallsTryCreateLineageResource:
    """Test runtime builder calls try_create_lineage_resource with correct args.

    Validates AC-11: runtime building MUST call try_create_lineage_resource(plugins).
    """

    @pytest.mark.requirement("AC-11")
    def test_create_definitions_calls_try_create_lineage_resource(
        self,
        tmp_path: Path,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test try_create_lineage_resource is called with the plugins from artifacts.

        Verifies the factory function is actually invoked (not skipped), and that
        the plugins argument passed to it comes from the validated CompiledArtifacts,
        not a hardcoded None or empty object.
        """
        mock_lineage_resource = MagicMock()

        with patch(f"{_RUNTIME_MODULE}.try_create_lineage_resource") as mock_try_create:
            mock_try_create.return_value = {"lineage": mock_lineage_resource}

            _build_runtime_definitions(valid_compiled_artifacts, tmp_path)

            # Verify the factory was called exactly once
            mock_try_create.assert_called_once()

            # Verify the plugins argument is passed (not None when artifacts have plugins)
            call_args = mock_try_create.call_args
            plugins_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("plugins")
            assert plugins_arg is not None, (
                "try_create_lineage_resource must be called with the plugins "
                "from validated CompiledArtifacts, not None"
            )

    @pytest.mark.requirement("AC-11")
    def test_create_definitions_passes_validated_plugins_to_lineage_factory(
        self,
        tmp_path: Path,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test the plugins object passed to try_create_lineage_resource has expected structure.

        A sloppy implementation might pass the raw dict instead of the validated
        ResolvedPlugins Pydantic model. This test catches that by checking the
        argument has attributes expected on a validated ResolvedPlugins instance.
        """
        from floe_core.schemas.compiled_artifacts import ResolvedPlugins

        captured_plugins: list[Any] = []

        def capture_plugins(plugins: Any) -> dict[str, Any]:
            captured_plugins.append(plugins)
            return {"lineage": MagicMock()}

        with patch(
            f"{_RUNTIME_MODULE}.try_create_lineage_resource",
            side_effect=capture_plugins,
        ):
            _build_runtime_definitions(valid_compiled_artifacts, tmp_path)

        assert len(captured_plugins) == 1, "try_create_lineage_resource must be called exactly once"
        assert isinstance(captured_plugins[0], ResolvedPlugins), (
            f"try_create_lineage_resource must receive a ResolvedPlugins instance, "
            f"got {type(captured_plugins[0]).__name__}"
        )


class TestCreateDefinitionsLineageResourceWhenNoPlugins:
    """Test runtime builder still provides lineage when plugins=None.

    Validates AC-11: When artifacts have plugins=None, lineage resource MUST
    still be present (NoOp).
    """

    @pytest.fixture
    def artifacts_without_plugins(self) -> dict[str, Any]:
        """Create valid CompiledArtifacts with no plugins field.

        Returns:
            CompiledArtifacts dict without plugins section.
        """
        return {
            "version": "0.3.0",
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.3.0",
                "source_hash": "sha256:abc123def456",
                "product_name": "test-pipeline",
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": "default.test_pipeline",
                "domain": "default",
                "repository": "github.com/test/test-pipeline",
            },
            "mode": "simple",
            "observability": {
                "telemetry": {
                    "enabled": True,
                    "resource_attributes": {
                        "service_name": "test-pipeline",
                        "service_version": "1.0.0",
                        "deployment_environment": "dev",
                        "floe_namespace": "default",
                        "floe_product_name": "test-pipeline",
                        "floe_product_version": "1.0.0",
                        "floe_mode": "dev",
                    },
                },
                "lineage": True,
                "lineage_namespace": "test-pipeline",
            },
            "transforms": {
                "models": [
                    {"name": "stg_customers", "compute": "duckdb"},
                ],
                "default_compute": "duckdb",
            },
        }

    @pytest.mark.requirement("AC-11")
    def test_create_definitions_lineage_resource_when_no_plugins(
        self,
        tmp_path: Path,
        artifacts_without_plugins: dict[str, Any],
    ) -> None:
        """Test lineage resource is still present when artifacts have no plugins.

        Even when plugins=None, create_definitions() MUST still call
        try_create_lineage_resource (which returns a NoOp resource), so
        assets that require "lineage" resource key can still execute.
        """
        from dagster import Definitions

        mock_noop_lineage = MagicMock()

        with patch(f"{_RUNTIME_MODULE}.try_create_lineage_resource") as mock_try_create:
            mock_try_create.return_value = {"lineage": mock_noop_lineage}

            result = _build_runtime_definitions(artifacts_without_plugins, tmp_path)

            assert isinstance(result, Definitions)

            # Verify try_create_lineage_resource was still called
            mock_try_create.assert_called_once()

            # Verify lineage is in resources
            assert isinstance(result.resources, dict)
            assert "lineage" in result.resources, (
                "Definitions must include 'lineage' resource even when "
                "plugins is None — try_create_lineage_resource returns a NoOp"
            )

    @pytest.mark.requirement("AC-11")
    def test_create_definitions_calls_lineage_factory_with_none_plugins(
        self,
        tmp_path: Path,
        artifacts_without_plugins: dict[str, Any],
    ) -> None:
        """Test lineage factory is called with None when artifacts have no plugins.

        The factory must handle None plugins gracefully (returning NoOp resource).
        This catches an implementation that skips calling the factory entirely
        when plugins is None.
        """
        captured_args: list[Any] = []

        def capture_call(plugins: Any) -> dict[str, Any]:
            captured_args.append(plugins)
            return {"lineage": MagicMock()}

        with patch(
            f"{_RUNTIME_MODULE}.try_create_lineage_resource",
            side_effect=capture_call,
        ):
            _build_runtime_definitions(artifacts_without_plugins, tmp_path)

        assert len(captured_args) == 1, (
            "try_create_lineage_resource must be called even when plugins is None"
        )
        # plugins=None is acceptable; the factory handles it
        # The key assertion is that the factory IS called (above)


class TestDBTResourceKeysIncludesLineage:
    """Test _DBT_RESOURCE_KEYS frozenset includes 'lineage'.

    Validates AC-11: _DBT_RESOURCE_KEYS MUST contain "lineage".
    """

    @pytest.mark.requirement("AC-11")
    def test_dbt_resource_keys_includes_lineage(self) -> None:
        """Test _DBT_RESOURCE_KEYS frozenset contains 'lineage'.

        The module-level constant _DBT_RESOURCE_KEYS must include "lineage"
        so that all assets created via _create_asset_for_transform() declare
        the lineage resource dependency.
        """
        from floe_orchestrator_dagster.plugin import _DBT_RESOURCE_KEYS

        assert "lineage" in _DBT_RESOURCE_KEYS, (
            f'_DBT_RESOURCE_KEYS must include "lineage" — current value: {_DBT_RESOURCE_KEYS}'
        )

    @pytest.mark.requirement("AC-11")
    def test_dbt_resource_keys_still_includes_dbt(self) -> None:
        """Test _DBT_RESOURCE_KEYS still contains 'dbt' after adding 'lineage'.

        Regression guard: adding "lineage" must not remove the existing "dbt" key.
        """
        from floe_orchestrator_dagster.plugin import _DBT_RESOURCE_KEYS

        assert "dbt" in _DBT_RESOURCE_KEYS, (
            f'_DBT_RESOURCE_KEYS must still include "dbt" — current value: {_DBT_RESOURCE_KEYS}'
        )

    @pytest.mark.requirement("AC-11")
    def test_dbt_resource_keys_is_frozenset(self) -> None:
        """Test _DBT_RESOURCE_KEYS is a frozenset (immutable).

        A mutable set could be accidentally modified at runtime, breaking
        resource key declarations for subsequently created assets.
        """
        from floe_orchestrator_dagster.plugin import _DBT_RESOURCE_KEYS

        assert isinstance(_DBT_RESOURCE_KEYS, frozenset), (
            f"_DBT_RESOURCE_KEYS must be a frozenset, got {type(_DBT_RESOURCE_KEYS).__name__}"
        )

    @pytest.mark.requirement("AC-11")
    def test_dbt_resource_keys_has_exactly_expected_members(self) -> None:
        """Test _DBT_RESOURCE_KEYS contains exactly {'dbt', 'lineage'}.

        Catches implementations that add unexpected extra keys or omit expected ones.
        """
        from floe_orchestrator_dagster.plugin import _DBT_RESOURCE_KEYS

        expected = frozenset({"dbt", "lineage"})
        assert _DBT_RESOURCE_KEYS == expected, (
            f"_DBT_RESOURCE_KEYS must be exactly {expected}, got {_DBT_RESOURCE_KEYS}"
        )


class TestAssetRequiredResourceKeysIncludesLineage:
    """Test assets from _create_asset_for_transform() include 'lineage' in resource keys.

    Validates AC-11: Assets created by _create_asset_for_transform() MUST have
    "lineage" in their required_resource_keys.
    """

    @pytest.mark.requirement("AC-11")
    def test_asset_required_resource_keys_includes_lineage(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: Any,
    ) -> None:
        """Test a single asset has 'lineage' in required_resource_keys.

        Creates an asset from a transform config and verifies the resulting
        AssetsDefinition declares "lineage" as a required resource key.
        """
        assets = dagster_plugin.create_assets_from_transforms([sample_transform_config])
        assert len(assets) == 1, "Expected exactly 1 asset"

        asset_def = assets[0]
        required_keys = asset_def.required_resource_keys
        assert "lineage" in required_keys, (
            f"Asset required_resource_keys must include 'lineage', got: {required_keys}"
        )

    @pytest.mark.requirement("AC-11")
    def test_asset_required_resource_keys_includes_dbt_and_lineage(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: Any,
    ) -> None:
        """Test asset has both 'dbt' and 'lineage' in required_resource_keys.

        Regression guard: adding "lineage" must not remove "dbt".
        """
        assets = dagster_plugin.create_assets_from_transforms([sample_transform_config])
        assert len(assets) == 1

        required_keys = assets[0].required_resource_keys
        assert "dbt" in required_keys, (
            f"Asset required_resource_keys must include 'dbt', got: {required_keys}"
        )
        assert "lineage" in required_keys, (
            f"Asset required_resource_keys must include 'lineage', got: {required_keys}"
        )

    @pytest.mark.requirement("AC-11")
    def test_all_assets_have_lineage_in_required_resource_keys(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_configs: list[Any],
    ) -> None:
        """Test ALL assets from multiple transforms include 'lineage' resource key.

        A sloppy implementation might only add lineage to the first asset. This
        test creates 3 assets and checks each one individually.
        """
        assets = dagster_plugin.create_assets_from_transforms(sample_transform_configs)
        assert len(assets) == 3, "Expected 3 assets from sample_transform_configs"

        for i, asset_def in enumerate(assets):
            required_keys = asset_def.required_resource_keys
            assert "lineage" in required_keys, (
                f"Asset {i} ({asset_def.key}) required_resource_keys must include "
                f"'lineage', got: {required_keys}"
            )

    @pytest.mark.requirement("AC-11")
    def test_create_definitions_assets_have_lineage_resource_key(
        self,
        tmp_path: Path,
        valid_compiled_artifacts: dict[str, Any],
    ) -> None:
        """Test runtime Definitions assets have lineage resource key.

        Runtime check: not just create_assets_from_transforms in isolation,
        but assets as they appear in the final Definitions object returned by
        build_product_definitions().
        """
        mock_lineage_resource = MagicMock()

        with patch(f"{_RUNTIME_MODULE}.try_create_lineage_resource") as mock_try_create:
            mock_try_create.return_value = {"lineage": mock_lineage_resource}

            result = _build_runtime_definitions(valid_compiled_artifacts, tmp_path)

        # valid_compiled_artifacts has 1 model (stg_customers)
        assert len(result.assets) >= 1, "Expected at least 1 asset in Definitions"

        for asset_def in result.assets:
            required_keys = asset_def.required_resource_keys
            assert "lineage" in required_keys, (
                f"Asset {asset_def.key} from build_product_definitions() must have 'lineage' "
                f"in required_resource_keys, got: {required_keys}"
            )


class TestLineageResourceExports:
    """Tests for lineage factory exports from resources package — T5.

    Validates AC-11: The resources package __init__.py MUST export
    create_lineage_resource and try_create_lineage_resource so that
    consumers can import them directly from
    floe_orchestrator_dagster.resources.
    """

    @pytest.mark.requirement("AC-11")
    def test_create_lineage_resource_importable_from_resources(self) -> None:
        """Test create_lineage_resource is exported from resources package.

        Verifies that the factory function is importable via the public
        resources package API, not only from the private submodule.
        """
        from floe_orchestrator_dagster.resources import create_lineage_resource

        assert callable(create_lineage_resource)

    @pytest.mark.requirement("AC-11")
    def test_try_create_lineage_resource_importable_from_resources(self) -> None:
        """Test try_create_lineage_resource is exported from resources package.

        Verifies that the try_ variant is importable via the public
        resources package API, not only from the private submodule.
        """
        from floe_orchestrator_dagster.resources import try_create_lineage_resource

        assert callable(try_create_lineage_resource)

    @pytest.mark.requirement("AC-11")
    def test_lineage_exports_in_all(self) -> None:
        """Test lineage factory functions are listed in __all__.

        Functions not in __all__ are considered private API and may not
        appear in wildcard imports or IDE autocompletion. Both factory
        functions MUST be explicitly listed.
        """
        import floe_orchestrator_dagster.resources as resources_mod

        assert hasattr(resources_mod, "__all__"), "resources package must define __all__"
        assert "create_lineage_resource" in resources_mod.__all__, (
            f"'create_lineage_resource' must be in resources.__all__, got: {resources_mod.__all__}"
        )
        assert "try_create_lineage_resource" in resources_mod.__all__, (
            f"'try_create_lineage_resource' must be in resources.__all__, "
            f"got: {resources_mod.__all__}"
        )
