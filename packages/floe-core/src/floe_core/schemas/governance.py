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
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


# ==============================================================================
# Epic 3B: Custom Rule Types (Discriminated Union)
# ==============================================================================


class RequireTagsForPrefix(BaseModel):
    """Custom rule requiring specific tags for models matching a prefix.

    Validates that models with names starting with a specific prefix have
    all required tags defined.

    Attributes:
        type: Discriminator value, always "require_tags_for_prefix".
        prefix: Model name prefix to match (e.g., "gold_").
        required_tags: List of tags that must be present on matching models.
        applies_to: Glob pattern for model selection (default: "*").

    Example:
        >>> rule = RequireTagsForPrefix(
        ...     prefix="gold_",
        ...     required_tags=["tested", "documented"],
        ... )

    Error Code: FLOE-E400

    See Also:
        - data-model.md: CustomRule entity specification
        - spec.md: FR-006
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    type: Literal["require_tags_for_prefix"] = Field(
        default="require_tags_for_prefix",
        description="Rule type discriminator",
    )
    prefix: str = Field(
        ...,
        min_length=1,
        description="Model name prefix to match (e.g., 'gold_')",
    )
    required_tags: list[str] = Field(
        ...,
        min_length=1,
        description="Tags that must be present on matching models",
    )
    applies_to: str = Field(
        default="*",
        description="Glob pattern for model selection (default: all models)",
    )


class RequireMetaField(BaseModel):
    """Custom rule requiring a specific meta field on models.

    Validates that models have a specific meta field defined, optionally
    requiring the field to have a non-empty value.

    Attributes:
        type: Discriminator value, always "require_meta_field".
        field: Name of the required meta field (e.g., "owner").
        required: Whether field must have non-empty value (default: True).
        applies_to: Glob pattern for model selection (default: "*").

    Example:
        >>> rule = RequireMetaField(
        ...     field="owner",
        ...     required=True,
        ...     applies_to="gold_*",
        ... )

    Error Code: FLOE-E401

    See Also:
        - data-model.md: CustomRule entity specification
        - spec.md: FR-007
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    type: Literal["require_meta_field"] = Field(
        default="require_meta_field",
        description="Rule type discriminator",
    )
    field: str = Field(
        ...,
        min_length=1,
        description="Name of the required meta field (e.g., 'owner')",
    )
    required: bool = Field(
        default=True,
        description="Whether field must have non-empty value",
    )
    applies_to: str = Field(
        default="*",
        description="Glob pattern for model selection (default: all models)",
    )


class RequireTestsOfType(BaseModel):
    """Custom rule requiring specific test types on model columns.

    Validates that models have at least a minimum number of columns with
    specific test types (e.g., not_null, unique).

    Attributes:
        type: Discriminator value, always "require_tests_of_type".
        test_types: List of required test types (e.g., ["not_null", "unique"]).
        min_columns: Minimum columns that must have these tests (default: 1).
        applies_to: Glob pattern for model selection (default: "*").

    Example:
        >>> rule = RequireTestsOfType(
        ...     test_types=["not_null", "unique"],
        ...     min_columns=1,
        ... )

    Error Code: FLOE-E402

    See Also:
        - data-model.md: CustomRule entity specification
        - spec.md: FR-008
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    type: Literal["require_tests_of_type"] = Field(
        default="require_tests_of_type",
        description="Rule type discriminator",
    )
    test_types: list[str] = Field(
        ...,
        min_length=1,
        description="List of required test types (e.g., ['not_null', 'unique'])",
    )
    min_columns: int = Field(
        default=1,
        ge=1,
        description="Minimum columns that must have these tests",
    )
    applies_to: str = Field(
        default="*",
        description="Glob pattern for model selection (default: all models)",
    )


# Discriminated union type for custom rules
CustomRule = Annotated[
    RequireTagsForPrefix | RequireMetaField | RequireTestsOfType,
    Field(discriminator="type"),
]
"""Discriminated union of custom rule types.

Use the 'type' field to specify which rule type to create.

Supported types:
    - require_tags_for_prefix: Require tags on models with specific prefix
    - require_meta_field: Require a meta field on models
    - require_tests_of_type: Require specific test types on columns

Example YAML:
    custom_rules:
      - type: require_tags_for_prefix
        prefix: "gold_"
        required_tags: ["tested", "documented"]
      - type: require_meta_field
        field: "owner"
        applies_to: "gold_*"
"""


# ==============================================================================
# Epic 3C: Data Contract Configuration
# ==============================================================================


class AutoGenerationConfig(BaseModel):
    """Configuration for automatic contract generation from output_ports.

    Controls how contracts are auto-generated when no explicit datacontract.yaml
    exists but floe.yaml defines output_ports.

    Attributes:
        enabled: Enable auto-generation of contracts. Default: True
        include_descriptions: Include column descriptions from port schema. Default: True
        default_classification: Default classification for generated fields. Default: "internal"

    Example:
        >>> config = AutoGenerationConfig(
        ...     enabled=True,
        ...     default_classification="confidential"
        ... )

    See Also:
        - spec.md: FR-003, FR-004
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    enabled: bool = Field(
        default=True,
        description="Enable auto-generation of contracts from output_ports",
    )
    include_descriptions: bool = Field(
        default=True,
        description="Include column descriptions from port schema in generated contract",
    )
    default_classification: Literal[
        "public", "internal", "confidential", "pii", "phi", "sensitive", "restricted"
    ] = Field(
        default="internal",
        description="Default classification for auto-generated fields",
    )


class DriftDetectionConfig(BaseModel):
    """Configuration for schema drift detection between contract and actual table.

    Controls how drift detection compares the contract schema against the actual
    Iceberg table schema via IcebergTableManager.

    Attributes:
        enabled: Enable drift detection. Default: True
        fail_on_type_mismatch: Fail on column type mismatches (FLOE-E530). Default: True
        fail_on_missing_column: Fail on columns in contract but not table (FLOE-E531). Default: True
        warn_on_extra_column: Warn on columns in table but not contract (FLOE-E532). Default: True

    Example:
        >>> config = DriftDetectionConfig(
        ...     enabled=True,
        ...     fail_on_type_mismatch=True,
        ...     warn_on_extra_column=False  # Ignore extra columns
        ... )

    See Also:
        - spec.md: FR-021 through FR-025
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    enabled: bool = Field(
        default=True,
        description="Enable schema drift detection against actual Iceberg table",
    )
    fail_on_type_mismatch: bool = Field(
        default=True,
        description="Fail on column type mismatches (FLOE-E530)",
    )
    fail_on_missing_column: bool = Field(
        default=True,
        description="Fail on columns in contract but not in table (FLOE-E531)",
    )
    warn_on_extra_column: bool = Field(
        default=True,
        description="Warn on columns in table but not in contract (FLOE-E532)",
    )


class DataContractsConfig(BaseModel):
    """Configuration for data contract validation in governance block.

    Defines how data contracts are validated, including enforcement level,
    auto-generation settings, drift detection, and inheritance mode.

    Attributes:
        enforcement: Enforcement level (off, warn, strict). Default: "warn"
        auto_generation: Auto-generation settings for contracts from output_ports.
        drift_detection: Schema drift detection settings.
        inheritance_mode: Contract inheritance mode. Default: "merge"

    Example:
        >>> config = DataContractsConfig(
        ...     enforcement="strict",
        ...     auto_generation=AutoGenerationConfig(enabled=True),
        ...     drift_detection=DriftDetectionConfig(enabled=True),
        ... )

    Strength Ordering (for inheritance):
        - enforcement: strict (3) > warn (2) > off (1)
        - Child cannot disable auto_generation or drift_detection if parent enables

    See Also:
        - spec.md: FR-036, FR-037, FR-038
        - data-model.md: DataContractsConfig entity specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "enforcement": "strict",
                    "auto_generation": {"enabled": True},
                    "drift_detection": {"enabled": True, "fail_on_type_mismatch": True},
                    "inheritance_mode": "merge",
                }
            ]
        },
    )

    enforcement: Literal["off", "warn", "strict"] = Field(
        default="warn",
        description="Enforcement level for data contract validation (strict > warn > off)",
    )
    auto_generation: AutoGenerationConfig = Field(
        default_factory=AutoGenerationConfig,
        description="Auto-generation settings for contracts from output_ports",
    )
    drift_detection: DriftDetectionConfig = Field(
        default_factory=DriftDetectionConfig,
        description="Schema drift detection settings",
    )
    inheritance_mode: Literal["merge", "override", "strict"] = Field(
        default="merge",
        description=(
            "Contract inheritance mode: "
            "'merge' (child extends parent), "
            "'override' (child replaces parent), "
            "'strict' (child must match parent exactly)"
        ),
    )


# Valid policy types for override filtering
# Epic 3C: Added "data_contract" for data contract validation
VALID_POLICY_TYPES = frozenset({
    "naming",
    "coverage",
    "documentation",
    "semantic",
    "custom",
    "data_contract",  # Epic 3C: Data contract validation
})


class PolicyOverride(BaseModel):
    """Override for policy enforcement to support gradual migration.

    PolicyOverride allows specific models or patterns to have reduced enforcement
    (downgrade errors to warnings) or be excluded from validation entirely.
    Supports expiration dates for time-limited exceptions.

    Attributes:
        pattern: Glob pattern matching model names (e.g., "legacy_*").
        action: Override action - "downgrade" (error→warning) or "exclude" (skip).
        reason: Audit trail explaining why override exists (required).
        expires: Optional expiration date (ISO-8601). Override ignored after this date.
        policy_types: Limit override to specific policies (default: all).

    Example:
        >>> override = PolicyOverride(
        ...     pattern="legacy_*",
        ...     action="downgrade",
        ...     reason="Legacy models being migrated - tracked in JIRA-123",
        ...     expires=date(2026, 6, 1),
        ... )

    Business Rules:
        - reason is required for audit compliance (non-empty string)
        - expired overrides are logged as warnings but ignored
        - policy_types values must be valid policy categories

    See Also:
        - data-model.md: PolicyOverride entity specification
        - spec.md: FR-011 through FR-015
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "pattern": "legacy_*",
                    "action": "downgrade",
                    "reason": "Legacy models being migrated",
                    "expires": "2026-06-01",
                },
                {
                    "pattern": "test_*",
                    "action": "exclude",
                    "reason": "Test fixtures exempt from policy",
                },
            ]
        },
    )

    pattern: str = Field(
        ...,
        min_length=1,
        description="Glob pattern matching model names (e.g., 'legacy_*', 'test_*')",
    )
    action: Literal["downgrade", "exclude"] = Field(
        ...,
        description="Override action: 'downgrade' (error→warning) or 'exclude' (skip validation)",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Audit trail explaining why this override exists",
    )
    expires: date | None = Field(
        default=None,
        description="Expiration date (ISO-8601). Override ignored after this date.",
    )
    policy_types: list[str] | None = Field(
        default=None,
        description="Limit override to specific policy types (default: all policies)",
    )

    @field_validator("policy_types")
    @classmethod
    def validate_policy_types(cls, v: list[str] | None) -> list[str] | None:
        """Validate that policy_types contains only valid policy type names.

        Args:
            v: List of policy type names or None.

        Returns:
            Validated list or None.

        Raises:
            ValueError: If any policy type is not valid.
        """
        if v is None:
            return v
        invalid = set(v) - VALID_POLICY_TYPES
        if invalid:
            msg = (
                f"Invalid policy_types: {sorted(invalid)}. "
                f"Valid values are: {sorted(VALID_POLICY_TYPES)}"
            )
            raise ValueError(msg)
        return v


__all__ = [
    "LayerThresholds",
    "NamingConfig",
    "QualityGatesConfig",
    # Epic 3B: Custom rule types
    "RequireTagsForPrefix",
    "RequireMetaField",
    "RequireTestsOfType",
    "CustomRule",
    # Epic 3B: Policy override
    "PolicyOverride",
    "VALID_POLICY_TYPES",
    # Epic 3C: Data contract configuration
    "AutoGenerationConfig",
    "DriftDetectionConfig",
    "DataContractsConfig",
]
