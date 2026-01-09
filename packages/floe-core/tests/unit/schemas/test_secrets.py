"""Unit tests for SecretSource enum and SecretReference model.

Tests validation of secret references including source types,
name patterns, and env var syntax generation.

Task: T010
Requirements: FR-010
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.secrets import (
    SECRET_NAME_PATTERN,
    SecretReference,
    SecretSource,
)


class TestSecretSourceEnum:
    """Tests for SecretSource enum values."""

    @pytest.mark.requirement("001-FR-010")
    def test_secret_source_values(self) -> None:
        """Test that all expected secret sources are defined."""
        assert SecretSource.ENV.value == "env"
        assert SecretSource.KUBERNETES.value == "kubernetes"
        assert SecretSource.VAULT.value == "vault"
        assert SecretSource.EXTERNAL_SECRETS.value == "external-secrets"

    @pytest.mark.requirement("001-FR-010")
    def test_secret_source_count(self) -> None:
        """Test that exactly 4 secret sources are defined."""
        assert len(SecretSource) == 4

    @pytest.mark.requirement("001-FR-010")
    def test_secret_source_string_enum(self) -> None:
        """Test that SecretSource is a string enum."""
        assert isinstance(SecretSource.KUBERNETES, str)
        assert SecretSource.KUBERNETES == "kubernetes"


class TestSecretReferenceValidation:
    """Tests for SecretReference validation rules."""

    @pytest.mark.requirement("001-FR-010")
    def test_valid_reference_minimal(self) -> None:
        """Test that minimal valid reference is accepted."""
        ref = SecretReference(name="db-password")
        assert ref.name == "db-password"
        assert ref.source == SecretSource.KUBERNETES  # default
        assert ref.key is None

    @pytest.mark.requirement("001-FR-010")
    def test_valid_reference_full(self) -> None:
        """Test that full valid reference is accepted."""
        ref = SecretReference(
            source=SecretSource.VAULT,
            name="database-credentials",
            key="password",
        )
        assert ref.source == SecretSource.VAULT
        assert ref.name == "database-credentials"
        assert ref.key == "password"

    @pytest.mark.requirement("001-FR-010")
    def test_valid_reference_all_sources(self) -> None:
        """Test that all secret sources are accepted."""
        for source in SecretSource:
            ref = SecretReference(source=source, name="test-secret")
            assert ref.source == source

    @pytest.mark.requirement("001-FR-010")
    def test_name_pattern_valid_simple(self) -> None:
        """Test that simple name is valid."""
        ref = SecretReference(name="a")
        assert ref.name == "a"

    @pytest.mark.requirement("001-FR-010")
    def test_name_pattern_valid_with_hyphens(self) -> None:
        """Test that name with hyphens is valid."""
        ref = SecretReference(name="my-secret-v2")
        assert ref.name == "my-secret-v2"

    @pytest.mark.requirement("001-FR-010")
    def test_name_pattern_valid_numbers(self) -> None:
        """Test that name with numbers is valid."""
        ref = SecretReference(name="secret123")
        assert ref.name == "secret123"

    @pytest.mark.requirement("001-FR-010")
    def test_name_pattern_invalid_uppercase(self) -> None:
        """Test that uppercase name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SecretReference(name="MySecret")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-010")
    def test_name_pattern_invalid_starts_with_hyphen(self) -> None:
        """Test that name starting with hyphen is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SecretReference(name="-secret")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-010")
    def test_name_pattern_invalid_ends_with_hyphen(self) -> None:
        """Test that name ending with hyphen is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SecretReference(name="secret-")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-010")
    def test_name_pattern_invalid_underscore(self) -> None:
        """Test that name with underscore is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SecretReference(name="my_secret")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-010")
    def test_name_empty_rejected(self) -> None:
        """Test that empty name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SecretReference(name="")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-010")
    def test_reference_immutable(self) -> None:
        """Test that SecretReference is immutable (frozen)."""
        ref = SecretReference(name="test")
        with pytest.raises(ValidationError):
            ref.name = "changed"  # type: ignore[misc]

    @pytest.mark.requirement("001-FR-010")
    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SecretReference(
                name="test",
                extra_field="not allowed",  # type: ignore[call-arg]
            )
        assert "extra" in str(exc_info.value).lower()


class TestSecretReferenceEnvVarSyntax:
    """Tests for to_env_var_syntax() method."""

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_syntax_simple(self) -> None:
        """Test env var syntax for simple secret name."""
        ref = SecretReference(name="db-password")
        expected = "{{ env_var('FLOE_SECRET_DB_PASSWORD') }}"
        assert ref.to_env_var_syntax() == expected

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_syntax_with_key(self) -> None:
        """Test env var syntax with key."""
        ref = SecretReference(name="db-creds", key="password")
        expected = "{{ env_var('FLOE_SECRET_DB_CREDS_PASSWORD') }}"
        assert ref.to_env_var_syntax() == expected

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_syntax_hyphen_conversion(self) -> None:
        """Test that hyphens are converted to underscores."""
        ref = SecretReference(name="my-super-secret")
        expected = "{{ env_var('FLOE_SECRET_MY_SUPER_SECRET') }}"
        assert ref.to_env_var_syntax() == expected

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_syntax_uppercase(self) -> None:
        """Test that result is uppercase."""
        ref = SecretReference(name="secret")
        result = ref.to_env_var_syntax()
        # Check the env var name part is uppercase
        assert "FLOE_SECRET_SECRET" in result


class TestSecretReferencePatterns:
    """Tests for exported pattern constants."""

    @pytest.mark.requirement("001-FR-010")
    def test_secret_name_pattern_exported(self) -> None:
        """Test that SECRET_NAME_PATTERN constant is exported."""
        assert SECRET_NAME_PATTERN is not None
        assert isinstance(SECRET_NAME_PATTERN, str)
