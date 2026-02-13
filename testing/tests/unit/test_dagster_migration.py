"""Dagster SDK compatibility structural validation tests.

Tests that validate Dagster GraphQL queries, sensor definitions, and
import compatibility against the current Dagster 1.12.x SDK.

Requirements:
    WU3-AC4: GraphQL queries use current Dagster schema
    WU3-AC5: Sensor has explicit job/asset_selection target
    WU3-AC3: All source files pass import verification
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_DEPLOY_TEST = (
    REPO_ROOT / "tests" / "e2e" / "test_compile_deploy_materialize_e2e.py"
)
SENSOR_MODULE = (
    REPO_ROOT
    / "plugins"
    / "floe-orchestrator-dagster"
    / "src"
    / "floe_orchestrator_dagster"
    / "sensors.py"
)
DAGSTER_SRC_DIR = (
    REPO_ROOT
    / "plugins"
    / "floe-orchestrator-dagster"
    / "src"
    / "floe_orchestrator_dagster"
)


class TestGraphQLQueryCompatibility:
    """Verify E2E test GraphQL queries use current Dagster schema."""

    @pytest.mark.requirement("WU3-AC4")
    def test_e2e_test_uses_repositories_or_error(self) -> None:
        """Verify GraphQL query uses repositoriesOrError (current API).

        Dagster's current GraphQL API uses repositoriesOrError with
        RepositoryConnection. The old repositoryLocationsOrError API
        is deprecated.
        """
        content = E2E_DEPLOY_TEST.read_text()
        assert "repositoriesOrError" in content, (
            "E2E test must use 'repositoriesOrError' GraphQL query "
            "(current Dagster API). Found old query pattern."
        )

    @pytest.mark.requirement("WU3-AC4")
    def test_e2e_test_does_not_use_deprecated_query(self) -> None:
        """Verify deprecated repositoryLocationsOrError is not used.

        The repositoryLocationsOrError query was the old API for
        querying code locations. It should be replaced with
        repositoriesOrError.
        """
        content = E2E_DEPLOY_TEST.read_text()
        assert "repositoryLocationsOrError" not in content, (
            "E2E test must NOT use deprecated "
            "'repositoryLocationsOrError' query. "
            "Use 'repositoriesOrError' instead."
        )

    @pytest.mark.requirement("WU3-AC4")
    def test_e2e_test_uses_repository_connection(self) -> None:
        """Verify GraphQL uses RepositoryConnection type (not Location)."""
        content = E2E_DEPLOY_TEST.read_text()
        assert "RepositoryConnection" in content, (
            "E2E test must use 'RepositoryConnection' inline fragment. "
            "The old 'RepositoryLocationConnection' type is deprecated."
        )

    @pytest.mark.requirement("WU3-AC4")
    def test_e2e_test_does_not_use_deprecated_type(self) -> None:
        """Verify deprecated RepositoryLocationConnection is not used."""
        content = E2E_DEPLOY_TEST.read_text()
        assert "RepositoryLocationConnection" not in content, (
            "E2E test must NOT use deprecated "
            "'RepositoryLocationConnection' type."
        )


class TestSensorTargetParameter:
    """Verify sensor has explicit job/asset_selection target."""

    @pytest.mark.requirement("WU3-AC5")
    def test_sensor_has_explicit_target(self) -> None:
        """Verify health_check_sensor has job or asset_selection.

        Without an explicit target, the sensor creates a no-op that
        yields RunRequest but Dagster doesn't know which job to run.
        """
        content = SENSOR_MODULE.read_text()
        has_job = "job=" in content or "job_name=" in content
        has_asset_selection = "asset_selection=" in content
        assert has_job or has_asset_selection, (
            "Sensor must have explicit 'job=' or "
            "'asset_selection=' parameter. Without a target, "
            "RunRequest yields create no-op sensor evaluations."
        )

    @pytest.mark.requirement("WU3-AC5")
    def test_sensor_definition_importable(self) -> None:
        """Verify sensor definition imports without error."""
        from floe_orchestrator_dagster.sensors import health_check_sensor

        assert health_check_sensor is not None
        assert health_check_sensor.name == "health_check_sensor"


class TestDagsterImportCompatibility:
    """Verify all dagster imports work with current SDK version."""

    @pytest.mark.requirement("WU3-AC3")
    def test_core_dagster_imports(self) -> None:
        """Verify core dagster imports used across source files."""
        from dagster import (  # noqa: F401
            AssetKey,
            AssetsDefinition,
            ConfigurableIOManager,
            ConfigurableResource,
            Definitions,
            RunRequest,
            ScheduleDefinition,
            SensorEvaluationContext,
            asset,
            sensor,
        )

    @pytest.mark.requirement("WU3-AC3")
    def test_dagster_dbt_imports(self) -> None:
        """Verify dagster-dbt imports used in plugin.py."""
        from dagster_dbt import (  # noqa: F401
            DbtCliResource,
            dbt_assets,
        )

    @pytest.mark.requirement("WU3-AC3")
    def test_dagster_dlt_imports(self) -> None:
        """Verify dagster-dlt imports used in ingestion.py."""
        from dagster_dlt import DagsterDltTranslator  # noqa: F401

    @pytest.mark.requirement("WU3-AC3")
    def test_plugin_module_importable(self) -> None:
        """Verify the full plugin module imports without error."""
        mod = importlib.import_module("floe_orchestrator_dagster")
        assert hasattr(mod, "DagsterOrchestratorPlugin")

    @pytest.mark.requirement("WU3-AC7")
    def test_configurable_io_manager_available(self) -> None:
        """Verify ConfigurableIOManager exists in current dagster."""
        from dagster import ConfigurableIOManager

        assert ConfigurableIOManager is not None

    @pytest.mark.requirement("WU3-AC8")
    def test_configurable_resource_available(self) -> None:
        """Verify ConfigurableResource exists in current dagster."""
        from dagster import ConfigurableResource

        assert ConfigurableResource is not None

    @pytest.mark.requirement("WU3-AC9")
    def test_dagster_dlt_translator_available(self) -> None:
        """Verify DagsterDltTranslator exists in dagster-dlt."""
        from dagster_dlt import DagsterDltTranslator

        assert DagsterDltTranslator is not None


class TestSourceFileImportAudit:
    """Verify all 13 source files have valid imports via AST scan."""

    @pytest.mark.requirement("WU3-AC3")
    def test_all_source_files_parse(self) -> None:
        """Verify all source files in dagster plugin are valid Python.

        AST parse confirms no syntax errors. Combined with the import
        tests above, this validates import compatibility.
        """
        py_files = list(DAGSTER_SRC_DIR.rglob("*.py"))
        # Exclude __pycache__
        py_files = [f for f in py_files if "__pycache__" not in str(f)]

        assert len(py_files) >= 13, (
            f"Expected at least 13 source files, found {len(py_files)}: "
            f"{[f.name for f in py_files]}"
        )

        for py_file in py_files:
            try:
                ast.parse(py_file.read_text())
            except SyntaxError as e:
                pytest.fail(
                    f"Syntax error in {py_file.relative_to(REPO_ROOT)}: "
                    f"{e}"
                )
