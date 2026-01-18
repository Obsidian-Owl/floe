"""Unit tests for SecretSource enum and SecretReference model.

Tests validation of secret references including source types,
name patterns, and env var syntax generation.

Task: T010, T053, T054
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
        assert SecretSource.INFISICAL.value == "infisical"

    @pytest.mark.requirement("001-FR-010")
    def test_secret_source_count(self) -> None:
        """Test that exactly 5 secret sources are defined."""
        assert len(SecretSource) == 5

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


class TestConnectionSecretRefValidation:
    """Tests for connection_secret_ref validation in PluginSelection (T053).

    Validates that secret references in plugin configurations follow
    the K8s Secret naming conventions.
    """

    @pytest.mark.requirement("001-FR-010")
    def test_plugin_selection_with_valid_secret_ref(self) -> None:
        """Test that valid connection_secret_ref is accepted.

        Given a PluginSelection with a valid K8s Secret name,
        When creating the selection,
        Then the secret reference is accepted.
        """
        from floe_core.schemas.plugins import PluginSelection

        selection = PluginSelection(
            type="snowflake",
            connection_secret_ref="snowflake-credentials",
        )
        assert selection.connection_secret_ref == "snowflake-credentials"

    @pytest.mark.requirement("001-FR-010")
    def test_plugin_selection_secret_ref_optional(self) -> None:
        """Test that connection_secret_ref is optional.

        Given a PluginSelection without connection_secret_ref,
        When creating the selection,
        Then no error occurs and the field is None.
        """
        from floe_core.schemas.plugins import PluginSelection

        selection = PluginSelection(type="duckdb")
        assert selection.connection_secret_ref is None

    @pytest.mark.requirement("001-FR-010")
    def test_plugin_selection_secret_ref_format_lowercase(self) -> None:
        """Test that secret ref follows K8s naming (lowercase with hyphens).

        Given a PluginSelection with a properly formatted secret name,
        When creating the selection,
        Then the secret reference is validated and accepted.
        """
        from floe_core.schemas.plugins import PluginSelection

        # Valid K8s secret names: lowercase, alphanumeric, hyphens
        valid_names = [
            "db-creds",
            "my-secret-v2",
            "a",
            "secret123",
            "polaris-catalog-credentials",
        ]
        for name in valid_names:
            selection = PluginSelection(type="duckdb", connection_secret_ref=name)
            assert selection.connection_secret_ref == name

    @pytest.mark.requirement("001-FR-010")
    def test_plugin_selection_secret_ref_rejects_invalid_format(self) -> None:
        """Test that invalid secret ref format is rejected.

        Given a PluginSelection with an invalid secret name format,
        When creating the selection,
        Then a validation error is raised.
        """
        from pydantic import ValidationError

        from floe_core.schemas.plugins import PluginSelection

        # Invalid: uppercase letters (K8s secret names must be lowercase)
        with pytest.raises(ValidationError) as exc_info:
            PluginSelection(type="snowflake", connection_secret_ref="MySecret")
        assert "connection_secret_ref" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-010")
    def test_plugin_selection_secret_ref_rejects_empty(self) -> None:
        """Test that empty secret ref is rejected.

        Given a PluginSelection with an empty connection_secret_ref,
        When creating the selection,
        Then a validation error is raised.
        """
        from pydantic import ValidationError

        from floe_core.schemas.plugins import PluginSelection

        with pytest.raises(ValidationError) as exc_info:
            PluginSelection(type="snowflake", connection_secret_ref="")
        assert "connection_secret_ref" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-010")
    def test_plugin_selection_secret_ref_rejects_starts_with_hyphen(self) -> None:
        """Test that secret ref starting with hyphen is rejected.

        Given a PluginSelection with a secret name starting with hyphen,
        When creating the selection,
        Then a validation error is raised.
        """
        from pydantic import ValidationError

        from floe_core.schemas.plugins import PluginSelection

        with pytest.raises(ValidationError) as exc_info:
            PluginSelection(type="snowflake", connection_secret_ref="-invalid")
        assert "connection_secret_ref" in str(exc_info.value)


class TestSecretReferencePlaceholderPreservation:
    """Tests for secret reference placeholder preservation (T054).

    Validates that secret references remain as placeholders and are NOT
    resolved at configuration validation time. Resolution happens at runtime.
    """

    @pytest.mark.requirement("001-FR-010")
    def test_secret_reference_remains_placeholder(self) -> None:
        """Test that SecretReference remains as a placeholder after validation.

        Given a SecretReference with a name,
        When validating and accessing the reference,
        Then the reference contains the name, not the resolved value.
        """
        ref = SecretReference(name="db-password")

        # The reference should contain the NAME, not the actual secret value
        assert ref.name == "db-password"
        # There should be NO method to get the actual secret value
        assert not hasattr(ref, "get_secret_value")
        assert not hasattr(ref, "resolve")

    @pytest.mark.requirement("001-FR-010")
    def test_secret_reference_no_resolution_at_validation(self) -> None:
        """Test that validation does not attempt to resolve secrets.

        Given a SecretReference with a non-existent secret name,
        When validating the reference,
        Then validation succeeds (no resolution attempted).
        """
        # This secret doesn't exist anywhere, but validation should pass
        # because we're only validating the format, not resolving the secret
        ref = SecretReference(
            source=SecretSource.VAULT,
            name="nonexistent-secret-abc123",
            key="password",
        )
        assert ref.name == "nonexistent-secret-abc123"
        # Validation passed - no resolution was attempted

    @pytest.mark.requirement("001-FR-010")
    def test_secret_reference_serialization_preserves_placeholder(self) -> None:
        """Test that serialization preserves the placeholder, not a resolved value.

        Given a SecretReference,
        When serializing to dict or JSON,
        Then the output contains the reference name, not a resolved value.
        """
        ref = SecretReference(
            source=SecretSource.KUBERNETES,
            name="api-key",
            key="token",
        )

        # Serialize to dict
        data = ref.model_dump()
        assert data["name"] == "api-key"
        assert data["key"] == "token"
        assert data["source"] == "kubernetes"
        # Should NOT have any "value" or "resolved" field
        assert "value" not in data
        assert "resolved" not in data
        assert "secret" not in data

    @pytest.mark.requirement("001-FR-010")
    def test_secret_reference_in_plugin_remains_placeholder(self) -> None:
        """Test that secret ref in PluginSelection remains as placeholder.

        Given a PluginSelection with connection_secret_ref,
        When accessing the plugin configuration,
        Then the secret reference is still a name, not resolved.
        """
        from floe_core.schemas.plugins import PluginSelection

        selection = PluginSelection(
            type="snowflake",
            connection_secret_ref="snowflake-creds",
        )

        # The connection_secret_ref should be the NAME only
        assert selection.connection_secret_ref == "snowflake-creds"
        # Should NOT be the actual credentials

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_syntax_is_template_not_value(self) -> None:
        """Test that to_env_var_syntax returns a template, not the value.

        Given a SecretReference,
        When calling to_env_var_syntax(),
        Then the result is a template string referencing an env var.
        """
        ref = SecretReference(name="db-password")
        syntax = ref.to_env_var_syntax()

        # Should be a Jinja/dbt template, NOT the actual password
        assert "env_var" in syntax
        assert "FLOE_SECRET" in syntax
        assert "{{" in syntax  # Template syntax
        # Should NOT contain any actual secret values
        assert "password123" not in syntax
        assert "actual_secret" not in syntax
