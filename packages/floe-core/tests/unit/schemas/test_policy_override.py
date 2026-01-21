"""Unit tests for PolicyOverride schema validation.

Tests for the PolicyOverride model:
- Valid override creation (downgrade and exclude actions)
- Expiration date validation
- Policy types filtering
- Invalid action handling
- Frozen model verification

Task: T012
Requirements: FR-011 through FR-015
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from floe_core.schemas.governance import VALID_POLICY_TYPES, PolicyOverride


class TestPolicyOverrideBasic:
    """Tests for basic PolicyOverride creation."""

    @pytest.mark.requirement("003b-FR-011")
    def test_valid_downgrade_override(self) -> None:
        """Test valid downgrade override creation.

        Given valid pattern, action='downgrade', and reason,
        When creating a PolicyOverride,
        Then the override is created with correct values.
        """
        override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Legacy models being migrated - tracked in JIRA-123",
        )

        assert override.pattern == "legacy_*"
        assert override.action == "downgrade"
        assert override.reason == "Legacy models being migrated - tracked in JIRA-123"
        assert override.expires is None  # Default
        assert override.policy_types is None  # Default (all policies)

    @pytest.mark.requirement("003b-FR-011")
    def test_valid_exclude_override(self) -> None:
        """Test valid exclude override creation.

        Given valid pattern, action='exclude', and reason,
        When creating a PolicyOverride,
        Then the override is created with correct values.
        """
        override = PolicyOverride(
            pattern="test_*",
            action="exclude",
            reason="Test fixtures exempt from policy validation",
        )

        assert override.pattern == "test_*"
        assert override.action == "exclude"
        assert override.reason == "Test fixtures exempt from policy validation"

    @pytest.mark.requirement("003b-FR-011")
    def test_override_with_glob_pattern(self) -> None:
        """Test override with various glob patterns.

        Given different glob pattern styles,
        When creating PolicyOverrides,
        Then all patterns are accepted.
        """
        patterns = [
            "legacy_*",
            "*_deprecated",
            "models/staging/*",
            "gold_*.sql",
            "**/*.sql",
        ]

        for pattern in patterns:
            override = PolicyOverride(
                pattern=pattern,
                action="downgrade",
                reason="Test pattern",
            )
            assert override.pattern == pattern


class TestPolicyOverrideExpiration:
    """Tests for PolicyOverride expiration date handling."""

    @pytest.mark.requirement("003b-FR-012")
    def test_override_with_expiration_date(self) -> None:
        """Test override with expiration date.

        Given a valid expiration date,
        When creating a PolicyOverride,
        Then the expiration date is stored correctly.
        """
        expiry = date(2026, 6, 1)
        override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Legacy models being migrated",
            expires=expiry,
        )

        assert override.expires == expiry

    @pytest.mark.requirement("003b-FR-012")
    def test_override_with_future_expiration(self) -> None:
        """Test override with future expiration date.

        Given a future expiration date,
        When creating a PolicyOverride,
        Then the override is valid.
        """
        future_date = date(2030, 12, 31)
        override = PolicyOverride(
            pattern="migration_*",
            action="exclude",
            reason="Long-term migration project",
            expires=future_date,
        )

        assert override.expires == future_date

    @pytest.mark.requirement("003b-FR-012")
    def test_override_with_past_expiration(self) -> None:
        """Test override with past expiration date is still valid at schema level.

        Given a past expiration date,
        When creating a PolicyOverride,
        Then the override is created (runtime checks expiration).

        Note: Expiration checking is done at runtime, not schema validation.
        """
        past_date = date(2020, 1, 1)
        override = PolicyOverride(
            pattern="old_*",
            action="downgrade",
            reason="Historical override",
            expires=past_date,
        )

        assert override.expires == past_date

    @pytest.mark.requirement("003b-FR-012")
    def test_override_with_string_date(self) -> None:
        """Test override with ISO-8601 date string.

        Given an ISO-8601 date string,
        When creating a PolicyOverride,
        Then the date is parsed correctly.
        """
        override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Test",
            expires="2026-06-01",  # type: ignore[arg-type]
        )

        assert override.expires == date(2026, 6, 1)


class TestPolicyOverridePolicyTypes:
    """Tests for PolicyOverride policy_types filtering."""

    @pytest.mark.requirement("003b-FR-013")
    def test_override_with_single_policy_type(self) -> None:
        """Test override with single policy type filter.

        Given a single policy type,
        When creating a PolicyOverride,
        Then the override applies only to that policy type.
        """
        override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Only naming conventions relaxed",
            policy_types=["naming"],
        )

        assert override.policy_types == ["naming"]

    @pytest.mark.requirement("003b-FR-013")
    def test_override_with_multiple_policy_types(self) -> None:
        """Test override with multiple policy type filters.

        Given multiple policy types,
        When creating a PolicyOverride,
        Then the override applies to all specified types.
        """
        override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Naming and coverage relaxed",
            policy_types=["naming", "coverage"],
        )

        assert override.policy_types == ["naming", "coverage"]

    @pytest.mark.requirement("003b-FR-013")
    def test_override_with_all_valid_policy_types(self) -> None:
        """Test override with all valid policy types.

        Given all valid policy types,
        When creating a PolicyOverride,
        Then all types are accepted.
        """
        all_types = list(VALID_POLICY_TYPES)
        override = PolicyOverride(
            pattern="test_*",
            action="exclude",
            reason="All policies exempted",
            policy_types=all_types,
        )

        assert set(override.policy_types or []) == VALID_POLICY_TYPES

    @pytest.mark.requirement("003b-FR-013")
    def test_override_with_invalid_policy_type_raises_error(self) -> None:
        """Test that invalid policy type raises ValidationError.

        Given an invalid policy type,
        When creating a PolicyOverride,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="legacy_*",
                action="downgrade",
                reason="Test",
                policy_types=["invalid_type"],
            )

        error_str = str(exc_info.value).lower()
        assert "invalid_type" in error_str or "policy_types" in error_str

    @pytest.mark.requirement("003b-FR-013")
    def test_override_with_mixed_valid_invalid_policy_types_raises_error(self) -> None:
        """Test that mixed valid/invalid policy types raises ValidationError.

        Given a mix of valid and invalid policy types,
        When creating a PolicyOverride,
        Then ValidationError is raised listing invalid types.
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="legacy_*",
                action="downgrade",
                reason="Test",
                policy_types=["naming", "invalid_policy", "coverage"],
            )

        error_str = str(exc_info.value).lower()
        assert "invalid_policy" in error_str

    @pytest.mark.requirement("003b-FR-013")
    def test_valid_policy_types_constant(self) -> None:
        """Test VALID_POLICY_TYPES constant contains expected values.

        Given VALID_POLICY_TYPES constant,
        When checking its contents,
        Then it contains all expected policy types.
        """
        expected = {"naming", "coverage", "documentation", "semantic", "custom"}
        assert VALID_POLICY_TYPES == expected


class TestPolicyOverrideValidation:
    """Tests for PolicyOverride validation constraints."""

    @pytest.mark.requirement("003b-FR-014")
    def test_override_missing_pattern_raises_error(self) -> None:
        """Test that missing pattern raises ValidationError.

        Given no pattern provided,
        When creating a PolicyOverride,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                action="downgrade",
                reason="Test",
            )  # type: ignore[call-arg]

        assert "pattern" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-014")
    def test_override_empty_pattern_raises_error(self) -> None:
        """Test that empty pattern raises ValidationError.

        Given an empty pattern string,
        When creating a PolicyOverride,
        Then ValidationError is raised for min_length constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="",
                action="downgrade",
                reason="Test",
            )

        assert "pattern" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-014")
    def test_override_missing_action_raises_error(self) -> None:
        """Test that missing action raises ValidationError.

        Given no action provided,
        When creating a PolicyOverride,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="legacy_*",
                reason="Test",
            )  # type: ignore[call-arg]

        assert "action" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-014")
    def test_override_invalid_action_raises_error(self) -> None:
        """Test that invalid action raises ValidationError.

        Given an invalid action value,
        When creating a PolicyOverride,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="legacy_*",
                action="invalid_action",  # type: ignore[arg-type]
                reason="Test",
            )

        error_str = str(exc_info.value).lower()
        assert "action" in error_str or "invalid_action" in error_str

    @pytest.mark.requirement("003b-FR-015")
    def test_override_missing_reason_raises_error(self) -> None:
        """Test that missing reason raises ValidationError.

        Given no reason provided,
        When creating a PolicyOverride,
        Then ValidationError is raised (audit trail required).
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="legacy_*",
                action="downgrade",
            )  # type: ignore[call-arg]

        assert "reason" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-015")
    def test_override_empty_reason_raises_error(self) -> None:
        """Test that empty reason raises ValidationError.

        Given an empty reason string,
        When creating a PolicyOverride,
        Then ValidationError is raised (audit trail required).
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="legacy_*",
                action="downgrade",
                reason="",
            )

        assert "reason" in str(exc_info.value).lower()


class TestPolicyOverrideFrozenModel:
    """Tests for PolicyOverride model immutability."""

    @pytest.mark.requirement("003b-FR-011")
    def test_policy_override_is_frozen(self) -> None:
        """Test that PolicyOverride is immutable.

        Given a PolicyOverride instance,
        When checking the model config,
        Then frozen=True is confirmed.
        """
        override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Test",
        )

        assert override.model_config.get("frozen") is True

    @pytest.mark.requirement("003b-FR-011")
    def test_policy_override_forbids_extra_fields(self) -> None:
        """Test that PolicyOverride forbids extra fields.

        Given extra fields in input,
        When creating a PolicyOverride,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            PolicyOverride(
                pattern="legacy_*",
                action="downgrade",
                reason="Test",
                extra_field="not_allowed",  # type: ignore[call-arg]
            )

        error_str = str(exc_info.value).lower()
        assert "extra" in error_str or "extra_field" in error_str


class TestPolicyOverrideJsonSerialization:
    """Tests for PolicyOverride JSON serialization."""

    @pytest.mark.requirement("003b-FR-011")
    def test_policy_override_to_json(self) -> None:
        """Test PolicyOverride JSON serialization.

        Given a PolicyOverride with all fields,
        When serializing to JSON,
        Then all fields are present and correctly formatted.
        """
        override = PolicyOverride(
            pattern="legacy_*",
            action="downgrade",
            reason="Migration in progress",
            expires=date(2026, 6, 1),
            policy_types=["naming", "coverage"],
        )

        json_data = override.model_dump()

        assert json_data["pattern"] == "legacy_*"
        assert json_data["action"] == "downgrade"
        assert json_data["reason"] == "Migration in progress"
        assert json_data["expires"] == date(2026, 6, 1)
        assert json_data["policy_types"] == ["naming", "coverage"]

    @pytest.mark.requirement("003b-FR-011")
    def test_policy_override_from_dict(self) -> None:
        """Test PolicyOverride creation from dictionary.

        Given a dictionary with override data,
        When creating a PolicyOverride via model_validate,
        Then the override is created correctly.
        """
        data = {
            "pattern": "test_*",
            "action": "exclude",
            "reason": "Test fixtures",
            "expires": "2026-12-31",
            "policy_types": ["documentation"],
        }

        override = PolicyOverride.model_validate(data)

        assert override.pattern == "test_*"
        assert override.action == "exclude"
        assert override.expires == date(2026, 12, 31)
        assert override.policy_types == ["documentation"]
