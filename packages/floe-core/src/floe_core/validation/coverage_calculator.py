"""Coverage calculation for quality gate validation.

This module provides functions for calculating test coverage metrics
including column coverage percentage and test type detection.

T072: Coverage calculation (% columns with tests)
T073: Required test type detection
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CoverageResult:
    """Result of coverage calculation for a model."""

    model_name: str
    total_columns: int
    columns_with_tests: int
    coverage_percentage: float
    test_types_present: set[str]
    tier: str


def calculate_coverage(model: dict[str, Any]) -> CoverageResult:
    """Calculate test coverage for a model.

    Coverage is calculated as the percentage of columns that have at least
    one test defined. Test types are extracted from the tests defined on
    columns and at the model level.

    Args:
        model: Model dictionary containing columns and tests.
            Expected structure:
            {
                "name": "model_name",
                "tier": "gold",
                "columns": [
                    {"name": "id", "tests": ["not_null", "unique"]},
                    {"name": "name", "tests": ["not_null"]},
                    {"name": "created_at", "tests": []},
                ],
                "tests": ["relationships"]  # Model-level tests
            }

    Returns:
        CoverageResult with coverage metrics and test types.
    """
    model_name = model.get("name", "unknown")
    tier = model.get("tier", "bronze")
    columns = model.get("columns", [])

    total_columns = len(columns)
    columns_with_tests = 0
    test_types: set[str] = set()

    for column in columns:
        column_tests = column.get("tests", [])
        if column_tests:
            columns_with_tests += 1
            for test in column_tests:
                test_type = _extract_test_type(test)
                test_types.add(test_type)

    model_tests = model.get("tests", [])
    for test in model_tests:
        test_type = _extract_test_type(test)
        test_types.add(test_type)

    coverage_percentage = 0.0
    if total_columns > 0:
        coverage_percentage = (columns_with_tests / total_columns) * 100.0

    return CoverageResult(
        model_name=model_name,
        total_columns=total_columns,
        columns_with_tests=columns_with_tests,
        coverage_percentage=coverage_percentage,
        test_types_present=test_types,
        tier=tier,
    )


def _extract_test_type(test: str | dict[str, Any]) -> str:
    """Extract the test type name from a test definition.

    Tests can be specified as:
    - Simple string: "not_null"
    - Dictionary with test name as key: {"unique": {"columns": ["id"]}}
    - dbt-style with schema_test: {"schema_test": "not_null"}

    Args:
        test: Test definition (string or dict).

    Returns:
        Test type name.
    """
    if isinstance(test, str):
        return test

    if isinstance(test, dict):
        if "schema_test" in test:
            return str(test["schema_test"])
        keys = list(test.keys())
        if keys:
            return str(keys[0])

    return "unknown"


def detect_test_types(model: dict[str, Any]) -> set[str]:
    """Detect all test types present in a model.

    Scans both column-level and model-level tests to build a complete
    set of test types used.

    Args:
        model: Model dictionary containing columns and tests.

    Returns:
        Set of test type names present in the model.
    """
    coverage = calculate_coverage(model)
    return coverage.test_types_present


__all__ = [
    "CoverageResult",
    "calculate_coverage",
    "detect_test_types",
]
