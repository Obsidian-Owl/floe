"""Unit tests for quality check implementation.

Tests quality expectation validation against configurable thresholds.
Quality score is calculated as weighted average of expectation results.

Tasks: T046 (Epic 3D)
Requirements: FR-015, FR-016, FR-017, FR-018
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.checks.quality import QualityCheck
from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import (
    CheckStatus,
    ViolationSeverity,
    ViolationType,
)


class MockQualityPlugin:
    """Mock quality plugin that returns controllable results.

    Simulates a real quality plugin that would analyze data against
    expectations (completeness, uniqueness, etc.) and return scores.
    """

    def __init__(self, results: dict[str, float]) -> None:
        """Initialize with preset results.

        Args:
            results: Map of expectation_name -> score (0.0-1.0).
        """
        self.results = results

    async def run_checks(self, expectations: list[dict[str, Any]]) -> dict[str, float]:
        """Run quality checks and return scores.

        Args:
            expectations: List of expectation dicts with 'name', 'type', etc.

        Returns:
            Map of expectation name to score (0.0-1.0).
        """
        return {exp["name"]: self.results.get(exp["name"], 1.0) for exp in expectations}


def _make_contract(
    *,
    expectations: list[dict[str, Any]] | None = None,
    threshold: float = 0.8,
    name: str = "test_contract",
    quality_present: bool = True,
) -> RegisteredContract:
    """Create a test RegisteredContract with configurable quality expectations.

    Args:
        expectations: List of quality expectations (name, type, threshold, weight).
        threshold: Overall quality score threshold (0.0-1.0).
        name: Contract name.
        quality_present: Whether to include quality config at all.

    Returns:
        RegisteredContract instance for testing.
    """
    now = datetime.now(tz=timezone.utc)
    contract_data: dict[str, Any] = {"apiVersion": "v3.1.0"}

    if quality_present:
        quality_config: dict[str, Any] = {"threshold": threshold}
        if expectations is not None:
            quality_config["expectations"] = expectations
        else:
            quality_config["expectations"] = []
        contract_data["quality"] = quality_config

    return RegisteredContract(
        contract_name=name,
        contract_version="1.0.0",
        contract_data=contract_data,
        connection_config={"catalog": "polaris"},
        registered_at=now - timedelta(hours=2),
    )


@pytest.mark.requirement("3D-FR-015")
def test_quality_check_type() -> None:
    """Test that check_type returns ViolationType.QUALITY."""
    check = QualityCheck()
    assert check.check_type == ViolationType.QUALITY


@pytest.mark.requirement("3D-FR-015")
@pytest.mark.asyncio
async def test_quality_above_threshold() -> None:
    """Test quality check passes when all expectations meet threshold.

    All expectations score >= threshold → overall score >= threshold → PASS.
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 1.0,
        },
        {"name": "uniqueness", "type": "uniqueness", "threshold": 0.98, "weight": 1.0},
    ]
    contract = _make_contract(expectations=expectations, threshold=0.8)
    config = MonitoringConfig()

    # Mock plugin returns perfect scores
    plugin = MockQualityPlugin({"completeness": 1.0, "uniqueness": 1.0})
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.PASS
    assert result.violation is None
    assert result.contract_name == "test_contract"
    assert result.check_type == ViolationType.QUALITY


@pytest.mark.requirement("3D-FR-015")
@pytest.mark.asyncio
async def test_quality_below_threshold() -> None:
    """Test quality check fails when score below threshold.

    Score below threshold → FAIL with violation event.
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 1.0,
        },
    ]
    contract = _make_contract(expectations=expectations, threshold=0.8)
    config = MonitoringConfig()

    # Mock plugin returns low score (below threshold)
    plugin = MockQualityPlugin({"completeness": 0.5})
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.QUALITY
    assert result.violation.severity in [
        ViolationSeverity.WARNING,
        ViolationSeverity.ERROR,
        ViolationSeverity.CRITICAL,
    ]
    assert result.violation.actual_value is not None
    assert "0.5" in result.violation.actual_value  # Score appears in actual value
    assert result.violation.expected_value is not None
    assert "0.8" in result.violation.expected_value  # Threshold appears in expected value


@pytest.mark.requirement("3D-FR-016")
@pytest.mark.asyncio
async def test_quality_multiple_expectations() -> None:
    """Test quality with mix of pass/fail expectations.

    Overall score determines outcome, not individual expectation pass/fail.
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 1.0,
        },
        {"name": "uniqueness", "type": "uniqueness", "threshold": 0.98, "weight": 1.0},
        {"name": "validity", "type": "validity", "threshold": 0.90, "weight": 1.0},
    ]
    contract = _make_contract(expectations=expectations, threshold=0.8)
    config = MonitoringConfig()

    # Mix of scores: weighted average should be >= 0.8
    plugin = MockQualityPlugin(
        {
            "completeness": 0.9,  # pass
            "uniqueness": 0.7,  # fail
            "validity": 0.85,  # pass
        }
    )
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    # Weighted average = (0.9 + 0.7 + 0.85) / 3 = 0.8166... → PASS
    assert result.status == CheckStatus.PASS
    assert result.violation is None


@pytest.mark.requirement("3D-FR-016")
@pytest.mark.asyncio
async def test_quality_weighted_score() -> None:
    """Test that weights affect final score calculation.

    Expectations with higher weights contribute more to overall score.
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 2.0,
        },
        {"name": "uniqueness", "type": "uniqueness", "threshold": 0.98, "weight": 1.0},
    ]
    contract = _make_contract(expectations=expectations, threshold=0.8)
    config = MonitoringConfig()

    # Weighted: (0.6 * 2.0 + 1.0 * 1.0) / (2.0 + 1.0) = 0.733... → FAIL
    plugin = MockQualityPlugin(
        {
            "completeness": 0.6,  # Low score, high weight
            "uniqueness": 1.0,  # High score, low weight
        }
    )
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None


@pytest.mark.requirement("3D-FR-017")
@pytest.mark.asyncio
async def test_quality_no_expectations() -> None:
    """Test quality check returns ERROR when no expectations defined.

    No expectations in contract → ERROR (cannot validate).
    """
    contract = _make_contract(expectations=[], threshold=0.8)
    config = MonitoringConfig()

    plugin = MockQualityPlugin({})
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None
    assert "expectations" in result.details.get("error", "").lower()


@pytest.mark.requirement("3D-FR-018")
@pytest.mark.asyncio
async def test_quality_plugin_unavailable() -> None:
    """Test quality check gracefully skips when quality_plugin not provided.

    No quality_plugin → SKIPPED (not ERROR).
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 1.0,
        },
    ]
    contract = _make_contract(expectations=expectations, threshold=0.8)
    config = MonitoringConfig()

    # No quality_plugin provided
    check = QualityCheck(quality_plugin=None)

    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.SKIPPED
    assert result.violation is None
    assert "plugin" in result.details.get("message", "").lower()


@pytest.mark.requirement("3D-FR-015")
@pytest.mark.asyncio
async def test_quality_violation_event_fields() -> None:
    """Test that ContractViolationEvent fields are populated correctly.

    Verify contract_name, contract_version, violation_type, severity,
    message, expected_value, actual_value, timestamp, check_duration_seconds.
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 1.0,
        },
    ]
    contract = _make_contract(expectations=expectations, threshold=0.9)
    config = MonitoringConfig()

    plugin = MockQualityPlugin({"completeness": 0.5})
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    assert result.violation is not None
    v = result.violation

    assert v.contract_name == "test_contract"
    assert v.contract_version == "1.0.0"
    assert v.violation_type == ViolationType.QUALITY
    assert v.severity in [
        ViolationSeverity.WARNING,
        ViolationSeverity.ERROR,
        ViolationSeverity.CRITICAL,
    ]
    assert len(v.message) > 0
    assert v.expected_value is not None
    assert v.actual_value is not None
    assert v.timestamp is not None
    assert v.check_duration_seconds >= 0.0


@pytest.mark.requirement("3D-FR-017")
@pytest.mark.asyncio
async def test_quality_empty_results() -> None:
    """Test quality check passes when plugin returns empty results.

    Empty results (no expectations evaluated) → vacuously true → PASS.
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 1.0,
        },
    ]
    contract = _make_contract(expectations=expectations, threshold=0.8)
    config = MonitoringConfig()

    # Plugin returns empty dict (no results)
    plugin = MockQualityPlugin({})
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    # Empty results → all expectations default to 1.0 → PASS
    assert result.status == CheckStatus.PASS
    assert result.violation is None


@pytest.mark.requirement("3D-FR-015")
@pytest.mark.asyncio
async def test_quality_all_fail() -> None:
    """Test quality check fails with CRITICAL severity when all expectations fail.

    All expectations score 0.0 → overall score 0.0 → far below threshold → CRITICAL.
    """
    expectations = [
        {
            "name": "completeness",
            "type": "completeness",
            "threshold": 0.95,
            "weight": 1.0,
        },
        {"name": "uniqueness", "type": "uniqueness", "threshold": 0.98, "weight": 1.0},
    ]
    contract = _make_contract(expectations=expectations, threshold=0.8)
    config = MonitoringConfig()

    # All expectations fail catastrophically
    plugin = MockQualityPlugin({"completeness": 0.0, "uniqueness": 0.0})
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.severity == ViolationSeverity.CRITICAL


@pytest.mark.requirement("3D-FR-017")
@pytest.mark.asyncio
async def test_quality_no_quality_config() -> None:
    """Test quality check returns ERROR when quality config missing from contract.

    No contract_data.quality → ERROR.
    """
    contract = _make_contract(quality_present=False)
    config = MonitoringConfig()

    plugin = MockQualityPlugin({})
    check = QualityCheck(quality_plugin=plugin)

    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None
    assert "quality" in result.details.get("error", "").lower()
