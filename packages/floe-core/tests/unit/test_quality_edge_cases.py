"""Unit tests for quality schema edge cases.

Tests edge cases and boundary conditions for quality schemas,
including empty table behavior, frozen model immutability,
and default value handling.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.quality_config import (
    CalculationParameters,
    Dimension,
    DimensionWeights,
    GateTier,
    QualityConfig,
    QualityGates,
    QualityThresholds,
    SeverityLevel,
)
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualityScore,
    QualitySuite,
    QualitySuiteResult,
)
from floe_core.schemas.quality_validation import GateResult, ValidationResult


class TestEmptyTableBehavior:
    """Test edge case: empty table with 0 records checked.

    This tests the requirement that not_null checks should pass
    when records_checked=0 (empty table scenario).
    """

    @pytest.mark.requirement("005B-FR-017")
    def test_quality_check_result_empty_table_zero_records(self) -> None:
        """Test QualityCheckResult with zero records checked (empty table)."""
        result = QualityCheckResult(
            check_name="customer_id_not_null",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
            records_checked=0,
            records_failed=0,
        )
        assert result.records_checked == 0
        assert result.records_failed == 0
        assert result.passed is True

    @pytest.mark.requirement("005B-FR-017")
    def test_quality_check_result_empty_table_not_null_passes(self) -> None:
        """Test not_null check passes with empty table (0 records)."""
        # Empty table: 0 records checked, 0 failed -> check passes
        result = QualityCheckResult(
            check_name="not_null_check",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
            records_checked=0,
            records_failed=0,
            execution_time_ms=0.5,
        )
        assert result.passed is True
        assert result.records_checked == 0

    @pytest.mark.requirement("005B-FR-017")
    def test_quality_suite_result_empty_table_all_checks_pass(self) -> None:
        """Test suite with empty table: all checks pass with 0 records."""
        checks = [
            QualityCheckResult(
                check_name="id_not_null",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
                records_checked=0,
                records_failed=0,
            ),
            QualityCheckResult(
                check_name="id_unique",
                passed=True,
                dimension=Dimension.CONSISTENCY,
                severity=SeverityLevel.CRITICAL,
                records_checked=0,
                records_failed=0,
            ),
        ]
        result = QualitySuiteResult(
            suite_name="empty_table_suite",
            model_name="empty_model",
            passed=True,
            checks=checks,
        )
        assert result.passed is True
        assert all(check.records_checked == 0 for check in result.checks)

    @pytest.mark.requirement("005B-FR-017")
    def test_quality_score_empty_table_scenario(self) -> None:
        """Test quality score calculation with empty table."""
        # Empty table: all checks pass, 0 records checked
        dimension_scores = {
            Dimension.COMPLETENESS: 100.0,  # not_null passes with 0 records
            Dimension.ACCURACY: 100.0,
            Dimension.VALIDITY: 100.0,
            Dimension.CONSISTENCY: 100.0,
            Dimension.TIMELINESS: 100.0,
        }
        score = QualityScore(
            overall=100.0,
            dimension_scores=dimension_scores,
            checks_passed=2,
            checks_failed=0,
            model_name="empty_model",
        )
        assert score.overall == 100.0
        assert score.checks_passed == 2
        assert score.checks_failed == 0


class TestFrozenModelImmutability:
    """Test that all quality models are frozen and immutable."""

    @pytest.mark.requirement("005B-FR-018")
    def test_dimension_weights_cannot_be_modified(self) -> None:
        """Test DimensionWeights cannot be modified after creation."""
        weights = DimensionWeights()
        with pytest.raises(ValidationError):
            weights.completeness = 0.5  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_calculation_parameters_cannot_be_modified(self) -> None:
        """Test CalculationParameters cannot be modified after creation."""
        params = CalculationParameters()
        with pytest.raises(ValidationError):
            params.baseline_score = 50  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_thresholds_cannot_be_modified(self) -> None:
        """Test QualityThresholds cannot be modified after creation."""
        thresholds = QualityThresholds()
        with pytest.raises(ValidationError):
            thresholds.min_score = 50  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_gate_tier_cannot_be_modified(self) -> None:
        """Test GateTier cannot be modified after creation."""
        tier = GateTier()
        with pytest.raises(ValidationError):
            tier.min_test_coverage = 50  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_gates_cannot_be_modified(self) -> None:
        """Test QualityGates cannot be modified after creation."""
        gates = QualityGates()
        with pytest.raises(ValidationError):
            gates.bronze = GateTier(min_test_coverage=50)  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_config_cannot_be_modified(self) -> None:
        """Test QualityConfig cannot be modified after creation."""
        config = QualityConfig(provider="test")
        with pytest.raises(ValidationError):
            config.provider = "other"  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_check_cannot_be_modified(self) -> None:
        """Test QualityCheck cannot be modified after creation."""
        check = QualityCheck(
            name="test",
            type="not_null",
            dimension=Dimension.COMPLETENESS,
        )
        with pytest.raises(ValidationError):
            check.name = "other"  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_check_result_cannot_be_modified(self) -> None:
        """Test QualityCheckResult cannot be modified after creation."""
        result = QualityCheckResult(
            check_name="test",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_suite_result_cannot_be_modified(self) -> None:
        """Test QualitySuiteResult cannot be modified after creation."""
        checks = [
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
        ]
        result = QualitySuiteResult(
            suite_name="test",
            model_name="test",
            passed=True,
            checks=checks,
        )
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_score_cannot_be_modified(self) -> None:
        """Test QualityScore cannot be modified after creation."""
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

    @pytest.mark.requirement("005B-FR-018")
    def test_quality_suite_cannot_be_modified(self) -> None:
        """Test QualitySuite cannot be modified after creation."""
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

    @pytest.mark.requirement("005B-FR-018")
    def test_validation_result_cannot_be_modified(self) -> None:
        """Test ValidationResult cannot be modified after creation."""
        result = ValidationResult(success=True)
        with pytest.raises(ValidationError):
            result.success = False  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-018")
    def test_gate_result_cannot_be_modified(self) -> None:
        """Test GateResult cannot be modified after creation."""
        result = GateResult(
            passed=True,
            tier="gold",
            coverage_actual=100.0,
            coverage_required=100.0,
        )
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]


class TestDefaultValueHandling:
    """Test that default values are correctly set and consistent."""

    @pytest.mark.requirement("005B-FR-019")
    def test_dimension_weights_defaults_sum_to_one(self) -> None:
        """Test DimensionWeights defaults sum to exactly 1.0."""
        weights = DimensionWeights()
        total = (
            weights.completeness
            + weights.accuracy
            + weights.validity
            + weights.consistency
            + weights.timeliness
        )
        assert abs(total - 1.0) < 1e-9

    @pytest.mark.requirement("005B-FR-019")
    def test_calculation_parameters_defaults_reasonable(self) -> None:
        """Test CalculationParameters defaults are reasonable."""
        params = CalculationParameters()
        # Baseline 70, can go up 30 to 100, down 50 to 20
        assert params.baseline_score == 70
        assert params.max_positive_influence == 30
        assert params.max_negative_influence == 50

    @pytest.mark.requirement("005B-FR-019")
    def test_quality_thresholds_defaults_reasonable(self) -> None:
        """Test QualityThresholds defaults are reasonable."""
        thresholds = QualityThresholds()
        # min_score < warn_score
        assert thresholds.min_score < thresholds.warn_score
        assert thresholds.min_score == 70
        assert thresholds.warn_score == 85

    @pytest.mark.requirement("005B-FR-019")
    def test_quality_gates_defaults_progressive(self) -> None:
        """Test QualityGates defaults are progressively stricter."""
        gates = QualityGates()
        # Bronze < Silver < Gold
        assert gates.bronze.min_test_coverage <= gates.silver.min_test_coverage
        assert gates.silver.min_test_coverage <= gates.gold.min_test_coverage
        assert gates.bronze.min_score <= gates.silver.min_score
        assert gates.silver.min_score <= gates.gold.min_score

    @pytest.mark.requirement("005B-FR-019")
    def test_quality_config_defaults_enabled(self) -> None:
        """Test QualityConfig is enabled by default."""
        config = QualityConfig(provider="test")
        assert config.enabled is True

    @pytest.mark.requirement("005B-FR-019")
    def test_quality_check_defaults_enabled(self) -> None:
        """Test QualityCheck is enabled by default."""
        check = QualityCheck(
            name="test",
            type="not_null",
            dimension=Dimension.COMPLETENESS,
        )
        assert check.enabled is True

    @pytest.mark.requirement("005B-FR-019")
    def test_quality_check_result_defaults_zero_records(self) -> None:
        """Test QualityCheckResult defaults to zero records."""
        result = QualityCheckResult(
            check_name="test",
            passed=True,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        assert result.records_checked == 0
        assert result.records_failed == 0
        assert result.execution_time_ms == 0.0

    @pytest.mark.requirement("005B-FR-019")
    def test_quality_suite_defaults_no_fail_fast(self) -> None:
        """Test QualitySuite defaults to not fail_fast."""
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
        assert suite.fail_fast is False


class TestExtraFieldsRejection:
    """Test that all models reject extra fields (extra='forbid')."""

    @pytest.mark.requirement("005B-FR-020")
    def test_validation_result_rejects_extra_fields(self) -> None:
        """Test ValidationResult rejects extra fields."""
        with pytest.raises(ValidationError, match="extra_field"):
            ValidationResult(  # type: ignore[call-arg, arg-type]
                success=True,
                extra_field="not_allowed",  # type: ignore[arg-type]
            )

    @pytest.mark.requirement("005B-FR-020")
    def test_gate_result_rejects_extra_fields(self) -> None:
        """Test GateResult rejects extra fields."""
        with pytest.raises(ValidationError, match="extra_field"):
            GateResult(  # type: ignore[call-arg, arg-type]
                passed=True,
                tier="gold",
                coverage_actual=100.0,
                coverage_required=100.0,
                extra_field="not_allowed",  # type: ignore[arg-type]
            )


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    @pytest.mark.requirement("005B-FR-021")
    def test_multi_check_suite_with_mixed_results(self) -> None:
        """Test suite with multiple checks, some passing, some failing."""
        checks = [
            QualityCheckResult(
                check_name="id_not_null",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
                records_checked=1000,
                records_failed=0,
            ),
            QualityCheckResult(
                check_name="id_unique",
                passed=False,
                dimension=Dimension.CONSISTENCY,
                severity=SeverityLevel.CRITICAL,
                records_checked=1000,
                records_failed=5,
            ),
            QualityCheckResult(
                check_name="email_valid",
                passed=True,
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.WARNING,
                records_checked=1000,
                records_failed=0,
            ),
        ]
        result = QualitySuiteResult(
            suite_name="customer_quality",
            model_name="dim_customers",
            passed=False,
            checks=checks,
            summary={
                "checks_passed": 2,
                "checks_failed": 1,
                "total_records": 1000,
            },
        )
        assert result.passed is False
        assert len(result.checks) == 3
        assert result.summary["checks_passed"] == 2
        assert result.summary["checks_failed"] == 1

    @pytest.mark.requirement("005B-FR-021")
    def test_quality_score_with_partial_dimension_scores(self) -> None:
        """Test quality score with varying dimension scores."""
        dimension_scores = {
            Dimension.COMPLETENESS: 100.0,  # Perfect
            Dimension.ACCURACY: 85.0,  # Good
            Dimension.VALIDITY: 70.0,  # Fair
            Dimension.CONSISTENCY: 60.0,  # Poor
            Dimension.TIMELINESS: 95.0,  # Very good
        }
        score = QualityScore(
            overall=82.0,
            dimension_scores=dimension_scores,
            checks_passed=40,
            checks_failed=10,
            dbt_tests_passed=15,
            dbt_tests_failed=3,
            model_name="fact_sales",
        )
        assert score.overall == 82.0
        assert score.dimension_scores[Dimension.COMPLETENESS] == 100.0
        assert score.dimension_scores[Dimension.CONSISTENCY] == 60.0

    @pytest.mark.requirement("005B-FR-021")
    def test_validation_result_with_many_errors_and_warnings(self) -> None:
        """Test validation result with many errors and warnings."""
        errors = [f"Error {i}" for i in range(10)]
        warnings = [f"Warning {i}" for i in range(5)]
        result = ValidationResult(
            success=False,
            errors=errors,
            warnings=warnings,
        )
        assert result.success is False
        assert len(result.errors) == 10
        assert len(result.warnings) == 5

    @pytest.mark.requirement("005B-FR-021")
    def test_gate_result_with_many_missing_tests(self) -> None:
        """Test gate result with many missing test types."""
        missing_tests = [
            "not_null",
            "unique",
            "accepted_values",
            "relationships",
            "expect_column_values_to_be_between",
        ]
        result = GateResult(
            passed=False,
            tier="gold",
            coverage_actual=50.0,
            coverage_required=100.0,
            missing_tests=missing_tests,
        )
        assert result.passed is False
        assert len(result.missing_tests) == 5
