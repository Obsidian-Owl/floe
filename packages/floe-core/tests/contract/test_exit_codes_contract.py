"""Contract tests for CLI exit codes (T088).

Task ID: T088
Phase: 9 - User Story 7 (CI/CD Automation)
User Story: US7 - CI/CD Automation Integration
Requirements: FR-032

These tests validate that exit codes are stable and predictable for CI/CD automation.
Exit codes are part of the public contract and must not change without a major version bump.

Exit Codes Contract:
- 0 = success
- 1 = general error (OCIError)
- 2 = authentication failed (AuthenticationError)
- 3 = artifact not found (ArtifactNotFoundError)
- 4 = immutability violation (ImmutabilityViolationError)
- 5 = network/connectivity error (RegistryUnavailableError, CircuitBreakerOpenError)
- 6 = signature verification failed (SignatureVerificationError)
- 7 = concurrent signing lock failed (ConcurrentSigningError)
- 8 = gate validation failed (GateValidationError)
- 9 = invalid transition (InvalidTransitionError)
- 10 = tag exists (TagExistsError)
- 11 = version not promoted (VersionNotPromotedError)
- 12 = authorization failed (AuthorizationError)
- 13 = environment locked (EnvironmentLockedError)

TDD: Tests written FIRST (T088), implementation follows if needed.
"""

from __future__ import annotations

import pytest

from floe_core.oci.errors import (
    ArtifactNotFoundError,
    AuthenticationError,
    AuthorizationError,
    CircuitBreakerOpenError,
    ConcurrentSigningError,
    EnvironmentLockedError,
    GateValidationError,
    ImmutabilityViolationError,
    InvalidTransitionError,
    OCIError,
    RegistryUnavailableError,
    SignatureVerificationError,
    TagExistsError,
    VersionNotPromotedError,
)


class TestExitCodesContract:
    """Contract tests validating exit codes are stable.

    These tests ensure CI/CD pipelines can rely on specific exit codes
    for error handling and decision making.
    """

    @pytest.mark.requirement("FR-032")
    def test_oci_error_base_exit_code_is_1(self) -> None:
        """OCIError (base) has exit_code 1."""
        assert OCIError.exit_code == 1

    @pytest.mark.requirement("FR-032")
    def test_authentication_error_exit_code_is_2(self) -> None:
        """AuthenticationError has exit_code 2."""
        assert AuthenticationError.exit_code == 2

        # Also verify on instance
        exc = AuthenticationError(
            registry="oci://example.com/repo",
            reason="Invalid credentials",
        )
        assert exc.exit_code == 2

    @pytest.mark.requirement("FR-032")
    def test_artifact_not_found_error_exit_code_is_3(self) -> None:
        """ArtifactNotFoundError has exit_code 3."""
        assert ArtifactNotFoundError.exit_code == 3

        # Also verify on instance
        exc = ArtifactNotFoundError(
            tag="v1.0.0",
            registry="oci://example.com/repo",
        )
        assert exc.exit_code == 3

    @pytest.mark.requirement("FR-032")
    def test_immutability_violation_error_exit_code_is_4(self) -> None:
        """ImmutabilityViolationError has exit_code 4."""
        assert ImmutabilityViolationError.exit_code == 4

        # Also verify on instance
        exc = ImmutabilityViolationError(
            tag="v1.0.0",
            registry="oci://example.com/repo",
        )
        assert exc.exit_code == 4

    @pytest.mark.requirement("FR-032")
    def test_registry_unavailable_error_exit_code_is_5(self) -> None:
        """RegistryUnavailableError has exit_code 5."""
        assert RegistryUnavailableError.exit_code == 5

        # Also verify on instance
        exc = RegistryUnavailableError(
            registry="oci://example.com/repo",
            reason="Connection refused",
        )
        assert exc.exit_code == 5

    @pytest.mark.requirement("FR-032")
    def test_circuit_breaker_open_error_exit_code_is_5(self) -> None:
        """CircuitBreakerOpenError has exit_code 5 (same as network errors)."""
        assert CircuitBreakerOpenError.exit_code == 5

        # Also verify on instance
        exc = CircuitBreakerOpenError(
            registry="oci://example.com/repo",
            failure_count=5,
        )
        assert exc.exit_code == 5

    @pytest.mark.requirement("FR-032")
    def test_signature_verification_error_exit_code_is_6(self) -> None:
        """SignatureVerificationError has exit_code 6."""
        assert SignatureVerificationError.exit_code == 6

        # Also verify on instance
        exc = SignatureVerificationError(
            artifact_ref="oci://example.com/repo:v1.0.0",
            reason="No signature found",
        )
        assert exc.exit_code == 6

    @pytest.mark.requirement("FR-032")
    def test_concurrent_signing_error_exit_code_is_7(self) -> None:
        """ConcurrentSigningError has exit_code 7."""
        assert ConcurrentSigningError.exit_code == 7

        # Also verify on instance
        exc = ConcurrentSigningError(
            artifact_ref="oci://example.com/repo:v1.0.0",
            timeout_seconds=30.0,
        )
        assert exc.exit_code == 7

    @pytest.mark.requirement("FR-032")
    def test_gate_validation_error_exit_code_is_8(self) -> None:
        """GateValidationError has exit_code 8."""
        assert GateValidationError.exit_code == 8

        # Also verify on instance
        exc = GateValidationError(
            gate="tests",
            details="Test suite failed with 3 failures",
        )
        assert exc.exit_code == 8

    @pytest.mark.requirement("FR-032")
    def test_invalid_transition_error_exit_code_is_9(self) -> None:
        """InvalidTransitionError has exit_code 9."""
        assert InvalidTransitionError.exit_code == 9

        # Also verify on instance
        exc = InvalidTransitionError(
            from_env="prod",
            to_env="dev",
            reason="Cannot demote from prod to dev",
        )
        assert exc.exit_code == 9

    @pytest.mark.requirement("FR-032")
    def test_tag_exists_error_exit_code_is_10(self) -> None:
        """TagExistsError has exit_code 10."""
        assert TagExistsError.exit_code == 10

        # Also verify on instance
        exc = TagExistsError(
            tag="v1.0.0-staging",
            existing_digest="sha256:abc123def456",
        )
        assert exc.exit_code == 10

    @pytest.mark.requirement("FR-032")
    def test_version_not_promoted_error_exit_code_is_11(self) -> None:
        """VersionNotPromotedError has exit_code 11."""
        assert VersionNotPromotedError.exit_code == 11

        # Also verify on instance
        exc = VersionNotPromotedError(
            tag="v2.0.0",
            environment="staging",
        )
        assert exc.exit_code == 11

    @pytest.mark.requirement("FR-032")
    def test_authorization_error_exit_code_is_12(self) -> None:
        """AuthorizationError has exit_code 12."""
        assert AuthorizationError.exit_code == 12

        # Also verify on instance
        exc = AuthorizationError(
            operator="user@example.com",
            required_groups=["platform-admins"],
            reason="Not a member of required groups",
        )
        assert exc.exit_code == 12

    @pytest.mark.requirement("FR-032")
    def test_environment_locked_error_exit_code_is_13(self) -> None:
        """EnvironmentLockedError has exit_code 13."""
        assert EnvironmentLockedError.exit_code == 13

        # Also verify on instance
        exc = EnvironmentLockedError(
            environment="prod",
            locked_by="sre@example.com",
            locked_at="2026-01-15T10:30:00Z",
            reason="Incident #123",
        )
        assert exc.exit_code == 13


class TestExitCodesExhaustiveness:
    """Contract tests ensuring all exception types have exit codes."""

    @pytest.mark.requirement("FR-032")
    def test_all_oci_exceptions_have_exit_code_attribute(self) -> None:
        """Every OCIError subclass must have an exit_code attribute."""
        oci_exceptions = [
            OCIError,
            AuthenticationError,
            ArtifactNotFoundError,
            ImmutabilityViolationError,
            CircuitBreakerOpenError,
            RegistryUnavailableError,
            SignatureVerificationError,
            ConcurrentSigningError,
            GateValidationError,
            InvalidTransitionError,
            TagExistsError,
            VersionNotPromotedError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        for exc_class in oci_exceptions:
            assert hasattr(exc_class, "exit_code"), (
                f"{exc_class.__name__} must have exit_code attribute"
            )
            assert isinstance(exc_class.exit_code, int), (
                f"{exc_class.__name__}.exit_code must be int"
            )
            assert exc_class.exit_code >= 0, (
                f"{exc_class.__name__}.exit_code must be non-negative"
            )

    @pytest.mark.requirement("FR-032")
    def test_exit_codes_are_unique_per_error_category(self) -> None:
        """Exit codes must be unique per error category (except network errors).

        Network errors (RegistryUnavailableError, CircuitBreakerOpenError)
        share exit code 5 as they represent the same operational category.
        """
        exit_code_map: dict[int, list[str]] = {}
        oci_exceptions = [
            OCIError,
            AuthenticationError,
            ArtifactNotFoundError,
            ImmutabilityViolationError,
            CircuitBreakerOpenError,
            RegistryUnavailableError,
            SignatureVerificationError,
            ConcurrentSigningError,
            GateValidationError,
            InvalidTransitionError,
            TagExistsError,
            VersionNotPromotedError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        for exc_class in oci_exceptions:
            code = exc_class.exit_code
            if code not in exit_code_map:
                exit_code_map[code] = []
            exit_code_map[code].append(exc_class.__name__)

        # Check for unexpected duplicates (5 is allowed for network errors)
        for code, classes in exit_code_map.items():
            if code == 5:
                # Network errors share code 5 - allowed
                allowed_network_errors = {
                    "CircuitBreakerOpenError",
                    "RegistryUnavailableError",
                }
                assert set(classes).issubset(allowed_network_errors), (
                    f"Exit code 5 should only be for network errors, got: {classes}"
                )
            elif len(classes) > 1:
                raise AssertionError(
                    f"Exit code {code} is used by multiple exceptions: {classes}"
                )

    @pytest.mark.requirement("FR-032")
    def test_promotion_lifecycle_errors_have_codes_8_to_13(self) -> None:
        """Promotion lifecycle errors (Epic 8C) use exit codes 8-13."""
        promotion_errors = {
            GateValidationError: 8,
            InvalidTransitionError: 9,
            TagExistsError: 10,
            VersionNotPromotedError: 11,
            AuthorizationError: 12,
            EnvironmentLockedError: 13,
        }

        for exc_class, expected_code in promotion_errors.items():
            assert exc_class.exit_code == expected_code, (
                f"{exc_class.__name__} exit_code should be {expected_code}, "
                f"got {exc_class.exit_code}"
            )


class TestExitCodesDocumentation:
    """Contract tests ensuring exit codes match documentation."""

    @pytest.mark.requirement("FR-032")
    def test_documented_exit_code_range(self) -> None:
        """Exit codes should be in the range 0-13 (documented range)."""
        oci_exceptions = [
            OCIError,
            AuthenticationError,
            ArtifactNotFoundError,
            ImmutabilityViolationError,
            CircuitBreakerOpenError,
            RegistryUnavailableError,
            SignatureVerificationError,
            ConcurrentSigningError,
            GateValidationError,
            InvalidTransitionError,
            TagExistsError,
            VersionNotPromotedError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        for exc_class in oci_exceptions:
            assert 0 <= exc_class.exit_code <= 13, (
                f"{exc_class.__name__}.exit_code ({exc_class.exit_code}) "
                "should be in range 0-13"
            )

    @pytest.mark.requirement("FR-032")
    def test_exit_code_inheritance(self) -> None:
        """All custom exceptions inherit from OCIError."""
        custom_exceptions = [
            AuthenticationError,
            ArtifactNotFoundError,
            ImmutabilityViolationError,
            CircuitBreakerOpenError,
            RegistryUnavailableError,
            SignatureVerificationError,
            ConcurrentSigningError,
            GateValidationError,
            InvalidTransitionError,
            TagExistsError,
            VersionNotPromotedError,
            AuthorizationError,
            EnvironmentLockedError,
        ]

        for exc_class in custom_exceptions:
            assert issubclass(exc_class, OCIError), (
                f"{exc_class.__name__} must inherit from OCIError"
            )


__all__: list[str] = [
    "TestExitCodesContract",
    "TestExitCodesExhaustiveness",
    "TestExitCodesDocumentation",
]
