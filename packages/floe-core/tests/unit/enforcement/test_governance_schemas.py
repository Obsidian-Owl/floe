"""Unit tests for governance schema models.

Tests for NamingConfig, QualityGatesConfig, LayerThresholds, and GovernanceConfig
extension. Following TDD: these tests are written FIRST and will FAIL until
the models are implemented in T011-T014.

Task: T005-T008
Requirements: FR-013 (Required Fields), US2 (Policy Configuration via Manifest)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestNamingConfig:
    """Tests for NamingConfig model (T005).

    NamingConfig defines naming convention validation settings.
    See: data-model.md, governance-schema.json
    """

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_defaults(self) -> None:
        """Test NamingConfig has correct default values.

        Default values:
        - enforcement: "warn"
        - pattern: "medallion"
        - custom_patterns: None
        """
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig()
        assert config.enforcement == "warn"
        assert config.pattern == "medallion"
        assert config.custom_patterns is None

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_valid_enforcement_values(self) -> None:
        """Test NamingConfig accepts valid enforcement values."""
        from floe_core.schemas.governance import NamingConfig

        for enforcement in ["off", "warn", "strict"]:
            config = NamingConfig(enforcement=enforcement)
            assert config.enforcement == enforcement

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_invalid_enforcement_rejected(self) -> None:
        """Test NamingConfig rejects invalid enforcement values."""
        from floe_core.schemas.governance import NamingConfig

        with pytest.raises(ValidationError, match="enforcement"):
            NamingConfig(enforcement="invalid")

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_valid_pattern_values(self) -> None:
        """Test NamingConfig accepts valid pattern values."""
        from floe_core.schemas.governance import NamingConfig

        for pattern in ["medallion", "kimball", "custom"]:
            if pattern == "custom":
                # custom pattern requires custom_patterns to be provided
                config = NamingConfig(pattern=pattern, custom_patterns=["^test_.*$"])
            else:
                config = NamingConfig(pattern=pattern)
            assert config.pattern == pattern

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_invalid_pattern_rejected(self) -> None:
        """Test NamingConfig rejects invalid pattern values."""
        from floe_core.schemas.governance import NamingConfig

        with pytest.raises(ValidationError, match="pattern"):
            NamingConfig(pattern="invalid")

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_custom_pattern_requires_patterns(self) -> None:
        """Test that pattern=custom requires custom_patterns to be set.

        Business rule: If pattern="custom", custom_patterns MUST be provided.
        """
        from floe_core.schemas.governance import NamingConfig

        with pytest.raises(ValidationError, match="custom_patterns"):
            NamingConfig(pattern="custom", custom_patterns=None)

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_custom_pattern_with_patterns(self) -> None:
        """Test NamingConfig accepts custom pattern with patterns list."""
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(
            pattern="custom",
            custom_patterns=["^raw_.*$", "^clean_.*$", "^agg_.*$"],
        )
        assert config.pattern == "custom"
        assert config.custom_patterns == ["^raw_.*$", "^clean_.*$", "^agg_.*$"]

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_non_custom_ignores_patterns(self) -> None:
        """Test that non-custom patterns ignore custom_patterns if provided.

        Business rule: If pattern!="custom", custom_patterns is ignored.
        """
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(
            pattern="medallion",
            custom_patterns=["^ignored_.*$"],  # Should be ignored
        )
        assert config.pattern == "medallion"
        # The patterns are stored but not used for validation
        assert config.custom_patterns == ["^ignored_.*$"]

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_frozen(self) -> None:
        """Test NamingConfig is immutable (frozen=True)."""
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig()
        with pytest.raises((AttributeError, ValidationError)):
            config.enforcement = "strict"  # type: ignore[misc]

    @pytest.mark.requirement("3A-US2-FR013")
    def test_naming_config_forbids_extra_fields(self) -> None:
        """Test NamingConfig rejects unknown fields (extra=forbid)."""
        from floe_core.schemas.governance import NamingConfig

        with pytest.raises(ValidationError, match="extra_field"):
            NamingConfig(extra_field="value")  # type: ignore[call-arg]


class TestQualityGatesConfig:
    """Tests for QualityGatesConfig model (T006).

    QualityGatesConfig defines quality gate thresholds.
    See: data-model.md, governance-schema.json
    """

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_defaults(self) -> None:
        """Test QualityGatesConfig has correct default values."""
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig()
        assert config.minimum_test_coverage == 80
        assert config.require_descriptions is False
        assert config.require_column_descriptions is False
        assert config.block_on_failure is True
        assert config.layer_thresholds is None
        assert config.zero_column_coverage_behavior == "report_na"

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_coverage_range(self) -> None:
        """Test minimum_test_coverage accepts values 0-100."""
        from floe_core.schemas.governance import QualityGatesConfig

        # Valid values
        for coverage in [0, 50, 80, 100]:
            config = QualityGatesConfig(minimum_test_coverage=coverage)
            assert config.minimum_test_coverage == coverage

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_coverage_below_zero_rejected(self) -> None:
        """Test minimum_test_coverage rejects values below 0."""
        from floe_core.schemas.governance import QualityGatesConfig

        with pytest.raises(ValidationError, match="minimum_test_coverage"):
            QualityGatesConfig(minimum_test_coverage=-1)

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_coverage_above_hundred_rejected(self) -> None:
        """Test minimum_test_coverage rejects values above 100."""
        from floe_core.schemas.governance import QualityGatesConfig

        with pytest.raises(ValidationError, match="minimum_test_coverage"):
            QualityGatesConfig(minimum_test_coverage=101)

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_boolean_fields(self) -> None:
        """Test boolean fields accept True/False."""
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            require_descriptions=True,
            require_column_descriptions=True,
            block_on_failure=False,
        )
        assert config.require_descriptions is True
        assert config.require_column_descriptions is True
        assert config.block_on_failure is False

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_zero_column_behavior_values(self) -> None:
        """Test zero_column_coverage_behavior accepts valid values."""
        from floe_core.schemas.governance import QualityGatesConfig

        for behavior in ["report_100_percent", "report_na"]:
            config = QualityGatesConfig(zero_column_coverage_behavior=behavior)
            assert config.zero_column_coverage_behavior == behavior

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_zero_column_behavior_invalid_rejected(self) -> None:
        """Test zero_column_coverage_behavior rejects invalid values."""
        from floe_core.schemas.governance import QualityGatesConfig

        with pytest.raises(ValidationError, match="zero_column_coverage_behavior"):
            QualityGatesConfig(zero_column_coverage_behavior="invalid")

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_frozen(self) -> None:
        """Test QualityGatesConfig is immutable (frozen=True)."""
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig()
        with pytest.raises((AttributeError, ValidationError)):
            config.minimum_test_coverage = 50  # type: ignore[misc]

    @pytest.mark.requirement("3A-US2-FR013")
    def test_quality_gates_forbids_extra_fields(self) -> None:
        """Test QualityGatesConfig rejects unknown fields (extra=forbid)."""
        from floe_core.schemas.governance import QualityGatesConfig

        with pytest.raises(ValidationError, match="extra_field"):
            QualityGatesConfig(extra_field="value")  # type: ignore[call-arg]


class TestLayerThresholds:
    """Tests for LayerThresholds model (T007).

    LayerThresholds defines per-layer coverage thresholds.
    See: data-model.md, governance-schema.json
    """

    @pytest.mark.requirement("3A-US2-FR013")
    def test_layer_thresholds_defaults(self) -> None:
        """Test LayerThresholds has correct default values."""
        from floe_core.schemas.governance import LayerThresholds

        thresholds = LayerThresholds()
        assert thresholds.bronze == 50
        assert thresholds.silver == 80
        assert thresholds.gold == 100

    @pytest.mark.requirement("3A-US2-FR013")
    def test_layer_thresholds_custom_values(self) -> None:
        """Test LayerThresholds accepts custom values 0-100."""
        from floe_core.schemas.governance import LayerThresholds

        thresholds = LayerThresholds(bronze=0, silver=50, gold=75)
        assert thresholds.bronze == 0
        assert thresholds.silver == 50
        assert thresholds.gold == 75

    @pytest.mark.requirement("3A-US2-FR013")
    def test_layer_thresholds_bronze_range_validation(self) -> None:
        """Test bronze threshold must be 0-100."""
        from floe_core.schemas.governance import LayerThresholds

        with pytest.raises(ValidationError, match="bronze"):
            LayerThresholds(bronze=-1)

        with pytest.raises(ValidationError, match="bronze"):
            LayerThresholds(bronze=101)

    @pytest.mark.requirement("3A-US2-FR013")
    def test_layer_thresholds_silver_range_validation(self) -> None:
        """Test silver threshold must be 0-100."""
        from floe_core.schemas.governance import LayerThresholds

        with pytest.raises(ValidationError, match="silver"):
            LayerThresholds(silver=-1)

        with pytest.raises(ValidationError, match="silver"):
            LayerThresholds(silver=101)

    @pytest.mark.requirement("3A-US2-FR013")
    def test_layer_thresholds_gold_range_validation(self) -> None:
        """Test gold threshold must be 0-100."""
        from floe_core.schemas.governance import LayerThresholds

        with pytest.raises(ValidationError, match="gold"):
            LayerThresholds(gold=-1)

        with pytest.raises(ValidationError, match="gold"):
            LayerThresholds(gold=101)

    @pytest.mark.requirement("3A-US2-FR013")
    def test_layer_thresholds_frozen(self) -> None:
        """Test LayerThresholds is immutable (frozen=True)."""
        from floe_core.schemas.governance import LayerThresholds

        thresholds = LayerThresholds()
        with pytest.raises((AttributeError, ValidationError)):
            thresholds.bronze = 25  # type: ignore[misc]


class TestGovernanceConfigExtension:
    """Tests for extended GovernanceConfig with naming and quality_gates (T008).

    GovernanceConfig is extended with new fields for naming and quality gates.
    See: data-model.md, governance-schema.json
    """

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_accepts_naming(self) -> None:
        """Test GovernanceConfig accepts naming field."""
        from floe_core.schemas.governance import NamingConfig

        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig(
            naming=NamingConfig(enforcement="strict", pattern="medallion"),
        )
        assert config.naming is not None
        assert config.naming.enforcement == "strict"
        assert config.naming.pattern == "medallion"

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_accepts_quality_gates(self) -> None:
        """Test GovernanceConfig accepts quality_gates field."""
        from floe_core.schemas.governance import QualityGatesConfig

        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig(
            quality_gates=QualityGatesConfig(
                minimum_test_coverage=90,
                require_descriptions=True,
            ),
        )
        assert config.quality_gates is not None
        assert config.quality_gates.minimum_test_coverage == 90
        assert config.quality_gates.require_descriptions is True

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_all_fields(self) -> None:
        """Test GovernanceConfig with all existing and new fields."""
        from floe_core.schemas.governance import (
            LayerThresholds,
            NamingConfig,
            QualityGatesConfig,
        )

        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig(
            # Existing fields
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
            # New fields
            naming=NamingConfig(enforcement="strict", pattern="medallion"),
            quality_gates=QualityGatesConfig(
                minimum_test_coverage=80,
                require_descriptions=True,
                layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=100),
            ),
        )
        assert config.pii_encryption == "required"
        assert config.audit_logging == "enabled"
        assert config.policy_enforcement_level == "strict"
        assert config.data_retention_days == 90
        assert config.naming is not None
        assert config.quality_gates is not None
        assert config.quality_gates.layer_thresholds is not None
        assert config.quality_gates.layer_thresholds.gold == 100

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_naming_defaults_to_none(self) -> None:
        """Test GovernanceConfig naming defaults to None (backward compatible)."""
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        assert config.naming is None

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_quality_gates_defaults_to_none(self) -> None:
        """Test GovernanceConfig quality_gates defaults to None (backward compatible)."""
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        assert config.quality_gates is None

    @pytest.mark.requirement("3A-US2-FR013")
    def test_governance_config_backward_compatible(self) -> None:
        """Test existing GovernanceConfig usage still works (backward compatibility).

        Existing code that doesn't use naming/quality_gates should work unchanged.
        """
        from floe_core.schemas.manifest import GovernanceConfig

        # Legacy usage without new fields
        config = GovernanceConfig(
            pii_encryption="required",
            audit_logging="enabled",
        )
        assert config.pii_encryption == "required"
        assert config.audit_logging == "enabled"
        # New fields default to None
        assert config.naming is None
        assert config.quality_gates is None
