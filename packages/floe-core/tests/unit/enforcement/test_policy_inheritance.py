"""Unit tests for policy inheritance strengthening rules.

Tests for validate_security_policy_not_weakened() with new NamingConfig
and QualityGatesConfig fields. Following TDD: these tests are written FIRST
and will FAIL until the validation functions are extended in T015-T017.

Task: T009
Requirements: FR-017 (Policy Immutability), US2 (Policy Configuration via Manifest)
"""

from __future__ import annotations

import pytest

from floe_core.schemas.validation import SecurityPolicyViolationError


class TestNamingConfigInheritance:
    """Tests for NamingConfig inheritance strengthening rules (T009).

    Strength ordering for naming.enforcement: strict (3) > warn (2) > off (1)
    """

    @pytest.mark.requirement("3A-US2-FR017")
    def test_naming_enforcement_can_strengthen(self) -> None:
        """Test that naming.enforcement can be strengthened (off→warn, warn→strict)."""
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(naming=NamingConfig(enforcement="warn"))
        child = GovernanceConfig(naming=NamingConfig(enforcement="strict"))

        # Should not raise - strengthening is allowed
        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_naming_enforcement_cannot_weaken(self) -> None:
        """Test that naming.enforcement cannot be weakened (strict→warn→off)."""
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(naming=NamingConfig(enforcement="strict"))
        child = GovernanceConfig(naming=NamingConfig(enforcement="warn"))

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert exc_info.value.field == "naming.enforcement"
        assert exc_info.value.parent_value == "strict"
        assert exc_info.value.child_value == "warn"

    @pytest.mark.requirement("3A-US2-FR017")
    def test_naming_enforcement_can_stay_same(self) -> None:
        """Test that naming.enforcement can stay the same level."""
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(naming=NamingConfig(enforcement="warn"))
        child = GovernanceConfig(naming=NamingConfig(enforcement="warn"))

        # Should not raise - same level is allowed
        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_naming_enforcement_off_to_warn_allowed(self) -> None:
        """Test off→warn strengthening is allowed."""
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(naming=NamingConfig(enforcement="off"))
        child = GovernanceConfig(naming=NamingConfig(enforcement="warn"))

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_naming_enforcement_off_to_strict_allowed(self) -> None:
        """Test off→strict strengthening is allowed."""
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(naming=NamingConfig(enforcement="off"))
        child = GovernanceConfig(naming=NamingConfig(enforcement="strict"))

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_naming_none_parent_allows_any_child(self) -> None:
        """Test that None parent naming allows any child naming."""
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(naming=None)
        child = GovernanceConfig(naming=NamingConfig(enforcement="strict"))

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_naming_none_child_when_parent_set(self) -> None:
        """Test that None child naming when parent is set is allowed.

        Note: This is allowed because None means "inherit from parent"
        not "weaken to nothing".
        """
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(naming=NamingConfig(enforcement="strict"))
        child = GovernanceConfig(naming=None)

        # Should not raise - None means inherit
        validate_security_policy_not_weakened(parent, child)


class TestQualityGatesInheritance:
    """Tests for QualityGatesConfig inheritance strengthening rules (T009).

    Strength ordering:
    - minimum_test_coverage: higher is stricter
    - require_descriptions: True > False
    - require_column_descriptions: True > False
    - block_on_failure: True > False (cannot relax)
    """

    @pytest.mark.requirement("3A-US2-FR017")
    def test_coverage_can_be_increased(self) -> None:
        """Test that minimum_test_coverage can be increased."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(quality_gates=QualityGatesConfig(minimum_test_coverage=80))
        child = GovernanceConfig(quality_gates=QualityGatesConfig(minimum_test_coverage=90))

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_coverage_cannot_be_decreased(self) -> None:
        """Test that minimum_test_coverage cannot be decreased."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(quality_gates=QualityGatesConfig(minimum_test_coverage=80))
        child = GovernanceConfig(quality_gates=QualityGatesConfig(minimum_test_coverage=60))

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert "minimum_test_coverage" in exc_info.value.field
        assert exc_info.value.parent_value == 80
        assert exc_info.value.child_value == 60

    @pytest.mark.requirement("3A-US2-FR017")
    def test_require_descriptions_can_enable(self) -> None:
        """Test that require_descriptions can be enabled (False→True)."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(quality_gates=QualityGatesConfig(require_descriptions=False))
        child = GovernanceConfig(quality_gates=QualityGatesConfig(require_descriptions=True))

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_require_descriptions_cannot_disable(self) -> None:
        """Test that require_descriptions cannot be disabled (True→False)."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(quality_gates=QualityGatesConfig(require_descriptions=True))
        child = GovernanceConfig(quality_gates=QualityGatesConfig(require_descriptions=False))

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert "require_descriptions" in exc_info.value.field

    @pytest.mark.requirement("3A-US2-FR017")
    def test_require_column_descriptions_can_enable(self) -> None:
        """Test that require_column_descriptions can be enabled."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            quality_gates=QualityGatesConfig(require_column_descriptions=False)
        )
        child = GovernanceConfig(quality_gates=QualityGatesConfig(require_column_descriptions=True))

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_require_column_descriptions_cannot_disable(self) -> None:
        """Test that require_column_descriptions cannot be disabled."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            quality_gates=QualityGatesConfig(require_column_descriptions=True)
        )
        child = GovernanceConfig(
            quality_gates=QualityGatesConfig(require_column_descriptions=False)
        )

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert "require_column_descriptions" in exc_info.value.field

    @pytest.mark.requirement("3A-US2-FR017")
    def test_block_on_failure_cannot_relax(self) -> None:
        """Test that block_on_failure cannot be relaxed (True→False)."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(quality_gates=QualityGatesConfig(block_on_failure=True))
        child = GovernanceConfig(quality_gates=QualityGatesConfig(block_on_failure=False))

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert "block_on_failure" in exc_info.value.field

    @pytest.mark.requirement("3A-US2-FR017")
    def test_quality_gates_none_parent_allows_any_child(self) -> None:
        """Test that None parent quality_gates allows any child."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(quality_gates=None)
        child = GovernanceConfig(quality_gates=QualityGatesConfig(minimum_test_coverage=100))

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_quality_gates_none_child_when_parent_set(self) -> None:
        """Test that None child quality_gates when parent is set is allowed."""
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(quality_gates=QualityGatesConfig(minimum_test_coverage=80))
        child = GovernanceConfig(quality_gates=None)

        # None means inherit, not weaken
        validate_security_policy_not_weakened(parent, child)


class TestLayerThresholdsInheritance:
    """Tests for LayerThresholds inheritance within QualityGatesConfig (T009).

    Layer thresholds follow same rule: child cannot be lower than parent.
    """

    @pytest.mark.requirement("3A-US2-FR017")
    def test_layer_thresholds_can_be_increased(self) -> None:
        """Test that layer thresholds can be increased."""
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            quality_gates=QualityGatesConfig(
                layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=90)
            )
        )
        child = GovernanceConfig(
            quality_gates=QualityGatesConfig(
                layer_thresholds=LayerThresholds(bronze=60, silver=90, gold=100)
            )
        )

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_layer_threshold_bronze_cannot_decrease(self) -> None:
        """Test that bronze threshold cannot be decreased."""
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            quality_gates=QualityGatesConfig(layer_thresholds=LayerThresholds(bronze=50))
        )
        child = GovernanceConfig(
            quality_gates=QualityGatesConfig(layer_thresholds=LayerThresholds(bronze=30))
        )

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert "bronze" in exc_info.value.field.lower()

    @pytest.mark.requirement("3A-US2-FR017")
    def test_layer_threshold_silver_cannot_decrease(self) -> None:
        """Test that silver threshold cannot be decreased."""
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            quality_gates=QualityGatesConfig(layer_thresholds=LayerThresholds(silver=80))
        )
        child = GovernanceConfig(
            quality_gates=QualityGatesConfig(layer_thresholds=LayerThresholds(silver=70))
        )

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert "silver" in exc_info.value.field.lower()

    @pytest.mark.requirement("3A-US2-FR017")
    def test_layer_threshold_gold_cannot_decrease(self) -> None:
        """Test that gold threshold cannot be decreased."""
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            quality_gates=QualityGatesConfig(layer_thresholds=LayerThresholds(gold=100))
        )
        child = GovernanceConfig(
            quality_gates=QualityGatesConfig(layer_thresholds=LayerThresholds(gold=90))
        )

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert "gold" in exc_info.value.field.lower()


class TestCombinedInheritance:
    """Tests for combined inheritance with both existing and new fields (T009)."""

    @pytest.mark.requirement("3A-US2-FR017")
    def test_all_fields_strengthened(self) -> None:
        """Test strengthening all fields at once."""
        from floe_core.schemas.governance import (
            LayerThresholds,
            NamingConfig,
            QualityGatesConfig,
        )
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            pii_encryption="optional",
            audit_logging="disabled",
            policy_enforcement_level="warn",
            data_retention_days=30,
            naming=NamingConfig(enforcement="warn"),
            quality_gates=QualityGatesConfig(
                minimum_test_coverage=60,
                layer_thresholds=LayerThresholds(bronze=40, silver=60, gold=80),
            ),
        )
        child = GovernanceConfig(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
            naming=NamingConfig(enforcement="strict"),
            quality_gates=QualityGatesConfig(
                minimum_test_coverage=80,
                layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=100),
            ),
        )

        validate_security_policy_not_weakened(parent, child)

    @pytest.mark.requirement("3A-US2-FR017")
    def test_mixed_inheritance_one_weakened(self) -> None:
        """Test that even one weakened field raises error."""
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent = GovernanceConfig(
            pii_encryption="required",  # Will try to weaken this
            naming=NamingConfig(enforcement="warn"),  # This is fine
            quality_gates=QualityGatesConfig(minimum_test_coverage=80),  # This is fine
        )
        child = GovernanceConfig(
            pii_encryption="optional",  # WEAKENED
            naming=NamingConfig(enforcement="strict"),  # Strengthened
            quality_gates=QualityGatesConfig(minimum_test_coverage=90),  # Strengthened
        )

        # Even though naming and quality_gates are strengthened,
        # pii_encryption is weakened so it should fail
        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent, child)

        assert exc_info.value.field == "pii_encryption"
