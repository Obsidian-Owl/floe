"""Governance configuration models for policy enforcement.

This module provides Pydantic models for configuring policy enforcement
in the floe platform, including naming conventions and quality gates.

Implements:
    - FR-013: Required Fields Enforcement
    - FR-017: Governance Configuration
    - US2: Policy Configuration via Manifest

Task: T011-T013
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LayerThresholds(BaseModel):
    """Per-layer test coverage thresholds for medallion architecture.

    Defines minimum test coverage percentages for each data layer
    (bronze, silver, gold) in the medallion architecture pattern.

    Attributes:
        bronze: Bronze layer coverage threshold (default: 50%)
        silver: Silver layer coverage threshold (default: 80%)
        gold: Gold layer coverage threshold (default: 100%)

    Example:
        >>> thresholds = LayerThresholds(bronze=60, silver=85, gold=100)
        >>> thresholds.bronze
        60

    Strength Ordering (for inheritance):
        Higher thresholds are stricter - child cannot lower parent thresholds.

    See Also:
        - data-model.md: LayerThresholds entity specification
        - governance-schema.json: JSON Schema contract
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"bronze": 50, "silver": 80, "gold": 100},
            ]
        },
    )

    bronze: Annotated[
        int,
        Field(
            default=50,
            ge=0,
            le=100,
            description="Bronze layer coverage threshold (0-100)",
        ),
    ]
    silver: Annotated[
        int,
        Field(
            default=80,
            ge=0,
            le=100,
            description="Silver layer coverage threshold (0-100)",
        ),
    ]
    gold: Annotated[
        int,
        Field(
            default=100,
            ge=0,
            le=100,
            description="Gold layer coverage threshold (0-100)",
        ),
    ]


class NamingConfig(BaseModel):
    """Configuration for model naming convention validation.

    Defines how model names should be validated against naming patterns
    (medallion, kimball, or custom regex patterns).

    Attributes:
        enforcement: Enforcement level (off, warn, strict). Default: "warn"
        pattern: Naming pattern type (medallion, kimball, custom). Default: "medallion"
        custom_patterns: User-defined regex patterns (required if pattern="custom")

    Example:
        >>> naming = NamingConfig(enforcement="strict", pattern="medallion")
        >>> naming.enforcement
        'strict'

        >>> custom = NamingConfig(
        ...     pattern="custom",
        ...     custom_patterns=["^raw_.*$", "^clean_.*$", "^agg_.*$"]
        ... )

    Business Rules:
        - If pattern="custom", custom_patterns MUST be provided
        - If pattern!="custom", custom_patterns is ignored but stored
        - All custom patterns must be valid regex

    Strength Ordering (for inheritance):
        - enforcement: strict (3) > warn (2) > off (1)

    See Also:
        - data-model.md: NamingConfig entity specification
        - governance-schema.json: JSON Schema contract
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"enforcement": "strict", "pattern": "medallion"},
                {
                    "enforcement": "warn",
                    "pattern": "custom",
                    "custom_patterns": ["^raw_.*$", "^clean_.*$"],
                },
            ]
        },
    )

    enforcement: Literal["off", "warn", "strict"] = Field(
        default="warn",
        description="Enforcement level for naming conventions (strict > warn > off)",
    )
    pattern: Literal["medallion", "kimball", "custom"] = Field(
        default="medallion",
        description="Naming pattern type",
    )
    custom_patterns: list[str] | None = Field(
        default=None,
        description="User-defined regex patterns (required if pattern='custom')",
    )

    @model_validator(mode="after")
    def validate_custom_patterns(self) -> NamingConfig:
        """Validate that custom patterns are provided when pattern='custom'.

        Also validates that all custom patterns are valid regex.

        Raises:
            ValueError: If pattern='custom' but custom_patterns is None/empty
            ValueError: If any custom pattern is not a valid regex
        """
        if self.pattern == "custom":
            if not self.custom_patterns:
                msg = (
                    "custom_patterns is required when pattern='custom'. "
                    "Provide a list of regex patterns for model name validation."
                )
                raise ValueError(msg)

            # Validate each pattern is valid regex
            for pattern in self.custom_patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    msg = f"Invalid regex pattern '{pattern}': {e}"
                    raise ValueError(msg) from e

        return self


class QualityGatesConfig(BaseModel):
    """Configuration for quality gate thresholds.

    Defines minimum requirements for test coverage, model descriptions,
    and column descriptions that models must meet.

    Attributes:
        minimum_test_coverage: Minimum column-level test coverage (0-100). Default: 80
        require_descriptions: Require model descriptions. Default: False
        require_column_descriptions: Require column descriptions. Default: False
        block_on_failure: Block compilation on failure. Default: True
        layer_thresholds: Per-layer coverage thresholds (overrides minimum_test_coverage)
        zero_column_coverage_behavior: How to handle zero-column models. Default: "report_na"

    Example:
        >>> gates = QualityGatesConfig(
        ...     minimum_test_coverage=90,
        ...     require_descriptions=True,
        ...     layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=100)
        ... )

    Strength Ordering (for inheritance):
        - minimum_test_coverage: higher is stricter
        - require_descriptions: True > False
        - require_column_descriptions: True > False
        - block_on_failure: True > False (cannot relax)
        - layer_thresholds: each layer threshold follows numeric comparison

    See Also:
        - data-model.md: QualityGatesConfig entity specification
        - governance-schema.json: JSON Schema contract
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "minimum_test_coverage": 80,
                    "require_descriptions": True,
                    "layer_thresholds": {"bronze": 50, "silver": 80, "gold": 100},
                }
            ]
        },
    )

    minimum_test_coverage: Annotated[
        int,
        Field(
            default=80,
            ge=0,
            le=100,
            description="Minimum column-level test coverage percentage (0-100)",
        ),
    ]
    require_descriptions: bool = Field(
        default=False,
        description="Require model descriptions",
    )
    require_column_descriptions: bool = Field(
        default=False,
        description="Require column descriptions",
    )
    block_on_failure: bool = Field(
        default=True,
        description="Block compilation when quality gates fail",
    )
    layer_thresholds: LayerThresholds | None = Field(
        default=None,
        description="Per-layer coverage thresholds (overrides minimum_test_coverage)",
    )
    zero_column_coverage_behavior: Literal["report_100_percent", "report_na"] = Field(
        default="report_na",
        description="How to handle models with zero columns: 100% coverage or N/A",
    )


__all__ = [
    "LayerThresholds",
    "NamingConfig",
    "QualityGatesConfig",
]
