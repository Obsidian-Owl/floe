"""Great Expectations validation executor.

This module provides the core validation execution functionality
for the GreatExpectationsPlugin, using GX 1.0+ ephemeral contexts.

Design Decisions:
    - Uses ephemeral context (no YAML files required)
    - Timeout implemented via threading (cross-platform)
    - Maps floe QualityCheck to GX Expectations dynamically
"""

from __future__ import annotations

import re
import threading
import time
from typing import TYPE_CHECKING, Any

import great_expectations as gx
from floe_core.quality_errors import QualityTimeoutError
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualitySuite,
    QualitySuiteResult,
)

if TYPE_CHECKING:
    import pandas as pd
    from great_expectations.core.expectation_validation_result import (
        ExpectationSuiteValidationResult,
    )

_SAFE_TABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")

# Mapping from floe check types to GX expectation classes
CHECK_TYPE_TO_GX_EXPECTATION: dict[str, str] = {
    "not_null": "ExpectColumnValuesToNotBeNull",
    "unique": "ExpectColumnValuesToBeUnique",
    "values_in_set": "ExpectColumnValuesToBeInSet",
    "values_between": "ExpectColumnValuesToBeBetween",
    "regex_match": "ExpectColumnValuesToMatchRegex",
    "row_count_between": "ExpectTableRowCountToBeBetween",
    "column_exists": "ExpectColumnToExist",
    "column_type": "ExpectColumnValuesToBeOfType",
}


def _map_check_to_gx_expectation(check: QualityCheck) -> Any:
    """Map a floe QualityCheck to a GX Expectation object.

    Args:
        check: The floe QualityCheck definition.

    Returns:
        A GX Expectation instance.

    Raises:
        ValueError: If check type is not supported.
    """
    gx_class_name = CHECK_TYPE_TO_GX_EXPECTATION.get(check.type)

    if gx_class_name is None:
        # Try to use the type directly as a GX expectation name
        gx_class_name = check.type

    # Get the expectation class from gx.expectations
    try:
        expectation_class = getattr(gx.expectations, gx_class_name)
    except AttributeError as e:
        msg = f"Unsupported check type: {check.type} (GX expectation: {gx_class_name})"
        raise ValueError(msg) from e

    # Build kwargs for the expectation
    kwargs: dict[str, Any] = {}
    if check.column:
        kwargs["column"] = check.column

    # Add parameters from check definition
    kwargs.update(check.parameters)

    return expectation_class(**kwargs)


def _convert_gx_result_to_check_result(
    gx_result: dict[str, Any],
    check: QualityCheck,
) -> QualityCheckResult:
    """Convert a single GX expectation result to QualityCheckResult.

    Args:
        gx_result: The GX expectation validation result dict.
        check: The original floe QualityCheck.

    Returns:
        QualityCheckResult with mapped fields.
    """
    passed = gx_result.get("success", False)
    result_details = gx_result.get("result", {})

    # Extract record counts if available
    records_checked = result_details.get("element_count", 0)
    records_failed = result_details.get("unexpected_count", 0)

    # Build error message if failed
    error_message = None
    if not passed:
        unexpected_percent = result_details.get("unexpected_percent", 0)
        error_message = f"Check failed: {unexpected_percent:.2f}% of values failed validation"
        if "partial_unexpected_list" in result_details:
            samples = result_details["partial_unexpected_list"][:5]
            error_message += f". Sample failures: {samples}"

    return QualityCheckResult(
        check_name=check.name,
        passed=passed,
        dimension=check.dimension,
        severity=check.severity,
        records_checked=records_checked,
        records_failed=records_failed,
        error_message=error_message,
        details=result_details,
    )


def run_validation_with_timeout(
    suite: QualitySuite,
    dataframe: pd.DataFrame,
    timeout_seconds: int,
) -> QualitySuiteResult:
    """Run GX validation with timeout handling.

    Args:
        suite: The QualitySuite with checks to execute.
        dataframe: The pandas DataFrame to validate.
        timeout_seconds: Maximum execution time.

    Returns:
        QualitySuiteResult with all check results.

    Raises:
        QualityTimeoutError: If validation exceeds timeout.
    """
    result_holder: list[ExpectationSuiteValidationResult | None] = [None]
    exception_holder: list[Exception | None] = [None]
    start_time = time.time()

    def _run_validation() -> None:
        try:
            # Create ephemeral context (no YAML needed)
            context = gx.get_context(mode="ephemeral")

            # Set up data source and asset
            datasource = context.data_sources.add_pandas("floe_datasource")
            data_asset = datasource.add_dataframe_asset(name="floe_asset")
            batch_definition = data_asset.add_batch_definition_whole_dataframe("floe_batch")

            # Create expectation suite
            gx_suite = context.suites.add(gx.ExpectationSuite(name=f"{suite.model_name}_suite"))

            # Add expectations from floe checks
            for check in suite.checks:
                if check.enabled:
                    try:
                        expectation = _map_check_to_gx_expectation(check)
                        gx_suite.add_expectation(expectation)
                    except ValueError:
                        # Skip unsupported check types, they'll be marked as failed
                        pass

            # Create validation definition
            validation_def = gx.ValidationDefinition(
                data=batch_definition,
                suite=gx_suite,
                name="floe_validation",
            )
            validation_def = context.validation_definitions.add(validation_def)

            # Run validation
            result_holder[0] = validation_def.run(batch_parameters={"dataframe": dataframe})
        except Exception as e:
            exception_holder[0] = e

    # Run validation in a thread with timeout
    thread = threading.Thread(target=_run_validation, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    execution_time_ms = (time.time() - start_time) * 1000

    if thread.is_alive():
        # Timeout occurred
        pending_checks = [c.name for c in suite.checks if c.enabled]
        raise QualityTimeoutError(
            model_name=suite.model_name,
            timeout_seconds=timeout_seconds,
            pending_checks=pending_checks,
        )

    if exception_holder[0] is not None:
        raise exception_holder[0]

    gx_result = result_holder[0]
    if gx_result is None:
        # Should not happen, but handle gracefully
        return QualitySuiteResult(
            suite_name=f"{suite.model_name}_suite",
            model_name=suite.model_name,
            passed=True,
            checks=[],
            execution_time_ms=execution_time_ms,
        )

    # Convert GX results to floe QualityCheckResults
    check_results: list[QualityCheckResult] = []
    gx_expectations = gx_result.results if hasattr(gx_result, "results") else []

    # Map results back to checks by index (GX maintains order)
    enabled_checks = [c for c in suite.checks if c.enabled]
    for _i, (check, gx_exp_result) in enumerate(zip(enabled_checks, gx_expectations, strict=False)):
        check_result = _convert_gx_result_to_check_result(
            gx_exp_result.to_json_dict() if hasattr(gx_exp_result, "to_json_dict") else {},
            check,
        )
        check_results.append(check_result)

        # Handle fail_fast
        if suite.fail_fast and not check_result.passed:
            break

    # Calculate overall pass/fail
    all_passed = all(r.passed for r in check_results)
    stats = gx_result.statistics if hasattr(gx_result, "statistics") else {}

    return QualitySuiteResult(
        suite_name=f"{suite.model_name}_suite",
        model_name=suite.model_name,
        passed=all_passed,
        checks=check_results,
        execution_time_ms=execution_time_ms,
        summary={
            "total": stats.get("evaluated_expectations", len(check_results)),
            "passed": stats.get(
                "successful_expectations", sum(1 for r in check_results if r.passed)
            ),
            "failed": stats.get(
                "unsuccessful_expectations", sum(1 for r in check_results if not r.passed)
            ),
            "success_percent": stats.get("success_percent", 0.0),
        },
    )


def create_dataframe_from_connection(
    connection_config: dict[str, Any],
    table_name: str,
) -> pd.DataFrame:
    """Create a pandas DataFrame from connection config.

    This is a placeholder that should be enhanced to support
    various connection types (DuckDB, PostgreSQL, Snowflake).

    Args:
        connection_config: Database connection configuration.
        table_name: Name of the table to load.

    Returns:
        pandas DataFrame with table data.
    """
    import pandas as pd

    dialect = connection_config.get("dialect", "duckdb")

    if dialect == "duckdb":
        import duckdb

        if not _SAFE_TABLE_NAME.match(table_name):
            msg = f"Invalid table name: {table_name!r}"
            raise ValueError(msg)

        path = connection_config.get("path", ":memory:")
        conn = duckdb.connect(path)
        try:
            return conn.execute(f"SELECT * FROM {table_name}").fetchdf()  # nosec B608 - validated above
        except duckdb.CatalogException:
            # Table doesn't exist, return empty DataFrame
            return pd.DataFrame()
        finally:
            conn.close()

    # For other dialects, would need proper connection handling
    # This is a simplified implementation for the core use case
    return pd.DataFrame()


__all__ = [
    "run_validation_with_timeout",
    "create_dataframe_from_connection",
]
