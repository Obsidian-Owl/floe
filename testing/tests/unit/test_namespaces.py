"""Unit tests for namespace utilities.

Tests for testing.fixtures.namespaces module including generate_unique_namespace()
and validate_namespace().
"""

from __future__ import annotations

import pytest

from testing.fixtures.namespaces import (
    MAX_NAMESPACE_LENGTH,
    InvalidNamespaceError,
    generate_unique_namespace,
    validate_namespace,
)


class TestGenerateUniqueNamespace:
    """Tests for generate_unique_namespace() function."""

    @pytest.mark.requirement("9c-FR-008")
    def test_generates_unique_namespaces(self) -> None:
        """Test that each call generates a unique namespace."""
        namespaces = [generate_unique_namespace("test") for _ in range(10)]
        assert len(set(namespaces)) == 10  # All unique

    @pytest.mark.requirement("9c-FR-008")
    def test_respects_max_length(self) -> None:
        """Test namespace does not exceed K8s max length."""
        ns = generate_unique_namespace("test")
        assert len(ns) <= MAX_NAMESPACE_LENGTH

    @pytest.mark.requirement("9c-FR-008")
    def test_handles_long_prefix(self) -> None:
        """Test namespace is truncated for long prefixes."""
        long_prefix = "a" * 100
        ns = generate_unique_namespace(long_prefix)
        assert len(ns) <= MAX_NAMESPACE_LENGTH

    @pytest.mark.requirement("9c-FR-008")
    def test_lowercase_output(self) -> None:
        """Test namespace is always lowercase."""
        ns = generate_unique_namespace("TEST_PREFIX")
        assert ns.islower()

    @pytest.mark.requirement("9c-FR-008")
    def test_converts_underscores_to_hyphens(self) -> None:
        """Test underscores are converted to hyphens."""
        ns = generate_unique_namespace("test_polaris_catalog")
        assert "_" not in ns
        assert "test-polaris-catalog" in ns

    @pytest.mark.requirement("9c-FR-008")
    def test_removes_invalid_characters(self) -> None:
        """Test invalid characters are removed."""
        ns = generate_unique_namespace("test@prefix#123!")
        assert all(c.isalnum() or c == "-" for c in ns)

    @pytest.mark.requirement("9c-FR-008")
    def test_starts_and_ends_with_alphanumeric(self) -> None:
        """Test namespace starts and ends with alphanumeric character."""
        ns = generate_unique_namespace("test")
        assert ns[0].isalnum()
        assert ns[-1].isalnum()

    @pytest.mark.requirement("9c-FR-008")
    def test_default_prefix(self) -> None:
        """Test default prefix is used when none provided."""
        ns = generate_unique_namespace()
        assert ns.startswith("test-")

    @pytest.mark.requirement("9c-FR-008")
    def test_empty_prefix_uses_default(self) -> None:
        """Test empty prefix falls back to default."""
        ns = generate_unique_namespace("")
        assert ns.startswith("test-")

    @pytest.mark.requirement("9c-FR-008")
    def test_result_is_k8s_valid(self) -> None:
        """Test generated namespace is valid for K8s."""
        ns = generate_unique_namespace("test_prefix")
        assert validate_namespace(ns)


class TestValidateNamespace:
    """Tests for validate_namespace() function."""

    @pytest.mark.requirement("9c-FR-008")
    def test_valid_namespace(self) -> None:
        """Test valid namespace returns True."""
        assert validate_namespace("test-namespace-abc123") is True

    @pytest.mark.requirement("9c-FR-008")
    def test_empty_namespace(self) -> None:
        """Test empty namespace returns False."""
        assert validate_namespace("") is False

    @pytest.mark.requirement("9c-FR-008")
    def test_uppercase_invalid(self) -> None:
        """Test uppercase characters are invalid."""
        assert validate_namespace("Test-Namespace") is False

    @pytest.mark.requirement("9c-FR-008")
    def test_underscore_invalid(self) -> None:
        """Test underscores are invalid."""
        assert validate_namespace("test_namespace") is False

    @pytest.mark.requirement("9c-FR-008")
    def test_starts_with_hyphen_invalid(self) -> None:
        """Test namespace starting with hyphen is invalid."""
        assert validate_namespace("-invalid") is False

    @pytest.mark.requirement("9c-FR-008")
    def test_ends_with_hyphen_invalid(self) -> None:
        """Test namespace ending with hyphen is invalid."""
        assert validate_namespace("invalid-") is False

    @pytest.mark.requirement("9c-FR-008")
    def test_too_long_invalid(self) -> None:
        """Test namespace exceeding max length is invalid."""
        long_ns = "a" * (MAX_NAMESPACE_LENGTH + 1)
        assert validate_namespace(long_ns) is False

    @pytest.mark.requirement("9c-FR-008")
    def test_max_length_valid(self) -> None:
        """Test namespace at max length is valid."""
        max_ns = "a" * MAX_NAMESPACE_LENGTH
        assert validate_namespace(max_ns) is True

    @pytest.mark.requirement("9c-FR-008")
    def test_special_characters_invalid(self) -> None:
        """Test special characters are invalid."""
        assert validate_namespace("test@namespace") is False
        assert validate_namespace("test.namespace") is False
        assert validate_namespace("test namespace") is False


class TestInvalidNamespaceError:
    """Tests for InvalidNamespaceError exception."""

    @pytest.mark.requirement("9c-FR-008")
    def test_error_message(self) -> None:
        """Test error contains namespace and reason."""
        error = InvalidNamespaceError("invalid@ns", "contains special characters")
        assert "invalid@ns" in str(error)
        assert "contains special characters" in str(error)

    @pytest.mark.requirement("9c-FR-008")
    def test_error_attributes(self) -> None:
        """Test error stores namespace and reason."""
        error = InvalidNamespaceError("bad-ns", "too long")
        assert error.namespace == "bad-ns"
        assert error.reason == "too long"
