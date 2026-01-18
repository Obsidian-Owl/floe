"""Unit tests for SecretReference env var name generation.

Tests the SecretReference model and its to_env_var_syntax() method
for various input patterns and edge cases.

Task: T035
Requirements: 7A-FR-010 (Secret Reference Handling)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.secrets import SecretReference, SecretSource


class TestSecretReferenceModel:
    """Unit tests for SecretReference model creation."""

    @pytest.mark.requirement("7A-FR-010")
    def test_create_with_name_only(self) -> None:
        """Test creating SecretReference with only required name."""
        ref = SecretReference(name="test-secret")

        assert ref.name == "test-secret"
        assert ref.source == SecretSource.KUBERNETES
        assert ref.key is None

    @pytest.mark.requirement("7A-FR-010")
    def test_create_with_all_fields(self) -> None:
        """Test creating SecretReference with all fields."""
        ref = SecretReference(
            source=SecretSource.VAULT,
            name="db-creds",
            key="password",
        )

        assert ref.source == SecretSource.VAULT
        assert ref.name == "db-creds"
        assert ref.key == "password"

    @pytest.mark.requirement("7A-FR-010")
    def test_create_with_each_source(self) -> None:
        """Test creating SecretReference with each SecretSource."""
        for source in SecretSource:
            ref = SecretReference(source=source, name="test")
            assert ref.source == source

    @pytest.mark.requirement("7A-FR-010")
    def test_single_char_name_valid(self) -> None:
        """Test single character names are valid."""
        ref = SecretReference(name="a")
        assert ref.name == "a"

    @pytest.mark.requirement("7A-FR-010")
    def test_max_length_name_valid(self) -> None:
        """Test maximum length names (253 chars per K8s limits)."""
        # 253 is the K8s max secret name length
        name = "a" + "b" * 251 + "c"  # 253 chars, starts and ends alphanumeric
        ref = SecretReference(name=name)
        assert len(ref.name) == 253

    @pytest.mark.requirement("7A-FR-010")
    def test_name_exceeds_max_length_fails(self) -> None:
        """Test names over 253 chars are rejected."""
        name = "a" * 254
        with pytest.raises(ValidationError, match="String should have at most 253"):
            SecretReference(name=name)


class TestSecretReferenceNameValidation:
    """Unit tests for SecretReference name validation patterns."""

    @pytest.mark.requirement("7A-FR-010")
    def test_valid_alphanumeric_names(self) -> None:
        """Test various valid alphanumeric names."""
        valid_names = [
            "a",
            "ab",
            "abc",
            "a1",
            "1a",
            "123",
            "abc123",
            "123abc",
        ]
        for name in valid_names:
            ref = SecretReference(name=name)
            assert ref.name == name, f"Expected {name} to be valid"

    @pytest.mark.requirement("7A-FR-010")
    def test_valid_hyphenated_names(self) -> None:
        """Test valid names with hyphens."""
        valid_names = [
            "a-b",
            "a-b-c",
            "db-password",
            "polaris-credentials",
            "my-secret-123",
            "123-secret-456",
        ]
        for name in valid_names:
            ref = SecretReference(name=name)
            assert ref.name == name, f"Expected {name} to be valid"

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_leading_hyphen(self) -> None:
        """Test names starting with hyphen are invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="-invalid")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_trailing_hyphen(self) -> None:
        """Test names ending with hyphen are invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="invalid-")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_uppercase(self) -> None:
        """Test uppercase names are invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="UPPERCASE")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_mixed_case(self) -> None:
        """Test mixed case names are invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="mixedCase")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_underscore(self) -> None:
        """Test names with underscores are invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="has_underscore")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_dot(self) -> None:
        """Test names with dots are invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="has.dot")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_space(self) -> None:
        """Test names with spaces are invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="has space")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_empty_string(self) -> None:
        """Test empty string is invalid."""
        with pytest.raises(ValidationError):
            SecretReference(name="")

    @pytest.mark.requirement("7A-FR-010")
    def test_invalid_special_chars(self) -> None:
        """Test various special characters are invalid."""
        invalid_chars = ["@", "#", "$", "%", "^", "&", "*", "(", ")", "!"]
        for char in invalid_chars:
            with pytest.raises(ValidationError):
                SecretReference(name=f"test{char}secret")


class TestSecretReferenceEnvVarGeneration:
    """Unit tests for to_env_var_syntax() method."""

    @pytest.mark.requirement("7A-FR-010")
    def test_simple_name_conversion(self) -> None:
        """Test simple name is converted correctly."""
        ref = SecretReference(name="test")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_TEST') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_hyphenated_name_becomes_underscored(self) -> None:
        """Test hyphens are converted to underscores."""
        ref = SecretReference(name="db-password")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_DB_PASSWORD') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_multiple_hyphens_converted(self) -> None:
        """Test multiple hyphens are all converted."""
        ref = SecretReference(name="my-long-secret-name")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_MY_LONG_SECRET_NAME') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_name_uppercased(self) -> None:
        """Test lowercase name is uppercased."""
        ref = SecretReference(name="lowercase")
        result = ref.to_env_var_syntax()
        assert "LOWERCASE" in result

    @pytest.mark.requirement("7A-FR-010")
    def test_with_key_appended(self) -> None:
        """Test key is appended with underscore."""
        ref = SecretReference(name="db-creds", key="password")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_DB_CREDS_PASSWORD') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_key_hyphens_converted(self) -> None:
        """Test key hyphens are also converted to underscores."""
        ref = SecretReference(name="api-config", key="api-key")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_API_CONFIG_API_KEY') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_key_uppercased(self) -> None:
        """Test key is uppercased."""
        ref = SecretReference(name="secret", key="value")
        result = ref.to_env_var_syntax()
        assert "VALUE" in result

    @pytest.mark.requirement("7A-FR-010")
    def test_numeric_name(self) -> None:
        """Test numeric components in name work correctly."""
        ref = SecretReference(name="db1-creds")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_DB1_CREDS') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_numeric_key(self) -> None:
        """Test numeric key works correctly."""
        ref = SecretReference(name="secrets", key="key1")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_SECRETS_KEY1') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_floe_secret_prefix_present(self) -> None:
        """Test FLOE_SECRET_ prefix is always present."""
        test_cases = [
            SecretReference(name="a"),
            SecretReference(name="test-secret"),
            SecretReference(name="db-creds", key="pass"),
        ]
        for ref in test_cases:
            result = ref.to_env_var_syntax()
            assert "FLOE_SECRET_" in result

    @pytest.mark.requirement("7A-FR-010")
    def test_dbt_jinja_syntax_valid(self) -> None:
        """Test output is valid dbt Jinja syntax."""
        ref = SecretReference(name="test")
        result = ref.to_env_var_syntax()

        # Must have proper Jinja delimiters with spaces
        assert result.startswith("{{ ")
        assert result.endswith(" }}")

        # Must use env_var function
        assert "env_var(" in result

        # Must have proper quoting
        assert "env_var('" in result
        assert "')" in result


class TestSecretReferenceEdgeCases:
    """Unit tests for edge cases and special scenarios."""

    @pytest.mark.requirement("7A-FR-010")
    def test_single_char_name_env_var(self) -> None:
        """Test single char name produces valid env var."""
        ref = SecretReference(name="a")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_A') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_single_char_key_env_var(self) -> None:
        """Test single char key produces valid env var."""
        ref = SecretReference(name="secret", key="k")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_SECRET_K') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_none_key_not_included(self) -> None:
        """Test None key is not included in env var name."""
        ref = SecretReference(name="test", key=None)
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_TEST') }}"
        # Should not have trailing underscore
        assert "TEST_')" in result

    @pytest.mark.requirement("7A-FR-010")
    def test_empty_string_key_treated_as_no_key(self) -> None:
        """Test empty string key produces same result as no key.

        Empty string is falsy in Python, so should behave like None.
        """
        ref_with_empty = SecretReference(name="test", key="")
        ref_without = SecretReference(name="test")

        # Both should produce same output (empty string is falsy)
        result_empty = ref_with_empty.to_env_var_syntax()
        result_none = ref_without.to_env_var_syntax()

        assert result_empty == result_none

    @pytest.mark.requirement("7A-FR-010")
    def test_source_does_not_affect_env_var(self) -> None:
        """Test different sources produce same env var syntax."""
        results: set[str] = set()
        for source in SecretSource:
            ref = SecretReference(source=source, name="test-secret", key="value")
            results.add(ref.to_env_var_syntax())

        # All sources should produce identical output
        assert len(results) == 1
        assert "{{ env_var('FLOE_SECRET_TEST_SECRET_VALUE') }}" in results


class TestSecretReferenceHashability:
    """Unit tests for hashability (frozen model)."""

    @pytest.mark.requirement("7A-FR-010")
    def test_can_be_used_as_dict_key(self) -> None:
        """Test SecretReference can be used as dictionary key.

        Frozen Pydantic models are hashable at runtime, even though
        Pyright doesn't recognize this statically.
        """
        ref = SecretReference(name="test")
        # Frozen Pydantic models are hashable - Pyright doesn't know this
        mapping: dict[object, str] = {ref: "value"}

        assert mapping[ref] == "value"

    @pytest.mark.requirement("7A-FR-010")
    def test_can_be_added_to_set(self) -> None:
        """Test SecretReference can be added to a set.

        Frozen Pydantic models are hashable at runtime.
        """
        ref1 = SecretReference(name="test")
        ref2 = SecretReference(name="test")
        ref3 = SecretReference(name="other")

        # Use object set since Pyright doesn't recognize frozen models as hashable
        refs: set[object] = {ref1, ref2, ref3}

        # ref1 and ref2 are equal, so set should have 2 items
        assert len(refs) == 2

    @pytest.mark.requirement("7A-FR-010")
    def test_equal_refs_have_same_hash(self) -> None:
        """Test equal references have the same hash."""
        ref1 = SecretReference(name="test", key="value")
        ref2 = SecretReference(name="test", key="value")

        assert ref1 == ref2
        assert hash(ref1) == hash(ref2)

    @pytest.mark.requirement("7A-FR-010")
    def test_different_refs_have_different_hash(self) -> None:
        """Test different references have different hashes (usually)."""
        ref1 = SecretReference(name="test1")
        ref2 = SecretReference(name="test2")

        # Different refs should usually have different hashes
        # Note: hash collision is possible but unlikely for simple strings
        assert ref1 != ref2
        # We can't guarantee different hashes due to collision possibility
