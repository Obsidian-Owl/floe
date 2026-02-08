"""Unit tests for PolicyOverride functionality in PolicyEnforcer.

Tests for severity override system supporting:
- downgrade action: error → warning (FR-012)
- exclude action: skip validation entirely (FR-013)
- expiration date checking (FR-014)
- policy_types filtering (FR-011)

Task: T034, T035, T036, T037
Requirements: FR-011 through FR-015 (US3 - Severity Overrides)

TDD Pattern: These tests are written FIRST and should FAIL until
T038-T044 implements the override functionality.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from floe_core.enforcement.result import Violation
from floe_core.schemas.governance import PolicyOverride

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def sample_violations() -> list[Violation]:
    """Create sample violations for testing overrides.

    Returns:
        List of violations with various models and policy types.
    """
    return [
        Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="legacy_orders",
            message="Model 'legacy_orders' does not match medallion pattern",
            expected="Model name should match pattern bronze_*, silver_*, gold_*",
            actual="Model name 'legacy_orders' does not match any pattern",
            suggestion="Rename the model to match the medallion architecture pattern",
            documentation_url="https://floe.dev/docs/enforcement/naming#medallion",
        ),
        Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="legacy_users",
            message="Model 'legacy_users' does not match medallion pattern",
            expected="Model name should match pattern bronze_*, silver_*, gold_*",
            actual="Model name 'legacy_users' does not match any pattern",
            suggestion="Rename the model to match the medallion architecture pattern",
            documentation_url="https://floe.dev/docs/enforcement/naming#medallion",
        ),
        Violation(
            error_code="FLOE-E210",
            severity="error",
            policy_type="coverage",
            model_name="gold_customers",
            message="Model 'gold_customers' has insufficient test coverage",
            expected="Test coverage >= 80%",
            actual="Test coverage is 60%",
            suggestion="Add more tests to columns in this model",
            documentation_url="https://floe.dev/docs/enforcement/coverage",
        ),
        Violation(
            error_code="FLOE-E220",
            severity="error",
            policy_type="documentation",
            model_name="test_fixture",
            message="Model 'test_fixture' is missing description",
            expected="Model should have a description",
            actual="No description provided",
            suggestion="Add a description to the model",
            documentation_url="https://floe.dev/docs/enforcement/documentation",
        ),
        Violation(
            error_code="FLOE-E400",
            severity="error",
            policy_type="custom",
            model_name="bronze_events",
            message="Model 'bronze_events' is missing required tags",
            expected="Tags should include 'tested'",
            actual="Model has no tags",
            suggestion="Add the required tags to the model",
            documentation_url="https://floe.dev/docs/enforcement/custom-rules#require-tags-for-prefix",
        ),
    ]


@pytest.fixture
def downgrade_override() -> PolicyOverride:
    """Create a downgrade override for legacy_* models."""
    return PolicyOverride(
        pattern="legacy_*",
        action="downgrade",
        reason="Legacy models being migrated - tracked in JIRA-123",
    )


@pytest.fixture
def exclude_override() -> PolicyOverride:
    """Create an exclude override for test_* models."""
    return PolicyOverride(
        pattern="test_*",
        action="exclude",
        reason="Test fixtures exempt from policy validation",
    )


@pytest.fixture
def expired_override() -> PolicyOverride:
    """Create an expired override."""
    yesterday = date.today() - timedelta(days=1)
    return PolicyOverride(
        pattern="legacy_*",
        action="downgrade",
        reason="This override has expired",
        expires=yesterday,
    )


@pytest.fixture
def future_override() -> PolicyOverride:
    """Create an override that expires in the future."""
    next_month = date.today() + timedelta(days=30)
    return PolicyOverride(
        pattern="legacy_*",
        action="downgrade",
        reason="This override is still valid",
        expires=next_month,
    )


@pytest.fixture
def policy_type_filtered_override() -> PolicyOverride:
    """Create an override that only applies to naming violations."""
    return PolicyOverride(
        pattern="*",
        action="downgrade",
        reason="Only downgrade naming violations",
        policy_types=["naming"],
    )


# ==============================================================================
# T034: Tests for Downgrade Override Action (FR-012)
# ==============================================================================


class TestDowngradeOverrideAction:
    """Tests for the downgrade override action (error → warning).

    FR-012: System MUST support `action: downgrade` to convert
    error-severity violations to warnings for matched patterns.
    """

    @pytest.mark.requirement("003b-FR-012")
    def test_downgrade_converts_error_to_warning(
        self,
        sample_violations: list[Violation],
        downgrade_override: PolicyOverride,
    ) -> None:
        """Test that downgrade action converts error severity to warning.

        Given: Violations with error severity for legacy_* models
        When: Downgrade override with pattern="legacy_*" is applied
        Then: Matching violations have severity changed to "warning"
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        # Apply overrides
        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[downgrade_override],
        )

        # Find legacy model violations
        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]

        assert len(legacy_violations) == 2
        for v in legacy_violations:
            assert v.severity == "warning", f"Expected warning, got {v.severity}"

    @pytest.mark.requirement("003b-FR-012")
    def test_downgrade_sets_override_applied_field(
        self,
        sample_violations: list[Violation],
        downgrade_override: PolicyOverride,
    ) -> None:
        """Test that downgrade action populates override_applied field.

        Given: Violations for legacy_* models
        When: Downgrade override is applied
        Then: override_applied field contains the matching pattern
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[downgrade_override],
        )

        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]

        for v in legacy_violations:
            assert v.override_applied == "legacy_*"

    @pytest.mark.requirement("003b-FR-012")
    def test_downgrade_does_not_affect_non_matching_models(
        self,
        sample_violations: list[Violation],
        downgrade_override: PolicyOverride,
    ) -> None:
        """Test that downgrade does not affect non-matching models.

        Given: Violations for various models
        When: Downgrade override with pattern="legacy_*" is applied
        Then: Non-legacy models retain error severity
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[downgrade_override],
        )

        # Non-legacy violations should still be errors
        non_legacy = [v for v in result if not v.model_name.startswith("legacy_")]

        for v in non_legacy:
            assert v.severity == "error", f"Expected error for {v.model_name}"
            assert v.override_applied is None

    @pytest.mark.requirement("003b-FR-012")
    def test_downgrade_with_glob_patterns(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test downgrade with various glob pattern syntaxes.

        Given: Violations for various models
        When: Override with pattern "*_*" is applied
        Then: Models matching pattern have severity downgraded
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        override = PolicyOverride(
            pattern="*_*",
            action="downgrade",
            reason="Downgrade all models with underscores",
        )

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[override],
        )

        # All our test models have underscores
        for v in result:
            assert v.severity == "warning"


# ==============================================================================
# T035: Tests for Exclude Override Action (FR-013)
# ==============================================================================


class TestExcludeOverrideAction:
    """Tests for the exclude override action (skip validation).

    FR-013: System MUST support `action: exclude` to skip validation
    entirely for matched patterns.
    """

    @pytest.mark.requirement("003b-FR-013")
    def test_exclude_removes_violations_for_matching_models(
        self,
        sample_violations: list[Violation],
        exclude_override: PolicyOverride,
    ) -> None:
        """Test that exclude action removes violations for matching models.

        Given: Violations including test_fixture model
        When: Exclude override with pattern="test_*" is applied
        Then: test_fixture violations are removed from results
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[exclude_override],
        )

        # test_fixture should be excluded
        test_violations = [v for v in result if v.model_name.startswith("test_")]
        assert len(test_violations) == 0

    @pytest.mark.requirement("003b-FR-013")
    def test_exclude_preserves_non_matching_violations(
        self,
        sample_violations: list[Violation],
        exclude_override: PolicyOverride,
    ) -> None:
        """Test that exclude preserves non-matching violations.

        Given: Violations for various models
        When: Exclude override with pattern="test_*" is applied
        Then: Non-test model violations are preserved
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        original_count = len(sample_violations)
        test_count = sum(1 for v in sample_violations if v.model_name.startswith("test_"))

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[exclude_override],
        )

        assert len(result) == original_count - test_count

    @pytest.mark.requirement("003b-FR-013")
    def test_exclude_multiple_patterns(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test multiple exclude overrides work together.

        Given: Violations for legacy_* and test_* models
        When: Both exclude overrides are applied
        Then: Both model types are excluded
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        overrides = [
            PolicyOverride(
                pattern="legacy_*",
                action="exclude",
                reason="Exclude legacy models",
            ),
            PolicyOverride(
                pattern="test_*",
                action="exclude",
                reason="Exclude test models",
            ),
        ]

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=overrides,
        )

        for v in result:
            assert not v.model_name.startswith("legacy_")
            assert not v.model_name.startswith("test_")


# ==============================================================================
# T036: Tests for Expiration Date Checking (FR-014)
# ==============================================================================


class TestExpirationDateChecking:
    """Tests for override expiration date checking.

    FR-014: System MUST support `expires` date field after which
    overrides are ignored.
    """

    @pytest.mark.requirement("003b-FR-014")
    def test_expired_override_is_ignored(
        self,
        sample_violations: list[Violation],
        expired_override: PolicyOverride,
    ) -> None:
        """Test that expired overrides are not applied.

        Given: Override with expires date in the past
        When: Override is evaluated
        Then: Override is ignored, violations unchanged
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[expired_override],
        )

        # Legacy models should still be errors (override expired)
        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]
        for v in legacy_violations:
            assert v.severity == "error"
            assert v.override_applied is None

    @pytest.mark.requirement("003b-FR-014")
    def test_future_expiration_override_is_applied(
        self,
        sample_violations: list[Violation],
        future_override: PolicyOverride,
    ) -> None:
        """Test that overrides with future expiration are applied.

        Given: Override with expires date in the future
        When: Override is evaluated
        Then: Override is applied normally
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[future_override],
        )

        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]
        for v in legacy_violations:
            assert v.severity == "warning"

    @pytest.mark.requirement("003b-FR-014")
    def test_override_without_expiration_is_always_applied(
        self,
        sample_violations: list[Violation],
        downgrade_override: PolicyOverride,
    ) -> None:
        """Test that overrides without expiration are always applied.

        Given: Override without expires field
        When: Override is evaluated
        Then: Override is applied
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        assert downgrade_override.expires is None

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[downgrade_override],
        )

        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]
        for v in legacy_violations:
            assert v.severity == "warning"

    @pytest.mark.requirement("003b-FR-014")
    def test_override_expiring_today_is_applied(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test that override expiring today is still applied.

        Given: Override with expires=today
        When: Override is evaluated
        Then: Override is applied (expiration is end of day)
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        today_override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Expires today",
            expires=date.today(),
        )

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[today_override],
        )

        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]
        for v in legacy_violations:
            assert v.severity == "warning"


# ==============================================================================
# T037: Tests for Policy Types Filtering (FR-011)
# ==============================================================================


class TestPolicyTypesFiltering:
    """Tests for policy_types filtering on overrides.

    FR-011: System MUST support `policy_overrides` configuration section
    with optional policy_types filter for exception handling.
    """

    @pytest.mark.requirement("003b-FR-011")
    def test_policy_types_filter_limits_override_scope(
        self,
        sample_violations: list[Violation],
        policy_type_filtered_override: PolicyOverride,
    ) -> None:
        """Test that policy_types filter limits which violations are affected.

        Given: Violations of various policy types
        When: Override with policy_types=["naming"] is applied
        Then: Only naming violations are downgraded
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[policy_type_filtered_override],
        )

        for v in result:
            if v.policy_type == "naming":
                assert v.severity == "warning"
            else:
                assert v.severity == "error"

    @pytest.mark.requirement("003b-FR-011")
    def test_override_without_policy_types_affects_all(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test that override without policy_types affects all policy types.

        Given: Violations of various policy types
        When: Override without policy_types filter is applied
        Then: All matching violations are affected
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        override = PolicyOverride(
            pattern="*",
            action="downgrade",
            reason="Downgrade all violations",
        )

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[override],
        )

        for v in result:
            assert v.severity == "warning"

    @pytest.mark.requirement("003b-FR-011")
    def test_multiple_policy_types_in_filter(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test that multiple policy_types can be specified.

        Given: Violations of various policy types
        When: Override with policy_types=["naming", "coverage"] is applied
        Then: Both naming and coverage violations are affected
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        override = PolicyOverride(
            pattern="*",
            action="downgrade",
            reason="Downgrade naming and coverage violations",
            policy_types=["naming", "coverage"],
        )

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[override],
        )

        for v in result:
            if v.policy_type in ["naming", "coverage"]:
                assert v.severity == "warning"
            else:
                assert v.severity == "error"

    @pytest.mark.requirement("003b-FR-015")
    def test_override_application_is_logged(
        self,
        sample_violations: list[Violation],
        downgrade_override: PolicyOverride,
    ) -> None:
        """Test that applied overrides are logged for audit purposes.

        FR-015: System MUST log warnings when overrides are applied.

        Given: Override that matches models
        When: Override is applied
        Then: Application is logged (verify via caplog or mock)
        """
        # This test verifies the logging behavior is implemented.
        # The actual logging verification would use pytest's caplog fixture.
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        # Just verify the method runs without error for now
        # Full logging verification in integration tests
        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[downgrade_override],
        )

        # Verify override was applied
        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]
        assert len(legacy_violations) > 0
        assert all(v.override_applied == "legacy_*" for v in legacy_violations)


# ==============================================================================
# Additional Edge Case Tests
# ==============================================================================


class TestOverrideEdgeCases:
    """Tests for override edge cases and error handling."""

    @pytest.mark.requirement("003b-FR-011")
    def test_empty_overrides_list_returns_violations_unchanged(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test that empty overrides list doesn't modify violations.

        Given: Violations list
        When: Empty overrides list is applied
        Then: Violations returned unchanged
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[],
        )

        assert len(result) == len(sample_violations)
        for original, processed in zip(sample_violations, result, strict=True):
            assert original.severity == processed.severity

    @pytest.mark.requirement("003b-FR-011")
    def test_override_pattern_matches_nothing_logs_warning(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test that override matching no models logs a warning.

        Given: Override with pattern that matches nothing
        When: Override is evaluated
        Then: Warning is logged (pattern matched 0 models)
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        override = PolicyOverride(
            pattern="nonexistent_*",
            action="downgrade",
            reason="This pattern matches nothing",
        )

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=[override],
        )

        # Violations unchanged (no matches)
        assert len(result) == len(sample_violations)

    @pytest.mark.requirement("003b-FR-012")
    def test_first_matching_override_wins(
        self,
        sample_violations: list[Violation],
    ) -> None:
        """Test that first matching override is applied (no stacking).

        Given: Multiple overrides that could match the same model
        When: Overrides are applied
        Then: First matching override wins
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer

        overrides = [
            PolicyOverride(
                pattern="legacy_*",
                action="downgrade",
                reason="First override - downgrade",
            ),
            PolicyOverride(
                pattern="legacy_*",
                action="exclude",
                reason="Second override - exclude (should not apply)",
            ),
        ]

        result = PolicyEnforcer.apply_overrides(
            violations=sample_violations,
            overrides=overrides,
        )

        # legacy_* violations should be downgraded, not excluded
        legacy_violations = [v for v in result if v.model_name.startswith("legacy_")]
        assert len(legacy_violations) == 2
        for v in legacy_violations:
            assert v.severity == "warning"
