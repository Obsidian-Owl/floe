"""Quality score calculator implementing the three-layer scoring model.

This module provides the core scoring functions:
- calculate_quality_score: Score from plugin check results
- calculate_unified_score: Combined score from plugin + dbt results
- check_score_thresholds: Check score against min/warn thresholds
"""

from __future__ import annotations

from typing import Any

from floe_core.schemas.quality_config import (
    Dimension,
    QualityConfig,
    SeverityLevel,
)
from floe_core.schemas.quality_score import (
    QualityCheckResult,
    QualityScore,
    QualitySuiteResult,
)


def _calculate_dimension_scores(
    checks: list[QualityCheckResult],
    severity_weights: dict[SeverityLevel, float],
) -> dict[Dimension, float]:
    """Calculate per-dimension quality scores.

    For each dimension, calculates: (weighted_passed / weighted_total) * 100

    Args:
        checks: List of check results.
        severity_weights: Mapping of severity to weight.

    Returns:
        Dict mapping each dimension to its score (0-100).
    """
    # Initialize tracking for each dimension
    dimension_weighted_passed: dict[Dimension, float] = dict.fromkeys(Dimension, 0.0)
    dimension_weighted_total: dict[Dimension, float] = dict.fromkeys(Dimension, 0.0)

    for check in checks:
        weight = severity_weights.get(check.severity, 1.0)
        dimension_weighted_total[check.dimension] += weight
        if check.passed:
            dimension_weighted_passed[check.dimension] += weight

    # Calculate scores
    scores: dict[Dimension, float] = {}
    for dimension in Dimension:
        total = dimension_weighted_total[dimension]
        if total == 0:
            # No checks for this dimension - consider it perfect
            scores[dimension] = 100.0
        else:
            scores[dimension] = (dimension_weighted_passed[dimension] / total) * 100.0

    return scores


def _calculate_weighted_overall(
    dimension_scores: dict[Dimension, float],
    dimension_weights: dict[str, float],
) -> float:
    """Calculate overall score from dimension scores.

    Args:
        dimension_scores: Per-dimension scores (0-100).
        dimension_weights: Weights for each dimension (sum to 1.0).

    Returns:
        Weighted overall score (0-100).
    """
    total = 0.0
    for dimension in Dimension:
        weight = dimension_weights.get(dimension.value, 0.2)  # Default equal weight
        total += dimension_scores[dimension] * weight
    return total


def _apply_influence_capping(
    raw_score: float,
    baseline: int,
    max_positive: int,
    max_negative: int,
) -> float:
    """Apply influence capping to constrain score changes.

    The final score is constrained to:
    - Not exceed baseline + max_positive
    - Not fall below baseline - max_negative
    - Always be between 0 and 100

    Args:
        raw_score: The uncapped score.
        baseline: Starting baseline score.
        max_positive: Maximum positive influence.
        max_negative: Maximum negative influence.

    Returns:
        Capped score between 0 and 100.
    """
    # Calculate delta from baseline based on raw score
    # If raw_score is 100, delta should be +max_positive
    # If raw_score is 0, delta should be -max_negative

    if raw_score >= baseline:
        # Positive influence - scale to max_positive
        delta_ratio = (raw_score - baseline) / (100 - baseline) if baseline < 100 else 0
        delta = delta_ratio * max_positive
    else:
        # Negative influence - scale to max_negative
        delta_ratio = (baseline - raw_score) / baseline if baseline > 0 else 0
        delta = -delta_ratio * max_negative

    # Apply capping
    capped_score = baseline + delta
    capped_score = max(baseline - max_negative, capped_score)
    capped_score = min(baseline + max_positive, capped_score)

    # Constrain to 0-100
    return max(0.0, min(100.0, capped_score))


def calculate_quality_score(
    results: QualitySuiteResult,
    config: QualityConfig,
) -> QualityScore:
    """Calculate quality score from check results.

    Implements the three-layer scoring model:
    1. Layer 1 - Dimension weights
    2. Layer 2 - Severity weights
    3. Layer 3 - Calculation parameters (baseline, capping)

    Args:
        results: Quality suite execution results.
        config: Quality configuration with scoring parameters.

    Returns:
        QualityScore with overall and per-dimension scores.
    """
    checks = list(results.checks)

    # Handle empty checks case
    if not checks:
        return QualityScore(
            overall=100.0,
            dimension_scores=dict.fromkeys(Dimension, 100.0),
            checks_passed=0,
            checks_failed=0,
            model_name=results.model_name,
        )

    # Count passed/failed
    passed = sum(1 for c in checks if c.passed)
    failed = len(checks) - passed

    # Get severity weights
    severity_weights = config.calculation.severity_weights

    # Calculate per-dimension scores (Layer 1 & 2)
    dimension_scores = _calculate_dimension_scores(checks, severity_weights)

    # Calculate weighted overall from dimension scores
    dimension_weights = {
        "completeness": config.dimension_weights.completeness,
        "accuracy": config.dimension_weights.accuracy,
        "validity": config.dimension_weights.validity,
        "consistency": config.dimension_weights.consistency,
        "timeliness": config.dimension_weights.timeliness,
    }
    raw_overall = _calculate_weighted_overall(dimension_scores, dimension_weights)

    # Apply influence capping (Layer 3)
    capped_overall = _apply_influence_capping(
        raw_score=raw_overall,
        baseline=config.calculation.baseline_score,
        max_positive=config.calculation.max_positive_influence,
        max_negative=config.calculation.max_negative_influence,
    )

    return QualityScore(
        overall=capped_overall,
        dimension_scores=dimension_scores,
        checks_passed=passed,
        checks_failed=failed,
        model_name=results.model_name,
    )


def calculate_unified_score(
    plugin_results: QualitySuiteResult,
    dbt_results: dict[str, Any] | None,
    config: QualityConfig,
) -> QualityScore:
    """Calculate unified quality score from plugin checks and dbt tests.

    Combines results from QualityPlugin.run_checks() and dbt test outcomes
    into a single quality score.

    Args:
        plugin_results: Results from plugin quality checks.
        dbt_results: Optional dict with 'passed', 'failed', 'total' keys.
        config: Quality configuration with scoring parameters.

    Returns:
        QualityScore with combined results.
    """
    # Start with plugin results score
    plugin_score = calculate_quality_score(plugin_results, config)

    # Extract dbt test counts
    dbt_passed = 0
    dbt_failed = 0

    if dbt_results:
        dbt_passed = dbt_results.get("passed", 0)
        dbt_failed = dbt_results.get("failed", 0)

    # If we have dbt results, factor them into the overall score
    if dbt_results and (dbt_passed + dbt_failed) > 0:
        # Calculate combined pass rate
        total_passed = plugin_score.checks_passed + dbt_passed
        total_failed = plugin_score.checks_failed + dbt_failed
        total_checks = total_passed + total_failed

        if total_checks > 0:
            # Simple weighted combination - dbt tests are treated as WARNING severity
            combined_pass_rate = (total_passed / total_checks) * 100

            # Apply capping
            capped_overall = _apply_influence_capping(
                raw_score=combined_pass_rate,
                baseline=config.calculation.baseline_score,
                max_positive=config.calculation.max_positive_influence,
                max_negative=config.calculation.max_negative_influence,
            )
        else:
            capped_overall = 100.0
    else:
        capped_overall = plugin_score.overall

    return QualityScore(
        overall=capped_overall,
        dimension_scores=plugin_score.dimension_scores,
        checks_passed=plugin_score.checks_passed,
        checks_failed=plugin_score.checks_failed,
        dbt_tests_passed=dbt_passed,
        dbt_tests_failed=dbt_failed,
        model_name=plugin_results.model_name,
    )


def check_score_thresholds(
    score: float,
    config: QualityConfig,
) -> dict[str, bool]:
    """Check score against configured thresholds.

    Args:
        score: The quality score to check.
        config: Configuration with threshold values.

    Returns:
        Dict with 'warning' (bool) and 'blocked' (bool) flags.
    """
    min_score = config.thresholds.min_score
    warn_score = config.thresholds.warn_score

    return {
        "warning": score < warn_score,
        "blocked": score < min_score,
    }


__all__ = [
    "calculate_quality_score",
    "calculate_unified_score",
    "check_score_thresholds",
]
