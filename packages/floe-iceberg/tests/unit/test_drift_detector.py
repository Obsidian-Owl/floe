"""Unit tests for schema drift detection.

Task: T056, T057, T058
Requirements: FR-021 (Schema drift detection), FR-022 (Type mapping),
              FR-023 (Missing columns), FR-024 (Extra columns)

Tests for comparing contract schema against Iceberg table schema.
"""

from __future__ import annotations

import pytest
from pyiceberg.schema import Schema
from pyiceberg.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    TimestampType,
)

from floe_core.schemas.data_contract import SchemaComparisonResult, TypeMismatch


class TestTypeMismatchDetection:
    """Tests for type mismatch detection (FR-021, FR-022).

    Task: T056
    """

    @pytest.mark.requirement("3C-FR-021")
    def test_string_vs_integer_mismatch(self) -> None:
        """Test that string vs integer type mismatch is detected."""
        from floe_iceberg.drift_detector import DriftDetector

        # Contract says string, table has integer
        contract_schema = [
            {"name": "id", "logicalType": "string"},
        ]

        # Build proper Iceberg schema
        from pyiceberg.schema import NestedField

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="id",
                field_type=IntegerType(),
                required=True,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is False
        assert len(result.type_mismatches) == 1
        mismatch = result.type_mismatches[0]
        assert mismatch.column == "id"
        assert mismatch.contract_type == "string"
        assert "int" in mismatch.table_type.lower()

    @pytest.mark.requirement("3C-FR-022")
    def test_integer_vs_long_compatible(self) -> None:
        """Test that integer and long are considered compatible."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        # Contract says integer, table has long (compatible)
        contract_schema = [
            {"name": "count", "logicalType": "integer"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="count",
                field_type=LongType(),
                required=True,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        # Long is a superset of integer, should be compatible
        assert result.matches is True
        assert len(result.type_mismatches) == 0

    @pytest.mark.requirement("3C-FR-022")
    def test_number_vs_double_compatible(self) -> None:
        """Test that ODCS 'number' maps to Iceberg double."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        # ODCS 'number' should map to double
        contract_schema = [
            {"name": "price", "logicalType": "number"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="price",
                field_type=DoubleType(),
                required=True,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is True

    @pytest.mark.requirement("3C-FR-022")
    def test_timestamp_type_mapping(self) -> None:
        """Test that ODCS 'timestamp' maps to Iceberg timestamp."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        contract_schema = [
            {"name": "created_at", "logicalType": "timestamp"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="created_at",
                field_type=TimestampType(),
                required=True,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is True

    @pytest.mark.requirement("3C-FR-021")
    def test_boolean_vs_string_mismatch(self) -> None:
        """Test that boolean vs string mismatch is detected."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        contract_schema = [
            {"name": "active", "logicalType": "boolean"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="active",
                field_type=StringType(),
                required=True,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is False
        assert len(result.type_mismatches) == 1
        assert result.type_mismatches[0].column == "active"


class TestMissingColumnDetection:
    """Tests for missing column detection (FR-023).

    Task: T057
    """

    @pytest.mark.requirement("3C-FR-023")
    def test_column_in_contract_but_not_in_table(self) -> None:
        """Test detection of columns in contract but missing from table."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        # Contract expects id and email, table only has id
        contract_schema = [
            {"name": "id", "logicalType": "string"},
            {"name": "email", "logicalType": "string"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="id",
                field_type=StringType(),
                required=True,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is False
        assert "email" in result.missing_columns

    @pytest.mark.requirement("3C-FR-023")
    def test_multiple_missing_columns(self) -> None:
        """Test detection of multiple missing columns."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        contract_schema = [
            {"name": "id", "logicalType": "string"},
            {"name": "email", "logicalType": "string"},
            {"name": "name", "logicalType": "string"},
            {"name": "phone", "logicalType": "string"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="id",
                field_type=StringType(),
                required=True,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is False
        assert len(result.missing_columns) == 3
        assert "email" in result.missing_columns
        assert "name" in result.missing_columns
        assert "phone" in result.missing_columns


class TestExtraColumnDetection:
    """Tests for extra column detection (FR-024).

    Task: T058

    Extra columns are informational only - they don't cause validation failure.
    """

    @pytest.mark.requirement("3C-FR-024")
    def test_column_in_table_but_not_in_contract(self) -> None:
        """Test detection of columns in table but not in contract (info only)."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        # Contract expects id, table has id and extra_column
        contract_schema = [
            {"name": "id", "logicalType": "string"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="id",
                field_type=StringType(),
                required=True,
            ),
            NestedField(
                field_id=2,
                name="extra_column",
                field_type=StringType(),
                required=False,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        # Extra columns don't cause failure
        assert result.matches is True
        assert "extra_column" in result.extra_columns

    @pytest.mark.requirement("3C-FR-024")
    def test_extra_columns_with_type_match(self) -> None:
        """Test that extra columns are reported even when types match."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        contract_schema = [
            {"name": "id", "logicalType": "string"},
            {"name": "name", "logicalType": "string"},
        ]

        table_schema = Schema(
            NestedField(
                field_id=1,
                name="id",
                field_type=StringType(),
                required=True,
            ),
            NestedField(
                field_id=2,
                name="name",
                field_type=StringType(),
                required=True,
            ),
            NestedField(
                field_id=3,
                name="created_at",
                field_type=TimestampType(),
                required=False,
            ),
            NestedField(
                field_id=4,
                name="updated_at",
                field_type=TimestampType(),
                required=False,
            ),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is True
        assert len(result.extra_columns) == 2
        assert "created_at" in result.extra_columns
        assert "updated_at" in result.extra_columns


class TestCompleteSchemaComparison:
    """Tests for complete schema comparison scenarios.

    Task: T056, T057, T058
    """

    @pytest.mark.requirement("3C-FR-021")
    def test_exact_schema_match(self) -> None:
        """Test that identical schemas match."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        contract_schema = [
            {"name": "id", "logicalType": "string"},
            {"name": "name", "logicalType": "string"},
            {"name": "age", "logicalType": "integer"},
            {"name": "active", "logicalType": "boolean"},
        ]

        table_schema = Schema(
            NestedField(1, "id", StringType(), required=True),
            NestedField(2, "name", StringType(), required=True),
            NestedField(3, "age", IntegerType(), required=True),
            NestedField(4, "active", BooleanType(), required=True),
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is True
        assert len(result.type_mismatches) == 0
        assert len(result.missing_columns) == 0
        assert len(result.extra_columns) == 0

    @pytest.mark.requirement("3C-FR-021")
    def test_combined_issues(self) -> None:
        """Test detection of multiple issue types simultaneously."""
        from floe_iceberg.drift_detector import DriftDetector
        from pyiceberg.schema import NestedField

        # Contract has type mismatch, missing column, and table has extra column
        contract_schema = [
            {"name": "id", "logicalType": "string"},  # Type mismatch (table has int)
            {"name": "missing_col", "logicalType": "string"},  # Missing from table
        ]

        table_schema = Schema(
            NestedField(1, "id", IntegerType(), required=True),  # Mismatch
            NestedField(2, "extra_col", StringType(), required=False),  # Extra
        )

        detector = DriftDetector()
        result = detector.compare_schemas(
            contract_columns=contract_schema,
            table_schema=table_schema,
        )

        assert result.matches is False
        assert len(result.type_mismatches) == 1
        assert result.type_mismatches[0].column == "id"
        assert "missing_col" in result.missing_columns
        assert "extra_col" in result.extra_columns


__all__ = [
    "TestTypeMismatchDetection",
    "TestMissingColumnDetection",
    "TestExtraColumnDetection",
    "TestCompleteSchemaComparison",
]
