"""Integration tests for DBTCorePlugin with real dbt-core execution.

These tests execute real dbt commands against DuckDB to verify:
- Project compilation works end-to-end
- Model execution produces correct artifacts
- Test execution works correctly
- Error handling captures real dbt errors

Requirements:
    - dbt-core installed
    - dbt-duckdb adapter installed

Note:
    These tests create temporary dbt projects and execute real dbt commands.
    They are slower than unit tests but provide higher confidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from floe_dbt_core import DBTCorePlugin
from floe_dbt_core.errors import DBTCompilationError, DBTExecutionError

if TYPE_CHECKING:
    from typing import Any


class TestDBTCorePluginIntegration:
    """Integration tests for DBTCorePlugin with real dbt execution."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-002")
    def test_compile_project_real_execution(self, temp_dbt_project: Path) -> None:
        """Test compile_project with real dbt-core execution.

        Verifies:
        - dbt compile runs successfully
        - manifest.json is generated
        - Manifest contains expected model
        """
        plugin = DBTCorePlugin()

        manifest_path = plugin.compile_project(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
        )

        # Verify manifest was created
        assert manifest_path.exists(), "manifest.json should be created"
        assert manifest_path.name == "manifest.json"

        # Verify manifest content
        manifest = plugin.get_manifest(temp_dbt_project)
        assert "metadata" in manifest
        assert manifest["metadata"]["project_name"] == "test_project"
        assert "nodes" in manifest
        # Should contain our example model
        model_keys = [k for k in manifest["nodes"] if k.startswith("model.")]
        assert len(model_keys) >= 1, "Should have at least one model"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-003")
    def test_run_models_real_execution(self, temp_dbt_project: Path) -> None:
        """Test run_models with real dbt-core and DuckDB execution.

        Verifies:
        - dbt run executes successfully
        - DBTRunResult has correct counts
        - run_results.json is created
        - DuckDB database file is created
        """
        plugin = DBTCorePlugin()

        # First compile
        plugin.compile_project(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
        )

        # Then run
        result = plugin.run_models(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
        )

        # Verify result
        assert result.success is True
        assert result.models_run >= 1
        assert result.failures == 0
        assert result.execution_time_seconds > 0

        # Verify artifacts
        assert result.manifest_path.exists()
        assert result.run_results_path.exists()

        # Verify run_results content
        run_results = plugin.get_run_results(temp_dbt_project)
        assert "results" in run_results
        assert len(run_results["results"]) >= 1
        assert run_results["results"][0]["status"] == "success"

        # Verify DuckDB file was created
        duckdb_file = temp_dbt_project / "dev.duckdb"
        assert duckdb_file.exists(), "DuckDB database should be created"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-003")
    def test_run_models_with_select(self, temp_dbt_project: Path) -> None:
        """Test run_models with select pattern.

        Verifies:
        - Select pattern is passed to dbt
        - Only selected models are run
        """
        plugin = DBTCorePlugin()

        # First compile
        plugin.compile_project(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
        )

        # Run with select pattern
        result = plugin.run_models(
            project_dir=temp_dbt_project,
            profiles_dir=temp_dbt_project,
            target="dev",
            select="example",  # Our model is named 'example'
        )

        assert result.success is True
        assert result.models_run >= 1

    @pytest.mark.integration
    @pytest.mark.requirement("FR-004")
    def test_test_models_real_execution(
        self, temp_dbt_project_with_tests: Path
    ) -> None:
        """Test test_models with real dbt test execution.

        Verifies:
        - dbt test runs successfully
        - DBTRunResult has correct test counts
        """
        plugin = DBTCorePlugin()

        # First compile and run models
        plugin.compile_project(
            project_dir=temp_dbt_project_with_tests,
            profiles_dir=temp_dbt_project_with_tests,
            target="dev",
        )
        plugin.run_models(
            project_dir=temp_dbt_project_with_tests,
            profiles_dir=temp_dbt_project_with_tests,
            target="dev",
        )

        # Run tests
        result = plugin.test_models(
            project_dir=temp_dbt_project_with_tests,
            profiles_dir=temp_dbt_project_with_tests,
            target="dev",
        )

        assert result.success is True
        assert result.tests_run >= 1
        assert result.failures == 0

    @pytest.mark.integration
    @pytest.mark.requirement("FR-008")
    def test_supports_parallel_execution_returns_false(self) -> None:
        """Test that DBTCorePlugin reports non-thread-safe.

        dbtRunner is NOT thread-safe per dbt documentation.
        This capability check ensures users know to use Fusion
        for parallel execution.
        """
        plugin = DBTCorePlugin()
        assert plugin.supports_parallel_execution() is False

    @pytest.mark.integration
    @pytest.mark.requirement("FR-009")
    def test_supports_sql_linting_returns_true(self) -> None:
        """Test that DBTCorePlugin reports SQL linting support."""
        plugin = DBTCorePlugin()
        assert plugin.supports_sql_linting() is True

    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_get_runtime_metadata_includes_dbt_version(self) -> None:
        """Test that runtime metadata includes dbt version."""
        plugin = DBTCorePlugin()
        metadata = plugin.get_runtime_metadata()

        assert metadata["runtime"] == "core"
        assert metadata["thread_safe"] is False
        assert "dbt_version" in metadata
        assert metadata["dbt_version"].startswith("1.")  # dbt 1.x

    @pytest.mark.integration
    @pytest.mark.requirement("FR-015")
    def test_compile_failure_structured_error(
        self, temp_dbt_project_invalid: Path
    ) -> None:
        """Test that compilation failures provide structured errors.

        Uses a project with invalid SQL to trigger a real dbt error.
        """
        plugin = DBTCorePlugin()

        with pytest.raises(DBTCompilationError) as exc_info:
            plugin.compile_project(
                project_dir=temp_dbt_project_invalid,
                profiles_dir=temp_dbt_project_invalid,
                target="dev",
            )

        error = exc_info.value
        assert error.message  # Should have an error message
        # Original dbt message should be captured
        assert error.original_message

    @pytest.mark.integration
    @pytest.mark.requirement("FR-014")
    def test_automatic_dbt_deps(
        self, temp_dbt_project_with_packages: Path
    ) -> None:
        """Test that dbt deps runs automatically when packages.yml exists.

        Note: This test may take longer as it downloads packages.
        """
        plugin = DBTCorePlugin()

        # packages.yml exists, deps should run automatically
        manifest_path = plugin.compile_project(
            project_dir=temp_dbt_project_with_packages,
            profiles_dir=temp_dbt_project_with_packages,
            target="dev",
        )

        assert manifest_path.exists()
        # dbt_packages directory should be created by deps
        dbt_packages = temp_dbt_project_with_packages / "dbt_packages"
        assert dbt_packages.exists(), "dbt_packages should be created by dbt deps"


# ---------------------------------------------------------------------------
# Additional Fixtures for Integration Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dbt_project_with_tests(temp_dbt_project: Path) -> Path:
    """Create a dbt project with schema tests.

    Extends temp_dbt_project with tests for the example model.
    """
    # Create schema.yml with tests
    schema_yml = """
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
    (temp_dbt_project / "models" / "schema.yml").write_text(schema_yml)
    return temp_dbt_project


@pytest.fixture
def temp_dbt_project_invalid(tmp_path: Path) -> Path:
    """Create a dbt project with invalid SQL that will fail compilation.

    Useful for testing error handling paths.
    """
    project_dir = tmp_path / "invalid_project"
    project_dir.mkdir(parents=True)

    # Create dbt_project.yml
    dbt_project = """
name: invalid_project
version: "1.0.0"
config-version: 2
profile: test_profile
model-paths: ["models"]
"""
    (project_dir / "dbt_project.yml").write_text(dbt_project)

    # Create profiles.yml
    profiles = """
test_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: dev.duckdb
      threads: 1
"""
    (project_dir / "profiles.yml").write_text(profiles)

    # Create invalid model with undefined variable
    models_dir = project_dir / "models"
    models_dir.mkdir()
    (models_dir / "invalid_model.sql").write_text(
        "-- Invalid model\n"
        "SELECT {{ undefined_variable }} AS bad_column\n"
    )

    return project_dir
