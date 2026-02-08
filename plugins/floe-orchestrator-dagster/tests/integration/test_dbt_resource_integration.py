"""Integration tests for DBTResource with real Dagster execution.

These tests verify DBTResource works correctly with Dagster asset
materialization using real dbt execution against DuckDB.

Requirements:
    - FR-037: DBTResource MUST be a Dagster ConfigurableResource
    - FR-030: DBTResource MUST load DBTPlugin from registry
    - FR-031: DBTResource MUST delegate to plugin methods
    - FR-032: DBTResource MUST pass select/exclude patterns

Note:
    These tests run in Kind cluster with real Dagster deployment.
    They require dbt-core and dbt-duckdb to be installed.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

# Import types at module level for Dagster decorator resolution
# (needed because `from __future__ import annotations` defers type hints)
from dagster import Output
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

if TYPE_CHECKING:
    pass


def _generate_unique_project_name(prefix: str = "test_project") -> str:
    """Generate unique project name to prevent test pollution.

    Uses UUID suffix to ensure isolation between parallel test runs.
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# Check if dbt-core is available
try:
    from dbt.cli.main import dbtRunner  # noqa: F401

    DBT_AVAILABLE = True
except ImportError:
    DBT_AVAILABLE = False


def require_dbt() -> None:
    """Fail test if dbt-core is not installed.

    Tests FAIL (not skip) when infrastructure missing per testing standards.
    """
    if not DBT_AVAILABLE:
        pytest.fail(
            "dbt-core not installed - integration tests require dbt-core.\n"
            "Install with: pip install dbt-core dbt-duckdb\n"
            "Or run: uv sync --all-extras"
        )


class TestDBTResourceWithDagster(IntegrationTestBase):
    """Integration tests for DBTResource with real Dagster execution."""

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.fixture
    def temp_dbt_project(self, tmp_path: Path) -> Path:
        """Create a minimal temporary dbt project for testing.

        Creates a valid dbt project structure with:
        - dbt_project.yml (project configuration)
        - profiles.yml (DuckDB target)
        - models/example.sql (simple model)

        Uses unique project name to prevent test pollution.
        """
        project_name = _generate_unique_project_name()
        project_dir = tmp_path / project_name
        project_dir.mkdir(parents=True)

        # Create dbt_project.yml
        dbt_project = f"""\
name: {project_name}
version: "1.0.0"
config-version: 2
profile: test_profile
model-paths:
  - models
"""
        (project_dir / "dbt_project.yml").write_text(dbt_project)

        # Create profiles.yml with DuckDB target
        profiles = f"""\
test_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: {project_dir / "dev.duckdb"}
      threads: 1
"""
        (project_dir / "profiles.yml").write_text(profiles)

        # Create models directory with example model
        models_dir = project_dir / "models"
        models_dir.mkdir()
        (models_dir / "example.sql").write_text(
            "-- Example model for testing\nSELECT 1 AS id, 'test' AS name\n"
        )

        return project_dir

    @pytest.mark.integration
    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_is_configurable_resource(self) -> None:
        """Test that DBTResource is a Dagster ConfigurableResource."""
        from dagster import ConfigurableResource

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        assert issubclass(DBTResource, ConfigurableResource)

    @pytest.mark.integration
    @pytest.mark.requirement("FR-030")
    def test_dbt_resource_loads_core_plugin(self, temp_dbt_project: Path) -> None:
        """Test that DBTResource loads the core plugin from registry."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        plugin = resource.get_plugin()

        # Plugin should be a dbt adapter plugin
        assert hasattr(plugin, "name")
        assert plugin.name == "core"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_compile_with_real_dbt(self, temp_dbt_project: Path) -> None:
        """Test DBTResource.compile() with real dbt execution."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        manifest_path = resource.compile()

        assert manifest_path.exists()
        assert manifest_path.name == "manifest.json"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_run_models_with_real_dbt(
        self, temp_dbt_project: Path
    ) -> None:
        """Test DBTResource.run_models() with real dbt execution."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        # First compile
        resource.compile()

        # Then run
        result = resource.run_models()

        assert result.success is True
        assert result.models_run >= 1
        assert result.failures == 0

        # Verify DuckDB file was created
        duckdb_file = temp_dbt_project / "dev.duckdb"
        assert duckdb_file.exists()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-032")
    def test_dbt_resource_run_models_with_select(self, temp_dbt_project: Path) -> None:
        """Test DBTResource.run_models() with select pattern."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        # First compile
        resource.compile()

        # Run with select pattern
        result = resource.run_models(select="example")

        assert result.success is True
        assert result.models_run >= 1

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_get_manifest(self, temp_dbt_project: Path) -> None:
        """Test DBTResource.get_manifest() returns valid manifest."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        # First compile to generate manifest
        resource.compile()

        # Get manifest
        manifest = resource.get_manifest()

        assert "metadata" in manifest
        # Project name has unique suffix for test isolation
        assert manifest["metadata"]["project_name"].startswith("test_project")
        assert "nodes" in manifest

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_get_run_results(self, temp_dbt_project: Path) -> None:
        """Test DBTResource.get_run_results() returns valid results."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        # First compile and run
        resource.compile()
        resource.run_models()

        # Get run results
        run_results = resource.get_run_results()

        assert "results" in run_results
        assert len(run_results["results"]) >= 1
        assert run_results["results"][0]["status"] == "success"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_supports_parallel_execution(self) -> None:
        """Test DBTResource.supports_parallel_execution() for core plugin."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(plugin_name="core")
        result = resource.supports_parallel_execution()

        # Core plugin (dbtRunner) is NOT thread-safe
        assert result is False

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_supports_sql_linting(self) -> None:
        """Test DBTResource.supports_sql_linting() for core plugin."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(plugin_name="core")
        result = resource.supports_sql_linting()

        # Core plugin supports linting
        assert result is True

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_get_runtime_metadata(self) -> None:
        """Test DBTResource.get_runtime_metadata() includes dbt version."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        resource = DBTResource(plugin_name="core")
        metadata = resource.get_runtime_metadata()

        assert metadata["runtime"] == "core"
        assert metadata["thread_safe"] is False
        assert "dbt_version" in metadata
        assert metadata["dbt_version"].startswith("1.")  # dbt 1.x


class TestDBTResourceWithDagsterAsset(IntegrationTestBase):
    """Integration tests for DBTResource used within Dagster assets."""

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.fixture
    def temp_dbt_project(self, tmp_path: Path) -> Path:
        """Create a minimal temporary dbt project for testing.

        Uses unique project name to prevent test pollution.
        """
        project_name = _generate_unique_project_name()
        project_dir = tmp_path / project_name
        project_dir.mkdir(parents=True)

        dbt_project = f"""\
name: {project_name}
version: "1.0.0"
config-version: 2
profile: test_profile
model-paths:
  - models
"""
        (project_dir / "dbt_project.yml").write_text(dbt_project)

        profiles = f"""\
test_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: {project_dir / "dev.duckdb"}
      threads: 1
"""
        (project_dir / "profiles.yml").write_text(profiles)

        models_dir = project_dir / "models"
        models_dir.mkdir()
        (models_dir / "staging_customers.sql").write_text(
            "SELECT 1 AS customer_id, 'Alice' AS name"
        )
        (models_dir / "staging_orders.sql").write_text(
            "SELECT 1 AS order_id, 1 AS customer_id, 100.00 AS amount"
        )

        return project_dir

    @pytest.mark.integration
    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_in_dagster_definitions(self, temp_dbt_project: Path) -> None:
        """Test DBTResource can be used in Dagster Definitions."""
        require_dbt()

        from dagster import Definitions, asset

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        @asset
        def my_dbt_models(dbt: DBTResource) -> dict[str, Any]:
            """Asset that uses DBTResource."""
            result = dbt.run_models()
            return {
                "success": result.success,
                "models_run": result.models_run,
            }

        dbt_resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        # First compile to generate manifest
        dbt_resource.compile()

        definitions = Definitions(
            assets=[my_dbt_models],
            resources={"dbt": dbt_resource},
        )

        # Verify definitions are valid
        assert isinstance(definitions, Definitions)
        assert len(definitions.assets) == 1

    @pytest.mark.integration
    @pytest.mark.requirement("FR-037")
    def test_dbt_resource_asset_execution(self, temp_dbt_project: Path) -> None:
        """Test asset materialization with DBTResource."""
        require_dbt()

        from dagster import (
            Output,
            asset,
            materialize,
        )

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        @asset
        def dbt_run_asset(dbt: DBTResource) -> Output[dict[str, Any]]:
            """Asset that runs dbt models."""
            result = dbt.run_models()
            return Output(
                value={
                    "success": result.success,
                    "models_run": result.models_run,
                    "failures": result.failures,
                },
                metadata={
                    "models_run": result.models_run,
                    "failures": result.failures,
                },
            )

        dbt_resource = DBTResource(
            plugin_name="core",
            project_dir=str(temp_dbt_project),
            profiles_dir=str(temp_dbt_project),
            target="dev",
        )

        # First compile to generate manifest
        dbt_resource.compile()

        # Materialize the asset
        result = materialize(
            assets=[dbt_run_asset],
            resources={"dbt": dbt_resource},
        )

        # Verify materialization succeeded
        assert result.success
        materialization_event = result.asset_materializations_for_node("dbt_run_asset")
        assert len(list(materialization_event)) == 1

    @pytest.mark.integration
    @pytest.mark.requirement("FR-031")
    def test_dbt_resource_test_models(self, tmp_path: Path) -> None:
        """Test DBTResource.test_models() with real dbt execution."""
        require_dbt()

        from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

        # Create project with tests (using unique name for isolation)
        project_name = _generate_unique_project_name("test_with_tests")
        project_dir = tmp_path / project_name
        project_dir.mkdir(parents=True)

        dbt_project = f"""\
name: {project_name}
version: "1.0.0"
config-version: 2
profile: test_profile
model-paths:
  - models
"""
        (project_dir / "dbt_project.yml").write_text(dbt_project)

        profiles = f"""\
test_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: {project_dir / "dev.duckdb"}
      threads: 1
"""
        (project_dir / "profiles.yml").write_text(profiles)

        models_dir = project_dir / "models"
        models_dir.mkdir()
        (models_dir / "example.sql").write_text("SELECT 1 AS id, 'test' AS name")

        # Create schema.yml with tests
        schema_yml = """\
version: 2

models:
  - name: example
    description: "Example model for testing"
    columns:
      - name: id
        description: "Primary key"
        tests:
          - not_null
      - name: name
        description: "Name field"
        tests:
          - not_null
"""
        (models_dir / "schema.yml").write_text(schema_yml)

        resource = DBTResource(
            plugin_name="core",
            project_dir=str(project_dir),
            profiles_dir=str(project_dir),
            target="dev",
        )

        # Compile and run models first
        resource.compile()
        resource.run_models()

        # Run tests
        result = resource.test_models()

        assert result.success is True
        assert result.tests_run >= 1
        assert result.failures == 0
