"""dbt-expectations validation executor.

This module provides the core validation execution functionality
for the DBTExpectationsPlugin, using dbtRunner programmatic API.

Design Decisions:
    - Uses dbtRunner for in-process execution (no subprocess)
    - Parses run_results for test outcomes
    - Maps dbt test results to QualityCheckResult
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from floe_core.quality_errors import QualityTimeoutError
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualitySuite,
    QualitySuiteResult,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


# Mapping from dbt test names to quality dimensions
TEST_NAME_TO_DIMENSION: dict[str, Dimension] = {
    "not_null": Dimension.COMPLETENESS,
    "unique": Dimension.CONSISTENCY,
    "accepted_values": Dimension.VALIDITY,
    "relationships": Dimension.CONSISTENCY,
    # dbt-expectations tests
    "expect_column_values_to_not_be_null": Dimension.COMPLETENESS,
    "expect_column_values_to_be_unique": Dimension.CONSISTENCY,
    "expect_column_values_to_be_in_set": Dimension.VALIDITY,
    "expect_column_values_to_be_between": Dimension.VALIDITY,
    "expect_column_values_to_match_regex": Dimension.VALIDITY,
    "expect_table_row_count_to_be_between": Dimension.COMPLETENESS,
}


def _infer_dimension_from_test_name(test_name: str) -> Dimension:
    """Infer quality dimension from dbt test name.

    Args:
        test_name: The dbt test name (e.g., "not_null_users_email").

    Returns:
        The inferred Dimension, defaults to VALIDITY.
    """
    test_name_lower = test_name.lower()

    for pattern, dimension in TEST_NAME_TO_DIMENSION.items():
        if pattern in test_name_lower:
            return dimension

    # Default to validity for unknown tests
    return Dimension.VALIDITY


def _convert_dbt_result_to_check_result(
    dbt_result: dict[str, Any],
    check: QualityCheck | None = None,
) -> QualityCheckResult:
    """Convert a dbt test result to QualityCheckResult.

    Args:
        dbt_result: The dbt test result dict from run_results.
        check: Optional original QualityCheck for metadata.

    Returns:
        QualityCheckResult with mapped fields.
    """
    status = dbt_result.get("status", "error")
    passed = status == "pass"
    test_name = dbt_result.get("unique_id", "").split(".")[-1]

    # Determine dimension
    dimension = Dimension.VALIDITY
    if check:
        dimension = check.dimension
    else:
        dimension = _infer_dimension_from_test_name(test_name)

    # Determine severity from check or default
    severity = SeverityLevel.WARNING
    if check:
        severity = check.severity
    elif status == "error":
        severity = SeverityLevel.CRITICAL

    # Extract failure count
    failures = dbt_result.get("failures", 0) or 0

    # Build error message
    error_message = None
    if not passed:
        message = dbt_result.get("message")
        if message:
            error_message = message
        elif failures > 0:
            error_message = f"{failures} rows failed the test"
        else:
            error_message = f"Test failed with status: {status}"

    return QualityCheckResult(
        check_name=check.name if check else test_name,
        passed=passed,
        dimension=dimension,
        severity=severity,
        records_failed=failures,
        execution_time_ms=dbt_result.get("execution_time", 0) * 1000,
        error_message=error_message,
        details={
            "dbt_status": status,
            "unique_id": dbt_result.get("unique_id"),
            "compiled_code": dbt_result.get("compiled_code"),
        },
    )


def run_dbt_tests_with_timeout(
    suite: QualitySuite,
    project_dir: str | None = None,
    profiles_dir: str | None = None,
    timeout_seconds: int = 300,
) -> QualitySuiteResult:
    """Run dbt tests with timeout handling.

    Args:
        suite: The QualitySuite with checks to execute.
        project_dir: Path to dbt project directory.
        profiles_dir: Path to dbt profiles directory.
        timeout_seconds: Maximum execution time.

    Returns:
        QualitySuiteResult with all check results.

    Raises:
        QualityTimeoutError: If execution exceeds timeout.
    """
    result_holder: list[dict[str, Any] | None] = [None]
    exception_holder: list[Exception | None] = [None]
    cancel_event = threading.Event()
    start_time = time.time()

    def _run_tests() -> None:
        try:
            from dbt.cli.main import dbtRunner

            dbt = dbtRunner()

            # Build CLI args
            cli_args = ["test"]
            if project_dir:
                cli_args.extend(["--project-dir", project_dir])
            if profiles_dir:
                cli_args.extend(["--profiles-dir", profiles_dir])

            # Add model selection if we have specific checks
            if suite.checks:
                # Select tests for the specific model
                cli_args.extend(["--select", suite.model_name])

            if suite.fail_fast:
                cli_args.append("--fail-fast")

            # Execute tests
            res = dbt.invoke(cli_args)

            # Parse results
            results: dict[str, Any] = {
                "success": res.success,
                "exception": str(res.exception) if res.exception else None,
                "tests": [],
            }

            if res.result is not None and hasattr(res.result, "results"):
                # res.result is RunExecutionResult for test command.
                # Use getattr with defaults for resilience against
                # dbt version differences in result object shapes.
                for test_result in res.result.results:
                    node = getattr(test_result, "node", None)
                    status = getattr(test_result, "status", None)
                    test_info = {
                        "unique_id": getattr(node, "unique_id", "") if node else "",
                        "name": getattr(node, "name", "") if node else "",
                        "status": str(status.value) if status else "error",
                        "execution_time": getattr(test_result, "execution_time", 0),
                        "failures": getattr(test_result, "failures", 0),
                        "message": getattr(test_result, "message", None),
                        "compiled_code": (getattr(node, "compiled_code", None) if node else None),
                    }
                    results["tests"].append(test_info)

            result_holder[0] = results
        except Exception as e:
            exception_holder[0] = e

    # Run tests in a thread with timeout.
    # See GX executor for rationale on daemon threads + cancel_event.
    thread = threading.Thread(target=_run_tests, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    execution_time_ms = (time.time() - start_time) * 1000

    if thread.is_alive():
        cancel_event.set()
        logger.warning(
            "dbt tests for %s timed out after %ds; daemon thread may still be running",
            suite.model_name,
            timeout_seconds,
        )
        pending_checks = [c.name for c in suite.checks]
        raise QualityTimeoutError(
            model_name=suite.model_name,
            timeout_seconds=timeout_seconds,
            pending_checks=pending_checks,
        )

    if exception_holder[0] is not None:
        raise exception_holder[0]

    dbt_results = result_holder[0]
    if dbt_results is None:
        # Should not happen, but handle gracefully
        return QualitySuiteResult(
            suite_name=f"{suite.model_name}_suite",
            model_name=suite.model_name,
            passed=True,
            checks=[],
            execution_time_ms=execution_time_ms,
        )

    # Convert dbt results to QualityCheckResults
    check_results: list[QualityCheckResult] = []
    dbt_tests = dbt_results.get("tests", [])

    # Map results to checks if we have them, otherwise create from dbt results
    if suite.checks:
        # We have predefined checks - try to match by name
        check_by_name = {c.name: c for c in suite.checks}
        for dbt_test in dbt_tests:
            test_name = dbt_test.get("name", "")
            check = check_by_name.get(test_name)
            check_result = _convert_dbt_result_to_check_result(dbt_test, check)
            check_results.append(check_result)

            # Handle fail_fast
            if suite.fail_fast and not check_result.passed:
                break
    else:
        # No predefined checks - convert all dbt test results
        for dbt_test in dbt_tests:
            check_result = _convert_dbt_result_to_check_result(dbt_test)
            check_results.append(check_result)

            if suite.fail_fast and not check_result.passed:
                break

    # Calculate pass/fail
    passed_count = sum(1 for r in check_results if r.passed)
    failed_count = len(check_results) - passed_count
    all_passed = failed_count == 0

    return QualitySuiteResult(
        suite_name=f"{suite.model_name}_suite",
        model_name=suite.model_name,
        passed=all_passed,
        checks=check_results,
        execution_time_ms=execution_time_ms,
        summary={
            "total": len(check_results),
            "passed": passed_count,
            "failed": failed_count,
            "dbt_success": dbt_results.get("success", False),
        },
    )


__all__ = [
    "run_dbt_tests_with_timeout",
]
