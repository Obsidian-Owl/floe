"""Integration test for unified quality scoring (T100).

Tests end-to-end quality score calculation combining dbt tests
and plugin check results.
"""

from __future__ import annotations

import pytest
from floe_core.schemas.quality_config import (
    Dimension,
    QualityConfig,
    QualityThresholds,
    SeverityLevel,
)
from floe_core.schemas.quality_score import (
    QualityCheckResult,
    QualitySuiteResult,
)
from floe_core.scoring import (
    calculate_quality_score,
    calculate_unified_score,
    check_score_thresholds,
)


class TestEndToEndScoring:
    """Integration tests for full scoring pipeline."""

    @pytest.mark.requirement("FR-005", "FR-015")
    def test_full_scoring_pipeline(self) -> None:
        """End-to-end: checks → dimension scores → capping → unified score."""
        # Simulate realistic check results across multiple dimensions
        checks = [
            # Completeness checks (2 pass, 1 fail)
            QualityCheckResult(
                check_name="id_not_null",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            ),
            QualityCheckResult(
                check_name="name_not_null",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
            QualityCheckResult(
                check_name="email_not_null",
                passed=False,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
                error_message="15% of values are null",
            ),
            # Accuracy checks (1 pass)
            QualityCheckResult(
                check_name="age_between",
                passed=True,
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.WARNING,
            ),
            # Validity checks (1 fail)
            QualityCheckResult(
                check_name="email_regex",
                passed=False,
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.INFO,
                error_message="3% of emails invalid",
            ),
            # Consistency checks (1 pass)
            QualityCheckResult(
                check_name="id_unique",
                passed=True,
                dimension=Dimension.CONSISTENCY,
                severity=SeverityLevel.CRITICAL,
            ),
        ]

        results = QualitySuiteResult(
            suite_name="customers_quality",
            model_name="dim_customers",
            passed=False,
            checks=checks,
        )

        config = QualityConfig(
            provider="great_expectations",
            thresholds=QualityThresholds(min_score=70, warn_score=85),
        )

        # Calculate score
        score = calculate_quality_score(results, config)

        # Verify structure
        assert 0.0 <= score.overall <= 100.0
        assert score.checks_passed == 4
        assert score.checks_failed == 2
        assert score.model_name == "dim_customers"

        # Verify dimension scores make sense
        assert score.dimension_scores[Dimension.ACCURACY] == 100.0  # All passed
        assert score.dimension_scores[Dimension.CONSISTENCY] == 100.0  # All passed
        assert score.dimension_scores[Dimension.COMPLETENESS] < 100.0  # 1 failed
        assert score.dimension_scores[Dimension.VALIDITY] < 100.0  # 1 failed

        # Check thresholds
        threshold_result = check_score_thresholds(score.overall, config)
        assert isinstance(threshold_result["warning"], bool)
        assert isinstance(threshold_result["blocked"], bool)

    @pytest.mark.requirement("FR-005")
    def test_unified_score_with_dbt_results(self) -> None:
        """Unified score combines plugin checks and dbt test results."""
        plugin_results = QualitySuiteResult(
            suite_name="plugin_suite",
            model_name="dim_customers",
            passed=True,
            checks=[
                QualityCheckResult(
                    check_name="check1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                ),
                QualityCheckResult(
                    check_name="check2",
                    passed=True,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.WARNING,
                ),
            ],
        )

        dbt_results = {"passed": 10, "failed": 2, "total": 12}

        config = QualityConfig(provider="great_expectations")

        score = calculate_unified_score(
            plugin_results=plugin_results,
            dbt_results=dbt_results,
            config=config,
        )

        assert score.checks_passed == 2
        assert score.checks_failed == 0
        assert score.dbt_tests_passed == 10
        assert score.dbt_tests_failed == 2
        assert score.overall < 100.0  # dbt failures lower the score


class TestQualityJobFailure:
    """Integration test for T100a: Job failure when score < min_score."""

    @pytest.mark.requirement("FR-030")
    def test_score_below_min_blocks_deployment(self) -> None:
        """Score below min_score should signal deployment block."""
        # Failures across ALL dimensions so overall score is low
        checks = []
        for dim in Dimension:
            checks.append(
                QualityCheckResult(
                    check_name=f"fail_{dim.value}",
                    passed=False,
                    dimension=dim,
                    severity=SeverityLevel.CRITICAL,
                )
            )

        results = QualitySuiteResult(
            suite_name="test",
            model_name="model",
            passed=False,
            checks=checks,
        )

        config = QualityConfig(
            provider="great_expectations",
            thresholds=QualityThresholds(min_score=70),
        )

        score = calculate_quality_score(results, config)
        # All dimensions score 0, so raw overall = 0
        # With capping: baseline(70) - max_negative(50) = 20
        assert score.overall < 70.0

        threshold_result = check_score_thresholds(score.overall, config)
        assert threshold_result["blocked"] is True


class TestScoringPerformance:
    """Performance test for T100b: 100+ checks execute without degradation."""

    @pytest.mark.requirement("SC-004")
    def test_score_calculation_under_100ms(self) -> None:
        """Quality score calculation completes in under 100ms for 1000 checks."""
        import time

        # Create 1000 check results
        checks = []
        for i in range(1000):
            dimension = list(Dimension)[i % len(Dimension)]
            severity = list(SeverityLevel)[i % len(SeverityLevel)]
            checks.append(
                QualityCheckResult(
                    check_name=f"check_{i}",
                    passed=(i % 3 != 0),  # ~33% failure rate
                    dimension=dimension,
                    severity=severity,
                )
            )

        results = QualitySuiteResult(
            suite_name="perf_test",
            model_name="large_model",
            passed=False,
            checks=checks,
        )

        config = QualityConfig(provider="great_expectations")

        # Measure calculation time
        start = time.time()
        score = calculate_quality_score(results, config)
        elapsed_ms = (time.time() - start) * 1000

        # Should complete in under 100ms
        assert elapsed_ms < 100, f"Score calculation took {elapsed_ms:.1f}ms (>100ms)"
        assert 0.0 <= score.overall <= 100.0
        assert score.checks_passed + score.checks_failed == 1000
