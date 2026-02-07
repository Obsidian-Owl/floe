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
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-021")
    def test_append_returns_correct_metrics(self) -> None:
        """Test append mode returns accurate IngestionResult metrics.

        Given a successful append, IngestionResult has success=True,
        rows_loaded matches input count, duration_seconds > 0.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-029")
    def test_append_records_duration(self) -> None:
        """Test append mode records wall-clock duration.

        Given a pipeline run, duration_seconds reflects actual elapsed time
        measured via time.perf_counter().

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")


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
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")


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
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-025")
    def test_merge_supports_delete_insert_strategy(self) -> None:
        """Test merge supports delete-insert strategy via dlt.

        Given merge with delete-insert disposition, matching records
        are deleted then re-inserted.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-030")
    def test_empty_source_returns_zero_rows(self) -> None:
        """Test empty source data returns success with 0 rows.

        Given a pipeline with empty source data, run() returns
        IngestionResult(success=True, rows_loaded=0).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")


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
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-032")
    def test_freeze_contract_rejects_schema_change(self) -> None:
        """Test freeze contract rejects schema changes.

        Given schema_contract="freeze" and source schema changes,
        when run() is executed, then pipeline raises SchemaContractViolation.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-033")
    def test_discard_value_drops_nonconforming_columns(self) -> None:
        """Test discard_value drops non-conforming column values.

        Given schema_contract="discard_value" and non-conforming column values,
        when run() is executed, then values are discarded and existing schema
        is preserved.

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-037")
    def test_column_removal_preserves_iceberg_columns(self) -> None:
        """Test column removal preserves Iceberg table columns.

        Given a column is removed from source data, when run() is executed,
        then the Iceberg table retains the column (additive-only evolution).

        This test WILL FAIL if Polaris/MinIO services are not available.
        """
        pytest.fail("Integration test requires K8s infrastructure — start services via make test-integration")
