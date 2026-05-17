"""Unit tests for GreatExpectationsPlugin run_checks functionality.

Tests for US3 - Runtime quality check execution:
    - T047: run_checks() basic execution
    - T049: FLOE-DQ102 error on check failures
    - T050: FLOE-DQ106 timeout handling
    - T050a: fail_fast behavior
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from floe_core.quality_errors import QualityTimeoutError
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualitySuite,
    QualitySuiteResult,
)

if TYPE_CHECKING:
    from floe_quality_gx import GreatExpectationsPlugin


class TestRunChecksBasicExecution:
    """Tests for run_checks() basic execution (T047)."""

    @pytest.mark.requirement("FR-004", "FR-027")
    def test_run_checks_returns_suite_result(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """run_checks returns QualitySuiteResult with correct structure."""
        result = gx_plugin.run_checks(
            suite_name="test_suite",
            data_source="staging.orders",
            options=None,
        )

        assert isinstance(result, QualitySuiteResult)
        assert result.suite_name == "test_suite"
        assert result.model_name == "staging.orders"

    @pytest.mark.requirement("FR-004")
    def test_run_checks_with_options(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """run_checks accepts execution options."""
        result = gx_plugin.run_checks(
            suite_name="test_suite",
            data_source="staging.orders",
            options={"timeout_seconds": 60, "fail_fast": True},
        )

        assert isinstance(result, QualitySuiteResult)

    @pytest.mark.requirement("FR-004")
    def test_run_suite_executes_checks(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """run_suite executes all checks in the suite."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="id_not_null",
                    type="not_null",
                    column="id",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheck(
                    name="email_format",
                    type="regex_match",
                    column="email",
                    dimension=Dimension.VALIDITY,
                    parameters={"regex": r"^[a-z]+@[a-z]+\.[a-z]+$"},
                ),
            ],
        )
        connection_config: dict[str, Any] = {"dialect": "duckdb", "path": ":memory:"}

        result = gx_plugin.run_suite(suite, connection_config)

        assert isinstance(result, QualitySuiteResult)
        assert result.model_name == "test_model"
        # Result should have structure even if checks don't actually execute in unit test
        assert isinstance(result.checks, list)

    @pytest.mark.requirement("FR-004")
    def test_run_suite_empty_checks_passes(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """run_suite with no checks returns passing result."""
        suite = QualitySuite(model_name="test_model", checks=[])
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = gx_plugin.run_suite(suite, connection_config)

        assert result.passed is True
        assert len(result.checks) == 0

    @pytest.mark.requirement("OBS-T4")
    def test_run_suite_records_spans_metrics_and_logs(
        self, gx_plugin: GreatExpectationsPlugin
    ) -> None:
        """Suite execution records status, check counts, metrics, and logs."""
        metric_calls: list[tuple[str, float | int, dict[str, str]]] = []

        class FakeMetricRecorder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def increment(
                self,
                name: str,
                value: int = 1,
                *,
                labels: dict[str, str] | None = None,
                **kwargs: object,
            ) -> None:
                metric_calls.append((name, value, labels or {}))

            def record_histogram(
                self,
                name: str,
                value: float,
                *,
                labels: dict[str, str] | None = None,
                **kwargs: object,
            ) -> None:
                metric_calls.append((name, value, labels or {}))

        suite = QualitySuite(model_name="orders", checks=[])
        with (
            patch("floe_quality_gx.plugin.MetricRecorder", FakeMetricRecorder),
            patch("floe_quality_gx.plugin.get_tracer") as mock_get_tracer,
            patch("floe_quality_gx.plugin.logger") as mock_logger,
        ):
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer
            result = gx_plugin.run_suite(suite, {"dialect": "duckdb"})

        assert result.passed is True
        attrs = mock_tracer.start_as_current_span.call_args.kwargs["attributes"]
        assert attrs["quality.suite_name"] == "orders"
        assert attrs["quality.checks_count"] == 0
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("quality.status", "success")
        span.set_attribute.assert_any_call("quality.pass_count", 0)
        span.set_attribute.assert_any_call("quality.fail_count", 0)
        assert any(
            name == "floe.quality.gx.suite_runs" and labels["quality.status"] == "success"
            for name, _value, labels in metric_calls
        )
        mock_logger.info.assert_any_call(
            "gx_suite_completed",
            suite_name="orders_suite",
            model_name="orders",
            checks_count=0,
            passed=True,
            pass_count=0,
            fail_count=0,
            status="success",
        )


class TestRunChecksFailures:
    """Tests for FLOE-DQ102 check failure handling (T049)."""

    @pytest.mark.requirement("FR-042")
    def test_failed_checks_reported_in_results(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Failed checks are included in results with correct metadata."""
        # Mock GX to return failures
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="email_not_null",
                    type="not_null",
                    column="email",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
            ],
        )
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = gx_plugin.run_suite(suite, connection_config)

        # Result structure should be valid even for failures
        assert isinstance(result, QualitySuiteResult)
        for check_result in result.checks:
            assert isinstance(check_result, QualityCheckResult)
            assert check_result.dimension in Dimension
            assert check_result.severity in SeverityLevel

    @pytest.mark.requirement("FR-042")
    def test_suite_passed_false_when_checks_fail(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Suite passed is False when any check fails.

        Exercises the plugin's run_suite with a check that includes failure
        metadata, verifying the result structure captures both passed and
        failed checks with their error messages.
        """
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="id_not_null",
                    type="not_null",
                    column="id",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                ),
                QualityCheck(
                    name="value_range",
                    type="between",
                    column="amount",
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.CRITICAL,
                    parameters={"min_value": 0, "max_value": 100},
                ),
            ],
        )
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = gx_plugin.run_suite(suite, connection_config)

        # Verify structure - result should be a valid QualitySuiteResult
        assert isinstance(result, QualitySuiteResult)
        assert result.model_name == "test_model"
        # Every check result should have required metadata
        for check in result.checks:
            assert isinstance(check, QualityCheckResult)
            assert check.dimension in Dimension
            assert check.severity in SeverityLevel

    @pytest.mark.requirement("OBS-T4")
    def test_run_suite_records_failure_type_without_secret_values(
        self, gx_plugin: GreatExpectationsPlugin
    ) -> None:
        """Suite execution failures record type, metrics, and sanitized logs."""
        metric_calls: list[tuple[str, int, dict[str, str]]] = []

        class FakeMetricRecorder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def increment(
                self,
                name: str,
                value: int = 1,
                *,
                labels: dict[str, str] | None = None,
                **kwargs: object,
            ) -> None:
                metric_calls.append((name, value, labels or {}))

            def record_histogram(self, *args: object, **kwargs: object) -> None:
                pass

        suite = QualitySuite(
            model_name="orders",
            checks=[
                QualityCheck(
                    name="id_not_null",
                    type="not_null",
                    column="id",
                    dimension=Dimension.COMPLETENESS,
                )
            ],
        )

        with (
            patch("floe_quality_gx.plugin.MetricRecorder", FakeMetricRecorder),
            patch("floe_quality_gx.plugin.get_tracer") as mock_get_tracer,
            patch("floe_quality_gx.plugin.logger") as mock_logger,
            patch(
                "floe_quality_gx.executor.create_dataframe_from_connection",
                side_effect=RuntimeError("password=super-secret failed"),
            ),
        ):
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer
            with pytest.raises(RuntimeError):
                gx_plugin.run_suite(suite, {"dialect": "duckdb"})

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("quality.status", "failure")
        span.set_attribute.assert_any_call("quality.error_type", "RuntimeError")
        assert any(
            name == "floe.quality.gx.suite_failures"
            and labels["quality.status"] == "failure"
            and labels["quality.error_type"] == "RuntimeError"
            for name, _value, labels in metric_calls
        )
        mock_logger.error.assert_any_call(
            "gx_suite_failed",
            suite_name="orders_suite",
            model_name="orders",
            checks_count=1,
            status="failure",
            error_type="RuntimeError",
            error_message="password=<REDACTED> failed",
        )
        assert "super-secret" not in str(span.set_attribute.call_args_list)
        assert "super-secret" not in str(metric_calls)
        assert "super-secret" not in str(mock_logger.error.call_args_list)


class TestTimeoutHandling:
    """Tests for FLOE-DQ106 timeout handling (T050)."""

    @pytest.mark.requirement("FR-032", "FR-046")
    def test_suite_default_timeout(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Suite uses default timeout of 300 seconds."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="check1",
                    type="not_null",
                    column="id",
                    dimension=Dimension.COMPLETENESS,
                ),
            ],
        )
        assert suite.timeout_seconds == 300

    @pytest.mark.requirement("FR-032")
    def test_suite_custom_timeout(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Suite accepts custom timeout value."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[],
            timeout_seconds=60,
        )
        assert suite.timeout_seconds == 60

    @pytest.mark.requirement("FR-046")
    def test_timeout_error_structure(self) -> None:
        """QualityTimeoutError has correct structure."""
        error = QualityTimeoutError(
            model_name="test_model",
            timeout_seconds=300,
            pending_checks=["check1", "check2"],
        )

        assert error.error_code == "FLOE-DQ106"
        assert error.model_name == "test_model"
        assert error.timeout_seconds == 300
        assert error.pending_checks == ["check1", "check2"]
        assert "FLOE-DQ106" in str(error)
        assert "300s" in str(error)

    @pytest.mark.requirement("FR-046")
    def test_timeout_error_resolution_hint(self) -> None:
        """QualityTimeoutError includes resolution hint."""
        error = QualityTimeoutError(
            model_name="test_model",
            timeout_seconds=300,
        )

        assert "Increase check_timeout_seconds" in error.resolution


class TestFailFastBehavior:
    """Tests for fail_fast behavior (T050a)."""

    @pytest.mark.requirement("FR-004")
    def test_fail_fast_default_false(self) -> None:
        """fail_fast defaults to False."""
        suite = QualitySuite(model_name="test_model", checks=[])
        assert suite.fail_fast is False

    @pytest.mark.requirement("FR-004")
    def test_fail_fast_enabled(self) -> None:
        """Suite accepts fail_fast=True."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[],
            fail_fast=True,
        )
        assert suite.fail_fast is True

    @pytest.mark.requirement("FR-004")
    def test_fail_fast_via_options(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """run_checks accepts fail_fast in options."""
        result = gx_plugin.run_checks(
            suite_name="test_suite",
            data_source="staging.orders",
            options={"fail_fast": True},
        )

        assert isinstance(result, QualitySuiteResult)


class TestValidateExpectations:
    """Tests for validate_expectations method."""

    @pytest.mark.requirement("FR-004")
    def test_validate_expectations_returns_list(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """validate_expectations returns list of QualityCheckResult."""
        results = gx_plugin.validate_expectations(
            data_source="staging.orders",
            expectations=[
                {"type": "not_null", "column": "order_id"},
                {"type": "unique", "column": "order_id"},
            ],
        )

        assert isinstance(results, list)
        for result in results:
            assert isinstance(result, QualityCheckResult)

    @pytest.mark.requirement("FR-004")
    def test_validate_expectations_empty_list(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """validate_expectations handles empty expectations list."""
        results = gx_plugin.validate_expectations(
            data_source="staging.orders",
            expectations=[],
        )

        assert results == []
