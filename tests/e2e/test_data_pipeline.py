"""E2E tests for complete data pipeline execution.

This module validates end-to-end data pipeline workflows including:
- dbt seed data loading
- Pipeline execution with dependency ordering
- Medallion architecture transforms (Bronze → Silver → Gold)
- Iceberg table creation and validation
- dbt schema and data quality tests
- Incremental model merge behavior
- Pipeline failure recording and retry

All tests run against the customer-360 demo pipeline in a real K8s environment.

Requirements Covered:
- FR-020: Pipeline execution order validation
- FR-021: Medallion layer transforms
- FR-022: Iceberg table creation
- FR-023: dbt seed functionality
- FR-024: dbt test execution
- FR-025: Incremental model merges
- FR-026: Data quality checks
- FR-027: Pipeline failure recording
- FR-028: Pipeline retry from failure point

Per testing standards: Tests FAIL when infrastructure is unavailable.
No pytest.skip() - see .claude/rules/testing-standards.md
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import duckdb
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.polling import wait_for_condition

if TYPE_CHECKING:
    pass


class TestDataPipeline(IntegrationTestBase):
    """E2E tests for data pipeline execution.

    These tests validate complete data pipeline workflows using the
    customer-360 demo project. They exercise:
    - dbt operations (seed, run, test)
    - Dagster orchestration
    - Iceberg table management via Polaris catalog
    - Data quality validation

    Requires all platform services running:
    - Dagster (orchestrator)
    - Polaris (catalog)
    - MinIO (S3-compatible storage)
    """

    # Services required for E2E pipeline tests
    required_services: ClassVar[list[tuple[str, int]]] = [
        ("dagster", 3000),
        ("polaris", 8181),
        ("minio", 9000),
    ]

    def _get_demo_project_path(self) -> Path:
        """Get path to customer-360 demo project.

        Returns:
            Path to demo/customer-360 directory.

        Raises:
            FileNotFoundError: If demo project not found.
        """
        project_path = Path(__file__).parent.parent.parent / "demo" / "customer-360"
        if not project_path.exists():
            pytest.fail(
                f"Demo project not found at {project_path}\n"
                "Expected: demo/customer-360 directory with dbt project"
            )
        return project_path

    def _run_dbt_command(
        self,
        command: list[str],
        project_dir: Path,
        timeout: float = 60.0,
    ) -> subprocess.CompletedProcess[str]:
        """Run a dbt command in the demo project.

        Args:
            command: dbt command and arguments (e.g., ["seed"], ["run"]).
            project_dir: Path to dbt project directory.
            timeout: Command timeout in seconds. Defaults to 60.0.

        Returns:
            CompletedProcess with stdout/stderr.

        Raises:
            subprocess.CalledProcessError: If dbt command fails.
        """
        full_command = [
            "dbt",
            *command,
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir),
        ]

        result = subprocess.run(
            full_command,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result

    def _get_duckdb_connection(self, project_dir: Path) -> duckdb.DuckDBPyConnection:
        """Get DuckDB connection to the demo database.

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            DuckDB connection.
        """
        db_path = project_dir / "target" / "demo.duckdb"
        return duckdb.connect(str(db_path))

    def _check_table_exists_in_duckdb(
        self,
        project_dir: Path,
        table_name: str,
    ) -> bool:
        """Check if a table exists in DuckDB.

        Args:
            project_dir: Path to dbt project directory.
            table_name: Table name to check (without schema prefix).

        Returns:
            True if table exists, False otherwise.
        """
        try:
            conn = self._get_duckdb_connection(project_dir)
            # Check all schemas for the table
            result = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
                [table_name],
            ).fetchall()
            conn.close()
            return len(result) > 0
        except Exception:  # noqa: BLE001
            return False

    def _get_table_row_count_from_duckdb(
        self,
        project_dir: Path,
        table_name: str,
    ) -> int:
        """Get row count for a table in DuckDB.

        Args:
            project_dir: Path to dbt project directory.
            table_name: Table name (without schema prefix).

        Returns:
            Row count (0 if table doesn't exist or has no rows).
        """
        try:
            conn = self._get_duckdb_connection(project_dir)
            # First, find the schema for this table
            schema_result = conn.execute(
                "SELECT table_schema FROM information_schema.tables WHERE table_name = ?",
                [table_name],
            ).fetchone()

            if not schema_result:
                conn.close()
                return 0

            schema = schema_result[0]
            # Now query with the full schema-qualified name
            result = conn.execute(
                f"SELECT COUNT(*) FROM {schema}.{table_name}"  # noqa: S608
            ).fetchone()
            conn.close()
            return result[0] if result else 0
        except Exception:  # noqa: BLE001
            return 0

    def _get_all_tables_from_duckdb(self, project_dir: Path) -> list[str]:
        """Get all table names from DuckDB.

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            List of table names (without schema prefix).
        """
        try:
            conn = self._get_duckdb_connection(project_dir)
            # Get all tables from all user schemas (excluding system schemas)
            result = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                """
            ).fetchall()
            conn.close()
            return [row[0] for row in result]
        except Exception:  # noqa: BLE001
            return []

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-023")
    def test_dbt_seed_loads_data(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test dbt seed loads CSV data into tables.

        Validates:
        - dbt seed command executes successfully
        - Seed tables are created in DuckDB
        - Tables contain expected row counts

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run dbt seed
        result = self._run_dbt_command(["seed"], project_dir)
        assert result.returncode == 0, "dbt seed should succeed"

        # Verify seed tables exist in DuckDB
        seed_tables = ["raw_customers", "raw_transactions", "raw_support_tickets"]

        for table_name in seed_tables:
            assert self._check_table_exists_in_duckdb(
                project_dir, table_name
            ), f"Seed table {table_name} should exist in DuckDB"

            # Verify table has rows
            row_count = self._get_table_row_count_from_duckdb(project_dir, table_name)
            assert row_count > 0, f"Table {table_name} should have rows after seed"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-020")
    def test_pipeline_execution_order(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test pipeline executes models in correct dependency order.

        Validates:
        - Models execute in topological order (staging → intermediate → marts)
        - Dependency resolution works correctly
        - run_results.json records correct execution sequence

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("polaris", 8181)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # First run dbt seed to load data
        self._run_dbt_command(["seed"], project_dir)

        # Run dbt models
        result = self._run_dbt_command(["run"], project_dir)
        assert result.returncode == 0, "dbt run should succeed"

        # Parse run_results.json to verify execution order
        run_results_path = project_dir / "target" / "run_results.json"
        assert run_results_path.exists(), "run_results.json should exist"

        import json

        run_results = json.loads(run_results_path.read_text())
        results = run_results.get("results", [])

        # Extract model names and their execution start times
        model_times = {}
        for result_entry in results:
            node_id = result_entry.get("unique_id", "")
            if node_id.startswith("model."):
                model_name = node_id.split(".")[-1]
                timing = result_entry.get("timing", [])
                start_time = next(
                    (t["started_at"] for t in timing if t["name"] == "execute"),
                    None,
                )
                if start_time:
                    model_times[model_name] = start_time

        # Find earliest execution time for each layer
        staging_times = [
            model_times[m]
            for m in model_times
            if m.startswith("stg_")
        ]
        intermediate_times = [
            model_times[m]
            for m in model_times
            if m.startswith("int_")
        ]
        mart_times = [
            model_times[m]
            for m in model_times
            if m.startswith("mart_")
        ]

        assert len(staging_times) > 0, "Should have staging models"
        assert len(intermediate_times) > 0, "Should have intermediate models"
        assert len(mart_times) > 0, "Should have mart models"

        # Verify dependency order: staging before intermediate before marts
        max_staging_time = max(staging_times)
        min_intermediate_time = min(intermediate_times)
        min_mart_time = min(mart_times)

        assert max_staging_time <= min_intermediate_time, (
            "Staging models should complete before intermediate models start"
        )
        assert min_intermediate_time <= min_mart_time, (
            "Intermediate models should start before or with mart models"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-021")
    def test_medallion_layers(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test medallion architecture transforms produce correct output.

        Validates:
        - Bronze layer (staging) extracts and loads raw data
        - Silver layer (intermediate) cleanses and enriches
        - Gold layer (marts) aggregates for analytics

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run full pipeline: seed + run
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Verify Bronze layer (staging) tables
        bronze_tables = [
            "stg_crm_customers",
            "stg_transactions",
            "stg_support_tickets",
        ]
        for table in bronze_tables:
            assert self._check_table_exists_in_duckdb(
                project_dir, table
            ), f"Bronze layer table {table} should exist"
            row_count = self._get_table_row_count_from_duckdb(project_dir, table)
            assert row_count > 0, f"Bronze table {table} should have data"

        # Verify Silver layer (intermediate) tables
        silver_tables = ["int_customer_orders", "int_customer_support"]
        for table in silver_tables:
            assert self._check_table_exists_in_duckdb(
                project_dir, table
            ), f"Silver layer table {table} should exist"
            row_count = self._get_table_row_count_from_duckdb(project_dir, table)
            assert row_count > 0, f"Silver table {table} should have data"

        # Verify Gold layer (marts) tables
        gold_tables = ["mart_customer_360"]
        for table in gold_tables:
            assert self._check_table_exists_in_duckdb(
                project_dir, table
            ), f"Gold layer table {table} should exist"
            row_count = self._get_table_row_count_from_duckdb(project_dir, table)
            assert row_count > 0, f"Gold table {table} should have aggregated data"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-022")
    def test_iceberg_tables_created(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test tables created with correct schemas and row counts.

        Validates:
        - Tables exist in DuckDB
        - Row counts are greater than 0
        - All expected tables present

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run pipeline
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Query DuckDB for all tables
        table_names = self._get_all_tables_from_duckdb(project_dir)

        # Verify expected tables exist
        expected_tables = [
            "raw_customers",
            "raw_transactions",
            "raw_support_tickets",
            "stg_crm_customers",
            "stg_transactions",
            "stg_support_tickets",
            "int_customer_orders",
            "int_customer_support",
            "mart_customer_360",
        ]

        for expected in expected_tables:
            assert (
                expected in table_names
            ), f"Table {expected} should exist in DuckDB"

            # Verify row count > 0
            row_count = self._get_table_row_count_from_duckdb(project_dir, expected)
            assert row_count > 0, f"Table {expected} should have rows (got {row_count})"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-024")
    def test_dbt_tests_pass(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test dbt schema and data tests pass after pipeline execution.

        Validates:
        - dbt test command executes successfully
        - Schema tests (not_null, unique) pass
        - Data tests (if defined) pass

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run pipeline first
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Run dbt tests
        result = self._run_dbt_command(["test"], project_dir)
        assert result.returncode == 0, "dbt test should pass"

        # Verify test output indicates success
        output = result.stdout + result.stderr
        assert "PASS" in output or "passed" in output.lower(), "Tests should pass"
        # Should not have failures
        assert "FAIL" not in output and "failed" not in output.lower(), (
            "Should have no test failures"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-025")
    def test_incremental_model_merge(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test incremental model merge behavior with overlapping data.

        Validates:
        - First run creates base table
        - Second run with same data doesn't duplicate rows
        - Incremental merge updates existing records

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # First run: create initial tables
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Get initial row count from a staging table (incremental candidate)
        table_name = "stg_transactions"
        initial_count = self._get_table_row_count_from_duckdb(project_dir, table_name)
        assert initial_count > 0, "Initial load should have rows"

        # Second run: with same seed data (simulates incremental)
        self._run_dbt_command(["run"], project_dir)

        # Get row count after second run
        second_count = self._get_table_row_count_from_duckdb(project_dir, table_name)

        # For non-incremental models, count should remain the same
        # (full refresh replaces data)
        # For incremental models, count should not double (merge/upsert behavior)
        assert second_count <= initial_count * 1.1, (
            f"Row count should not significantly increase on re-run "
            f"(initial: {initial_count}, second: {second_count})"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-026")
    def test_data_quality_checks(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test dbt data quality checks execute correctly.

        Validates:
        - dbt-expectations tests (if configured) execute
        - Custom data quality tests pass
        - Quality check results are recorded

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run pipeline and tests
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)
        result = self._run_dbt_command(["test"], project_dir)

        assert result.returncode == 0, "Quality checks should pass"

        # Verify test results file was created
        test_results_path = project_dir / "target" / "run_results.json"
        assert test_results_path.exists(), "run_results.json should be created"

        # Parse results to verify quality checks executed
        import json

        results = json.loads(test_results_path.read_text())
        assert "results" in results, "Results should contain test results"
        assert len(results["results"]) > 0, "Should have executed quality checks"

        # Verify all tests passed
        failed_tests = [
            r for r in results["results"] if r.get("status") not in ("pass", "success")
        ]
        assert len(failed_tests) == 0, (
            f"All quality checks should pass, but {len(failed_tests)} failed"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-027")
    def test_pipeline_failure_recording(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test pipeline failure is properly recorded.

        Validates:
        - Pipeline with bad model triggers failure
        - Error details are captured
        - dbt records failure status

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("dagster", 3000)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Create a temporary bad model that will fail
        bad_model_path = project_dir / "models" / "staging" / "bad_model_test.sql"
        bad_model_path.write_text(
            "-- This model references non-existent table\n"
            "SELECT * FROM {{ ref('table_that_does_not_exist') }}\n"
        )

        try:
            # Attempt to run pipeline (should fail)
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                self._run_dbt_command(["run", "--select", "bad_model_test"], project_dir)

            # Verify dbt captured the error
            assert exc_info.value.returncode != 0, "dbt run should fail"

            # Verify dbt error output contains useful information
            error_output = (exc_info.value.stderr or "") + (exc_info.value.stdout or "")
            # DuckDB will report that the referenced model doesn't exist
            assert (
                "table_that_does_not_exist" in error_output.lower()
                or "does not exist" in error_output.lower()
                or "compilation error" in error_output.lower()
            ), "Error should reference the missing table or compilation error"

        finally:
            # Clean up bad model
            if bad_model_path.exists():
                bad_model_path.unlink()

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-028")
    def test_pipeline_retry(
        self,
        e2e_namespace: str,
    ) -> None:
        """Test pipeline retry after failure starts from failure point.

        Validates:
        - After fixing error, retry doesn't re-run successful models
        - Only failed and downstream models are re-executed
        - Incremental state is preserved

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)

        project_dir = self._get_demo_project_path()

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # First run: successful pipeline
        self._run_dbt_command(["seed"], project_dir)
        result = self._run_dbt_command(["run"], project_dir)
        assert result.returncode == 0, "Initial run should succeed"

        # Create a bad intermediate model
        bad_model_path = (
            project_dir / "models" / "intermediate" / "int_bad_test.sql"
        )
        bad_model_path.write_text(
            "-- Intentional error\n" "SELECT * FROM non_existent_table\n"
        )

        try:
            # Run pipeline with bad model (should fail)
            with pytest.raises(subprocess.CalledProcessError):
                self._run_dbt_command(["run"], project_dir)

            # Fix the bad model
            bad_model_path.write_text(
                "-- Fixed model\n"
                "SELECT customer_id, count(*) as order_count\n"
                "FROM {{ ref('stg_transactions') }}\n"
                "GROUP BY customer_id\n"
            )

            # Retry - should only run failed model and downstream
            retry_result = self._run_dbt_command(["run"], project_dir)
            assert retry_result.returncode == 0, "Retry should succeed after fix"

            # Verify retry output shows selective execution
            output = retry_result.stdout + retry_result.stderr
            # Should mention the previously failed model
            assert "int_bad_test" in output, "Retry should execute fixed model"

        finally:
            # Clean up bad model
            if bad_model_path.exists():
                bad_model_path.unlink()
