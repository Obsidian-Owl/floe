"""Contract tests for rollback command exit codes and error types.

These tests ensure the rollback error hierarchy and exit codes remain stable.
Breaking changes to exit codes or error attributes should fail these tests.

Contract tests prevent accidental breaking changes to:
- Error class exit codes (CLI relies on these)
- Error class attributes (logging and handling relies on these)
- Rollback tag patterns (FR-014)
- RollbackRecord schema stability

Task: T045
Requirements: FR-013, FR-014, FR-015, FR-016, FR-017
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from floe_core.oci.errors import (
    AuthorizationError,
    EnvironmentLockedError,
    OCIError,
    SignatureVerificationError,
    VersionNotPromotedError,
)
from floe_core.schemas.promotion import RollbackRecord

# Rollback tag pattern per FR-014: v{X.Y.Z}-{env}-rollback-{N}
ROLLBACK_TAG_PATTERN = r"^v\d+\.\d+\.\d+-[a-z]+-rollback-\d+$"
"""Regex pattern for rollback-specific tags per FR-014."""


class TestRollbackErrorExitCodeContract:
    """Contract tests for rollback-relevant error exit codes."""

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_exit_code(self) -> None:
        """Contract: VersionNotPromotedError exit code MUST be 11.

        Used when rollback target version was never promoted to the environment.
        """
        assert VersionNotPromotedError.exit_code == 11

    @pytest.mark.requirement("8C-FR-013")
    def test_signature_verification_exit_code(self) -> None:
        """Contract: SignatureVerificationError exit code MUST be 6.

        Used when rollback target artifact fails signature verification.
        """
        assert SignatureVerificationError.exit_code == 6

    @pytest.mark.requirement("8C-FR-013")
    def test_authorization_error_exit_code(self) -> None:
        """Contract: AuthorizationError exit code MUST be 12.

        Used when operator is not authorized to perform rollback.
        """
        assert AuthorizationError.exit_code == 12

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_error_exit_code(self) -> None:
        """Contract: EnvironmentLockedError exit code MUST be 13.

        Used when rollback target environment is locked.
        """
        assert EnvironmentLockedError.exit_code == 13


class TestRollbackErrorInheritanceContract:
    """Contract tests for rollback error inheritance hierarchy."""

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_inherits_oci_error(self) -> None:
        """Contract: VersionNotPromotedError MUST inherit from OCIError."""
        assert issubclass(VersionNotPromotedError, OCIError)

    @pytest.mark.requirement("8C-FR-013")
    def test_authorization_error_inherits_oci_error(self) -> None:
        """Contract: AuthorizationError MUST inherit from OCIError."""
        assert issubclass(AuthorizationError, OCIError)

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_inherits_oci_error(self) -> None:
        """Contract: EnvironmentLockedError MUST inherit from OCIError."""
        assert issubclass(EnvironmentLockedError, OCIError)


class TestRollbackErrorAttributesContract:
    """Contract tests for rollback error attributes."""

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_has_rollback_attributes(self) -> None:
        """Contract: VersionNotPromotedError MUST have tag, environment, available_versions.

        These attributes enable CLI to display helpful rollback suggestions.
        """
        error = VersionNotPromotedError(
            tag="v1.0.0",
            environment="prod",
            available_versions=["v0.9.0", "v0.8.0"],
        )

        assert hasattr(error, "tag")
        assert hasattr(error, "environment")
        assert hasattr(error, "available_versions")
        assert error.tag == "v1.0.0"
        assert error.environment == "prod"
        assert "v0.9.0" in error.available_versions

    @pytest.mark.requirement("8C-FR-017")
    def test_authorization_error_has_operator_attribute(self) -> None:
        """Contract: AuthorizationError MUST have operator for audit trails."""
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=["sre-team"],
            reason="Not authorized for prod rollback",
        )

        assert hasattr(error, "operator")
        assert error.operator == "user@example.com"

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_has_reason_attribute(self) -> None:
        """Contract: EnvironmentLockedError MUST have reason for context."""
        error = EnvironmentLockedError(
            environment="prod",
            locked_by="incident-bot",
            locked_at="2026-01-15T10:00:00Z",
            reason="Active incident INC-456",
        )

        assert hasattr(error, "reason")
        assert "INC-456" in error.reason


class TestRollbackTagPatternContract:
    """Contract tests for rollback tag pattern (FR-014)."""

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_tag_pattern_matches_spec(self) -> None:
        """Contract: Rollback tags MUST follow v{X.Y.Z}-{env}-rollback-{N} pattern."""
        valid_tags = [
            "v1.0.0-prod-rollback-1",
            "v2.1.3-staging-rollback-5",
            "v0.0.1-dev-rollback-10",
            "v10.20.30-production-rollback-999",
        ]

        for tag in valid_tags:
            assert re.match(
                ROLLBACK_TAG_PATTERN, tag
            ), f"Tag '{tag}' should match rollback pattern"

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_tag_pattern_rejects_invalid(self) -> None:
        """Contract: Invalid rollback tags MUST NOT match the pattern."""
        invalid_tags = [
            "v1.0.0-prod",  # Missing rollback suffix
            "v1.0.0-rollback-1",  # Missing environment
            "1.0.0-prod-rollback-1",  # Missing 'v' prefix
            "v1.0-prod-rollback-1",  # Invalid semver (missing patch)
            "v1.0.0-PROD-rollback-1",  # Uppercase environment
            "v1.0.0-prod-rollback",  # Missing rollback number
            "latest-rollback-1",  # Not semver
        ]

        for tag in invalid_tags:
            assert not re.match(
                ROLLBACK_TAG_PATTERN, tag
            ), f"Tag '{tag}' should NOT match rollback pattern"

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_tag_sequential_numbers(self) -> None:
        """Contract: Rollback number N MUST be sequential per environment-version.

        This is a pattern contract - the implementation must ensure uniqueness.
        """
        # Example sequence for v1.0.0 in prod
        tags: list[str] = [
            "v1.0.0-prod-rollback-1",
            "v1.0.0-prod-rollback-2",
            "v1.0.0-prod-rollback-3",
        ]

        # Extract numbers
        numbers: list[int] = []
        for tag in tags:
            match = re.match(ROLLBACK_TAG_PATTERN, tag)
            assert match is not None
            number = int(tag.split("-rollback-")[1])
            numbers.append(number)

        # Verify sequential (can have gaps, but must be ascending)
        assert numbers == sorted(numbers), "Rollback numbers must be ascending"
        assert len(set(numbers)) == len(numbers), "Rollback numbers must be unique"


class TestRollbackRecordContract:
    """Contract tests for RollbackRecord schema stability (FR-017)."""

    @pytest.fixture
    def minimal_rollback_record(self) -> RollbackRecord:
        """Create a minimal valid RollbackRecord for testing."""
        return RollbackRecord(
            rollback_id=uuid4(),
            artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            previous_digest="sha256:b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            environment="prod",
            reason="Performance regression in v2.0.0",
            operator="sre@example.com",
            rolled_back_at=datetime.now(timezone.utc),
            trace_id="abc123def456",
        )

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_record_required_fields(self) -> None:
        """Contract: RollbackRecord has all fields required for audit trail."""
        schema = RollbackRecord.model_json_schema()
        required_fields = set(schema.get("required", []))

        # Core audit trail fields for rollback - must be present
        core_fields = {
            "rollback_id",
            "artifact_digest",
            "previous_digest",
            "environment",
            "reason",
            "operator",
            "rolled_back_at",
            "trace_id",
        }

        for field in core_fields:
            assert (
                field in required_fields
            ), f"Required field '{field}' missing from RollbackRecord schema"

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_record_serialization_round_trip(
        self, minimal_rollback_record: RollbackRecord
    ) -> None:
        """Contract: RollbackRecord serializes to JSON and back."""
        import json

        json_str = minimal_rollback_record.model_dump_json()
        assert isinstance(json_str, str)

        data = json.loads(json_str)
        restored = RollbackRecord.model_validate(data)

        assert restored.rollback_id == minimal_rollback_record.rollback_id
        assert restored.environment == minimal_rollback_record.environment
        assert restored.reason == minimal_rollback_record.reason
        assert restored.operator == minimal_rollback_record.operator
        assert restored.trace_id == minimal_rollback_record.trace_id
        assert restored.previous_digest == minimal_rollback_record.previous_digest

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_record_extra_fields_forbidden(self) -> None:
        """Contract: RollbackRecord extra='forbid' prevents undocumented fields."""
        with pytest.raises(ValidationError) as exc_info:
            RollbackRecord(
                rollback_id=uuid4(),
                artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                previous_digest="sha256:b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
                environment="prod",
                reason="Rollback reason",
                operator="test@example.com",
                rolled_back_at=datetime.now(timezone.utc),
                trace_id="abc123",
                undocumented_field="should_fail",  # type: ignore[call-arg]
            )
        assert "undocumented_field" in str(exc_info.value)

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_record_immutability(
        self, minimal_rollback_record: RollbackRecord
    ) -> None:
        """Contract: RollbackRecord is immutable (frozen=True)."""
        with pytest.raises(ValidationError):
            minimal_rollback_record.reason = "Modified reason"  # type: ignore[misc]


class TestRollbackErrorMessageContract:
    """Contract tests for rollback error message format stability."""

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_message_contains_environment(self) -> None:
        """Contract: VersionNotPromotedError message MUST contain environment."""
        error = VersionNotPromotedError(
            tag="v1.0.0",
            environment="staging",
            available_versions=["v0.9.0"],
        )
        assert "staging" in str(error)

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_message_contains_tag(self) -> None:
        """Contract: VersionNotPromotedError message MUST contain requested tag."""
        error = VersionNotPromotedError(
            tag="v2.0.0",
            environment="prod",
            available_versions=["v1.0.0"],
        )
        assert "v2.0.0" in str(error)

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_message_contains_reason(self) -> None:
        """Contract: EnvironmentLockedError message MUST contain lock reason."""
        error = EnvironmentLockedError(
            environment="prod",
            locked_by="sre@example.com",
            locked_at="2026-01-15T10:00:00Z",
            reason="Incident INC-789 in progress",
        )
        assert "INC-789" in str(error) or "Incident" in str(error)


class TestRollbackExitCodeRangeContract:
    """Contract tests for rollback exit code range validity."""

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_errors_use_valid_exit_codes(self) -> None:
        """Contract: All rollback-relevant errors use codes in valid range (1-13)."""
        rollback_errors = [
            VersionNotPromotedError,
            SignatureVerificationError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        for error_class in rollback_errors:
            assert 1 <= error_class.exit_code <= 13, (
                f"{error_class.__name__} exit_code {error_class.exit_code} "
                f"is outside valid range 1-13"
            )

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_exit_codes_are_unique(self) -> None:
        """Contract: All rollback error exit codes MUST be unique."""
        rollback_errors = [
            VersionNotPromotedError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        exit_codes = [err.exit_code for err in rollback_errors]
        unique_codes = set(exit_codes)

        assert len(exit_codes) == len(
            unique_codes
        ), f"Duplicate exit codes found! Codes: {exit_codes}"
