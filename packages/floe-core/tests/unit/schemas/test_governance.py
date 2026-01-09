"""Unit tests for governance and security policy validation.

Tests for security policy enforcement during inheritance:
- Policy immutability (cannot weaken parent policies)
- Policy strengthening (allowed)

Task: T028, T029
Requirements: FR-017
"""

from __future__ import annotations

import pytest


class TestSecurityPolicyImmutability:
    """Tests for security policy immutability (T028)."""

    @pytest.mark.requirement("001-FR-017")
    def test_cannot_weaken_pii_encryption(self) -> None:
        """Test that child cannot weaken pii_encryption from required to optional.

        Given an enterprise manifest with pii_encryption=required,
        When a domain manifest attempts to set pii_encryption=optional,
        Then the system rejects with "Cannot weaken security policy" error.
        """
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        parent_governance = GovernanceConfig(
            pii_encryption="required",
        )
        child_governance = GovernanceConfig(
            pii_encryption="optional",  # Attempting to weaken
        )

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent_governance, child_governance)

        assert "pii_encryption" in str(exc_info.value).lower()
        assert "weaken" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-017")
    def test_cannot_weaken_audit_logging(self) -> None:
        """Test that child cannot weaken audit_logging from enabled to disabled.

        Given an enterprise manifest with audit_logging=enabled,
        When a domain manifest attempts to set audit_logging=disabled,
        Then the system rejects the configuration.
        """
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        parent_governance = GovernanceConfig(
            audit_logging="enabled",
        )
        child_governance = GovernanceConfig(
            audit_logging="disabled",  # Attempting to weaken
        )

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent_governance, child_governance)

        assert "audit_logging" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-017")
    def test_cannot_weaken_policy_enforcement_level(self) -> None:
        """Test that child cannot weaken policy_enforcement_level."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        # Test strict → warn (weakening)
        parent_governance = GovernanceConfig(
            policy_enforcement_level="strict",
        )
        child_governance = GovernanceConfig(
            policy_enforcement_level="warn",  # Attempting to weaken
        )

        with pytest.raises(SecurityPolicyViolationError):
            validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_cannot_weaken_policy_enforcement_strict_to_off(self) -> None:
        """Test that child cannot weaken policy_enforcement_level from strict to off."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        parent_governance = GovernanceConfig(
            policy_enforcement_level="strict",
        )
        child_governance = GovernanceConfig(
            policy_enforcement_level="off",  # Attempting major weakening
        )

        with pytest.raises(SecurityPolicyViolationError):
            validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_cannot_weaken_policy_enforcement_warn_to_off(self) -> None:
        """Test that child cannot weaken policy_enforcement_level from warn to off."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        parent_governance = GovernanceConfig(
            policy_enforcement_level="warn",
        )
        child_governance = GovernanceConfig(
            policy_enforcement_level="off",  # Attempting to weaken
        )

        with pytest.raises(SecurityPolicyViolationError):
            validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_cannot_reduce_data_retention_days(self) -> None:
        """Test that child cannot reduce data_retention_days (higher is stricter)."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import (
            SecurityPolicyViolationError,
            validate_security_policy_not_weakened,
        )

        parent_governance = GovernanceConfig(
            data_retention_days=90,
        )
        child_governance = GovernanceConfig(
            data_retention_days=30,  # Attempting to reduce retention
        )

        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            validate_security_policy_not_weakened(parent_governance, child_governance)

        assert "data_retention" in str(exc_info.value).lower()


class TestSecurityPolicyStrengthening:
    """Tests for security policy strengthening (T029)."""

    @pytest.mark.requirement("001-FR-017")
    def test_can_strengthen_pii_encryption(self) -> None:
        """Test that child can strengthen pii_encryption from optional to required.

        Given an enterprise manifest with pii_encryption=optional,
        When a domain manifest sets pii_encryption=required,
        Then the configuration is accepted.
        """
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent_governance = GovernanceConfig(
            pii_encryption="optional",
        )
        child_governance = GovernanceConfig(
            pii_encryption="required",  # Strengthening
        )

        # Should not raise
        validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_can_strengthen_audit_logging(self) -> None:
        """Test that child can strengthen audit_logging from disabled to enabled."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent_governance = GovernanceConfig(
            audit_logging="disabled",
        )
        child_governance = GovernanceConfig(
            audit_logging="enabled",  # Strengthening
        )

        # Should not raise
        validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_can_strengthen_policy_enforcement_level(self) -> None:
        """Test that child can strengthen policy_enforcement_level."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        # Test warn → strict (strengthening)
        parent_governance = GovernanceConfig(
            policy_enforcement_level="warn",
        )
        child_governance = GovernanceConfig(
            policy_enforcement_level="strict",  # Strengthening
        )

        # Should not raise
        validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_can_strengthen_policy_enforcement_off_to_warn(self) -> None:
        """Test that child can strengthen policy_enforcement_level from off to warn."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent_governance = GovernanceConfig(
            policy_enforcement_level="off",
        )
        child_governance = GovernanceConfig(
            policy_enforcement_level="warn",  # Strengthening
        )

        # Should not raise
        validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_can_maintain_same_level(self) -> None:
        """Test that child can maintain the same security level as parent.

        Given an enterprise manifest with policy_enforcement_level=strict,
        When a domain manifest sets policy_enforcement_level=strict (same level),
        Then the configuration is accepted.
        """
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent_governance = GovernanceConfig(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
        )
        child_governance = GovernanceConfig(
            pii_encryption="required",  # Same
            audit_logging="enabled",  # Same
            policy_enforcement_level="strict",  # Same
            data_retention_days=90,  # Same
        )

        # Should not raise
        validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_can_increase_data_retention_days(self) -> None:
        """Test that child can increase data_retention_days (higher is stricter)."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent_governance = GovernanceConfig(
            data_retention_days=30,
        )
        child_governance = GovernanceConfig(
            data_retention_days=90,  # Increasing retention (stricter)
        )

        # Should not raise
        validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_child_can_add_policy_when_parent_has_none(self) -> None:
        """Test that child can add a policy when parent has None."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent_governance = GovernanceConfig()  # All None
        child_governance = GovernanceConfig(
            pii_encryption="required",
            audit_logging="enabled",
        )

        # Should not raise - adding policy is always allowed
        validate_security_policy_not_weakened(parent_governance, child_governance)

    @pytest.mark.requirement("001-FR-017")
    def test_child_can_keep_none_when_parent_has_none(self) -> None:
        """Test that child can keep None when parent has None."""
        from floe_core.schemas import GovernanceConfig
        from floe_core.schemas.validation import validate_security_policy_not_weakened

        parent_governance = GovernanceConfig()  # All None
        child_governance = GovernanceConfig()  # All None

        # Should not raise
        validate_security_policy_not_weakened(parent_governance, child_governance)


class TestPolicyStrengthOrdering:
    """Tests for policy strength ordering constants."""

    @pytest.mark.requirement("001-FR-017")
    def test_pii_encryption_strength_ordering(self) -> None:
        """Test PII encryption strength ordering: required > optional."""
        from floe_core.schemas.validation import PII_ENCRYPTION_STRENGTH

        assert PII_ENCRYPTION_STRENGTH["required"] > PII_ENCRYPTION_STRENGTH["optional"]

    @pytest.mark.requirement("001-FR-017")
    def test_audit_logging_strength_ordering(self) -> None:
        """Test audit logging strength ordering: enabled > disabled."""
        from floe_core.schemas.validation import AUDIT_LOGGING_STRENGTH

        assert AUDIT_LOGGING_STRENGTH["enabled"] > AUDIT_LOGGING_STRENGTH["disabled"]

    @pytest.mark.requirement("001-FR-017")
    def test_policy_level_strength_ordering(self) -> None:
        """Test policy enforcement level ordering: strict > warn > off."""
        from floe_core.schemas.validation import POLICY_LEVEL_STRENGTH

        assert POLICY_LEVEL_STRENGTH["strict"] > POLICY_LEVEL_STRENGTH["warn"]
        assert POLICY_LEVEL_STRENGTH["warn"] > POLICY_LEVEL_STRENGTH["off"]
        assert POLICY_LEVEL_STRENGTH["strict"] > POLICY_LEVEL_STRENGTH["off"]
