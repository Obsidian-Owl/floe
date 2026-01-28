"""Unit tests for quality scoring module.

Tests for US5 - Quality Score Calculation:
    - T077: All checks pass = score 100
    - T078: Weighted score calculation with severities
    - T079: Influence capping (baseline + delta)
    - T080: Unified score with dbt tests and plugin checks
"""

from __future__ import annotations

import pytest

from floe_core.schemas.quality_config import (
    CalculationParameters,
    Dimension,
    QualityConfig,
    QualityThresholds,
    SeverityLevel,
)
from floe_core.schemas.quality_score import (
    QualityCheckResult,
    QualitySuiteResult,
)


class TestAllChecksPasScore100:
    """Tests for T077: All checks pass = score 100."""

    @pytest.mark.requirement("FR-015", "FR-016")
    def test_all_checks_pass_returns_100(self) -> None:
        """When all checks pass, quality score should be 100."""
        from floe_core.scoring import calculate_quality_score

        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=True,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheckResult(
                    check_name="c2",
                    passed=True,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.WARNING,
                ),
                QualityCheckResult(
                    check_name="c3",
                    passed=True,
                    dimension=Dimension.VALIDITY,
                    severity=SeverityLevel.INFO,
                ),
            ],
        )
        config = QualityConfig(provider="great_expectations")

        score = calculate_quality_score(results, config)

        assert score.overall == 100.0
        assert score.checks_passed == 3
        assert score.checks_failed == 0

    @pytest.mark.requirement("FR-015")
    def test_empty_checks_returns_100(self) -> None:
        """Empty check list should return score of 100."""
        from floe_core.scoring import calculate_quality_score

        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=True,
            checks=[],
        )
        config = QualityConfig(provider="great_expectations")

        score = calculate_quality_score(results, config)

        assert score.overall == 100.0


class TestWeightedScoreCalculation:
    """Tests for T078: Weighted score calculation with severities."""

    @pytest.mark.requirement("FR-015a", "FR-016")
    def test_dimension_weights_affect_score(self) -> None:
        """Dimension weights should affect overall score calculation."""
        from floe_core.scoring import calculate_quality_score

        # All completeness checks fail, others pass
        # With default weights: completeness=0.25
        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=False,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=False,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheckResult(
                    check_name="c2",
                    passed=True,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.WARNING,
                ),
                QualityCheckResult(
                    check_name="c3",
                    passed=True,
                    dimension=Dimension.VALIDITY,
                    severity=SeverityLevel.INFO,
                ),
            ],
        )
        config = QualityConfig(provider="great_expectations")

        score = calculate_quality_score(results, config)

        # Score should be less than 100 due to failed completeness check
        assert score.overall < 100.0
        assert score.checks_passed == 2
        assert score.checks_failed == 1

    @pytest.mark.requirement("FR-015a")
    def test_severity_weights_affect_score(self) -> None:
        """Critical failures should impact score more than info failures.

        Severity weights affect the weighted average WITHIN a dimension.
        We need multiple checks in the same dimension to see the effect.
        """
        from floe_core.scoring import calculate_quality_score

        # Critical failure + warning pass in SAME dimension
        results_critical = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=False,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=False,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,  # Weight 3.0
                ),
                QualityCheckResult(
                    check_name="c2",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,  # Weight 1.0
                ),
            ],
        )
        # Critical fail (3.0) + Warning pass (1.0) = 1.0/4.0 = 25% dimension score

        # Info failure + warning pass in SAME dimension
        results_info = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=False,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=False,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.INFO,  # Weight 0.5
                ),
                QualityCheckResult(
                    check_name="c2",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,  # Weight 1.0
                ),
            ],
        )
        # Info fail (0.5) + Warning pass (1.0) = 1.0/1.5 = 66.7% dimension score

        config = QualityConfig(provider="great_expectations")

        score_critical = calculate_quality_score(results_critical, config)
        score_info = calculate_quality_score(results_info, config)

        # Info failure should result in higher score (less weighted)
        assert score_critical.overall < score_info.overall
        # Verify completeness dimension scores differ
        assert (
            score_critical.dimension_scores[Dimension.COMPLETENESS]
            < score_info.dimension_scores[Dimension.COMPLETENESS]
        )

    @pytest.mark.requirement("FR-015a")
    def test_per_dimension_scores_calculated(self) -> None:
        """Each dimension should have its own score."""
        from floe_core.scoring import calculate_quality_score

        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=True,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                ),
                QualityCheckResult(
                    check_name="c2",
                    passed=False,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.WARNING,
                ),
            ],
        )
        config = QualityConfig(provider="great_expectations")

        score = calculate_quality_score(results, config)

        # Completeness should be 100, accuracy should be 0
        assert score.dimension_scores[Dimension.COMPLETENESS] == 100.0
        assert score.dimension_scores[Dimension.ACCURACY] == 0.0


class TestInfluenceCapping:
    """Tests for T079: Influence capping (baseline + delta)."""

    @pytest.mark.requirement("FR-016d")
    def test_max_positive_influence_capped(self) -> None:
        """Score cannot exceed baseline + max_positive_influence."""
        from floe_core.scoring import calculate_quality_score

        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=True,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
            ],
        )

        # Baseline 50, max_positive 10 -> max score capped at 60
        config = QualityConfig(
            provider="great_expectations",
            calculation=CalculationParameters(
                baseline_score=50,
                max_positive_influence=10,
            ),
        )

        score = calculate_quality_score(results, config)

        # Cap should be 60 (50 + 10), proving the cap is active
        assert score.overall <= 60.0
        assert score.overall == pytest.approx(60.0, abs=1.0)

    @pytest.mark.requirement("FR-016d")
    def test_max_negative_influence_capped(self) -> None:
        """Smaller max_negative constrains score closer to baseline.

        The proportional scaling ensures that with max_negative=5 the score
        stays much closer to baseline than with max_negative=50, proving
        the negative influence cap is active.
        """
        from floe_core.scoring import calculate_quality_score

        # All checks fail
        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=False,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=False,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheckResult(
                    check_name="c2",
                    passed=False,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheckResult(
                    check_name="c3",
                    passed=False,
                    dimension=Dimension.VALIDITY,
                    severity=SeverityLevel.CRITICAL,
                ),
            ],
        )

        # Tight cap: max_negative=5
        config_tight = QualityConfig(
            provider="great_expectations",
            calculation=CalculationParameters(
                baseline_score=70,
                max_negative_influence=5,
            ),
        )
        # Loose cap: max_negative=50
        config_loose = QualityConfig(
            provider="great_expectations",
            calculation=CalculationParameters(
                baseline_score=70,
                max_negative_influence=50,
            ),
        )

        score_tight = calculate_quality_score(results, config_tight)
        score_loose = calculate_quality_score(results, config_loose)

        # Tight cap keeps score closer to baseline
        assert score_tight.overall >= 65.0  # Floor: 70 - 5
        assert score_loose.overall >= 20.0  # Floor: 70 - 50
        # Tight cap score must be higher (closer to baseline)
        assert score_tight.overall > score_loose.overall

    @pytest.mark.requirement("FR-016d")
    def test_score_constrained_to_0_100(self) -> None:
        """Final score must be between 0 and 100."""
        from floe_core.scoring import calculate_quality_score

        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=False,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=False,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
            ],
        )

        # Even with extreme parameters
        config = QualityConfig(
            provider="great_expectations",
            calculation=CalculationParameters(
                baseline_score=10,
                max_negative_influence=100,
            ),
        )

        score = calculate_quality_score(results, config)

        assert 0.0 <= score.overall <= 100.0


class TestUnifiedScoring:
    """Tests for T080: Unified score with dbt tests and plugin checks."""

    @pytest.mark.requirement("FR-005")
    def test_dbt_tests_included_in_score(self) -> None:
        """Quality score should include dbt test results."""
        from floe_core.scoring import calculate_unified_score

        # Plugin check results
        plugin_results = QualitySuiteResult(
            suite_name="plugin_suite",
            model_name="test_model",
            passed=True,
            checks=[
                QualityCheckResult(
                    check_name="plugin_check",
                    passed=True,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.WARNING,
                ),
            ],
        )

        # dbt test results (simulated as dict)
        dbt_results = {
            "passed": 5,
            "failed": 1,
            "total": 6,
        }

        config = QualityConfig(provider="great_expectations")

        score = calculate_unified_score(
            plugin_results=plugin_results,
            dbt_results=dbt_results,
            config=config,
        )

        # Score should reflect both sources
        assert score.dbt_tests_passed == 5
        assert score.dbt_tests_failed == 1
        assert score.checks_passed == 1
        assert score.checks_failed == 0
        # Overall should be less than 100 due to dbt failure
        assert score.overall < 100.0

    @pytest.mark.requirement("FR-005")
    def test_unified_score_without_dbt(self) -> None:
        """Unified score works when dbt results are None."""
        from floe_core.scoring import calculate_unified_score

        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=True,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                ),
            ],
        )
        config = QualityConfig(provider="great_expectations")

        score = calculate_unified_score(
            plugin_results=results,
            dbt_results=None,
            config=config,
        )

        assert score.overall == 100.0
        assert score.dbt_tests_passed == 0
        assert score.dbt_tests_failed == 0


class TestScoreThresholds:
    """Tests for score threshold warnings and errors."""

    @pytest.mark.requirement("FR-030")
    def test_warn_score_check(self) -> None:
        """Score below warn_score should trigger warning."""
        from floe_core.scoring import check_score_thresholds

        config = QualityConfig(
            provider="great_expectations",
            thresholds=QualityThresholds(
                min_score=70,
                warn_score=85,
            ),
        )

        # Score 80 is below warn_score (85) but above min_score (70)
        result = check_score_thresholds(score=80.0, config=config)

        assert result["warning"] is True
        assert result["blocked"] is False

    @pytest.mark.requirement("FR-030")
    def test_min_score_blocks(self) -> None:
        """Score below min_score should block deployment."""
        from floe_core.scoring import check_score_thresholds

        config = QualityConfig(
            provider="great_expectations",
            thresholds=QualityThresholds(
                min_score=70,
                warn_score=85,
            ),
        )

        # Score 60 is below min_score (70)
        result = check_score_thresholds(score=60.0, config=config)

        assert result["blocked"] is True
        assert result["warning"] is True

    @pytest.mark.requirement("FR-030")
    def test_good_score_passes(self) -> None:
        """Score above warn_score should pass without issues."""
        from floe_core.scoring import check_score_thresholds

        config = QualityConfig(
            provider="great_expectations",
            thresholds=QualityThresholds(
                min_score=70,
                warn_score=85,
            ),
        )

        # Score 90 is above warn_score (85)
        result = check_score_thresholds(score=90.0, config=config)

        assert result["warning"] is False
        assert result["blocked"] is False
