"""Contract tests for drift detection between floe-core and floe-iceberg.

Task: T059
Requirements: FR-021 (Schema drift detection)

Tests that SchemaComparisonResult and TypeMismatch models from floe-core
are correctly used by DriftDetector in floe-iceberg.
"""

from __future__ import annotations

import pytest


class TestDriftDetectionContract:
    """Contract tests for drift detection models.

    Validates that floe-iceberg's DriftDetector correctly uses
    floe-core's SchemaComparisonResult and TypeMismatch models.
    """

    @pytest.mark.requirement("3C-FR-021")
    def test_drift_detector_returns_schema_comparison_result(self) -> None:
        """Test that DriftDetector.compare_schemas returns SchemaComparisonResult."""
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import StringType

        from floe_core.schemas.data_contract import SchemaComparisonResult
        from floe_iceberg.drift_detector import DriftDetector

        contract_columns = [{"name": "id", "logicalType": "string"}]
        table_schema = Schema(
            NestedField(1, "id", StringType(), required=True),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=table_schema,
        )

        # Result should be a SchemaComparisonResult from floe-core
        assert isinstance(result, SchemaComparisonResult)
        assert result.matches is True

    @pytest.mark.requirement("3C-FR-021")
    def test_type_mismatch_model_used_correctly(self) -> None:
        """Test that TypeMismatch model is used for type mismatches."""
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import IntegerType

        from floe_core.schemas.data_contract import TypeMismatch
        from floe_iceberg.drift_detector import DriftDetector

        # Contract says string, table has integer
        contract_columns = [{"name": "id", "logicalType": "string"}]
        table_schema = Schema(
            NestedField(1, "id", IntegerType(), required=True),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=table_schema,
        )

        assert result.matches is False
        assert len(result.type_mismatches) == 1
        # Type mismatch should be TypeMismatch from floe-core
        assert isinstance(result.type_mismatches[0], TypeMismatch)
        assert result.type_mismatches[0].column == "id"
        assert result.type_mismatches[0].contract_type == "string"

    @pytest.mark.requirement("3C-FR-021")
    def test_schema_comparison_result_immutable(self) -> None:
        """Test that SchemaComparisonResult is immutable (frozen)."""
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import StringType

        from floe_iceberg.drift_detector import DriftDetector

        contract_columns = [{"name": "id", "logicalType": "string"}]
        table_schema = Schema(
            NestedField(1, "id", StringType(), required=True),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=table_schema,
        )

        # Attempting to modify should raise an error (frozen model)
        with pytest.raises(Exception):  # ValidationError or AttributeError
            result.matches = False  # type: ignore[misc]

    @pytest.mark.requirement("3C-FR-021")
    def test_missing_columns_list_immutable(self) -> None:
        """Test that missing_columns list is returned correctly."""
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import StringType

        from floe_iceberg.drift_detector import DriftDetector

        # Contract has extra column not in table
        contract_columns = [
            {"name": "id", "logicalType": "string"},
            {"name": "missing_col", "logicalType": "string"},
        ]
        table_schema = Schema(
            NestedField(1, "id", StringType(), required=True),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=table_schema,
        )

        assert isinstance(result.missing_columns, list)
        assert "missing_col" in result.missing_columns

    @pytest.mark.requirement("3C-FR-024")
    def test_extra_columns_reported(self) -> None:
        """Test that extra columns in table are reported."""
        from pyiceberg.schema import NestedField, Schema
        from pyiceberg.types import StringType

        from floe_iceberg.drift_detector import DriftDetector

        # Table has extra column not in contract
        contract_columns = [{"name": "id", "logicalType": "string"}]
        table_schema = Schema(
            NestedField(1, "id", StringType(), required=True),
            NestedField(2, "extra_col", StringType(), required=False),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_columns,
            table_schema=table_schema,
        )

        # Extra columns don't cause failure
        assert result.matches is True
        assert isinstance(result.extra_columns, list)
        assert "extra_col" in result.extra_columns


class TestDriftDetectorExport:
    """Tests that DriftDetector is properly exported from floe-iceberg."""

    @pytest.mark.requirement("3C-FR-021")
    def test_drift_detector_importable_from_package(self) -> None:
        """Test that DriftDetector can be imported from floe_iceberg."""
        from floe_iceberg import DriftDetector

        assert DriftDetector is not None
        detector = DriftDetector()
        assert hasattr(detector, "compare_schemas")


__all__ = [
    "TestDriftDetectionContract",
    "TestDriftDetectorExport",
]
