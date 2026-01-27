"""Unit tests for quality configuration models.

Tests the Pydantic models in quality_config.py for validation,
serialization, and edge cases. Covers enums, dimension weights,
quality gates, and the top-level quality configuration.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from floe_core.schemas.quality_config import (
    CalculationParameters,
    Dimension,
    DimensionWeights,
    GateTier,
    OverrideConfig,
    QualityConfig,
    QualityGates,
    QualityThresholds,
    SeverityLevel,
)


class TestDimensionEnum:
    """Test Dimension enum values and behavior."""

    @pytest.mark.requirement("005B-FR-001")
    def test_dimension_values(self) -> None:
        """Test Dimension has all expected values."""
        assert Dimension.COMPLETENESS.value == "completeness"
        assert Dimension.ACCURACY.value == "accuracy"
        assert Dimension.VALIDITY.value == "validity"
        assert Dimension.CONSISTENCY.value == "consistency"
        assert Dimension.TIMELINESS.value == "timeliness"

    @pytest.mark.requirement("005B-FR-001")
    def test_dimension_from_string(self) -> None:
        """Test Dimension can be created from string value."""
        assert Dimension("completeness") == Dimension.COMPLETENESS
        assert Dimension("accuracy") == Dimension.ACCURACY
        assert Dimension("validity") == Dimension.VALIDITY
        assert Dimension("consistency") == Dimension.CONSISTENCY
        assert Dimension("timeliness") == Dimension.TIMELINESS

    @pytest.mark.requirement("005B-FR-001")
    def test_dimension_invalid_value(self) -> None:
        """Test Dimension rejects invalid values."""
        with pytest.raises(ValueError):
            Dimension("invalid_dimension")


class TestSeverityLevelEnum:
    """Test SeverityLevel enum values and behavior."""

    @pytest.mark.requirement("005B-FR-002")
    def test_severity_level_values(self) -> None:
        """Test SeverityLevel has all expected values."""
        assert SeverityLevel.CRITICAL.value == "critical"
        assert SeverityLevel.WARNING.value == "warning"
        assert SeverityLevel.INFO.value == "info"

    @pytest.mark.requirement("005B-FR-002")
    def test_severity_level_from_string(self) -> None:
        """Test SeverityLevel can be created from string value."""
        assert SeverityLevel("critical") == SeverityLevel.CRITICAL
        assert SeverityLevel("warning") == SeverityLevel.WARNING
        assert SeverityLevel("info") == SeverityLevel.INFO

    @pytest.mark.requirement("005B-FR-002")
    def test_severity_level_invalid_value(self) -> None:
        """Test SeverityLevel rejects invalid values."""
        with pytest.raises(ValueError):
            SeverityLevel("invalid_severity")


class TestDimensionWeights:
    """Test DimensionWeights Pydantic model."""

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_defaults(self) -> None:
        """Test DimensionWeights has sensible defaults that sum to 1.0."""
        weights = DimensionWeights()
        assert weights.completeness == 0.25
        assert weights.accuracy == 0.25
        assert weights.validity == 0.20
        assert weights.consistency == 0.15
        assert weights.timeliness == 0.15
        total = (
            weights.completeness
            + weights.accuracy
            + weights.validity
            + weights.consistency
            + weights.timeliness
        )
        assert math.isclose(total, 1.0, rel_tol=1e-9)

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_custom_valid(self) -> None:
        """Test DimensionWeights with custom valid weights."""
        weights = DimensionWeights(
            completeness=0.30,
            accuracy=0.25,
            validity=0.20,
            consistency=0.15,
            timeliness=0.10,
        )
        assert weights.completeness == 0.30
        assert weights.accuracy == 0.25
        assert weights.validity == 0.20
        assert weights.consistency == 0.15
        assert weights.timeliness == 0.10

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_sum_to_one_validation(self) -> None:
        """Test DimensionWeights validates that weights sum to 1.0."""
        with pytest.raises(ValidationError, match="must sum to 1.0"):
            DimensionWeights(
                completeness=0.30,
                accuracy=0.30,
                validity=0.20,
                consistency=0.15,
                timeliness=0.10,  # Total = 1.05, should fail
            )

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_sum_to_one_below_one(self) -> None:
        """Test DimensionWeights rejects weights that sum below 1.0."""
        with pytest.raises(ValidationError, match="must sum to 1.0"):
            DimensionWeights(
                completeness=0.20,
                accuracy=0.20,
                validity=0.20,
                consistency=0.15,
                timeliness=0.10,  # Total = 0.85, should fail
            )

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_boundary_values(self) -> None:
        """Test DimensionWeights with boundary values (0 and 1)."""
        weights = DimensionWeights(
            completeness=1.0,
            accuracy=0.0,
            validity=0.0,
            consistency=0.0,
            timeliness=0.0,
        )
        assert weights.completeness == 1.0
        assert weights.accuracy == 0.0

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_negative_invalid(self) -> None:
        """Test DimensionWeights rejects negative weights."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DimensionWeights(
                completeness=-0.1,
                accuracy=0.3,
                validity=0.3,
                consistency=0.2,
                timeliness=0.3,
            )

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_over_one_invalid(self) -> None:
        """Test DimensionWeights rejects individual weights over 1.0."""
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            DimensionWeights(
                completeness=1.1,
                accuracy=0.0,
                validity=0.0,
                consistency=0.0,
                timeliness=0.0,
            )

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_frozen(self) -> None:
        """Test DimensionWeights is immutable."""
        weights = DimensionWeights()
        with pytest.raises(ValidationError):
            weights.completeness = 0.5  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-003")
    def test_dimension_weights_extra_fields_forbidden(self) -> None:
        """Test DimensionWeights rejects extra fields."""
        with pytest.raises(ValidationError, match="extra_field"):
            DimensionWeights(  # type: ignore[call-arg, arg-type]
                completeness=0.25,
                accuracy=0.25,
                validity=0.20,
                consistency=0.15,
                timeliness=0.15,
                extra_field="not_allowed",  # type: ignore[arg-type]
            )


class TestCalculationParameters:
    """Test CalculationParameters Pydantic model."""

    @pytest.mark.requirement("005B-FR-004")
    def test_calculation_parameters_defaults(self) -> None:
        """Test CalculationParameters has sensible defaults."""
        params = CalculationParameters()
        assert params.baseline_score == 70
        assert params.max_positive_influence == 30
        assert params.max_negative_influence == 50
        assert params.severity_weights[SeverityLevel.CRITICAL] == 3.0
        assert params.severity_weights[SeverityLevel.WARNING] == 1.0
        assert params.severity_weights[SeverityLevel.INFO] == 0.5

    @pytest.mark.requirement("005B-FR-004")
    def test_calculation_parameters_custom(self) -> None:
        """Test CalculationParameters with custom values."""
        params = CalculationParameters(
            baseline_score=80,
            max_positive_influence=20,
            max_negative_influence=40,
        )
        assert params.baseline_score == 80
        assert params.max_positive_influence == 20
        assert params.max_negative_influence == 40

    @pytest.mark.requirement("005B-FR-004")
    def test_calculation_parameters_custom_severity_weights(self) -> None:
        """Test CalculationParameters with custom severity weights."""
        custom_weights = {
            SeverityLevel.CRITICAL: 5.0,
            SeverityLevel.WARNING: 2.0,
            SeverityLevel.INFO: 0.1,
        }
        params = CalculationParameters(severity_weights=custom_weights)
        assert params.severity_weights[SeverityLevel.CRITICAL] == 5.0
        assert params.severity_weights[SeverityLevel.WARNING] == 2.0
        assert params.severity_weights[SeverityLevel.INFO] == 0.1

    @pytest.mark.requirement("005B-FR-004")
    def test_calculation_parameters_baseline_score_boundary(self) -> None:
        """Test CalculationParameters baseline_score boundaries."""
        params_min = CalculationParameters(baseline_score=0)
        assert params_min.baseline_score == 0

        params_max = CalculationParameters(baseline_score=100)
        assert params_max.baseline_score == 100

    @pytest.mark.requirement("005B-FR-004")
    def test_calculation_parameters_baseline_score_invalid(self) -> None:
        """Test CalculationParameters rejects invalid baseline_score."""
        with pytest.raises(ValidationError, match="baseline_score"):
            CalculationParameters(baseline_score=-1)

        with pytest.raises(ValidationError, match="baseline_score"):
            CalculationParameters(baseline_score=101)

    @pytest.mark.requirement("005B-FR-004")
    def test_calculation_parameters_frozen(self) -> None:
        """Test CalculationParameters is immutable."""
        params = CalculationParameters()
        with pytest.raises(ValidationError):
            params.baseline_score = 50  # type: ignore[misc]


class TestQualityThresholds:
    """Test QualityThresholds Pydantic model."""

    @pytest.mark.requirement("005B-FR-005")
    def test_quality_thresholds_defaults(self) -> None:
        """Test QualityThresholds has sensible defaults."""
        thresholds = QualityThresholds()
        assert thresholds.min_score == 70
        assert thresholds.warn_score == 85

    @pytest.mark.requirement("005B-FR-005")
    def test_quality_thresholds_custom(self) -> None:
        """Test QualityThresholds with custom values."""
        thresholds = QualityThresholds(min_score=60, warn_score=80)
        assert thresholds.min_score == 60
        assert thresholds.warn_score == 80

    @pytest.mark.requirement("005B-FR-005")
    def test_quality_thresholds_boundary_values(self) -> None:
        """Test QualityThresholds with boundary values."""
        thresholds = QualityThresholds(min_score=0, warn_score=100)
        assert thresholds.min_score == 0
        assert thresholds.warn_score == 100

    @pytest.mark.requirement("005B-FR-005")
    def test_quality_thresholds_invalid_min_score(self) -> None:
        """Test QualityThresholds rejects invalid min_score."""
        with pytest.raises(ValidationError, match="min_score"):
            QualityThresholds(min_score=-1)

        with pytest.raises(ValidationError, match="min_score"):
            QualityThresholds(min_score=101)

    @pytest.mark.requirement("005B-FR-005")
    def test_quality_thresholds_frozen(self) -> None:
        """Test QualityThresholds is immutable."""
        thresholds = QualityThresholds()
        with pytest.raises(ValidationError):
            thresholds.min_score = 50  # type: ignore[misc]


class TestGateTier:
    """Test GateTier Pydantic model."""

    @pytest.mark.requirement("005B-FR-006")
    def test_gate_tier_defaults(self) -> None:
        """Test GateTier has sensible defaults."""
        tier = GateTier()
        assert tier.min_test_coverage == 0
        assert tier.required_tests == []
        assert tier.min_score == 0
        assert tier.overridable is True

    @pytest.mark.requirement("005B-FR-006")
    def test_gate_tier_custom(self) -> None:
        """Test GateTier with custom values."""
        tier = GateTier(
            min_test_coverage=100,
            required_tests=["not_null", "unique"],
            min_score=90,
            overridable=False,
        )
        assert tier.min_test_coverage == 100
        assert tier.required_tests == ["not_null", "unique"]
        assert tier.min_score == 90
        assert tier.overridable is False

    @pytest.mark.requirement("005B-FR-006")
    def test_gate_tier_coverage_boundary(self) -> None:
        """Test GateTier coverage percentage boundaries."""
        tier_min = GateTier(min_test_coverage=0)
        assert tier_min.min_test_coverage == 0

        tier_max = GateTier(min_test_coverage=100)
        assert tier_max.min_test_coverage == 100

    @pytest.mark.requirement("005B-FR-006")
    def test_gate_tier_coverage_invalid(self) -> None:
        """Test GateTier rejects invalid coverage percentage."""
        with pytest.raises(ValidationError, match="min_test_coverage"):
            GateTier(min_test_coverage=-1)

        with pytest.raises(ValidationError, match="min_test_coverage"):
            GateTier(min_test_coverage=101)

    @pytest.mark.requirement("005B-FR-006")
    def test_gate_tier_frozen(self) -> None:
        """Test GateTier is immutable."""
        tier = GateTier()
        with pytest.raises(ValidationError):
            tier.min_test_coverage = 50  # type: ignore[misc]


class TestQualityGates:
    """Test QualityGates Pydantic model."""

    @pytest.mark.requirement("005B-FR-007")
    def test_quality_gates_defaults(self) -> None:
        """Test QualityGates has sensible defaults for all tiers."""
        gates = QualityGates()

        # Bronze tier (minimum)
        assert gates.bronze.min_test_coverage == 0
        assert gates.bronze.required_tests == []
        assert gates.bronze.min_score == 0

        # Silver tier (standard)
        assert gates.silver.min_test_coverage == 80
        assert "not_null" in gates.silver.required_tests
        assert "unique" in gates.silver.required_tests
        assert gates.silver.min_score == 75

        # Gold tier (strictest)
        assert gates.gold.min_test_coverage == 100
        assert "not_null" in gates.gold.required_tests
        assert "unique" in gates.gold.required_tests
        assert "accepted_values" in gates.gold.required_tests
        assert "relationships" in gates.gold.required_tests
        assert gates.gold.min_score == 90

    @pytest.mark.requirement("005B-FR-007")
    def test_quality_gates_custom(self) -> None:
        """Test QualityGates with custom tier definitions."""
        bronze = GateTier(min_test_coverage=50)
        silver = GateTier(min_test_coverage=80, required_tests=["not_null"])
        gold = GateTier(min_test_coverage=100, required_tests=["not_null", "unique"])

        gates = QualityGates(bronze=bronze, silver=silver, gold=gold)
        assert gates.bronze.min_test_coverage == 50
        assert gates.silver.min_test_coverage == 80
        assert gates.gold.min_test_coverage == 100

    @pytest.mark.requirement("005B-FR-007")
    def test_quality_gates_frozen(self) -> None:
        """Test QualityGates is immutable."""
        gates = QualityGates()
        with pytest.raises(ValidationError):
            gates.bronze = GateTier(min_test_coverage=50)  # type: ignore[misc]


class TestOverrideConfig:
    """Test OverrideConfig Pydantic model."""

    @pytest.mark.requirement("005B-FR-008")
    def test_override_config_minimal(self) -> None:
        """Test OverrideConfig with minimal fields."""
        config = OverrideConfig(value=90)
        assert config.value == 90
        assert config.overridable is True
        assert config.locked_by is None

    @pytest.mark.requirement("005B-FR-008")
    def test_override_config_full(self) -> None:
        """Test OverrideConfig with all fields."""
        config = OverrideConfig(
            value=90,
            overridable=False,
            locked_by="enterprise",
        )
        assert config.value == 90
        assert config.overridable is False
        assert config.locked_by == "enterprise"

    @pytest.mark.requirement("005B-FR-008")
    def test_override_config_various_value_types(self) -> None:
        """Test OverrideConfig accepts various value types."""
        # String value
        config_str = OverrideConfig(value="some_string")
        assert config_str.value == "some_string"

        # Integer value
        config_int = OverrideConfig(value=42)
        assert config_int.value == 42

        # List value
        config_list = OverrideConfig(value=["a", "b", "c"])
        assert config_list.value == ["a", "b", "c"]

        # Dict value
        config_dict = OverrideConfig(value={"key": "value"})
        assert config_dict.value == {"key": "value"}

    @pytest.mark.requirement("005B-FR-008")
    def test_override_config_frozen(self) -> None:
        """Test OverrideConfig is immutable."""
        config = OverrideConfig(value=90)
        with pytest.raises(ValidationError):
            config.value = 50  # type: ignore[misc]


class TestQualityConfig:
    """Test QualityConfig Pydantic model."""

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_minimal(self) -> None:
        """Test QualityConfig with minimal required fields."""
        config = QualityConfig(provider="great_expectations")
        assert config.provider == "great_expectations"
        assert isinstance(config.quality_gates, QualityGates)
        assert isinstance(config.dimension_weights, DimensionWeights)
        assert isinstance(config.calculation, CalculationParameters)
        assert isinstance(config.thresholds, QualityThresholds)
        assert config.check_timeout_seconds == 300
        assert config.enabled is True

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_full(self) -> None:
        """Test QualityConfig with all fields specified."""
        gates = QualityGates()
        weights = DimensionWeights()
        calc = CalculationParameters()
        thresholds = QualityThresholds()

        config = QualityConfig(
            provider="dbt_expectations",
            quality_gates=gates,
            dimension_weights=weights,
            calculation=calc,
            thresholds=thresholds,
            check_timeout_seconds=600,
            enabled=False,
        )
        assert config.provider == "dbt_expectations"
        assert config.quality_gates is gates
        assert config.dimension_weights is weights
        assert config.calculation is calc
        assert config.thresholds is thresholds
        assert config.check_timeout_seconds == 600
        assert config.enabled is False

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_provider_required(self) -> None:
        """Test QualityConfig requires provider."""
        with pytest.raises(ValidationError, match="provider"):
            QualityConfig()  # type: ignore[call-arg]

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_provider_empty_invalid(self) -> None:
        """Test QualityConfig rejects empty provider."""
        with pytest.raises(ValidationError, match="provider"):
            QualityConfig(provider="")

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_timeout_boundary(self) -> None:
        """Test QualityConfig timeout boundaries."""
        config_min = QualityConfig(provider="test", check_timeout_seconds=1)
        assert config_min.check_timeout_seconds == 1

        config_max = QualityConfig(provider="test", check_timeout_seconds=3600)
        assert config_max.check_timeout_seconds == 3600

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_timeout_invalid(self) -> None:
        """Test QualityConfig rejects invalid timeout."""
        with pytest.raises(ValidationError, match="check_timeout_seconds"):
            QualityConfig(provider="test", check_timeout_seconds=0)

        with pytest.raises(ValidationError, match="check_timeout_seconds"):
            QualityConfig(provider="test", check_timeout_seconds=3601)

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_frozen(self) -> None:
        """Test QualityConfig is immutable."""
        config = QualityConfig(provider="test")
        with pytest.raises(ValidationError):
            config.provider = "other"  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-009")
    def test_quality_config_extra_fields_forbidden(self) -> None:
        """Test QualityConfig rejects extra fields."""
        with pytest.raises(ValidationError, match="extra_field"):
            QualityConfig(  # type: ignore[call-arg, arg-type]
                provider="test",
                extra_field="not_allowed",  # type: ignore[arg-type]
            )
