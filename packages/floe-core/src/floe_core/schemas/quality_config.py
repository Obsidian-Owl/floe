"""Quality Configuration Schemas for data quality validation.

This module defines the configuration schemas for quality plugins,
including dimension weights, calculation parameters, quality gates,
and the top-level QualityConfig.

Contract Version: 0.4.0

See Also:
    - specs/5b-dataquality-plugin/spec.md: Feature specification
    - specs/5b-dataquality-plugin/data-model.md: Entity definitions
    - ADR-0044: Unified Data Quality Plugin
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class Dimension(str, Enum):
    """Quality dimensions for data quality scoring.

    Each quality check is mapped to one dimension. Dimension weights
    determine how much each dimension contributes to the overall score.

    Attributes:
        COMPLETENESS: Data is present where expected (not_null, expect_column_to_exist)
        ACCURACY: Data values are correct (expect_column_values_to_be_between)
        VALIDITY: Data conforms to defined rules (regex, accepted_values)
        CONSISTENCY: Data is consistent across sources (relationships, uniqueness)
        TIMELINESS: Data is current and up-to-date (timestamp checks)
    """

    COMPLETENESS = "completeness"
    """Data is present where expected (not_null, expect_column_to_exist)."""

    ACCURACY = "accuracy"
    """Data values are correct (expect_column_values_to_be_between)."""

    VALIDITY = "validity"
    """Data conforms to defined rules (regex, accepted_values)."""

    CONSISTENCY = "consistency"
    """Data is consistent across sources (relationships, uniqueness)."""

    TIMELINESS = "timeliness"
    """Data is current and up-to-date (timestamp checks)."""


class SeverityLevel(str, Enum):
    """Severity levels for quality checks.

    Severity determines the weight of a check in the quality score.
    Higher severity checks have more impact on the final score.

    Attributes:
        CRITICAL: Critical checks (default weight: 3.0). Failures significantly impact score.
        WARNING: Warning checks (default weight: 1.0). Standard business rule violations.
        INFO: Informational checks (default weight: 0.5). Nice-to-have validations.
    """

    CRITICAL = "critical"
    """Critical checks (default weight: 3.0). Failures significantly impact score."""

    WARNING = "warning"
    """Warning checks (default weight: 1.0). Standard business rule violations."""

    INFO = "info"
    """Informational checks (default weight: 0.5). Nice-to-have validations."""


class DimensionWeights(BaseModel):
    """Layer 1 of scoring model: weights for quality dimensions.

    Weights determine how much each dimension contributes to the overall
    quality score. Must sum to 1.0.

    Example:
        >>> weights = DimensionWeights(
        ...     completeness=0.30,
        ...     accuracy=0.25,
        ...     validity=0.20,
        ...     consistency=0.15,
        ...     timeliness=0.10,
        ... )
        >>> weights.completeness
        0.30
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    completeness: Annotated[float, Field(ge=0, le=1.0)] = 0.25
    """Weight for completeness dimension."""

    accuracy: Annotated[float, Field(ge=0, le=1.0)] = 0.25
    """Weight for accuracy dimension."""

    validity: Annotated[float, Field(ge=0, le=1.0)] = 0.20
    """Weight for validity dimension."""

    consistency: Annotated[float, Field(ge=0, le=1.0)] = 0.15
    """Weight for consistency dimension."""

    timeliness: Annotated[float, Field(ge=0, le=1.0)] = 0.15
    """Weight for timeliness dimension."""

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> Self:
        """Validate that all weights sum to 1.0."""
        total = (
            self.completeness + self.accuracy + self.validity + self.consistency + self.timeliness
        )
        if not math.isclose(total, 1.0, rel_tol=1e-9):
            msg = f"Dimension weights must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self


class CalculationParameters(BaseModel):
    """Layer 3 of scoring model: calculation parameters.

    Controls how the final quality score is calculated, including
    baseline score and influence capping to prevent extreme swings.

    Example:
        >>> params = CalculationParameters(
        ...     baseline_score=70,
        ...     max_positive_influence=30,
        ...     max_negative_influence=50,
        ... )
        >>> # All checks pass: score = min(100, 70 + 30) = 100
        >>> # All checks fail: score = max(0, 70 - 50) = 20
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_score: Annotated[int, Field(ge=0, le=100)] = 70
    """Starting score before applying check results."""

    max_positive_influence: Annotated[int, Field(ge=0, le=100)] = 30
    """Maximum score increase from baseline (capped)."""

    max_negative_influence: Annotated[int, Field(ge=0, le=100)] = 50
    """Maximum score decrease from baseline (capped)."""

    severity_weights: dict[SeverityLevel, float] = Field(
        default={
            SeverityLevel.CRITICAL: 3.0,
            SeverityLevel.WARNING: 1.0,
            SeverityLevel.INFO: 0.5,
        },
        description="Mapping of severity levels to numeric weights",
    )


class QualityThresholds(BaseModel):
    """Quality score thresholds for enforcement.

    min_score blocks deployment; warn_score emits warnings.

    Example:
        >>> thresholds = QualityThresholds(min_score=70, warn_score=85)
        >>> # Score 60 -> FLOE-DQ102 (blocks deployment)
        >>> # Score 75 -> Warning emitted, deployment allowed
        >>> # Score 90 -> Clean deployment
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_score: Annotated[int, Field(ge=0, le=100)] = 70
    """Minimum quality score required. Below this, deployment is blocked."""

    warn_score: Annotated[int, Field(ge=0, le=100)] = 85
    """Warning threshold. Below this (but above min_score), warning is emitted."""


class GateTier(BaseModel):
    """Quality gate requirements for a single tier.

    Defines minimum coverage and required test types for a quality tier.

    Example:
        >>> gold = GateTier(
        ...     min_test_coverage=100,
        ...     required_tests=["not_null", "unique", "accepted_values"],
        ...     min_score=90,
        ...     overridable=False,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_test_coverage: Annotated[float, Field(ge=0, le=100)] = 0
    """Minimum percentage of columns that must have tests."""

    required_tests: list[str] = Field(default_factory=list)
    """List of test types that must be present (not_null, unique, etc.)."""

    min_score: Annotated[int, Field(ge=0, le=100)] = 0
    """Minimum quality score for this tier."""

    overridable: bool = True
    """Whether lower levels (Domain/Product) can modify these settings."""


class QualityGates(BaseModel):
    """Tier-based quality requirements (bronze/silver/gold).

    Each tier defines progressively stricter requirements.

    Example:
        >>> gates = QualityGates(
        ...     bronze=GateTier(min_test_coverage=50),
        ...     silver=GateTier(min_test_coverage=80, required_tests=["not_null"]),
        ...     gold=GateTier(min_test_coverage=100, required_tests=["not_null", "unique"]),
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bronze: GateTier = Field(default_factory=GateTier)
    """Bronze tier requirements (minimum)."""

    silver: GateTier = Field(
        default_factory=lambda: GateTier(
            min_test_coverage=80,
            required_tests=["not_null", "unique"],
            min_score=75,
        )
    )
    """Silver tier requirements (standard)."""

    gold: GateTier = Field(
        default_factory=lambda: GateTier(
            min_test_coverage=100,
            required_tests=["not_null", "unique", "accepted_values", "relationships"],
            min_score=90,
        )
    )
    """Gold tier requirements (strictest)."""


class OverrideConfig(BaseModel):
    """Configuration for a single overridable setting.

    Controls whether a setting can be modified at lower inheritance levels.

    Example:
        >>> override = OverrideConfig(
        ...     value=90,
        ...     overridable=False,  # Cannot be changed at Domain/Product level
        ...     locked_by="enterprise",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Any = Field(..., description="The setting value")
    overridable: bool = Field(default=True, description="Can lower levels modify this")
    locked_by: str | None = Field(default=None, description="Which level locked this setting")


class QualityConfig(BaseModel):
    """Top-level quality configuration with three-tier inheritance.

    This is the resolved quality configuration after inheritance from
    Enterprise → Domain → Product levels.

    Example:
        >>> config = QualityConfig(
        ...     provider="great_expectations",
        ...     quality_gates=QualityGates(),
        ...     dimension_weights=DimensionWeights(),
        ...     calculation=CalculationParameters(),
        ...     thresholds=QualityThresholds(),
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(
        ...,
        min_length=1,
        description="Quality plugin name (e.g., 'great_expectations', 'dbt_expectations')",
    )

    quality_gates: QualityGates = Field(default_factory=QualityGates)
    """Bronze/silver/gold tier requirements."""

    dimension_weights: DimensionWeights = Field(default_factory=DimensionWeights)
    """Layer 1: Weights for quality dimensions."""

    calculation: CalculationParameters = Field(default_factory=CalculationParameters)
    """Layer 3: Score calculation parameters."""

    thresholds: QualityThresholds = Field(default_factory=QualityThresholds)
    """Score thresholds (min_score, warn_score)."""

    check_timeout_seconds: Annotated[int, Field(ge=1, le=3600)] = 300
    """Default timeout for quality check execution."""

    enabled: bool = True
    """Whether quality validation is enabled."""


__all__ = [
    "CalculationParameters",
    "Dimension",
    "DimensionWeights",
    "GateTier",
    "OverrideConfig",
    "QualityConfig",
    "QualityGates",
    "QualityThresholds",
    "SeverityLevel",
]
