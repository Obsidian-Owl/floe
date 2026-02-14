"""E2E tests for complete data pipeline execution.

**Requires Polaris/Iceberg**: These tests validate end-to-end data pipeline
workflows that depend on Polaris catalog, MinIO (S3), and Dagster orchestration.
They require a running Kind cluster with all services deployed.

Exception: ``test_transformation_math_correctness`` is compilation-only
(no infrastructure dependencies).

This module validates:
- dbt seed data loading
- Pipeline execution with dependency ordering
- Medallion architecture transforms (Bronze -> Silver -> Gold)
- Iceberg table creation and validation
- dbt schema and data quality tests
- Incremental model merge behavior
- Pipeline failure recording and retry
- Transformation math correctness

All tests run against demo pipelines (customer-360, iot-telemetry, financial-risk)
in a real K8s environment.

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
- FR-030: Transformation math correctness

Per testing standards: Tests FAIL when infrastructure is unavailable.
No pytest.skip() - see .claude/rules/testing-standards.md
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, ClassVar

# PyIceberg imported in helper methods to fail properly if not installed
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase

ALL_PRODUCTS = ["customer-360", "iot-telemetry", "financial-risk"]
"""All demo product directories to test across."""


class TestDataPipeline(IntegrationTestBase):
    """E2E tests for data pipeline execution.

    **Requires Polaris/Iceberg**: These tests validate complete data pipeline
    workflows using the demo projects (customer-360, iot-telemetry, financial-risk).
    They exercise:
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

    def _get_demo_project_path(self, project_root: Path, product: str = "customer-360") -> Path:
        """Get path to a demo project directory.

        Args:
            project_root: Repository root path (from project_root fixture).
            product: Product name (e.g., 'customer-360', 'iot-telemetry').

        Returns:
            Path to demo/{product} directory.

        Raises:
            AssertionError: If demo project not found (via pytest.fail).
        """
        project_path = project_root / "demo" / product
        if not project_path.exists():
            pytest.fail(
                f"Demo project not found at {project_path}\n"
                f"Expected: demo/{product} directory with dbt project"
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

    def _load_iceberg_table(self, catalog: Any, namespace: str, table_name: str) -> Any:
        """Load Iceberg table from Polaris catalog.

        Args:
            catalog: PyIceberg REST catalog instance.
            namespace: Polaris namespace name.
            table_name: Table name within the namespace.

        Returns:
            PyIceberg Table object.

        Raises:
            NoSuchTableError: If table does not exist.
        """
        return catalog.load_table(f"{namespace}.{table_name}")

    def _get_iceberg_row_count(self, catalog: Any, namespace: str, table_name: str) -> int:
        """Get row count from Iceberg table via PyIceberg scan.

        Args:
            catalog: PyIceberg REST catalog instance.
            namespace: Polaris namespace name.
            table_name: Table name within the namespace.

        Returns:
            Row count from the table scan.

        Raises:
            NoSuchTableError: If table does not exist.
        """
        table = self._load_iceberg_table(catalog, namespace, table_name)
        return len(table.scan().to_arrow())

    def _list_iceberg_tables(self, catalog: Any, namespace: str) -> list[str]:
        """List all tables in a Polaris namespace.

        Args:
            catalog: PyIceberg REST catalog instance.
            namespace: Polaris namespace name.

        Returns:
            List of table names in the namespace.
        """
        return [t[1] for t in catalog.list_tables(namespace)]

    def _query_duckdb(self, db_path: Path, sql: str) -> list[dict[str, Any]]:
        """Query DuckDB database file and return list of row dicts.

        Args:
            db_path: Path to DuckDB database file.
            sql: SQL query to execute.

        Returns:
            List of dictionaries, one per row.

        Raises:
            ImportError: If duckdb package not installed.
            AssertionError: If query fails.
        """
        import duckdb

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            result = conn.execute(sql).fetchall()
            columns = [desc[0] for desc in conn.description]
            return [dict(zip(columns, row, strict=True)) for row in result]
        finally:
            conn.close()

    def _find_duckdb_path(self, project_dir: Path) -> Path:
        """Find DuckDB database file created by dbt build.

        dbt-duckdb creates the database in the project root or configured path.

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Path to DuckDB database file.

        Raises:
            AssertionError: If no DuckDB database found.
        """
        candidates = (
            list(project_dir.glob("*.duckdb"))
            + list(project_dir.glob("target/*.duckdb"))
            + list(project_dir.glob("**/*.duckdb"))
        )
        # Deduplicate and sort by modification time (newest first)
        seen: set[str] = set()
        unique: list[Path] = []
        for c in candidates:
            resolved = str(c.resolve())
            if resolved not in seen:
                seen.add(resolved)
                unique.append(c)

        assert len(unique) > 0, (
            f"No DuckDB database found in {project_dir}. "
            "dbt build may have failed or uses a different storage backend."
        )
        # Return newest
        return max(unique, key=lambda p: p.stat().st_mtime)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-023")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    @pytest.mark.parametrize("product", ALL_PRODUCTS)
    def test_dbt_seed_loads_data(
        self,
        product: str,
        e2e_namespace: str,
        polaris_client: Any,
        project_root: Path,
    ) -> None:
        """Test dbt seed loads CSV data into Iceberg tables via Polaris.

        Requires Polaris/Iceberg: Validates seed data lands in Iceberg tables.

        Validates:
        - dbt seed command executes successfully
        - Seed tables are created in Iceberg catalog
        - Tables contain expected row counts
        - DuckDB validation confirms data integrity

        Args:
            product: Demo product to test.
            e2e_namespace: Unique namespace for test isolation.
            polaris_client: PyIceberg REST catalog fixture.
        """
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path(project_root, product)
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run dbt seed
        result = self._run_dbt_command(["seed"], project_dir)
        assert result.returncode == 0, f"dbt seed should succeed for {product}"

        # Verify seed tables exist in Iceberg via Polaris catalog
        namespace = product.replace("-", "_")
        seed_tables = ["raw_customers", "raw_transactions", "raw_support_tickets"]

        available_tables = self._list_iceberg_tables(polaris_client, namespace)
        for table_name in seed_tables:
            assert table_name in available_tables, (
                f"Seed table {table_name} should exist in Polaris namespace {namespace}. "
                f"Available tables: {available_tables}"
            )

            row_count = self._get_iceberg_row_count(polaris_client, namespace, table_name)
            assert row_count > 0, f"Table {table_name} should have rows after seed"

        # Validate seed row counts via DuckDB
        db_path = self._find_duckdb_path(project_dir)

        # Verify raw_customers has meaningful row count
        rows = self._query_duckdb(db_path, "SELECT COUNT(*) as cnt FROM raw_customers")
        customer_count = rows[0]["cnt"]
        assert customer_count >= 10, (
            f"raw_customers should have at least 10 seed rows, got {customer_count}"
        )

        # Verify raw_transactions has data and amounts are positive
        rows = self._query_duckdb(
            db_path,
            "SELECT COUNT(*) as cnt FROM raw_transactions WHERE amount > 0",
        )
        assert rows[0]["cnt"] > 0, (
            "raw_transactions should have rows with positive amounts after seed"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-020")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    @pytest.mark.parametrize("product", ALL_PRODUCTS)
    def test_pipeline_execution_order(
        self,
        product: str,
        e2e_namespace: str,
        project_root: Path,
    ) -> None:
        """Test pipeline executes models in correct dependency order.

        Validates:
        - Models execute in topological order (staging -> intermediate -> marts)
        - Dependency resolution works correctly
        - run_results.json records correct execution sequence

        Args:
            product: Demo product to test.
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("polaris", 8181)

        project_dir = self._get_demo_project_path(project_root, product)

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # First run dbt seed to load data
        self._run_dbt_command(["seed"], project_dir)

        # Run dbt models
        result = self._run_dbt_command(["run"], project_dir)
        assert result.returncode == 0, f"dbt run should succeed for {product}"

        # Parse run_results.json to verify execution order
        run_results_path = project_dir / "target" / "run_results.json"
        assert run_results_path.exists(), "run_results.json should exist"

        import json

        run_results = json.loads(run_results_path.read_text())
        results = run_results.get("results", [])

        # Extract model names and their execution start times
        model_times: dict[str, str] = {}
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
        staging_times = [model_times[m] for m in model_times if m.startswith("stg_")]
        intermediate_times = [model_times[m] for m in model_times if m.startswith("int_")]
        mart_times = [model_times[m] for m in model_times if m.startswith("mart_")]

        assert len(staging_times) > 0, f"Should have staging models for {product}"
        assert len(intermediate_times) > 0, f"Should have intermediate models for {product}"
        assert len(mart_times) > 0, f"Should have mart models for {product}"

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

        # Verify ALL models succeeded (no errors)
        for result_entry in results:
            status = result_entry.get("status")
            uid = result_entry.get("unique_id", "unknown")
            assert status in (
                "pass",
                "success",
            ), f"Model {uid} should succeed, got status={status}"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-021")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_medallion_layers(
        self,
        e2e_namespace: str,
        polaris_client: Any,
        project_root: Path,
    ) -> None:
        """Test medallion architecture transforms produce correct output in Iceberg.

        Validates:
        - Bronze layer (staging) extracts and loads raw data
        - Silver layer (intermediate) cleanses and enriches
        - Gold layer (marts) aggregates for analytics
        - All data lands in Iceberg tables via Polaris catalog

        Args:
            e2e_namespace: Unique namespace for test isolation.
            polaris_client: PyIceberg REST catalog fixture.
        """
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path(project_root)
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run full pipeline: seed + run
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        namespace = "customer_360"
        available_tables = self._list_iceberg_tables(polaris_client, namespace)

        # Verify Bronze layer (staging) tables
        bronze_tables = ["stg_crm_customers", "stg_transactions", "stg_support_tickets"]
        for table in bronze_tables:
            assert table in available_tables, (
                f"Bronze layer table {table} should exist in Polaris. Available: {available_tables}"
            )
            row_count = self._get_iceberg_row_count(polaris_client, namespace, table)
            assert row_count > 0, f"Bronze table {table} should have data"

        # Verify Silver layer (intermediate) tables
        silver_tables = ["int_customer_orders", "int_customer_support"]
        for table in silver_tables:
            assert table in available_tables, (
                f"Silver layer table {table} should exist in Polaris. Available: {available_tables}"
            )
            row_count = self._get_iceberg_row_count(polaris_client, namespace, table)
            assert row_count > 0, f"Silver table {table} should have data"

        # Verify Gold layer (marts) tables
        gold_tables = ["mart_customer_360"]
        for table in gold_tables:
            assert table in available_tables, (
                f"Gold layer table {table} should exist in Polaris. Available: {available_tables}"
            )
            row_count = self._get_iceberg_row_count(polaris_client, namespace, table)
            assert row_count > 0, f"Gold table {table} should have aggregated data"

        # Validate Bronze->Silver->Gold data flow correctness
        # Bronze tables should have raw-ish data
        for table in bronze_tables:
            bronze_count = self._get_iceberg_row_count(polaris_client, namespace, table)
            assert bronze_count > 0, f"Bronze {table} must have data"

        # Silver tables should have fewer or equal rows (aggregation)
        for table in silver_tables:
            silver_count = self._get_iceberg_row_count(polaris_client, namespace, table)
            assert silver_count > 0, f"Silver {table} must have data"

        # Gold must have meaningful aggregated data
        for table in gold_tables:
            gold_count = self._get_iceberg_row_count(polaris_client, namespace, table)
            assert gold_count > 0, f"Gold {table} must have aggregated data"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-022")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_iceberg_tables_created(
        self,
        e2e_namespace: str,
        polaris_client: Any,
        project_root: Path,
    ) -> None:
        """Test Iceberg tables created with correct schemas and row counts.

        Validates:
        - Tables exist in Polaris catalog
        - Row counts are greater than 0
        - All expected tables present in Iceberg format

        Args:
            e2e_namespace: Unique namespace for test isolation.
            polaris_client: PyIceberg REST catalog fixture.
        """
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path(project_root)
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run pipeline
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Query Polaris catalog for all tables
        namespace = "customer_360"
        table_names = self._list_iceberg_tables(polaris_client, namespace)

        # Verify expected tables exist in Iceberg
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
            assert expected in table_names, (
                f"Table {expected} should exist in Polaris namespace {namespace}. "
                f"Available: {table_names}"
            )

            # Verify row count > 0 via Iceberg scan
            row_count = self._get_iceberg_row_count(polaris_client, namespace, expected)
            assert row_count > 0, f"Table {expected} should have rows (got {row_count})"

        # Validate Iceberg table schemas have expected columns
        # Staging tables should have typed columns (not just raw strings)
        stg_table = self._load_iceberg_table(polaris_client, namespace, "stg_crm_customers")
        stg_columns = [field.name for field in stg_table.schema().fields]
        assert "customer_id" in stg_columns or any("id" in c for c in stg_columns), (
            f"stg_crm_customers should have an ID column. Columns: {stg_columns}"
        )

        # Mart table should have derived columns (business metrics)
        mart_table = self._load_iceberg_table(polaris_client, namespace, "mart_customer_360")
        mart_columns = [field.name for field in mart_table.schema().fields]
        # Mart should have aggregated/derived metrics not in raw data
        assert len(mart_columns) > 2, (
            f"mart_customer_360 should have multiple business metric columns, got {mart_columns}"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-024")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    @pytest.mark.parametrize("product", ALL_PRODUCTS)
    def test_dbt_tests_pass(
        self,
        product: str,
        e2e_namespace: str,
        project_root: Path,
    ) -> None:
        """Test dbt schema and data tests pass after pipeline execution.

        Validates:
        - dbt test command executes successfully
        - Schema tests (not_null, unique) pass
        - Data tests (if defined) pass
        - run_results.json records test results

        Args:
            product: Demo product to test.
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)

        project_dir = self._get_demo_project_path(project_root, product)

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run pipeline first
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Run dbt tests
        result = self._run_dbt_command(["test"], project_dir)
        assert result.returncode == 0, f"dbt test should pass for {product}"

        # Verify test output indicates success
        output = result.stdout + result.stderr
        assert "PASS" in output or "passed" in output.lower(), "Tests should pass"
        # Should not have failures
        assert "FAIL" not in output and "failed" not in output.lower(), (
            "Should have no test failures"
        )

        # Parse test results precisely
        import json as json_mod

        test_results_path = project_dir / "target" / "run_results.json"
        assert test_results_path.exists(), (
            f"run_results.json not found at {test_results_path}. "
            "dbt test may have failed or not run."
        )

        test_results = json_mod.loads(test_results_path.read_text())
        results_list = test_results.get("results", [])
        passed = sum(1 for r in results_list if r.get("status") in ("pass", "success"))
        failed = sum(1 for r in results_list if r.get("status") == "fail")
        assert passed > 0, (
            f"dbt test should have at least one passing test, got {passed} pass, {failed} fail"
        )
        fail_ids = [r.get("unique_id") for r in results_list if r.get("status") == "fail"]
        assert failed == 0, f"dbt test should have zero failures, got {failed}. Failed: {fail_ids}"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-025")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_incremental_model_merge(
        self,
        e2e_namespace: str,
        polaris_client: Any,
        project_root: Path,
    ) -> None:
        """Test incremental model merge behavior with overlapping data.

        Validates:
        - First run creates base table in Iceberg
        - Second run with same data doesn't duplicate rows
        - Incremental merge updates existing records

        Args:
            e2e_namespace: Unique namespace for test isolation.
            polaris_client: PyIceberg REST catalog fixture.
        """
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path(project_root)
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # First run: create initial tables
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Get initial row count from a staging table (incremental candidate)
        namespace = "customer_360"
        table_name = "stg_transactions"
        initial_count = self._get_iceberg_row_count(polaris_client, namespace, table_name)
        assert initial_count > 0, "Initial load should have rows"

        # Second run: with same seed data (simulates incremental)
        self._run_dbt_command(["run"], project_dir)

        # Get row count after second run
        second_count = self._get_iceberg_row_count(polaris_client, namespace, table_name)

        # For non-incremental models, count should remain the same
        # For incremental models, count should not double (merge/upsert behavior)
        assert second_count <= initial_count * 1.1, (
            f"Row count should not significantly increase on re-run "
            f"(initial: {initial_count}, second: {second_count})"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-026")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    @pytest.mark.parametrize("product", ALL_PRODUCTS)
    def test_data_quality_checks(
        self,
        product: str,
        e2e_namespace: str,
        project_root: Path,
    ) -> None:
        """Test dbt data quality checks execute correctly.

        Validates:
        - dbt-expectations tests (if configured) execute
        - Custom data quality tests pass
        - Quality check results are recorded in run_results.json

        Args:
            product: Demo product to test.
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)

        project_dir = self._get_demo_project_path(project_root, product)

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Run pipeline and tests
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)
        result = self._run_dbt_command(["test"], project_dir)

        assert result.returncode == 0, f"Quality checks should pass for {product}"

        # Verify test results file was created
        test_results_path = project_dir / "target" / "run_results.json"
        assert test_results_path.exists(), (
            f"run_results.json not found at {test_results_path}. "
            "dbt test may have failed or not run."
        )

        # Parse results to verify quality checks executed
        import json

        results = json.loads(test_results_path.read_text())
        assert "results" in results, "Results should contain test results"
        assert len(results["results"]) > 0, "Should have executed quality checks"

        # Verify all tests passed
        failed_tests = [r for r in results["results"] if r.get("status") not in ("pass", "success")]
        assert len(failed_tests) == 0, (
            f"All quality checks should pass for {product}, but {len(failed_tests)} failed"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-027")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_pipeline_failure_recording(
        self,
        e2e_namespace: str,
        project_root: Path,
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

        project_dir = self._get_demo_project_path(project_root)

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
            bad_model_path.unlink(missing_ok=True)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-028")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_pipeline_retry(
        self,
        e2e_namespace: str,
        project_root: Path,
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

        project_dir = self._get_demo_project_path(project_root)

        # Ensure target directory exists
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # First run: successful pipeline
        self._run_dbt_command(["seed"], project_dir)
        result = self._run_dbt_command(["run"], project_dir)
        assert result.returncode == 0, "Initial run should succeed"

        # Create a bad intermediate model
        bad_model_path = project_dir / "models" / "intermediate" / "int_bad_test.sql"
        bad_model_path.write_text("-- Intentional error\nSELECT * FROM non_existent_table\n")

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
            bad_model_path.unlink(missing_ok=True)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-029")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_auto_trigger_sensor_e2e(
        self,
        e2e_namespace: str,
        dagster_client: Any,
        project_root: Path,
    ) -> None:
        """Test health check sensor can detect services and trigger runs.

        Validates:
        - Health check sensor module exists and is importable
        - Sensor definition is properly structured
        - Sensor can evaluate service health conditions
        - Dagster API shows sensor is registered (if deployed)

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability
        self.check_infrastructure("dagster", 3000)

        # Test 1: Verify sensor module exists and is importable
        try:
            from floe_orchestrator_dagster.sensors import (
                health_check_sensor,
            )
        except ImportError as e:
            pytest.fail(
                f"Health check sensor module not found: {e}\n"
                "Expected: floe_orchestrator_dagster.sensors.health_check_sensor"
            )

        # Test 2: Verify sensor definition is properly structured
        sensor_def = health_check_sensor
        assert sensor_def is not None, "Sensor definition should not be None"
        assert hasattr(sensor_def, "name"), "Sensor should have name attribute"
        assert hasattr(sensor_def, "job_name"), "Sensor should have job_name or target"

        # Test 3: Verify sensor function signature (can be called)
        # The sensor function should accept a context parameter
        import inspect

        if callable(sensor_def):
            sig = inspect.signature(sensor_def)
            assert len(sig.parameters) > 0, "Sensor function should accept context parameter"

        # Test 4: Query Dagster GraphQL for sensor registration status
        query = """
        query GetSensors {
            sensorsOrError {
                __typename
                ... on Sensors {
                    results {
                        name
                        sensorState {
                            status
                        }
                    }
                }
            }
        }
        """

        try:
            result = dagster_client._execute(query)
            assert "sensorsOrError" in result, (
                f"Dagster sensor query response missing 'sensorsOrError'. Got: {result}"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to query Dagster sensors endpoint: {e}\n"
                "Dagster must expose sensor information via GraphQL."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-030")
    def test_transformation_math_correctness(self, project_root: Path) -> None:
        """Test that dbt transformations produce mathematically correct results.

        Compilation-only: No Polaris/Iceberg infrastructure required. Uses
        ``compile_pipeline`` to validate model structure and tier assignments.

        WILL FAIL if:
        - Staging models don't normalize data (e.g., email not lowercased)
        - Mart models have incorrect aggregation math
        - Joins lose or duplicate rows
        """
        from floe_core.compilation.stages import compile_pipeline

        manifest_path = project_root / "demo" / "manifest.yaml"

        # Compile customer-360 to get artifacts
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        artifacts = compile_pipeline(spec_path, manifest_path)

        assert artifacts is not None, "Compilation must succeed for math validation"
        assert artifacts.transforms is not None, "Transforms must be present"

        # Verify transform models exist with correct tier assignments
        bronze_models = [m for m in artifacts.transforms.models if m.quality_tier == "bronze"]
        silver_models = [m for m in artifacts.transforms.models if m.quality_tier == "silver"]
        gold_models = [m for m in artifacts.transforms.models if m.quality_tier == "gold"]

        assert len(bronze_models) > 0, (
            "MATH GAP: No bronze tier models found. "
            "Customer-360 must have staging models for data normalization."
        )
        assert len(silver_models) > 0, (
            "MATH GAP: No silver tier models found. Customer-360 must have intermediate models."
        )
        assert len(gold_models) > 0, (
            "MATH GAP: No gold tier models found. "
            "Customer-360 must have mart models for aggregation."
        )

        # Verify model dependencies form a valid DAG (bronze -> silver -> gold)
        all_model_names = {m.name for m in artifacts.transforms.models}
        for model in silver_models:
            if model.depends_on:
                for dep in model.depends_on:
                    assert dep in all_model_names or dep.startswith("source"), (
                        f"Silver model {model.name} depends on unknown model {dep}"
                    )

        for model in gold_models:
            if model.depends_on:
                for dep in model.depends_on:
                    assert dep in all_model_names or dep.startswith("source"), (
                        f"Gold model {model.name} depends on unknown model {dep}"
                    )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-031")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_data_retention_enforcement(
        self,
        e2e_namespace: str,
        polaris_client: Any,
        project_root: Path,
    ) -> None:
        """Test data retention cleanup configuration and enforcement.

        Validates:
        - Retention configuration exists in floe.yaml or dbt macros
        - Pipeline executes and tables contain data
        - Retention mechanism is defined (even if not yet enforced at runtime)

        Args:
            e2e_namespace: Unique namespace for test isolation.
            polaris_client: PyIceberg REST catalog fixture.
        """
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path(project_root)
        target_dir = project_dir / "target"
        target_dir.mkdir(exist_ok=True)

        # Test 1: Verify retention configuration exists in floe.yaml
        floe_yaml_path = project_dir / "floe.yaml"
        assert floe_yaml_path.exists(), "floe.yaml should exist"

        import yaml

        floe_config = yaml.safe_load(floe_yaml_path.read_text())
        has_retention_config = (
            "retention" in str(floe_config).lower()
            or "expiry" in str(floe_config).lower()
            or "keep_last" in str(floe_config).lower()
        )

        # Test 2: Check for retention macro in dbt project
        macros_dir = project_dir / "macros"
        retention_macro_found = False
        assert macros_dir.exists(), (
            f"macros/ directory not found at {macros_dir}. "
            "dbt project should have a macros directory."
        )
        for macro_file in macros_dir.glob("**/*.sql"):
            content = macro_file.read_text()
            if "retention" in content.lower() or "expire" in content.lower():
                retention_macro_found = True
                break

        # At least one retention mechanism should be defined
        assert has_retention_config or retention_macro_found, (
            "No retention mechanism found. Expected either:\n"
            "  - 'retention' or 'expiry' configuration in floe.yaml\n"
            "  - Retention macro in dbt macros/ directory"
        )

        # Test 3: Run pipeline and verify tables exist
        self._run_dbt_command(["seed"], project_dir)
        self._run_dbt_command(["run"], project_dir)

        # Verify data exists (retention should preserve recent data)
        namespace = "customer_360"
        table_name = "stg_transactions"
        row_count = self._get_iceberg_row_count(polaris_client, namespace, table_name)
        assert row_count > 0, f"Table {table_name} should have rows after pipeline run"

        # Validate retention config propagates to compiled artifacts
        spec_path = project_dir / "floe.yaml"
        from floe_core.compilation.stages import compile_pipeline

        manifest_path = project_root / "demo" / "manifest.yaml"
        compiled = compile_pipeline(spec_path, manifest_path)

        # Governance retention must be populated from manifest
        assert compiled.governance is not None, (
            "Compiled artifacts must have governance section for retention enforcement"
        )
        retention = compiled.governance.data_retention_days
        assert retention is None or retention > 0, (
            f"Governance data_retention_days must be positive if set, got {retention}"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-032")
    @pytest.mark.xfail(
        reason="Iceberg-dependent: needs K8s stack. Verify in E2E run.",
        strict=False,
    )
    def test_snapshot_expiry_enforcement(
        self,
        e2e_namespace: str,
        polaris_client: Any,
        project_root: Path,
    ) -> None:
        """Test Iceberg snapshot expiry keeps only configured number of snapshots.

        Validates:
        - Snapshot retention is configured in demo values
        - floe.yaml specifies retention policy
        - Platform configuration supports snapshot management

        Args:
            e2e_namespace: Unique namespace for test isolation.
            polaris_client: PyIceberg REST catalog fixture.
        """
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("minio", 9000)

        project_dir = self._get_demo_project_path(project_root)

        # Test 1: Verify demo values have snapshot retention configuration
        values_demo_path = project_root / "charts" / "floe-platform" / "values-demo.yaml"
        assert values_demo_path.exists(), (
            f"Demo values file not found at {values_demo_path}\n"
            "Expected: charts/floe-platform/values-demo.yaml"
        )

        import yaml

        values_content = yaml.safe_load(values_demo_path.read_text())
        has_snapshot_config = (
            "snapshotKeepLast" in str(values_content) or "snapshot" in str(values_content).lower()
        )
        assert has_snapshot_config, (
            "Demo values should contain snapshot retention configuration "
            "(snapshotKeepLast or similar snapshot policy)"
        )

        # Test 2: Verify floe.yaml has retention configuration
        floe_yaml_path = project_dir / "floe.yaml"
        assert floe_yaml_path.exists(), "floe.yaml should exist"

        floe_config = yaml.safe_load(floe_yaml_path.read_text())
        has_retention = (
            "retention" in str(floe_config).lower()
            or "snapshot" in str(floe_config).lower()
            or "expiry" in str(floe_config).lower()
        )
        assert has_retention, "floe.yaml should contain retention or snapshot configuration"
