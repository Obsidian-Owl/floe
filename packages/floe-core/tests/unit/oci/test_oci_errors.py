"""Unit tests for OCI error hierarchy.

This module tests the OCI exception hierarchy defined in floe_core.oci.errors.

Requirements tested:
    FR-019: Error hierarchy provides specific exception types
    FR-021: Exit codes map correctly to exception types

Task ID: T041
Phase: 8 - US6 (Add Missing Test Coverage)
User Story: US6 - Add Missing Test Coverage
"""

from __future__ import annotations

# Import directly from errors module to avoid client.py which requires oras
import importlib.util
import sys
from pathlib import Path

import pytest

# Load errors module directly without going through __init__.py
# Path: tests/unit/oci/test_errors.py -> parents[3] = tests -> packages/floe-core
errors_path = Path(__file__).parents[3] / "src" / "floe_core" / "oci" / "errors.py"
spec = importlib.util.spec_from_file_location("oci_errors", errors_path)
assert spec is not None and spec.loader is not None
oci_errors = importlib.util.module_from_spec(spec)
sys.modules["oci_errors"] = oci_errors
spec.loader.exec_module(oci_errors)

# Import error classes from loaded module
OCIError = oci_errors.OCIError
AuthenticationError = oci_errors.AuthenticationError
ArtifactNotFoundError = oci_errors.ArtifactNotFoundError
ImmutabilityViolationError = oci_errors.ImmutabilityViolationError
CircuitBreakerOpenError = oci_errors.CircuitBreakerOpenError
RegistryUnavailableError = oci_errors.RegistryUnavailableError
DigestMismatchError = oci_errors.DigestMismatchError
CacheError = oci_errors.CacheError


class TestOCIErrorHierarchy:
    """Tests for OCI error class hierarchy."""

    @pytest.mark.requirement("FR-019")
    def test_all_errors_inherit_from_oci_error(self) -> None:
        """All OCI exceptions inherit from OCIError base class."""
        error_classes = [
            AuthenticationError,
            ArtifactNotFoundError,
            ImmutabilityViolationError,
            CircuitBreakerOpenError,
            RegistryUnavailableError,
            DigestMismatchError,
            CacheError,
        ]

        for error_class in error_classes:
            assert issubclass(error_class, OCIError), (
                f"{error_class.__name__} should inherit from OCIError"
            )

    @pytest.mark.requirement("FR-019")
    def test_oci_error_inherits_from_exception(self) -> None:
        """OCIError inherits from Python's Exception class."""
        assert issubclass(OCIError, Exception)


class TestOCIErrorExitCodes:
    """Tests for OCI error exit codes per spec."""

    @pytest.mark.requirement("FR-021")
    def test_oci_error_exit_code(self) -> None:
        """OCIError has exit code 1 (general error)."""
        error = OCIError("General OCI error")
        assert error.exit_code == 1

    @pytest.mark.requirement("FR-021")
    def test_authentication_error_exit_code(self) -> None:
        """AuthenticationError has exit code 2."""
        error = AuthenticationError(
            registry="oci://registry.example.com/floe",
            reason="Invalid credentials",
        )
        assert error.exit_code == 2

    @pytest.mark.requirement("FR-021")
    def test_artifact_not_found_error_exit_code(self) -> None:
        """ArtifactNotFoundError has exit code 3."""
        error = ArtifactNotFoundError(
            tag="v1.0.0",
            registry="oci://registry.example.com/floe",
        )
        assert error.exit_code == 3

    @pytest.mark.requirement("FR-021")
    def test_immutability_violation_error_exit_code(self) -> None:
        """ImmutabilityViolationError has exit code 4."""
        error = ImmutabilityViolationError(
            tag="v1.0.0",
            registry="oci://registry.example.com/floe",
        )
        assert error.exit_code == 4

    @pytest.mark.requirement("FR-021")
    def test_circuit_breaker_open_error_exit_code(self) -> None:
        """CircuitBreakerOpenError has exit code 5."""
        error = CircuitBreakerOpenError(
            registry="oci://registry.example.com/floe",
        )
        assert error.exit_code == 5

    @pytest.mark.requirement("FR-021")
    def test_registry_unavailable_error_exit_code(self) -> None:
        """RegistryUnavailableError has exit code 5."""
        error = RegistryUnavailableError(
            registry="oci://registry.example.com/floe",
            reason="Connection timed out",
        )
        assert error.exit_code == 5


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    @pytest.mark.requirement("FR-019")
    def test_authentication_error_attributes(self) -> None:
        """AuthenticationError stores registry and reason."""
        error = AuthenticationError(
            registry="oci://harbor.example.com/floe",
            reason="Token expired",
        )
        assert error.registry == "oci://harbor.example.com/floe"
        assert error.reason == "Token expired"

    @pytest.mark.requirement("FR-019")
    def test_authentication_error_message(self) -> None:
        """AuthenticationError formats message correctly."""
        error = AuthenticationError(
            registry="oci://registry.example.com/floe",
            reason="Invalid username or password",
        )
        assert "Authentication failed" in str(error)
        assert "oci://registry.example.com/floe" in str(error)
        assert "Invalid username or password" in str(error)


class TestArtifactNotFoundError:
    """Tests for ArtifactNotFoundError."""

    @pytest.mark.requirement("FR-019")
    def test_artifact_not_found_error_attributes(self) -> None:
        """ArtifactNotFoundError stores tag and registry."""
        error = ArtifactNotFoundError(
            tag="v2.0.0",
            registry="oci://harbor.example.com/floe",
        )
        assert error.tag == "v2.0.0"
        assert error.registry == "oci://harbor.example.com/floe"
        assert error.available_tags is None

    @pytest.mark.requirement("FR-019")
    def test_artifact_not_found_error_with_available_tags(self) -> None:
        """ArtifactNotFoundError shows available tags in message."""
        error = ArtifactNotFoundError(
            tag="v2.0.0",
            registry="oci://harbor.example.com/floe",
            available_tags=["v1.0.0", "v1.1.0", "v1.2.0"],
        )
        assert error.available_tags == ["v1.0.0", "v1.1.0", "v1.2.0"]
        msg = str(error)
        assert "Available tags:" in msg
        assert "v1.0.0" in msg

    @pytest.mark.requirement("FR-019")
    def test_artifact_not_found_error_truncates_many_tags(self) -> None:
        """ArtifactNotFoundError truncates long tag list."""
        many_tags = [f"v{i}.0.0" for i in range(10)]
        error = ArtifactNotFoundError(
            tag="v99.0.0",
            registry="oci://harbor.example.com/floe",
            available_tags=many_tags,
        )
        msg = str(error)
        assert "and 5 more" in msg


class TestImmutabilityViolationError:
    """Tests for ImmutabilityViolationError."""

    @pytest.mark.requirement("FR-019")
    def test_immutability_violation_error_attributes(self) -> None:
        """ImmutabilityViolationError stores tag, registry, digest."""
        error = ImmutabilityViolationError(
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            digest="sha256:abc123def456",
        )
        assert error.tag == "v1.0.0"
        assert error.registry == "oci://harbor.example.com/floe"
        assert error.digest == "sha256:abc123def456"

    @pytest.mark.requirement("FR-019")
    def test_immutability_violation_error_message(self) -> None:
        """ImmutabilityViolationError formats message with digest."""
        error = ImmutabilityViolationError(
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            digest="sha256:abc123def456789",
        )
        msg = str(error)
        assert "Cannot overwrite immutable tag" in msg
        assert "v1.0.0" in msg
        assert "Use a new version number" in msg

    @pytest.mark.requirement("FR-019")
    def test_immutability_violation_error_without_digest(self) -> None:
        """ImmutabilityViolationError works without digest."""
        error = ImmutabilityViolationError(
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
        )
        assert error.digest is None
        assert "Cannot overwrite" in str(error)


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError."""

    @pytest.mark.requirement("FR-019")
    def test_circuit_breaker_open_error_attributes(self) -> None:
        """CircuitBreakerOpenError stores registry and failure info."""
        error = CircuitBreakerOpenError(
            registry="oci://harbor.example.com/floe",
            failure_count=5,
            recovery_at="2026-01-22T12:00:00Z",
        )
        assert error.registry == "oci://harbor.example.com/floe"
        assert error.failure_count == 5
        assert error.recovery_at == "2026-01-22T12:00:00Z"

    @pytest.mark.requirement("FR-019")
    def test_circuit_breaker_open_error_message_with_details(self) -> None:
        """CircuitBreakerOpenError includes failure count and recovery time."""
        error = CircuitBreakerOpenError(
            registry="oci://harbor.example.com/floe",
            failure_count=3,
            recovery_at="2026-01-22T12:00:00Z",
        )
        msg = str(error)
        assert "Circuit breaker open" in msg
        assert "3 failures" in msg
        assert "Retry after" in msg

    @pytest.mark.requirement("FR-019")
    def test_circuit_breaker_open_error_minimal(self) -> None:
        """CircuitBreakerOpenError works with minimal args."""
        error = CircuitBreakerOpenError(
            registry="oci://harbor.example.com/floe",
        )
        assert error.failure_count == 0
        assert error.recovery_at is None
        assert "Circuit breaker open" in str(error)


class TestRegistryUnavailableError:
    """Tests for RegistryUnavailableError."""

    @pytest.mark.requirement("FR-019")
    def test_registry_unavailable_error_attributes(self) -> None:
        """RegistryUnavailableError stores registry and reason."""
        error = RegistryUnavailableError(
            registry="oci://harbor.example.com/floe",
            reason="DNS resolution failed",
        )
        assert error.registry == "oci://harbor.example.com/floe"
        assert error.reason == "DNS resolution failed"

    @pytest.mark.requirement("FR-019")
    def test_registry_unavailable_error_message(self) -> None:
        """RegistryUnavailableError formats message correctly."""
        error = RegistryUnavailableError(
            registry="oci://harbor.example.com/floe",
            reason="Connection refused",
        )
        msg = str(error)
        assert "Registry unavailable" in msg
        assert "Connection refused" in msg


class TestDigestMismatchError:
    """Tests for DigestMismatchError."""

    @pytest.mark.requirement("FR-019")
    def test_digest_mismatch_error_attributes(self) -> None:
        """DigestMismatchError stores expected, actual, and artifact ref."""
        error = DigestMismatchError(
            expected="sha256:abc123def456789012345678901234567890123456789012345678901234",
            actual="sha256:xyz789abc123def456789012345678901234567890123456789012345678",
            artifact_ref="v1.0.0",
        )
        assert error.expected.startswith("sha256:abc")
        assert error.actual.startswith("sha256:xyz")
        assert error.artifact_ref == "v1.0.0"

    @pytest.mark.requirement("FR-019")
    def test_digest_mismatch_error_message_truncates_digests(self) -> None:
        """DigestMismatchError truncates long digests in message."""
        error = DigestMismatchError(
            expected="sha256:abc123def456789012345678901234567890123456789012345678901234",
            actual="sha256:xyz789abc123def456789012345678901234567890123456789012345678",
            artifact_ref="v1.0.0",
        )
        msg = str(error)
        assert "Digest mismatch" in msg
        assert "..." in msg  # Truncated
        assert "v1.0.0" in msg

    @pytest.mark.requirement("FR-021")
    def test_digest_mismatch_error_uses_default_exit_code(self) -> None:
        """DigestMismatchError uses default exit code 1."""
        error = DigestMismatchError(
            expected="sha256:abc",
            actual="sha256:xyz",
            artifact_ref="v1.0.0",
        )
        assert error.exit_code == 1  # Default from OCIError


class TestCacheError:
    """Tests for CacheError."""

    @pytest.mark.requirement("FR-019")
    def test_cache_error_attributes(self) -> None:
        """CacheError stores operation, reason, and path."""
        error = CacheError(
            operation="put",
            reason="Disk full",
            path="/var/cache/floe/oci",
        )
        assert error.operation == "put"
        assert error.reason == "Disk full"
        assert error.path == "/var/cache/floe/oci"

    @pytest.mark.requirement("FR-019")
    def test_cache_error_message_with_path(self) -> None:
        """CacheError includes path in message when provided."""
        error = CacheError(
            operation="get",
            reason="File corrupted",
            path="/var/cache/floe/oci/artifact.tar",
        )
        msg = str(error)
        assert "Cache operation 'get' failed" in msg
        assert "File corrupted" in msg
        assert "/var/cache/floe/oci/artifact.tar" in msg

    @pytest.mark.requirement("FR-019")
    def test_cache_error_message_without_path(self) -> None:
        """CacheError works without path."""
        error = CacheError(
            operation="evict",
            reason="Lock timeout",
        )
        assert error.path is None
        msg = str(error)
        assert "Cache operation 'evict' failed" in msg
        assert "Lock timeout" in msg

    @pytest.mark.requirement("FR-021")
    def test_cache_error_uses_default_exit_code(self) -> None:
        """CacheError uses default exit code 1."""
        error = CacheError(operation="get", reason="test")
        assert error.exit_code == 1  # Default from OCIError


class TestExceptionCatching:
    """Tests for exception catching patterns."""

    @pytest.mark.requirement("FR-019")
    def test_catch_all_oci_errors(self) -> None:
        """All OCI errors can be caught with single except clause."""
        errors = [
            AuthenticationError("reg", "reason"),
            ArtifactNotFoundError("tag", "reg"),
            ImmutabilityViolationError("tag", "reg"),
            CircuitBreakerOpenError("reg"),
            RegistryUnavailableError("reg", "reason"),
            DigestMismatchError("exp", "act", "ref"),
            CacheError("op", "reason"),
        ]

        for error in errors:
            caught = False
            try:
                raise error
            except OCIError:
                caught = True
            assert caught, f"Failed to catch {type(error).__name__} as OCIError"

    @pytest.mark.requirement("FR-019")
    def test_specific_error_catching(self) -> None:
        """Specific errors can be caught individually."""
        caught_auth = False
        try:
            raise AuthenticationError("reg", "reason")
        except AuthenticationError:
            caught_auth = True
        except OCIError:
            pass
        assert caught_auth, "AuthenticationError should be caught specifically"


# =============================================================================
# Promotion-Specific Exceptions (Epic 8C)
# =============================================================================


# Import promotion error classes
GateValidationError = getattr(oci_errors, "GateValidationError", None)
InvalidTransitionError = getattr(oci_errors, "InvalidTransitionError", None)
TagExistsError = getattr(oci_errors, "TagExistsError", None)
VersionNotPromotedError = getattr(oci_errors, "VersionNotPromotedError", None)
AuthorizationError = getattr(oci_errors, "AuthorizationError", None)
EnvironmentLockedError = getattr(oci_errors, "EnvironmentLockedError", None)


class TestGateValidationError:
    """Tests for GateValidationError (exit_code=8)."""

    @pytest.mark.requirement("8C-FR-008")
    def test_gate_validation_error_exit_code(self) -> None:
        """GateValidationError has exit code 8."""
        assert GateValidationError is not None, "GateValidationError not implemented"
        error = GateValidationError(
            gate="tests",
            details="Test suite failed: 3 tests failing",
        )
        assert error.exit_code == 8

    @pytest.mark.requirement("8C-FR-008")
    def test_gate_validation_error_attributes(self) -> None:
        """GateValidationError stores gate and details."""
        assert GateValidationError is not None
        error = GateValidationError(
            gate="security_scan",
            details="Critical CVE found: CVE-2024-1234",
        )
        assert error.gate == "security_scan"
        assert error.details == "Critical CVE found: CVE-2024-1234"

    @pytest.mark.requirement("8C-FR-008")
    def test_gate_validation_error_message(self) -> None:
        """GateValidationError formats message correctly."""
        assert GateValidationError is not None
        error = GateValidationError(
            gate="policy_compliance",
            details="Required label 'owner' missing",
        )
        msg = str(error)
        assert "policy_compliance" in msg
        assert "Required label" in msg

    @pytest.mark.requirement("8C-FR-008")
    def test_gate_validation_error_inherits_oci_error(self) -> None:
        """GateValidationError inherits from OCIError."""
        assert GateValidationError is not None
        assert issubclass(GateValidationError, OCIError)


class TestInvalidTransitionError:
    """Tests for InvalidTransitionError (exit_code=9)."""

    @pytest.mark.requirement("8C-FR-009")
    def test_invalid_transition_error_exit_code(self) -> None:
        """InvalidTransitionError has exit code 9."""
        assert InvalidTransitionError is not None, "InvalidTransitionError not implemented"
        error = InvalidTransitionError(
            from_env="prod",
            to_env="dev",
            reason="Cannot demote from prod to dev",
        )
        assert error.exit_code == 9

    @pytest.mark.requirement("8C-FR-009")
    def test_invalid_transition_error_attributes(self) -> None:
        """InvalidTransitionError stores from_env, to_env, reason."""
        assert InvalidTransitionError is not None
        error = InvalidTransitionError(
            from_env="dev",
            to_env="prod",
            reason="Must promote through staging first",
        )
        assert error.from_env == "dev"
        assert error.to_env == "prod"
        assert error.reason == "Must promote through staging first"

    @pytest.mark.requirement("8C-FR-009")
    def test_invalid_transition_error_message(self) -> None:
        """InvalidTransitionError formats message correctly."""
        assert InvalidTransitionError is not None
        error = InvalidTransitionError(
            from_env="staging",
            to_env="dev",
            reason="Cannot demote artifacts",
        )
        msg = str(error)
        assert "staging" in msg
        assert "dev" in msg
        assert "demote" in msg.lower() or "Cannot" in msg

    @pytest.mark.requirement("8C-FR-009")
    def test_invalid_transition_error_inherits_oci_error(self) -> None:
        """InvalidTransitionError inherits from OCIError."""
        assert InvalidTransitionError is not None
        assert issubclass(InvalidTransitionError, OCIError)


class TestTagExistsError:
    """Tests for TagExistsError (exit_code=10)."""

    @pytest.mark.requirement("8C-FR-010")
    def test_tag_exists_error_exit_code(self) -> None:
        """TagExistsError has exit code 10."""
        assert TagExistsError is not None, "TagExistsError not implemented"
        error = TagExistsError(
            tag="v1.0.0-staging",
            existing_digest="sha256:abc123",
        )
        assert error.exit_code == 10

    @pytest.mark.requirement("8C-FR-010")
    def test_tag_exists_error_attributes(self) -> None:
        """TagExistsError stores tag and existing_digest."""
        assert TagExistsError is not None
        error = TagExistsError(
            tag="v1.0.0-prod",
            existing_digest="sha256:def456",
        )
        assert error.tag == "v1.0.0-prod"
        assert error.existing_digest == "sha256:def456"

    @pytest.mark.requirement("8C-FR-010")
    def test_tag_exists_error_message(self) -> None:
        """TagExistsError formats message correctly."""
        assert TagExistsError is not None
        error = TagExistsError(
            tag="v1.0.0-staging",
            existing_digest="sha256:abc123def456789",
        )
        msg = str(error)
        assert "v1.0.0-staging" in msg
        assert "exists" in msg.lower() or "already" in msg.lower()

    @pytest.mark.requirement("8C-FR-010")
    def test_tag_exists_error_inherits_oci_error(self) -> None:
        """TagExistsError inherits from OCIError."""
        assert TagExistsError is not None
        assert issubclass(TagExistsError, OCIError)


class TestVersionNotPromotedError:
    """Tests for VersionNotPromotedError (exit_code=11)."""

    @pytest.mark.requirement("8C-FR-011")
    def test_version_not_promoted_error_exit_code(self) -> None:
        """VersionNotPromotedError has exit code 11."""
        assert VersionNotPromotedError is not None, "VersionNotPromotedError not implemented"
        error = VersionNotPromotedError(
            tag="v1.0.0",
            environment="staging",
            available_versions=["v0.9.0", "v0.9.1"],
        )
        assert error.exit_code == 11

    @pytest.mark.requirement("8C-FR-011")
    def test_version_not_promoted_error_attributes(self) -> None:
        """VersionNotPromotedError stores tag, environment, available_versions."""
        assert VersionNotPromotedError is not None
        error = VersionNotPromotedError(
            tag="v2.0.0",
            environment="prod",
            available_versions=["v1.0.0", "v1.1.0"],
        )
        assert error.tag == "v2.0.0"
        assert error.environment == "prod"
        assert error.available_versions == ["v1.0.0", "v1.1.0"]

    @pytest.mark.requirement("8C-FR-011")
    def test_version_not_promoted_error_message(self) -> None:
        """VersionNotPromotedError formats message correctly."""
        assert VersionNotPromotedError is not None
        error = VersionNotPromotedError(
            tag="v1.0.0",
            environment="staging",
            available_versions=["v0.9.0"],
        )
        msg = str(error)
        assert "v1.0.0" in msg
        assert "staging" in msg

    @pytest.mark.requirement("8C-FR-011")
    def test_version_not_promoted_error_inherits_oci_error(self) -> None:
        """VersionNotPromotedError inherits from OCIError."""
        assert VersionNotPromotedError is not None
        assert issubclass(VersionNotPromotedError, OCIError)


class TestAuthorizationError:
    """Tests for AuthorizationError (exit_code=12)."""

    @pytest.mark.requirement("8C-FR-012")
    def test_authorization_error_exit_code(self) -> None:
        """AuthorizationError has exit code 12."""
        assert AuthorizationError is not None, "AuthorizationError not implemented"
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=["platform-admins"],
            reason="Not a member of required groups",
        )
        assert error.exit_code == 12

    @pytest.mark.requirement("8C-FR-012")
    def test_authorization_error_attributes(self) -> None:
        """AuthorizationError stores operator, required_groups, reason."""
        assert AuthorizationError is not None
        error = AuthorizationError(
            operator="dev@example.com",
            required_groups=["release-managers", "platform-admins"],
            reason="Separation of duties violation",
        )
        assert error.operator == "dev@example.com"
        assert error.required_groups == ["release-managers", "platform-admins"]
        assert error.reason == "Separation of duties violation"

    @pytest.mark.requirement("8C-FR-012")
    def test_authorization_error_message(self) -> None:
        """AuthorizationError formats message correctly."""
        assert AuthorizationError is not None
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=["admins"],
            reason="Not authorized",
        )
        msg = str(error)
        assert "user@example.com" in msg
        assert "admins" in msg or "authorized" in msg.lower()

    @pytest.mark.requirement("8C-FR-012")
    def test_authorization_error_inherits_oci_error(self) -> None:
        """AuthorizationError inherits from OCIError."""
        assert AuthorizationError is not None
        assert issubclass(AuthorizationError, OCIError)


class TestEnvironmentLockedError:
    """Tests for EnvironmentLockedError (exit_code=13)."""

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_error_exit_code(self) -> None:
        """EnvironmentLockedError has exit code 13."""
        assert EnvironmentLockedError is not None, "EnvironmentLockedError not implemented"
        error = EnvironmentLockedError(
            environment="prod",
            locked_by="sre@example.com",
            locked_at="2026-01-15T10:30:00Z",
            reason="Incident #123",
        )
        assert error.exit_code == 13

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_error_attributes(self) -> None:
        """EnvironmentLockedError stores environment, locked_by, locked_at, reason."""
        assert EnvironmentLockedError is not None
        error = EnvironmentLockedError(
            environment="staging",
            locked_by="ops@example.com",
            locked_at="2026-01-20T08:00:00Z",
            reason="Maintenance window",
        )
        assert error.environment == "staging"
        assert error.locked_by == "ops@example.com"
        assert error.locked_at == "2026-01-20T08:00:00Z"
        assert error.reason == "Maintenance window"

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_error_message(self) -> None:
        """EnvironmentLockedError formats message correctly."""
        assert EnvironmentLockedError is not None
        error = EnvironmentLockedError(
            environment="prod",
            locked_by="admin@example.com",
            locked_at="2026-01-15T10:30:00Z",
            reason="Database migration",
        )
        msg = str(error)
        assert "prod" in msg
        assert "locked" in msg.lower()

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_error_inherits_oci_error(self) -> None:
        """EnvironmentLockedError inherits from OCIError."""
        assert EnvironmentLockedError is not None
        assert issubclass(EnvironmentLockedError, OCIError)


# Import additional error classes for complete coverage
SignatureVerificationError = getattr(oci_errors, "SignatureVerificationError", None)
ConcurrentSigningError = getattr(oci_errors, "ConcurrentSigningError", None)
SeparationOfDutiesError = getattr(oci_errors, "SeparationOfDutiesError", None)


class TestSignatureVerificationError:
    """Tests for SignatureVerificationError (exit_code=6)."""

    @pytest.mark.requirement("8B-FR-006")
    def test_signature_verification_error_exit_code(self) -> None:
        """SignatureVerificationError has exit code 6."""
        assert SignatureVerificationError is not None
        error = SignatureVerificationError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            reason="No signature found",
        )
        assert error.exit_code == 6

    @pytest.mark.requirement("8B-FR-006")
    def test_signature_verification_error_attributes(self) -> None:
        """SignatureVerificationError stores artifact_ref, reason, signers."""
        assert SignatureVerificationError is not None
        error = SignatureVerificationError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            reason="Signer mismatch",
            expected_signer="repo:acme/floe:ref:refs/heads/main",
            actual_signer="repo:unknown/repo:ref:refs/heads/main",
        )
        assert error.artifact_ref == "oci://registry.example.com/floe:v1.0.0"
        assert error.reason == "Signer mismatch"
        assert error.expected_signer == "repo:acme/floe:ref:refs/heads/main"
        assert error.actual_signer == "repo:unknown/repo:ref:refs/heads/main"

    @pytest.mark.requirement("8B-FR-006")
    def test_signature_verification_error_message_with_signers(self) -> None:
        """SignatureVerificationError includes signer mismatch in message."""
        assert SignatureVerificationError is not None
        error = SignatureVerificationError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            reason="Signer not in trusted issuers",
            expected_signer="expected@example.com",
            actual_signer="actual@example.com",
        )
        msg = str(error)
        assert "expected@example.com" in msg
        assert "actual@example.com" in msg

    @pytest.mark.requirement("8B-FR-006")
    def test_signature_verification_error_remediation_unsigned(self) -> None:
        """SignatureVerificationError provides remediation for unsigned artifacts."""
        assert SignatureVerificationError is not None
        error = SignatureVerificationError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            reason="No signature found - artifact is unsigned",
        )
        msg = str(error)
        assert "Sign the artifact" in msg or "floe artifact sign" in msg

    @pytest.mark.requirement("8B-FR-006")
    def test_signature_verification_error_remediation_signer_mismatch(self) -> None:
        """SignatureVerificationError provides remediation for signer mismatch."""
        assert SignatureVerificationError is not None
        error = SignatureVerificationError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            reason="Signer not in trusted issuers",
        )
        msg = str(error)
        assert "trusted_issuers" in msg or "re-sign" in msg.lower()

    @pytest.mark.requirement("8B-FR-006")
    def test_signature_verification_error_remediation_expired(self) -> None:
        """SignatureVerificationError provides remediation for expired signatures."""
        assert SignatureVerificationError is not None
        error = SignatureVerificationError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            reason="Signature has expired",
        )
        msg = str(error)
        assert "re-sign" in msg.lower() or "--force" in msg

    @pytest.mark.requirement("8B-FR-006")
    def test_signature_verification_error_inherits_oci_error(self) -> None:
        """SignatureVerificationError inherits from OCIError."""
        assert SignatureVerificationError is not None
        assert issubclass(SignatureVerificationError, OCIError)


class TestConcurrentSigningError:
    """Tests for ConcurrentSigningError (exit_code=7)."""

    @pytest.mark.requirement("8B-FR-007")
    def test_concurrent_signing_error_exit_code(self) -> None:
        """ConcurrentSigningError has exit code 7."""
        assert ConcurrentSigningError is not None
        error = ConcurrentSigningError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            timeout_seconds=30.0,
        )
        assert error.exit_code == 7

    @pytest.mark.requirement("8B-FR-007")
    def test_concurrent_signing_error_attributes(self) -> None:
        """ConcurrentSigningError stores artifact_ref and timeout_seconds."""
        assert ConcurrentSigningError is not None
        error = ConcurrentSigningError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            timeout_seconds=60.0,
        )
        assert error.artifact_ref == "oci://registry.example.com/floe:v1.0.0"
        assert error.timeout_seconds == 60.0

    @pytest.mark.requirement("8B-FR-007")
    def test_concurrent_signing_error_message(self) -> None:
        """ConcurrentSigningError formats message with timeout."""
        assert ConcurrentSigningError is not None
        error = ConcurrentSigningError(
            artifact_ref="oci://registry.example.com/floe:v1.0.0",
            timeout_seconds=30.0,
        )
        msg = str(error)
        assert "signing lock" in msg.lower() or "lock" in msg.lower()
        assert "30" in msg  # timeout
        assert "FLOE_SIGNING_LOCK_TIMEOUT" in msg

    @pytest.mark.requirement("8B-FR-007")
    def test_concurrent_signing_error_inherits_oci_error(self) -> None:
        """ConcurrentSigningError inherits from OCIError."""
        assert ConcurrentSigningError is not None
        assert issubclass(ConcurrentSigningError, OCIError)


class TestSeparationOfDutiesError:
    """Tests for SeparationOfDutiesError (exit_code=14)."""

    @pytest.mark.requirement("8C-FR-049")
    def test_separation_of_duties_error_exit_code(self) -> None:
        """SeparationOfDutiesError has exit code 14."""
        assert SeparationOfDutiesError is not None
        error = SeparationOfDutiesError(
            operator="alice@example.com",
            previous_operator="alice@example.com",
            from_env="staging",
            to_env="prod",
        )
        assert error.exit_code == 14

    @pytest.mark.requirement("8C-FR-049")
    def test_separation_of_duties_error_attributes(self) -> None:
        """SeparationOfDutiesError stores operator, previous_operator, envs."""
        assert SeparationOfDutiesError is not None
        error = SeparationOfDutiesError(
            operator="bob@example.com",
            previous_operator="bob@example.com",
            from_env="dev",
            to_env="staging",
        )
        assert error.operator == "bob@example.com"
        assert error.previous_operator == "bob@example.com"
        assert error.from_env == "dev"
        assert error.to_env == "staging"

    @pytest.mark.requirement("8C-FR-049")
    def test_separation_of_duties_error_message(self) -> None:
        """SeparationOfDutiesError formats message with environments."""
        assert SeparationOfDutiesError is not None
        error = SeparationOfDutiesError(
            operator="alice@example.com",
            previous_operator="alice@example.com",
            from_env="staging",
            to_env="prod",
        )
        msg = str(error)
        assert "alice@example.com" in msg
        assert "staging" in msg
        assert "prod" in msg
        assert "separation" in msg.lower() or "different" in msg.lower()

    @pytest.mark.requirement("8C-FR-049")
    def test_separation_of_duties_error_remediation(self) -> None:
        """SeparationOfDutiesError provides remediation steps."""
        assert SeparationOfDutiesError is not None
        error = SeparationOfDutiesError(
            operator="alice@example.com",
            previous_operator="alice@example.com",
            from_env="staging",
            to_env="prod",
        )
        msg = str(error)
        assert "different team member" in msg.lower() or "remediation" in msg.lower()

    @pytest.mark.requirement("8C-FR-049")
    def test_separation_of_duties_error_inherits_oci_error(self) -> None:
        """SeparationOfDutiesError inherits from OCIError."""
        assert SeparationOfDutiesError is not None
        assert issubclass(SeparationOfDutiesError, OCIError)


class TestAuthorizationErrorGuidance:
    """Tests for AuthorizationError.get_actionable_guidance() method."""

    @pytest.mark.requirement("8C-FR-048")
    def test_authorization_error_get_actionable_guidance_with_groups(self) -> None:
        """get_actionable_guidance returns group-based guidance."""
        assert AuthorizationError is not None
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=["platform-admins", "release-managers"],
            reason="Not authorized",
            environment="prod",
        )
        guidance = error.get_actionable_guidance()
        assert "platform-admins" in guidance
        assert "release-managers" in guidance
        assert "floe promote info" in guidance or "floe whoami" in guidance

    @pytest.mark.requirement("8C-FR-048")
    def test_authorization_error_get_actionable_guidance_with_operators(self) -> None:
        """get_actionable_guidance returns operator-based guidance."""
        assert AuthorizationError is not None
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=[],
            reason="Not in allowed operators",
            environment="prod",
            allowed_operators=["admin@example.com", "sre@example.com"],
        )
        guidance = error.get_actionable_guidance()
        assert "allowed operators" in guidance.lower() or "contact" in guidance.lower()

    @pytest.mark.requirement("8C-FR-048")
    def test_authorization_error_message_includes_environment(self) -> None:
        """AuthorizationError message includes environment when provided."""
        assert AuthorizationError is not None
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=["admins"],
            reason="Not authorized",
            environment="prod",
        )
        msg = str(error)
        assert "prod" in msg

    @pytest.mark.requirement("8C-FR-048")
    def test_authorization_error_message_truncates_many_operators(self) -> None:
        """AuthorizationError truncates long allowed_operators list."""
        assert AuthorizationError is not None
        many_operators = [f"user{i}@example.com" for i in range(10)]
        error = AuthorizationError(
            operator="user@example.com",
            required_groups=[],
            reason="Not authorized",
            allowed_operators=many_operators,
        )
        msg = str(error)
        # Should truncate to first 3 and show "... (7 more)"
        assert "more" in msg.lower() or "user0@example.com" in msg
