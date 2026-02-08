"""dbt test to QualityCheck mapper for floe compilation.

This module maps dbt generic tests (not_null, unique, accepted_values,
relationships) to floe QualityCheck format, including dimension mapping
and check deduplication.

Implements:
    - FR-018: Reference without duplication
    - T043: dbt generic test mapping
    - T044: Custom expectation support
    - T044a: Check deduplication logic
"""

from __future__ import annotations

from typing import Any

from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import QualityCheck

# Mapping of dbt test types to quality dimensions
DBT_TEST_DIMENSION_MAP: dict[str, Dimension] = {
    # Completeness: Data is present where expected
    "not_null": Dimension.COMPLETENESS,
    "expect_column_to_exist": Dimension.COMPLETENESS,
    # Consistency: Data is consistent across sources
    "unique": Dimension.CONSISTENCY,
    "relationships": Dimension.CONSISTENCY,
    "compound_unique": Dimension.CONSISTENCY,
    # Validity: Data conforms to defined rules
    "accepted_values": Dimension.VALIDITY,
    "expect_column_values_to_match_regex": Dimension.VALIDITY,
    "expect_column_values_to_be_in_set": Dimension.VALIDITY,
    # Accuracy: Data values are correct
    "expect_column_values_to_be_between": Dimension.ACCURACY,
    "expect_column_min_to_be_between": Dimension.ACCURACY,
    "expect_column_max_to_be_between": Dimension.ACCURACY,
    "expect_column_mean_to_be_between": Dimension.ACCURACY,
    # Timeliness: Data is current
    "expect_column_values_to_be_dateutil_parseable": Dimension.TIMELINESS,
    "recency": Dimension.TIMELINESS,
}

# Default severity for dbt tests (can be overridden per-check)
DEFAULT_DBT_TEST_SEVERITY = SeverityLevel.WARNING


def infer_dimension(test_type: str) -> Dimension:
    """Infer quality dimension from test type.

    Args:
        test_type: The dbt test type (e.g., 'not_null', 'unique').

    Returns:
        The inferred Dimension, defaults to VALIDITY if unknown.
    """
    return DBT_TEST_DIMENSION_MAP.get(test_type, Dimension.VALIDITY)


def map_dbt_test_to_check(
    model_name: str,
    test_type: str,
    column: str | None = None,
    parameters: dict[str, Any] | None = None,
    severity: SeverityLevel | None = None,
) -> QualityCheck:
    """Map a dbt test to a QualityCheck.

    Args:
        model_name: The dbt model name.
        test_type: The dbt test type (not_null, unique, etc.).
        column: The target column (None for table-level tests).
        parameters: Test parameters (e.g., values for accepted_values).
        severity: Override severity (defaults to WARNING).

    Returns:
        QualityCheck instance mapped from the dbt test.
    """
    dimension = infer_dimension(test_type)
    check_severity = severity or DEFAULT_DBT_TEST_SEVERITY

    # Generate a unique check name
    if column:
        check_name = f"{model_name}_{column}_{test_type}"
    else:
        check_name = f"{model_name}_{test_type}"

    return QualityCheck(
        name=check_name,
        type=test_type,
        column=column,
        dimension=dimension,
        severity=check_severity,
        parameters=parameters or {},
    )


def get_check_signature(check: QualityCheck) -> str:
    """Get a unique signature for a check for deduplication.

    Two checks with the same signature are considered duplicates.
    Signature is based on: type + column (if any).

    Args:
        check: The QualityCheck to get signature for.

    Returns:
        A string signature for deduplication.
    """
    if check.column:
        return f"{check.type}:{check.column}"
    return f"{check.type}:__table__"


def deduplicate_checks(
    dbt_checks: list[QualityCheck],
    floe_checks: list[QualityCheck],
) -> list[QualityCheck]:
    """Deduplicate quality checks, with dbt definitions taking precedence.

    When the same check is defined in both dbt schema.yml and floe.yaml,
    the dbt definition takes precedence (Edge Case 6 / FR-018).

    Args:
        dbt_checks: Checks derived from dbt schema.yml tests.
        floe_checks: Checks defined directly in floe.yaml.

    Returns:
        Deduplicated list of QualityCheck, dbt checks first.
    """
    # Build signature set from dbt checks
    dbt_signatures = {get_check_signature(check) for check in dbt_checks}

    # Filter floe checks that don't duplicate dbt checks
    unique_floe_checks = [
        check
        for check in floe_checks
        if get_check_signature(check) not in dbt_signatures
    ]

    # dbt checks come first (they take precedence)
    return list(dbt_checks) + unique_floe_checks


def merge_model_checks(
    model_name: str,
    dbt_tests: list[dict[str, Any]],
    floe_checks: list[QualityCheck] | None,
) -> list[QualityCheck]:
    """Merge dbt tests and floe quality checks for a model.

    Converts dbt tests to QualityCheck format and deduplicates
    with any explicitly defined floe.yaml checks.

    Args:
        model_name: The dbt model name.
        dbt_tests: List of dbt test definitions from schema.yml.
        floe_checks: Quality checks from floe.yaml (may be None).

    Returns:
        Merged and deduplicated list of QualityCheck.
    """
    # Convert dbt tests to QualityCheck
    dbt_quality_checks = []
    for test in dbt_tests:
        test_type = test.get("type") or test.get("test")
        column = test.get("column")
        parameters = {
            k: v for k, v in test.items() if k not in ("type", "test", "column")
        }

        if test_type:
            check = map_dbt_test_to_check(
                model_name=model_name,
                test_type=test_type,
                column=column,
                parameters=parameters if parameters else None,
            )
            dbt_quality_checks.append(check)

    # Deduplicate with floe checks
    return deduplicate_checks(dbt_quality_checks, floe_checks or [])


__all__ = [
    "DBT_TEST_DIMENSION_MAP",
    "DEFAULT_DBT_TEST_SEVERITY",
    "deduplicate_checks",
    "get_check_signature",
    "infer_dimension",
    "map_dbt_test_to_check",
    "merge_model_checks",
]
