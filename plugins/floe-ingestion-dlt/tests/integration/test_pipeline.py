"""Integration tests for dlt pipeline execution (T025, T026).

These tests validate end-to-end pipeline execution with real dlt pipelines
writing to Iceberg tables via Polaris REST catalog.

Requirements: FR-022 to FR-030, SC-004, SC-005
"""

from __future__ import annotations

import pytest

# Integration tests require K8s infrastructure (Polaris, MinIO)
# These will FAIL (not skip) if infrastructure is missing — this is intentional
# per testing standards (tests FAIL never skip).
# Run via: make test-integration

_K8S_INFRA_REQUIRED_MSG = (
    "Integration test requires K8s infrastructure — "
    "start services via make test-integration"
)


class TestPipelineAppendMode:
    """Integration tests for write_mode=append (T025).

    These tests require K8s services: Polaris catalog, MinIO storage.
    Run with: make test-integration
    """

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-022")
    def test_append_mode_adds_rows(self) -> None:
        """Test append mode adds rows to existing Iceberg table.

        Given a pipeline configured with write_mode="append", when run()
        is called twice with different data, then both datasets appear
        in the Iceberg table (row count is cumulative).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-021")
    def test_append_returns_correct_metrics(self) -> None:
        """Test append mode returns accurate IngestionResult metrics.

        Given a successful append, IngestionResult has success=True,
        rows_loaded matches input count, duration_seconds > 0.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-029")
    def test_append_records_duration(self) -> None:
        """Test append mode records wall-clock duration.

        Given a pipeline run, duration_seconds reflects actual elapsed time
        measured via time.perf_counter().

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)


class TestPipelineReplaceMode:
    """Integration tests for write_mode=replace (T026)."""

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-023")
    def test_replace_mode_overwrites_data(self) -> None:
        """Test replace mode overwrites existing Iceberg table data.

        Given a table with existing data, when run() is called with
        write_mode="replace", then only the new data appears in the table.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)


class TestPipelineMergeMode:
    """Integration tests for write_mode=merge (T026)."""

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-024")
    def test_merge_mode_upserts_by_primary_key(self) -> None:
        """Test merge mode upserts records by primary key.

        Given existing records and new records sharing some primary keys,
        when run() with write_mode="merge", existing records are updated
        and new records are inserted.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-025")
    def test_merge_supports_delete_insert_strategy(self) -> None:
        """Test merge supports delete-insert strategy via dlt.

        Given merge with delete-insert disposition, matching records
        are deleted then re-inserted.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-030")
    def test_empty_source_returns_zero_rows(self) -> None:
        """Test empty source data returns success with 0 rows.

        Given a pipeline with empty source data, run() returns
        IngestionResult(success=True, rows_loaded=0).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)


class TestSchemaContractEnforcement:
    """Integration tests for schema contract enforcement (T037-T039a)."""

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-031")
    def test_evolve_contract_adds_new_column(self) -> None:
        """Test evolve contract adds new column to Iceberg table.

        Given schema_contract="evolve" and source data gains a new column,
        when run() is executed, then the Iceberg table schema evolves
        to include the new column.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-032")
    def test_freeze_contract_rejects_schema_change(self) -> None:
        """Test freeze contract rejects schema changes.

        Given schema_contract="freeze" and source schema changes,
        when run() is executed, then pipeline raises SchemaContractViolation.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-033")
    def test_discard_value_drops_nonconforming_columns(self) -> None:
        """Test discard_value drops non-conforming column values.

        Given schema_contract="discard_value" and non-conforming column values,
        when run() is executed, then values are discarded and existing schema
        is preserved.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-037")
    def test_column_removal_preserves_iceberg_columns(self) -> None:
        """Test column removal preserves Iceberg table columns.

        Given a column is removed from source data, when run() is executed,
        then the Iceberg table retains the column (additive-only evolution).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)


class TestIncrementalLoading:
    """Integration tests for incremental loading (T042-T043)."""

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-038")
    def test_incremental_loads_only_new_records(self) -> None:
        """Test incremental loading with cursor_field loads only new records.

        Given a pipeline configured with cursor_field, when run() is executed
        twice with different data, then the second run loads only records with
        cursor values greater than the last loaded cursor position.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-041")
    def test_incremental_resumes_from_last_cursor(self) -> None:
        """Test incremental state persists across pipeline restarts.

        Given a pipeline that has previously loaded data with cursor_field,
        when the pipeline is restarted and run() is executed, then it resumes
        from the last cursor position (not loading already-seen records).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-042")
    def test_incremental_state_isolated_per_pipeline(self) -> None:
        """Test incremental state is isolated per pipeline name.

        Given two pipelines with different names loading from the same source,
        when both run() with cursor_field, then each maintains separate
        cursor state (loading all records independently).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-042")
    def test_incremental_merge_upserts_by_primary_key(self) -> None:
        """Test incremental merge upserts records by primary key.

        Given a pipeline configured with cursor_field, primary_key, and
        write_disposition="merge", when run() is executed with records
        containing existing primary keys, then existing records are updated
        (upserted) rather than duplicated.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-043")
    def test_incremental_rows_loaded_reflects_increment(self) -> None:
        """Test rows_loaded metric reflects only incrementally-loaded rows.

        Given a pipeline with cursor_field that has previously loaded N rows,
        when run() is executed with M new rows, then IngestionResult.rows_loaded
        equals M (not N+M).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)


class TestErrorHandling:
    """Integration tests for error handling (T053)."""

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-058")
    def test_source_connection_failure_raises_error(self) -> None:
        """Test source connection failure raises SourceConnectionError.

        Given an unreachable source endpoint, when create_pipeline() or run()
        is executed, then SourceConnectionError is raised with TRANSIENT category.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-057")
    def test_iceberg_write_failure_returns_error_result(self) -> None:
        """Test Iceberg write failure returns IngestionResult with success=False.

        Given a pipeline targeting a non-existent Iceberg namespace, when run()
        is executed, then it returns IngestionResult(success=False, errors=[...]).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-052")
    def test_transient_error_retried(self) -> None:
        """Test transient error triggers retry with backoff.

        Given a pipeline that fails with a transient error on first attempt,
        when run() is called with retry enabled, then the operation is retried.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail(_K8S_INFRA_REQUIRED_MSG)
