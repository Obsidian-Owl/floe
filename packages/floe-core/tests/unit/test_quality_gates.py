"""Unit tests for quality gate validation.

Tests the quality gate validation functions including:
- T066: min_test_coverage validation
- T067: FLOE-DQ103 coverage violation error
- T068: FLOE-DQ104 missing required tests error
- T069: FLOE-DQ107 locked setting override error
"""

from __future__ import annotations

import pytest

from floe_core.quality_errors import (
    QualityCoverageError,
    QualityMissingTestsError,
    QualityOverrideError,
)
from floe_core.schemas.quality_config import GateTier, QualityGates
from floe_core.validation.quality_gates import (
    validate_coverage,
    validate_override,
    validate_required_tests,
)


class TestValidateCoverage:
    """Test validate_coverage function (T066, T067)."""

    @pytest.mark.requirement("005B-FR-021")
    def test_coverage_passes_when_at_minimum(self) -> None:
        """Test coverage passes when exactly at minimum."""
        gates = QualityGates(
            gold=GateTier(min_test_coverage=100.0),
        )
        validate_coverage(
            model_name="gold_customers",
            tier="gold",
            actual_coverage=100.0,
            gates=gates,
        )

    @pytest.mark.requirement("005B-FR-021")
    def test_coverage_passes_when_above_minimum(self) -> None:
        """Test coverage passes when above minimum."""
        gates = QualityGates(
            silver=GateTier(min_test_coverage=80.0),
        )
        validate_coverage(
            model_name="silver_customers",
            tier="silver",
            actual_coverage=95.0,
            gates=gates,
        )

    @pytest.mark.requirement("005B-FR-021")
    def test_coverage_passes_bronze_tier(self) -> None:
        """Test bronze tier with default (0%) coverage requirement."""
        gates = QualityGates()
        validate_coverage(
            model_name="bronze_raw",
            tier="bronze",
            actual_coverage=50.0,
            gates=gates,
        )

    @pytest.mark.requirement("005B-FR-021", "005B-FR-043")
    def test_coverage_fails_when_below_minimum(self) -> None:
        """Test coverage fails when below minimum (FLOE-DQ103)."""
        gates = QualityGates(
            gold=GateTier(min_test_coverage=100.0),
        )
        with pytest.raises(QualityCoverageError) as exc_info:
            validate_coverage(
                model_name="gold_customers",
                tier="gold",
                actual_coverage=85.0,
                gates=gates,
            )
        assert exc_info.value.error_code == "FLOE-DQ103"
        assert exc_info.value.model_name == "gold_customers"
        assert exc_info.value.tier == "gold"
        assert exc_info.value.actual_coverage == 85.0
        assert exc_info.value.required_coverage == 100.0

    @pytest.mark.requirement("005B-FR-021", "005B-FR-043")
    def test_coverage_fails_silver_tier(self) -> None:
        """Test silver tier coverage failure (FLOE-DQ103)."""
        gates = QualityGates(
            silver=GateTier(min_test_coverage=80.0),
        )
        with pytest.raises(QualityCoverageError) as exc_info:
            validate_coverage(
                model_name="silver_orders",
                tier="silver",
                actual_coverage=60.0,
                gates=gates,
            )
        assert exc_info.value.error_code == "FLOE-DQ103"
        assert exc_info.value.tier == "silver"
        assert exc_info.value.required_coverage == 80.0

    @pytest.mark.requirement("005B-FR-021")
    def test_coverage_passes_zero_requirement(self) -> None:
        """Test coverage passes when requirement is 0%."""
        gates = QualityGates(
            bronze=GateTier(min_test_coverage=0.0),
        )
        validate_coverage(
            model_name="bronze_raw",
            tier="bronze",
            actual_coverage=0.0,
            gates=gates,
        )

    @pytest.mark.requirement("005B-FR-021", "005B-FR-043")
    def test_coverage_error_message_format(self) -> None:
        """Test FLOE-DQ103 error message contains resolution."""
        gates = QualityGates(
            gold=GateTier(min_test_coverage=100.0),
        )
        with pytest.raises(QualityCoverageError) as exc_info:
            validate_coverage(
                model_name="gold_customers",
                tier="gold",
                actual_coverage=50.0,
                gates=gates,
            )
        error_message = str(exc_info.value)
        assert "FLOE-DQ103" in error_message
        assert "gold_customers" in error_message
        assert "50.0%" in error_message
        assert "100.0%" in error_message
        assert "Resolution:" in error_message


class TestValidateRequiredTests:
    """Test validate_required_tests function (T068)."""

    @pytest.mark.requirement("005B-FR-022")
    def test_required_tests_passes_when_all_present(self) -> None:
        """Test passes when all required tests are present."""
        gates = QualityGates(
            silver=GateTier(required_tests=["not_null", "unique"]),
        )
        actual_tests = {"not_null", "unique", "accepted_values"}
        validate_required_tests(
            model_name="silver_orders",
            tier="silver",
            actual_tests=actual_tests,
            gates=gates,
        )

    @pytest.mark.requirement("005B-FR-022")
    def test_required_tests_passes_with_extras(self) -> None:
        """Test passes when more tests than required are present."""
        gates = QualityGates(
            bronze=GateTier(required_tests=[]),
        )
        actual_tests = {"not_null", "unique"}
        validate_required_tests(
            model_name="bronze_raw",
            tier="bronze",
            actual_tests=actual_tests,
            gates=gates,
        )

    @pytest.mark.requirement("005B-FR-022")
    def test_required_tests_passes_empty_requirement(self) -> None:
        """Test passes when no tests are required."""
        gates = QualityGates(
            bronze=GateTier(required_tests=[]),
        )
        validate_required_tests(
            model_name="bronze_raw",
            tier="bronze",
            actual_tests=set(),
            gates=gates,
        )

    @pytest.mark.requirement("005B-FR-022", "005B-FR-044")
    def test_required_tests_fails_when_missing(self) -> None:
        """Test fails when required tests are missing (FLOE-DQ104)."""
        gates = QualityGates(
            gold=GateTier(required_tests=["not_null", "unique", "relationships"]),
        )
        actual_tests = {"not_null"}
        with pytest.raises(QualityMissingTestsError) as exc_info:
            validate_required_tests(
                model_name="gold_customers",
                tier="gold",
                actual_tests=actual_tests,
                gates=gates,
            )
        assert exc_info.value.error_code == "FLOE-DQ104"
        assert exc_info.value.model_name == "gold_customers"
        assert exc_info.value.tier == "gold"
        assert set(exc_info.value.missing_tests) == {"unique", "relationships"}

    @pytest.mark.requirement("005B-FR-022", "005B-FR-044")
    def test_required_tests_fails_single_missing(self) -> None:
        """Test fails when single required test is missing (FLOE-DQ104)."""
        gates = QualityGates(
            silver=GateTier(required_tests=["not_null", "unique"]),
        )
        actual_tests = {"not_null"}
        with pytest.raises(QualityMissingTestsError) as exc_info:
            validate_required_tests(
                model_name="silver_orders",
                tier="silver",
                actual_tests=actual_tests,
                gates=gates,
            )
        assert exc_info.value.error_code == "FLOE-DQ104"
        assert exc_info.value.missing_tests == ["unique"]

    @pytest.mark.requirement("005B-FR-022", "005B-FR-044")
    def test_required_tests_error_message_format(self) -> None:
        """Test FLOE-DQ104 error message contains resolution."""
        gates = QualityGates(
            gold=GateTier(required_tests=["not_null", "unique"]),
        )
        with pytest.raises(QualityMissingTestsError) as exc_info:
            validate_required_tests(
                model_name="gold_customers",
                tier="gold",
                actual_tests=set(),
                gates=gates,
            )
        error_message = str(exc_info.value)
        assert "FLOE-DQ104" in error_message
        assert "gold_customers" in error_message
        assert "not_null" in error_message
        assert "unique" in error_message
        assert "Resolution:" in error_message


class TestValidateOverride:
    """Test validate_override function (T069)."""

    @pytest.mark.requirement("005B-FR-016b")
    def test_override_allowed_when_overridable(self) -> None:
        """Test override is allowed when setting is overridable."""
        validate_override(
            setting_name="min_test_coverage",
            value=80.0,
            overridable=True,
            locked_by=None,
            attempted_by="product",
        )

    @pytest.mark.requirement("005B-FR-016b")
    def test_override_allowed_same_level(self) -> None:
        """Test setting can be set at same level that locked it."""
        validate_override(
            setting_name="min_test_coverage",
            value=90.0,
            overridable=False,
            locked_by="enterprise",
            attempted_by="enterprise",
        )

    @pytest.mark.requirement("005B-FR-016b", "005B-FR-047")
    def test_override_fails_when_locked(self) -> None:
        """Test override fails when setting is locked (FLOE-DQ107)."""
        with pytest.raises(QualityOverrideError) as exc_info:
            validate_override(
                setting_name="min_test_coverage",
                value=50.0,
                overridable=False,
                locked_by="enterprise",
                attempted_by="product",
            )
        assert exc_info.value.error_code == "FLOE-DQ107"
        assert exc_info.value.setting_name == "min_test_coverage"
        assert exc_info.value.locked_by == "enterprise"
        assert exc_info.value.attempted_by == "product"

    @pytest.mark.requirement("005B-FR-016b", "005B-FR-047")
    def test_override_fails_domain_to_product(self) -> None:
        """Test override fails when domain locks and product attempts."""
        with pytest.raises(QualityOverrideError) as exc_info:
            validate_override(
                setting_name="required_tests",
                value=["not_null"],
                overridable=False,
                locked_by="domain",
                attempted_by="product",
            )
        assert exc_info.value.error_code == "FLOE-DQ107"
        assert exc_info.value.locked_by == "domain"
        assert exc_info.value.attempted_by == "product"

    @pytest.mark.requirement("005B-FR-016b", "005B-FR-047")
    def test_override_fails_enterprise_to_domain(self) -> None:
        """Test override fails when enterprise locks and domain attempts."""
        with pytest.raises(QualityOverrideError) as exc_info:
            validate_override(
                setting_name="warn_score",
                value=70,
                overridable=False,
                locked_by="enterprise",
                attempted_by="domain",
            )
        assert exc_info.value.error_code == "FLOE-DQ107"
        assert exc_info.value.locked_by == "enterprise"
        assert exc_info.value.attempted_by == "domain"

    @pytest.mark.requirement("005B-FR-016b", "005B-FR-047")
    def test_override_error_message_format(self) -> None:
        """Test FLOE-DQ107 error message contains resolution."""
        with pytest.raises(QualityOverrideError) as exc_info:
            validate_override(
                setting_name="min_score",
                value=50,
                overridable=False,
                locked_by="enterprise",
                attempted_by="product",
            )
        error_message = str(exc_info.value)
        assert "FLOE-DQ107" in error_message
        assert "min_score" in error_message
        assert "enterprise" in error_message
        assert "product" in error_message
        assert "Resolution:" in error_message

    @pytest.mark.requirement("005B-FR-016b")
    def test_override_allowed_when_no_lock(self) -> None:
        """Test override is allowed when locked_by is None."""
        validate_override(
            setting_name="min_test_coverage",
            value=90.0,
            overridable=False,
            locked_by=None,
            attempted_by="product",
        )
