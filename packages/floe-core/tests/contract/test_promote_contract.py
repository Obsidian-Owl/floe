"""Contract tests for promote command exit codes and error types.

These tests ensure the promotion error hierarchy and exit codes remain stable.
Breaking changes to exit codes or error attributes should fail these tests.

Contract tests prevent accidental breaking changes to:
- Error class exit codes (CLI relies on these)
- Error class attributes (logging and handling relies on these)
- Error inheritance hierarchy

Task: T027
Requirements: FR-001, FR-001a, FR-001b, FR-002, FR-003, FR-004, FR-005, FR-006,
             FR-008, FR-009, FR-010, FR-011, FR-012
"""

from __future__ import annotations

import pytest

from floe_core.oci.errors import (
    AuthenticationError,
    AuthorizationError,
    EnvironmentLockedError,
    GateValidationError,
    InvalidTransitionError,
    OCIError,
    RegistryUnavailableError,
    SignatureVerificationError,
    TagExistsError,
    VersionNotPromotedError,
)


class TestOCIErrorExitCodeContract:
    """Contract tests for OCI error exit codes stability."""

    @pytest.mark.requirement("8C-FR-001")
    def test_oci_error_base_exit_code(self) -> None:
        """Contract: OCIError base exit code MUST be 1."""
        assert OCIError.exit_code == 1

    @pytest.mark.requirement("8C-FR-001")
    def test_authentication_error_exit_code(self) -> None:
        """Contract: AuthenticationError exit code MUST be 2."""
        assert AuthenticationError.exit_code == 2

    @pytest.mark.requirement("8C-FR-001")
    def test_registry_unavailable_exit_code(self) -> None:
        """Contract: RegistryUnavailableError exit code MUST be 5."""
        assert RegistryUnavailableError.exit_code == 5

    @pytest.mark.requirement("8C-FR-006")
    def test_signature_verification_exit_code(self) -> None:
        """Contract: SignatureVerificationError exit code MUST be 6."""
        assert SignatureVerificationError.exit_code == 6


class TestPromotionErrorExitCodeContract:
    """Contract tests for promotion-specific error exit codes."""

    @pytest.mark.requirement("8C-FR-002")
    def test_gate_validation_error_exit_code(self) -> None:
        """Contract: GateValidationError exit code MUST be 8."""
        assert GateValidationError.exit_code == 8

    @pytest.mark.requirement("8C-FR-003")
    def test_invalid_transition_error_exit_code(self) -> None:
        """Contract: InvalidTransitionError exit code MUST be 9."""
        assert InvalidTransitionError.exit_code == 9

    @pytest.mark.requirement("8C-FR-004")
    def test_tag_exists_error_exit_code(self) -> None:
        """Contract: TagExistsError exit code MUST be 10."""
        assert TagExistsError.exit_code == 10

    @pytest.mark.requirement("8C-FR-005")
    def test_version_not_promoted_error_exit_code(self) -> None:
        """Contract: VersionNotPromotedError exit code MUST be 11."""
        assert VersionNotPromotedError.exit_code == 11

    @pytest.mark.requirement("8C-FR-011")
    def test_authorization_error_exit_code(self) -> None:
        """Contract: AuthorizationError exit code MUST be 12."""
        assert AuthorizationError.exit_code == 12

    @pytest.mark.requirement("8C-FR-012")
    def test_environment_locked_error_exit_code(self) -> None:
        """Contract: EnvironmentLockedError exit code MUST be 13."""
        assert EnvironmentLockedError.exit_code == 13


class TestPromotionErrorInheritanceContract:
    """Contract tests for promotion error inheritance hierarchy."""

    @pytest.mark.requirement("8C-FR-001a")
    def test_gate_validation_error_inherits_oci_error(self) -> None:
        """Contract: GateValidationError MUST inherit from OCIError."""
        assert issubclass(GateValidationError, OCIError)

    @pytest.mark.requirement("8C-FR-001a")
    def test_invalid_transition_error_inherits_oci_error(self) -> None:
        """Contract: InvalidTransitionError MUST inherit from OCIError."""
        assert issubclass(InvalidTransitionError, OCIError)

    @pytest.mark.requirement("8C-FR-001a")
    def test_tag_exists_error_inherits_oci_error(self) -> None:
        """Contract: TagExistsError MUST inherit from OCIError."""
        assert issubclass(TagExistsError, OCIError)

    @pytest.mark.requirement("8C-FR-001a")
    def test_version_not_promoted_error_inherits_oci_error(self) -> None:
        """Contract: VersionNotPromotedError MUST inherit from OCIError."""
        assert issubclass(VersionNotPromotedError, OCIError)

    @pytest.mark.requirement("8C-FR-001a")
    def test_authorization_error_inherits_oci_error(self) -> None:
        """Contract: AuthorizationError MUST inherit from OCIError."""
        assert issubclass(AuthorizationError, OCIError)

    @pytest.mark.requirement("8C-FR-001a")
    def test_environment_locked_error_inherits_oci_error(self) -> None:
        """Contract: EnvironmentLockedError MUST inherit from OCIError."""
        assert issubclass(EnvironmentLockedError, OCIError)


class TestPromotionErrorAttributesContract:
    """Contract tests for promotion error attributes."""

    @pytest.mark.requirement("8C-FR-002")
    def test_gate_validation_error_has_required_attributes(self) -> None:
        """Contract: GateValidationError MUST have gate and details attributes."""
        error = GateValidationError(gate="tests", details="Test failed")

        assert hasattr(error, "gate")
        assert hasattr(error, "details")
        assert error.gate == "tests"
        assert error.details == "Test failed"

    @pytest.mark.requirement("8C-FR-003")
    def test_invalid_transition_error_has_required_attributes(self) -> None:
        """Contract: InvalidTransitionError MUST have from_env, to_env, reason."""
        error = InvalidTransitionError(
            from_env="dev",
            to_env="prod",
            reason="Cannot skip staging",
        )

        assert hasattr(error, "from_env")
        assert hasattr(error, "to_env")
        assert hasattr(error, "reason")
        assert error.from_env == "dev"
        assert error.to_env == "prod"
        assert "skip" in error.reason.lower()

    @pytest.mark.requirement("8C-FR-004")
    def test_tag_exists_error_has_required_attributes(self) -> None:
        """Contract: TagExistsError MUST have tag and existing_digest."""
        error = TagExistsError(
            tag="v1.0.0-staging",
            existing_digest="sha256:abc123def456",
        )

        assert hasattr(error, "tag")
        assert hasattr(error, "existing_digest")
        assert error.tag == "v1.0.0-staging"
        assert error.existing_digest == "sha256:abc123def456"

    @pytest.mark.requirement("8C-FR-005")
    def test_version_not_promoted_error_has_required_attributes(self) -> None:
        """Contract: VersionNotPromotedError MUST have tag, environment, available_versions."""
        error = VersionNotPromotedError(
            tag="v2.0.0",
            environment="staging",
            available_versions=["v1.0.0", "v1.1.0"],
        )

        assert hasattr(error, "tag")
        assert hasattr(error, "environment")
        assert hasattr(error, "available_versions")
        assert error.tag == "v2.0.0"
        assert error.environment == "staging"
        assert error.available_versions == ["v1.0.0", "v1.1.0"]

    @pytest.mark.requirement("8C-FR-011")
    def test_authorization_error_has_required_attributes(self) -> None:
        """Contract: AuthorizationError MUST have operator, required_groups, reason."""
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=["platform-admins"],
            reason="Not a member of required groups",
        )

        assert hasattr(error, "operator")
        assert hasattr(error, "required_groups")
        assert hasattr(error, "reason")
        assert error.operator == "user@example.com"
        assert error.required_groups == ["platform-admins"]
        assert "member" in error.reason.lower()

    @pytest.mark.requirement("8C-FR-012")
    def test_environment_locked_error_has_required_attributes(self) -> None:
        """Contract: EnvironmentLockedError MUST have environment, locked_by, locked_at, reason."""
        error = EnvironmentLockedError(
            environment="prod",
            locked_by="sre@example.com",
            locked_at="2026-01-15T10:30:00Z",
            reason="Incident #123",
        )

        assert hasattr(error, "environment")
        assert hasattr(error, "locked_by")
        assert hasattr(error, "locked_at")
        assert hasattr(error, "reason")
        assert error.environment == "prod"
        assert error.locked_by == "sre@example.com"
        assert error.locked_at == "2026-01-15T10:30:00Z"
        assert "123" in error.reason


class TestPromotionErrorMessageContract:
    """Contract tests for error message format stability."""

    @pytest.mark.requirement("8C-FR-001b")
    def test_gate_validation_error_message_contains_gate_name(self) -> None:
        """Contract: GateValidationError message MUST contain gate name."""
        error = GateValidationError(gate="security_scan", details="CVE found")
        assert "security_scan" in str(error)

    @pytest.mark.requirement("8C-FR-001b")
    def test_invalid_transition_error_message_contains_environments(self) -> None:
        """Contract: InvalidTransitionError message MUST contain both environments."""
        error = InvalidTransitionError(
            from_env="dev",
            to_env="prod",
            reason="Cannot skip staging",
        )
        assert "dev" in str(error)
        assert "prod" in str(error)

    @pytest.mark.requirement("8C-FR-001b")
    def test_tag_exists_error_message_contains_tag(self) -> None:
        """Contract: TagExistsError message MUST contain the tag name."""
        error = TagExistsError(
            tag="v1.0.0-staging",
            existing_digest="sha256:abc123",
        )
        assert "v1.0.0-staging" in str(error)

    @pytest.mark.requirement("8C-FR-001b")
    def test_environment_locked_error_message_contains_environment(self) -> None:
        """Contract: EnvironmentLockedError message MUST contain environment name."""
        error = EnvironmentLockedError(
            environment="prod",
            locked_by="admin",
            locked_at="2026-01-15T10:00:00Z",
            reason="Maintenance",
        )
        assert "prod" in str(error)


class TestExitCodeUniquenessContract:
    """Contract tests verifying exit code uniqueness."""

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_exit_codes_are_unique(self) -> None:
        """Contract: All promotion error exit codes MUST be unique."""
        promotion_errors = [
            GateValidationError,
            InvalidTransitionError,
            TagExistsError,
            VersionNotPromotedError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        exit_codes = [err.exit_code for err in promotion_errors]
        unique_codes = set(exit_codes)

        assert len(exit_codes) == len(unique_codes), (
            f"Duplicate exit codes found! Codes: {exit_codes}"
        )

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_exit_codes_in_valid_range(self) -> None:
        """Contract: Promotion error exit codes MUST be in range 8-13."""
        promotion_errors = [
            (GateValidationError, 8),
            (InvalidTransitionError, 9),
            (TagExistsError, 10),
            (VersionNotPromotedError, 11),
            (AuthorizationError, 12),
            (EnvironmentLockedError, 13),
        ]

        for error_class, expected_code in promotion_errors:
            assert error_class.exit_code == expected_code, (
                f"{error_class.__name__} exit_code is {error_class.exit_code}, "
                f"expected {expected_code}"
            )

    @pytest.mark.requirement("8C-FR-001")
    def test_no_exit_code_conflicts_with_core_errors(self) -> None:
        """Contract: Promotion exit codes MUST NOT conflict with core OCI errors.

        Core OCI errors use exit codes 1-7:
        - 1: General OCIError
        - 2: AuthenticationError
        - 3: ArtifactNotFoundError
        - 4: ImmutabilityViolationError
        - 5: RegistryUnavailableError/CircuitBreakerOpenError
        - 6: SignatureVerificationError
        - 7: ConcurrentSigningError

        Promotion errors MUST use 8+ to avoid conflicts.
        """
        promotion_errors = [
            GateValidationError,
            InvalidTransitionError,
            TagExistsError,
            VersionNotPromotedError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        core_exit_codes = {1, 2, 3, 4, 5, 6, 7}

        for error_class in promotion_errors:
            assert error_class.exit_code not in core_exit_codes, (
                f"{error_class.__name__} exit_code {error_class.exit_code} "
                f"conflicts with core OCI error codes"
            )
            assert error_class.exit_code >= 8, f"{error_class.__name__} exit_code must be >= 8"
