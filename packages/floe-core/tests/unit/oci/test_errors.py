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
