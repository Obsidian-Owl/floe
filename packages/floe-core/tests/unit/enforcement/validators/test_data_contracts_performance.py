"""Performance benchmarks for data contract validation.

Task: T080, T081
Requirements: SC-001 (Contract validation <2s for 50 models),
              SC-006 (Drift detection <5s for 100 columns)

These tests verify performance success criteria from the spec.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    pass


class TestContractValidationPerformance:
    """Performance tests for contract validation (T080).

    SC-001: Contract validation MUST complete within 2 seconds for
    a contract containing 50 models.
    """

    @pytest.fixture
    def large_contract_yaml(self, tmp_path: Path) -> Path:
        """Create a contract with 50 models for performance testing."""
        # Generate schema with 50 models
        schemas = []
        for i in range(50):
            schemas.append(f"""  - name: model_{i:03d}
    physicalName: model_{i:03d}
    columns:
      - name: id
        logicalType: string
        required: true
      - name: name
        logicalType: string
      - name: created_at
        logicalType: timestamp
      - name: value
        logicalType: decimal""")

        schema_yaml = "\n".join(schemas)

        contract_content = f"""apiVersion: v3.1.0
kind: DataContract
id: urn:datacontract:performance-test
version: 1.0.0
name: performance-test-50-models
status: active
schema:
{schema_yaml}
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_content)
        return contract_path

    @pytest.mark.requirement("3C-SC-001")
    @pytest.mark.performance
    def test_contract_validation_under_2_seconds_for_50_models(
        self,
        large_contract_yaml: Path,
    ) -> None:
        """SC-001: Contract validation MUST complete within 2 seconds for 50 models.

        Creates a contract with 50 model definitions and verifies that
        validation completes within the 2 second SLA.
        """
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        validator = ContractValidator()

        # Measure validation time
        start_time = time.perf_counter()
        result = validator.validate(large_contract_yaml, enforcement_level="strict")
        end_time = time.perf_counter()

        elapsed_seconds = end_time - start_time

        # Assert timing constraint
        assert elapsed_seconds < 2.0, (
            f"Contract validation took {elapsed_seconds:.3f}s, "
            f"exceeding 2s SLA (SC-001) for 50-model contract"
        )

        # Log performance for visibility (optional, helps debugging)
        print(f"\nPerformance: 50-model contract validated in {elapsed_seconds:.3f}s")

        # Validation should still produce valid results
        # (contract is syntactically valid, may have schema warnings)
        assert result is not None
        assert result.validated_at is not None

    @pytest.mark.requirement("3C-SC-001")
    @pytest.mark.performance
    def test_contract_validation_performance_with_multiple_runs(
        self,
        large_contract_yaml: Path,
    ) -> None:
        """Verify consistent validation performance across multiple runs.

        Runs validation with warm-up, then 5 measured runs. Uses median
        for more stable benchmarking (less affected by outliers).
        """
        import statistics

        from floe_core.enforcement.validators.data_contracts import ContractValidator

        validator = ContractValidator()

        # Warm-up run to ensure JIT compilation, caching, etc. are complete
        validator.validate(large_contract_yaml, enforcement_level="strict")

        times: list[float] = []

        # Run validation 5 times (after warm-up)
        for _ in range(5):
            start_time = time.perf_counter()
            validator.validate(large_contract_yaml, enforcement_level="strict")
            end_time = time.perf_counter()
            times.append(end_time - start_time)

        # Use median for more stable benchmarking (less affected by outliers)
        median_time = statistics.median(times)
        avg_time = sum(times) / len(times)

        assert median_time < 2.0, (
            f"Median validation time {median_time:.3f}s exceeds 2s SLA. "
            f"Times: {[f'{t:.3f}s' for t in times]}"
        )

        print(f"\nPerformance: avg={avg_time:.3f}s, median={median_time:.3f}s over 5 runs")


class TestDriftDetectionPerformance:
    """Performance tests for schema drift detection (T081).

    SC-006: Schema drift detection MUST complete within 5 seconds
    for a table with 100 columns.
    """

    @pytest.fixture
    def contract_100_columns_yaml(self, tmp_path: Path) -> Path:
        """Create a contract with 100 columns for performance testing."""
        columns = []
        for i in range(100):
            col_type = ["string", "integer", "decimal", "boolean", "timestamp"][i % 5]
            columns.append(f"""      - name: column_{i:03d}
        logicalType: {col_type}
        required: {str(i < 50).lower()}""")

        columns_yaml = "\n".join(columns)

        contract_content = f"""apiVersion: v3.1.0
kind: DataContract
id: urn:datacontract:drift-perf-test
version: 1.0.0
name: drift-performance-100-columns
status: active
schema:
  - name: large_table
    physicalName: large_table
    columns:
{columns_yaml}
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_content)
        return contract_path

    @pytest.fixture
    def mock_iceberg_schema_100_columns(self) -> MagicMock:
        """Create a mock Iceberg schema with 100 columns."""
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import (
            BooleanType,
            IntegerType,
            LongType,
            StringType,
            TimestampType,
        )

        fields = []
        type_cycle = [StringType, IntegerType, LongType, BooleanType, TimestampType]
        for i in range(100):
            field_type = type_cycle[i % 5]()
            fields.append(
                NestedField(
                    field_id=i + 1,
                    name=f"column_{i:03d}",
                    field_type=field_type,
                    required=(i < 50),
                )
            )

        return Schema(*fields)

    @pytest.mark.requirement("3C-SC-006")
    @pytest.mark.performance
    def test_drift_detection_under_5_seconds_for_100_columns(
        self,
        contract_100_columns_yaml: Path,
        mock_iceberg_schema_100_columns: MagicMock,
    ) -> None:
        """SC-006: Schema drift detection MUST complete within 5 seconds for 100 columns.

        Creates a contract with 100 columns and verifies that drift detection
        completes within the 5 second SLA.
        """
        from floe_iceberg.drift_detector import DriftDetector

        detector = DriftDetector()

        # Extract columns from contract for drift detection
        # (simplified extraction for performance testing)
        contract_columns: list[dict[str, Any]] = []
        type_cycle = ["string", "integer", "decimal", "boolean", "timestamp"]
        for i in range(100):
            contract_columns.append(
                {
                    "name": f"column_{i:03d}",
                    "logicalType": type_cycle[i % 5],
                    "required": (i < 50),
                }
            )

        # Measure drift detection time
        start_time = time.perf_counter()
        result = detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=mock_iceberg_schema_100_columns,
        )
        end_time = time.perf_counter()

        elapsed_seconds = end_time - start_time

        # Assert timing constraint
        assert elapsed_seconds < 5.0, (
            f"Drift detection took {elapsed_seconds:.3f}s, "
            f"exceeding 5s SLA (SC-006) for 100-column table"
        )

        print(f"\nPerformance: 100-column drift detection in {elapsed_seconds:.3f}s")

        # Drift detection should produce valid result
        assert result is not None
        assert hasattr(result, "matches")

    @pytest.mark.requirement("3C-SC-006")
    @pytest.mark.performance
    def test_drift_detection_performance_with_multiple_runs(
        self,
        mock_iceberg_schema_100_columns: MagicMock,
    ) -> None:
        """Verify consistent drift detection performance across multiple runs.

        Uses warm-up run and median for stable benchmarking.
        """
        import statistics

        from floe_iceberg.drift_detector import DriftDetector

        detector = DriftDetector()

        # Create 100-column contract data
        type_cycle = ["string", "integer", "decimal", "boolean", "timestamp"]
        contract_columns: list[dict[str, Any]] = [
            {
                "name": f"column_{i:03d}",
                "logicalType": type_cycle[i % 5],
                "required": (i < 50),
            }
            for i in range(100)
        ]

        # Warm-up run
        detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=mock_iceberg_schema_100_columns,
        )

        times: list[float] = []

        # Run drift detection 5 times (after warm-up)
        for _ in range(5):
            start_time = time.perf_counter()
            detector.compare_schemas(
                contract_columns=contract_columns,
                table_schema=mock_iceberg_schema_100_columns,
            )
            end_time = time.perf_counter()
            times.append(end_time - start_time)

        # Use median for more stable benchmarking
        median_time = statistics.median(times)
        avg_time = sum(times) / len(times)

        assert median_time < 5.0, (
            f"Median drift detection time {median_time:.3f}s exceeds 5s SLA. "
            f"Times: {[f'{t:.3f}s' for t in times]}"
        )

        print(f"\nPerformance: avg={avg_time:.3f}s, median={median_time:.3f}s over 5 runs")


class TestContractValidatorIntegrationPerformance:
    """Performance tests for ContractValidator.validate_with_drift_detection()."""

    @pytest.mark.requirement("3C-SC-001")
    @pytest.mark.requirement("3C-SC-006")
    @pytest.mark.performance
    def test_full_validation_with_drift_under_7_seconds(
        self,
        tmp_path: Path,
    ) -> None:
        """Combined validation + drift detection should complete within 7 seconds.

        This tests the full workflow: contract validation (2s budget) +
        drift detection (5s budget) = 7s total budget.
        """
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import IntegerType, StringType, TimestampType

        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create contract with 50 columns
        columns = []
        for i in range(50):
            col_type = ["string", "integer", "timestamp"][i % 3]
            columns.append(f"""      - name: col_{i:03d}
        logicalType: {col_type}
        required: true""")

        columns_yaml = "\n".join(columns)

        contract_content = f"""apiVersion: v3.1.0
kind: DataContract
id: urn:datacontract:combined-perf-test
version: 1.0.0
name: combined-performance-test
status: active
schema:
  - name: test_table
    physicalName: test_table
    columns:
{columns_yaml}
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_content)

        # Create matching Iceberg schema
        fields = []
        type_cycle = [StringType, IntegerType, TimestampType]
        for i in range(50):
            field_type = type_cycle[i % 3]()
            fields.append(
                NestedField(
                    field_id=i + 1,
                    name=f"col_{i:03d}",
                    field_type=field_type,
                    required=True,
                )
            )
        iceberg_schema = Schema(*fields)

        validator = ContractValidator()

        # Measure combined validation + drift detection time
        start_time = time.perf_counter()
        result = validator.validate_with_drift_detection(
            contract_path=contract_path,
            table_schema=iceberg_schema,
            enforcement_level="strict",
        )
        end_time = time.perf_counter()

        elapsed_seconds = end_time - start_time

        # Combined should be under 7 seconds (2s validation + 5s drift)
        assert elapsed_seconds < 7.0, (
            f"Combined validation took {elapsed_seconds:.3f}s, "
            "exceeding 7s budget (SC-001 + SC-006)"
        )

        print(f"\nPerformance: Combined validation + drift in {elapsed_seconds:.3f}s")

        # Should produce valid result
        assert result is not None
        assert result.validated_at is not None


__all__ = [
    "TestContractValidationPerformance",
    "TestDriftDetectionPerformance",
    "TestContractValidatorIntegrationPerformance",
]
