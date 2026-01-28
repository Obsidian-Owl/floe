"""Unit tests for quality score and check result models.

Tests the Pydantic models in quality_score.py for validation,
serialization, and edge cases. Covers quality checks, check results,
suite results, and unified quality scores.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualityScore,
    QualitySuite,
    QualitySuiteResult,
)


class TestQualityCheck:
    """Test QualityCheck Pydantic model."""

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_minimal(self) -> None:
        """Test QualityCheck with minimal required fields."""
        check = QualityCheck(
            name="customer_id_not_null",
            type="not_null",
            dimension=Dimension.COMPLETENESS,
        )
        assert check.name == "customer_id_not_null"
        assert check.type == "not_null"
        assert check.column is None
        assert check.dimension == Dimension.COMPLETENESS
        assert check.severity == SeverityLevel.WARNING
        assert check.custom_weight is None
        assert check.parameters == {}
        assert check.enabled is True

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_full(self) -> None:
        """Test QualityCheck with all fields specified."""
        check = QualityCheck(
            name="customer_id_not_null",
            type="not_null",
            column="customer_id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
            custom_weight=2.5,
            parameters={"threshold": 0.95},
            enabled=False,
        )
        assert check.name == "customer_id_not_null"
        assert check.type == "not_null"
        assert check.column == "customer_id"
        assert check.dimension == Dimension.COMPLETENESS
        assert check.severity == SeverityLevel.CRITICAL
        assert check.custom_weight == 2.5
        assert check.parameters == {"threshold": 0.95}
        assert check.enabled is False

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_name_required(self) -> None:
        """Test QualityCheck requires name."""
        with pytest.raises(ValidationError, match="name"):
            QualityCheck(  # type: ignore[call-arg]
                type="not_null",
                dimension=Dimension.COMPLETENESS,
            )

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_name_empty_invalid(self) -> None:
        """Test QualityCheck rejects empty name."""
        with pytest.raises(ValidationError, match="name"):
            QualityCheck(
                name="",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
            )

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_type_required(self) -> None:
        """Test QualityCheck requires type."""
        with pytest.raises(ValidationError, match="type"):
            QualityCheck(  # type: ignore[call-arg]
                name="test",
                dimension=Dimension.COMPLETENESS,
            )

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_type_empty_invalid(self) -> None:
        """Test QualityCheck rejects empty type."""
        with pytest.raises(ValidationError, match="type"):
            QualityCheck(
                name="test",
                type="",
                dimension=Dimension.COMPLETENESS,
            )

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_dimension_required(self) -> None:
        """Test QualityCheck requires dimension."""
        with pytest.raises(ValidationError, match="dimension"):
            QualityCheck(  # type: ignore[call-arg]
                name="test",
                type="not_null",
            )

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_custom_weight_boundary(self) -> None:
        """Test QualityCheck custom_weight boundaries."""
        check_min = QualityCheck(
            name="test",
            type="not_null",
            dimension=Dimension.COMPLETENESS,
            custom_weight=0.1,
        )
        assert check_min.custom_weight == 0.1

        check_max = QualityCheck(
            name="test",
            type="not_null",
            dimension=Dimension.COMPLETENESS,
            custom_weight=10.0,
        )
        assert check_max.custom_weight == 10.0

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_custom_weight_invalid(self) -> None:
        """Test QualityCheck rejects invalid custom_weight."""
        with pytest.raises(ValidationError, match="custom_weight"):
            QualityCheck(
                name="test",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
                custom_weight=0.05,  # Below 0.1
            )

        with pytest.raises(ValidationError, match="custom_weight"):
            QualityCheck(
                name="test",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
                custom_weight=10.5,  # Above 10.0
            )

    @pytest.mark.requirement("005B-FR-010")
    def test_quality_check_frozen(self) -> None:
        """Test QualityCheck is immutable."""
        check = QualityCheck(
            name="test",
            type="not_null",
            dimension=Dimension.COMPLETENESS,
        )
        with pytest.raises(ValidationError):
            check.name = "other"  # type: ignore[misc]


class TestQualityCheckResult:
    """Test QualityCheckResult Pydantic model."""

    @pytest.mark.requirement("005B-FR-011")
    def test_quality_check_result_minimal(self) -> None:
        """Test QualityCheckResult with minimal required fields."""
        result = QualityCheckResult(
            check_name="customer_id_not_null",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
        )
        assert result.check_name == "customer_id_not_null"
        assert result.passed is True
        assert result.dimension == Dimension.COMPLETENESS
        assert result.severity == SeverityLevel.CRITICAL
        assert result.records_checked == 0
        assert result.records_failed == 0
        assert result.execution_time_ms == 0.0
        assert result.details == {}
        assert result.error_message is None

    @pytest.mark.requirement("005B-FR-011")
    def test_quality_check_result_full(self) -> None:
        """Test QualityCheckResult with all fields specified."""
        result = QualityCheckResult(
            check_name="customer_id_not_null",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
            records_checked=1000,
            records_failed=0,
            execution_time_ms=45.2,
            details={"pass_rate": 1.0},
            error_message=None,
        )
        assert result.check_name == "customer_id_not_null"
        assert result.passed is True
        assert result.records_checked == 1000
        assert result.records_failed == 0
        assert result.execution_time_ms == pytest.approx(45.2)
        assert result.details == {"pass_rate": 1.0}

    @pytest.mark.requirement("005B-FR-011")
    def test_quality_check_result_failed_with_error(self) -> None:
        """Test QualityCheckResult with failure and error message."""
        result = QualityCheckResult(
            check_name="customer_id_not_null",
            passed=False,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
            records_checked=1000,
            records_failed=50,
            error_message="50 null values found",
        )
        assert result.passed is False
        assert result.records_failed == 50
        assert result.error_message == "50 null values found"

    @pytest.mark.requirement("005B-FR-011")
    def test_quality_check_result_records_checked_boundary(self) -> None:
        """Test QualityCheckResult records_checked boundaries."""
        result_zero = QualityCheckResult(
            check_name="test",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
            records_checked=0,
        )
        assert result_zero.records_checked == 0

    @pytest.mark.requirement("005B-FR-011")
    def test_quality_check_result_records_checked_invalid(self) -> None:
        """Test QualityCheckResult rejects negative records_checked."""
        with pytest.raises(ValidationError, match="records_checked"):
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
                records_checked=-1,
            )

    @pytest.mark.requirement("005B-FR-011")
    def test_quality_check_result_execution_time_invalid(self) -> None:
        """Test QualityCheckResult rejects negative execution_time_ms."""
        with pytest.raises(ValidationError, match="execution_time_ms"):
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
                execution_time_ms=-1.0,
            )

    @pytest.mark.requirement("005B-FR-011")
    def test_quality_check_result_frozen(self) -> None:
        """Test QualityCheckResult is immutable."""
        result = QualityCheckResult(
            check_name="test",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]


class TestQualitySuiteResult:
    """Test QualitySuiteResult Pydantic model."""

    @pytest.mark.requirement("005B-FR-012")
    def test_quality_suite_result_minimal(self) -> None:
        """Test QualitySuiteResult with minimal required fields."""
        checks = [
            QualityCheckResult(
                check_name="id_not_null",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            ),
        ]
        result = QualitySuiteResult(
            suite_name="dim_customers_quality",
            model_name="dim_customers",
            passed=True,
            checks=checks,
        )
        assert result.suite_name == "dim_customers_quality"
        assert result.model_name == "dim_customers"
        assert result.passed is True
        assert len(result.checks) == 1
        assert result.execution_time_ms == 0.0
        assert result.summary == {}
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.requirement("005B-FR-012")
    def test_quality_suite_result_full(self) -> None:
        """Test QualitySuiteResult with all fields specified."""
        checks = [
            QualityCheckResult(
                check_name="id_not_null",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
                records_checked=1000,
            ),
            QualityCheckResult(
                check_name="id_unique",
                passed=True,
                dimension=Dimension.CONSISTENCY,
                severity=SeverityLevel.CRITICAL,
                records_checked=1000,
            ),
        ]
        summary = {"checks_passed": 2, "checks_failed": 0}
        result = QualitySuiteResult(
            suite_name="dim_customers_quality",
            model_name="dim_customers",
            passed=True,
            checks=checks,
            execution_time_ms=250.5,
            summary=summary,
        )
        assert result.suite_name == "dim_customers_quality"
        assert result.model_name == "dim_customers"
        assert result.passed is True
        assert len(result.checks) == 2
        assert result.execution_time_ms == pytest.approx(250.5)
        assert result.summary == summary

    @pytest.mark.requirement("005B-FR-012")
    def test_quality_suite_result_failed_suite(self) -> None:
        """Test QualitySuiteResult with failed checks."""
        checks = [
            QualityCheckResult(
                check_name="id_not_null",
                passed=False,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
                records_checked=1000,
                records_failed=50,
            ),
        ]
        result = QualitySuiteResult(
            suite_name="dim_customers_quality",
            model_name="dim_customers",
            passed=False,
            checks=checks,
        )
        assert result.passed is False
        assert result.checks[0].passed is False

    @pytest.mark.requirement("005B-FR-012")
    def test_quality_suite_result_timestamp_auto_generated(self) -> None:
        """Test QualitySuiteResult auto-generates UTC timestamp."""
        checks = [
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
        ]
        result = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=True,
            checks=checks,
        )
        assert result.timestamp is not None
        assert result.timestamp.tzinfo == timezone.utc

    @pytest.mark.requirement("005B-FR-012")
    def test_quality_suite_result_frozen(self) -> None:
        """Test QualitySuiteResult is immutable."""
        checks = [
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
        ]
        result = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=True,
            checks=checks,
        )
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]


class TestQualityScore:
    """Test QualityScore Pydantic model."""

    @pytest.mark.requirement("005B-FR-013")
    def test_quality_score_minimal(self) -> None:
        """Test QualityScore with minimal required fields."""
        dimension_scores = {
            Dimension.COMPLETENESS: 100.0,
            Dimension.ACCURACY: 85.0,
            Dimension.VALIDITY: 90.0,
            Dimension.CONSISTENCY: 75.0,
            Dimension.TIMELINESS: 80.0,
        }
        score = QualityScore(
            overall=87.5,
            dimension_scores=dimension_scores,
            model_name="dim_customers",
        )
        assert score.overall == 87.5
        assert score.dimension_scores == dimension_scores
        assert score.model_name == "dim_customers"
        assert score.checks_passed == 0
        assert score.checks_failed == 0
        assert score.dbt_tests_passed == 0
        assert score.dbt_tests_failed == 0
        assert isinstance(score.timestamp, datetime)

    @pytest.mark.requirement("005B-FR-013")
    def test_quality_score_full(self) -> None:
        """Test QualityScore with all fields specified."""
        dimension_scores = {
            Dimension.COMPLETENESS: 100.0,
            Dimension.ACCURACY: 85.0,
            Dimension.VALIDITY: 90.0,
            Dimension.CONSISTENCY: 75.0,
            Dimension.TIMELINESS: 80.0,
        }
        score = QualityScore(
            overall=87.5,
            dimension_scores=dimension_scores,
            checks_passed=45,
            checks_failed=5,
            dbt_tests_passed=20,
            dbt_tests_failed=2,
            model_name="dim_customers",
        )
        assert score.overall == 87.5
        assert score.checks_passed == 45
        assert score.checks_failed == 5
        assert score.dbt_tests_passed == 20
        assert score.dbt_tests_failed == 2

    @pytest.mark.requirement("005B-FR-013")
    def test_quality_score_overall_boundary(self) -> None:
        """Test QualityScore overall score boundaries."""
        dimension_scores = {
            Dimension.COMPLETENESS: 0.0,
            Dimension.ACCURACY: 0.0,
            Dimension.VALIDITY: 0.0,
            Dimension.CONSISTENCY: 0.0,
            Dimension.TIMELINESS: 0.0,
        }
        score_min = QualityScore(
            overall=0.0,
            dimension_scores=dimension_scores,
            model_name="test",
        )
        assert score_min.overall == 0.0

        dimension_scores_max = {
            Dimension.COMPLETENESS: 100.0,
            Dimension.ACCURACY: 100.0,
            Dimension.VALIDITY: 100.0,
            Dimension.CONSISTENCY: 100.0,
            Dimension.TIMELINESS: 100.0,
        }
        score_max = QualityScore(
            overall=100.0,
            dimension_scores=dimension_scores_max,
            model_name="test",
        )
        assert score_max.overall == 100.0

    @pytest.mark.requirement("005B-FR-013")
    def test_quality_score_overall_invalid(self) -> None:
        """Test QualityScore rejects invalid overall score."""
        dimension_scores = {
            Dimension.COMPLETENESS: 100.0,
            Dimension.ACCURACY: 100.0,
            Dimension.VALIDITY: 100.0,
            Dimension.CONSISTENCY: 100.0,
            Dimension.TIMELINESS: 100.0,
        }
        with pytest.raises(ValidationError, match="overall"):
            QualityScore(
                overall=-1.0,
                dimension_scores=dimension_scores,
                model_name="test",
            )

        with pytest.raises(ValidationError, match="overall"):
            QualityScore(
                overall=101.0,
                dimension_scores=dimension_scores,
                model_name="test",
            )

    @pytest.mark.requirement("005B-FR-013")
    def test_quality_score_dimension_scores_boundary(self) -> None:
        """Test QualityScore dimension scores boundaries."""
        dimension_scores = {
            Dimension.COMPLETENESS: 0.0,
            Dimension.ACCURACY: 100.0,
            Dimension.VALIDITY: 50.0,
            Dimension.CONSISTENCY: 75.5,
            Dimension.TIMELINESS: 25.25,
        }
        score = QualityScore(
            overall=50.0,
            dimension_scores=dimension_scores,
            model_name="test",
        )
        assert score.dimension_scores[Dimension.COMPLETENESS] == 0.0
        assert score.dimension_scores[Dimension.ACCURACY] == 100.0

    @pytest.mark.requirement("005B-FR-013")
    def test_quality_score_frozen(self) -> None:
        """Test QualityScore is immutable."""
        dimension_scores = {
            Dimension.COMPLETENESS: 100.0,
            Dimension.ACCURACY: 100.0,
            Dimension.VALIDITY: 100.0,
            Dimension.CONSISTENCY: 100.0,
            Dimension.TIMELINESS: 100.0,
        }
        score = QualityScore(
            overall=100.0,
            dimension_scores=dimension_scores,
            model_name="test",
        )
        with pytest.raises(ValidationError):
            score.overall = 50.0  # type: ignore[misc]


class TestQualitySuite:
    """Test QualitySuite Pydantic model."""

    @pytest.mark.requirement("005B-FR-014")
    def test_quality_suite_minimal(self) -> None:
        """Test QualitySuite with minimal required fields."""
        checks = [
            QualityCheck(
                name="id_not_null",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
            ),
        ]
        suite = QualitySuite(
            model_name="dim_customers",
            checks=checks,
        )
        assert suite.model_name == "dim_customers"
        assert len(suite.checks) == 1
        assert suite.timeout_seconds == 300
        assert suite.fail_fast is False

    @pytest.mark.requirement("005B-FR-014")
    def test_quality_suite_full(self) -> None:
        """Test QualitySuite with all fields specified."""
        checks = [
            QualityCheck(
                name="id_not_null",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
            ),
            QualityCheck(
                name="id_unique",
                type="unique",
                dimension=Dimension.CONSISTENCY,
            ),
        ]
        suite = QualitySuite(
            model_name="dim_customers",
            checks=checks,
            timeout_seconds=600,
            fail_fast=True,
        )
        assert suite.model_name == "dim_customers"
        assert len(suite.checks) == 2
        assert suite.timeout_seconds == 600
        assert suite.fail_fast is True

    @pytest.mark.requirement("005B-FR-014")
    def test_quality_suite_timeout_boundary(self) -> None:
        """Test QualitySuite timeout boundaries."""
        checks = [
            QualityCheck(
                name="test",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
            ),
        ]
        suite_min = QualitySuite(
            model_name="test",
            checks=checks,
            timeout_seconds=1,
        )
        assert suite_min.timeout_seconds == 1

        suite_max = QualitySuite(
            model_name="test",
            checks=checks,
            timeout_seconds=3600,
        )
        assert suite_max.timeout_seconds == 3600

    @pytest.mark.requirement("005B-FR-014")
    def test_quality_suite_timeout_invalid(self) -> None:
        """Test QualitySuite rejects invalid timeout."""
        checks = [
            QualityCheck(
                name="test",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
            ),
        ]
        with pytest.raises(ValidationError, match="timeout_seconds"):
            QualitySuite(
                model_name="test",
                checks=checks,
                timeout_seconds=0,
            )

        with pytest.raises(ValidationError, match="timeout_seconds"):
            QualitySuite(
                model_name="test",
                checks=checks,
                timeout_seconds=3601,
            )

    @pytest.mark.requirement("005B-FR-014")
    def test_quality_suite_frozen(self) -> None:
        """Test QualitySuite is immutable."""
        checks = [
            QualityCheck(
                name="test",
                type="not_null",
                dimension=Dimension.COMPLETENESS,
            ),
        ]
        suite = QualitySuite(
            model_name="test",
            checks=checks,
        )
        with pytest.raises(ValidationError):
            suite.model_name = "other"  # type: ignore[misc]
