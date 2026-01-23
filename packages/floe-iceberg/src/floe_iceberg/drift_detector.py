"""Schema drift detection for Iceberg tables.

This module provides the DriftDetector class that compares contract schemas
against actual Iceberg table schemas to detect drift.

Task: T061, T062, T063, T064
Requirements: FR-021 (Schema drift detection), FR-022 (Type mapping),
              FR-023 (Missing columns), FR-024 (Extra columns)

Example:
    >>> from floe_iceberg.drift_detector import DriftDetector
    >>> from pyiceberg.catalog import load_catalog
    >>>
    >>> catalog = load_catalog("default")
    >>> table = catalog.load_table("my_namespace.my_table")
    >>>
    >>> detector = DriftDetector()
    >>> result = detector.compare_schemas(
    ...     contract_columns=[{"name": "id", "logicalType": "string"}],
    ...     table_schema=table.schema(),
    ... )
    >>> if not result.matches:
    ...     print(f"Type mismatches: {result.type_mismatches}")
    ...     print(f"Missing columns: {result.missing_columns}")
"""

from __future__ import annotations

from typing import Any

import structlog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    BooleanType,
    DateType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    StringType,
    TimestampType,
    TimeType,
)

from floe_core.schemas.data_contract import SchemaComparisonResult, TypeMismatch

logger = structlog.get_logger(__name__)


# ODCS logicalType to Iceberg type mapping
# Maps ODCS types to compatible Iceberg types
ODCS_TO_ICEBERG_TYPE_MAP: dict[str, list[type]] = {
    # String types
    "string": [StringType],
    # Integer types - integer is compatible with IntegerType and LongType
    "integer": [IntegerType, LongType],
    "int": [IntegerType, LongType],
    "long": [LongType, IntegerType],
    # Number types - number maps to float/double
    "number": [FloatType, DoubleType],
    "float": [FloatType, DoubleType],
    "double": [DoubleType, FloatType],
    "decimal": [FloatType, DoubleType],  # Simplified mapping
    # Boolean
    "boolean": [BooleanType],
    # Date/Time types
    "date": [DateType],
    "timestamp": [TimestampType],
    "time": [TimeType],
    # Complex types (simplified - could be expanded)
    "array": [],  # Would need ArrayType handling
    "object": [],  # Would need StructType handling
}


class DriftDetector:
    """Detector for schema drift between contract and Iceberg table.

    Compares contract schema definitions against actual Iceberg table
    schemas to detect type mismatches, missing columns, and extra columns.

    Task: T061
    Requirements: FR-021, FR-022, FR-023, FR-024

    Attributes:
        _log: Structured logger for this detector instance.

    Example:
        >>> detector = DriftDetector()
        >>> result = detector.compare_schemas(
        ...     contract_columns=[{"name": "id", "logicalType": "string"}],
        ...     table_schema=iceberg_schema,
        ... )
        >>> if not result.matches:
        ...     for m in result.type_mismatches:
        ...         print(f"{m.column}: {m.contract_type} vs {m.table_type}")
    """

    def __init__(self) -> None:
        """Initialize DriftDetector."""
        self._log = logger.bind(component="DriftDetector")
        self._log.debug("drift_detector_initialized")

    def compare_schemas(
        self,
        contract_columns: list[dict[str, Any]],
        table_schema: Schema,
    ) -> SchemaComparisonResult:
        """Compare contract schema against Iceberg table schema.

        Task: T063, T064
        Requirements: FR-021, FR-022, FR-023, FR-024

        Detects:
        - Type mismatches: Column type in contract differs from table
        - Missing columns: Column in contract but not in table
        - Extra columns: Column in table but not in contract (info only)

        Args:
            contract_columns: List of column definitions from contract.
                Each dict should have 'name' and 'logicalType' keys.
            table_schema: PyIceberg Schema from the table.

        Returns:
            SchemaComparisonResult with matches flag and any issues found.
        """
        self._log.info(
            "comparing_schemas",
            contract_column_count=len(contract_columns),
            table_column_count=len(table_schema.fields),
        )

        type_mismatches: list[TypeMismatch] = []
        missing_columns: list[str] = []
        extra_columns: list[str] = []

        # Build lookup of table columns
        table_columns: dict[str, Any] = {}
        for field in table_schema.fields:
            table_columns[field.name] = field

        # Build set of contract column names
        contract_column_names: set[str] = set()

        # Check each contract column against table
        for col in contract_columns:
            col_name = col.get("name", "")
            col_type = col.get("logicalType", "")
            contract_column_names.add(col_name)

            if col_name not in table_columns:
                # Column in contract but not in table
                missing_columns.append(col_name)
                self._log.debug(
                    "missing_column_detected",
                    column=col_name,
                )
                continue

            # Check type compatibility
            table_field = table_columns[col_name]
            if not self._is_type_compatible(col_type, table_field.field_type):
                type_mismatches.append(
                    TypeMismatch(
                        column=col_name,
                        contract_type=col_type,
                        table_type=str(table_field.field_type),
                    )
                )
                self._log.debug(
                    "type_mismatch_detected",
                    column=col_name,
                    contract_type=col_type,
                    table_type=str(table_field.field_type),
                )

        # Check for extra columns (in table but not in contract)
        for field in table_schema.fields:
            if field.name not in contract_column_names:
                extra_columns.append(field.name)
                self._log.debug(
                    "extra_column_detected",
                    column=field.name,
                )

        # Schema matches if no type mismatches and no missing columns
        # Extra columns are informational only and don't cause failure
        matches = len(type_mismatches) == 0 and len(missing_columns) == 0

        result = SchemaComparisonResult(
            matches=matches,
            type_mismatches=type_mismatches,
            missing_columns=missing_columns,
            extra_columns=extra_columns,
        )

        if matches:
            self._log.info(
                "schema_comparison_passed",
                extra_columns=len(extra_columns),
            )
        else:
            self._log.warning(
                "schema_comparison_failed",
                type_mismatches=len(type_mismatches),
                missing_columns=len(missing_columns),
                extra_columns=len(extra_columns),
            )

        return result

    def _is_type_compatible(
        self,
        odcs_type: str,
        iceberg_type: Any,
    ) -> bool:
        """Check if ODCS type is compatible with Iceberg type.

        Task: T062
        Requirements: FR-022

        Args:
            odcs_type: ODCS logicalType string (e.g., "string", "integer").
            iceberg_type: PyIceberg type instance.

        Returns:
            True if types are compatible, False otherwise.
        """
        odcs_type_lower = odcs_type.lower()

        # Get compatible Iceberg types for this ODCS type
        compatible_types = ODCS_TO_ICEBERG_TYPE_MAP.get(odcs_type_lower, [])

        if not compatible_types:
            # Unknown ODCS type - no match
            self._log.warning(
                "unknown_odcs_type",
                odcs_type=odcs_type,
            )
            return False

        # Check if iceberg_type is an instance of any compatible type
        for compat_type in compatible_types:
            if isinstance(iceberg_type, compat_type):
                return True

        return False


__all__ = [
    "DriftDetector",
    "ODCS_TO_ICEBERG_TYPE_MAP",
]
