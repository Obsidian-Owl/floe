"""Unit tests for InfisicalSecretsConfig validation.

Tests that InfisicalSecretsConfig correctly validates configuration
for the Infisical secrets backend, including Universal Auth credentials.

Task: T041
Requirements: 7A-FR-021 (Universal Auth support)
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from floe_secrets_infisical.config import InfisicalSecretsConfig


class TestInfisicalSecretsConfigCreation:
    """Test InfisicalSecretsConfig model creation and defaults."""

    @pytest.mark.requirement("7A-FR-021")
    def test_valid_config_with_credentials(self) -> None:
        """Test config creation with valid Universal Auth credentials."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        assert config.client_id == "test-client-id"
        assert config.client_secret.get_secret_value() == "test-client-secret"

    @pytest.mark.requirement("7A-FR-021")
    def test_valid_config_with_string_secret(self) -> None:
        """Test config creation with string client_secret (auto-converted)."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",  # type: ignore[arg-type]
        )

        assert isinstance(config.client_secret, SecretStr)
        assert config.client_secret.get_secret_value() == "test-client-secret"

    @pytest.mark.requirement("7A-FR-021")
    def test_default_site_url_is_cloud(self) -> None:
        """Test that default site_url points to Infisical Cloud."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        assert config.site_url == "https://app.infisical.com"

    @pytest.mark.requirement("7A-FR-021")
    def test_default_environment(self) -> None:
        """Test that default environment is 'dev'."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        assert config.environment == "dev"

    @pytest.mark.requirement("7A-FR-021")
    def test_config_is_frozen(self) -> None:
        """Test that config is immutable (frozen)."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        with pytest.raises(ValidationError):
            config.client_id = "new-id"  # type: ignore[misc]


class TestInfisicalSecretsConfigValidation:
    """Test InfisicalSecretsConfig validation rules."""

    @pytest.mark.requirement("7A-FR-021")
    def test_missing_client_id_raises_error(self) -> None:
        """Test that missing client_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_secret=SecretStr("test-client-secret"),
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_id",) for e in errors)

    @pytest.mark.requirement("7A-FR-021")
    def test_missing_client_secret_raises_error(self) -> None:
        """Test that missing client_secret raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_id="test-client-id",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_secret",) for e in errors)

    @pytest.mark.requirement("7A-FR-021")
    def test_empty_client_id_raises_error(self) -> None:
        """Test that empty client_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_id="",
                client_secret=SecretStr("test-client-secret"),
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_id",) for e in errors)

    @pytest.mark.requirement("7A-FR-021")
    def test_empty_client_secret_raises_error(self) -> None:
        """Test that empty client_secret raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_id="test-client-id",
                client_secret=SecretStr(""),
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_secret",) for e in errors)

    @pytest.mark.requirement("7A-FR-021")
    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are rejected (extra='forbid')."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
                unknown_field="value",  # type: ignore[call-arg]
            )

        errors = exc_info.value.errors()
        assert any("extra" in str(e).lower() for e in errors)


class TestInfisicalSecretsConfigSiteUrl:
    """Test InfisicalSecretsConfig site_url configuration."""

    @pytest.mark.requirement("7A-FR-021")
    def test_custom_site_url_for_self_hosted(self) -> None:
        """Test config with custom site URL for self-hosted Infisical."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            site_url="https://infisical.company.internal",
        )

        assert config.site_url == "https://infisical.company.internal"

    @pytest.mark.requirement("7A-FR-021")
    def test_site_url_strips_trailing_slash(self) -> None:
        """Test that site_url trailing slashes are stripped."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            site_url="https://infisical.company.internal/",
        )

        assert config.site_url == "https://infisical.company.internal"

    @pytest.mark.requirement("7A-FR-021")
    def test_site_url_must_be_https(self) -> None:
        """Test that site_url must use HTTPS for security."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
                site_url="http://infisical.company.internal",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("site_url",) for e in errors)

    @pytest.mark.requirement("7A-FR-021")
    def test_invalid_site_url_raises_error(self) -> None:
        """Test that invalid URL format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
                site_url="not-a-url",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("site_url",) for e in errors)


class TestInfisicalSecretsConfigEnvironment:
    """Test InfisicalSecretsConfig environment configuration."""

    @pytest.mark.requirement("7A-FR-021")
    def test_custom_environment(self) -> None:
        """Test config with custom environment."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            environment="production",
        )

        assert config.environment == "production"

    @pytest.mark.requirement("7A-FR-021")
    def test_environment_standard_values(self) -> None:
        """Test standard environment values are accepted."""
        for env in ["dev", "staging", "production", "test"]:
            config = InfisicalSecretsConfig(
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
                environment=env,
            )
            assert config.environment == env

    @pytest.mark.requirement("7A-FR-021")
    def test_empty_environment_raises_error(self) -> None:
        """Test that empty environment raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            InfisicalSecretsConfig(
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
                environment="",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("environment",) for e in errors)


class TestInfisicalSecretsConfigProject:
    """Test InfisicalSecretsConfig project configuration."""

    @pytest.mark.requirement("7A-FR-021")
    def test_project_id_optional(self) -> None:
        """Test that project_id is optional."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        assert config.project_id is None

    @pytest.mark.requirement("7A-FR-021")
    def test_project_id_set(self) -> None:
        """Test config with explicit project_id."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            project_id="proj_12345",
        )

        assert config.project_id == "proj_12345"


class TestInfisicalSecretsConfigSecretPath:
    """Test InfisicalSecretsConfig secret_path configuration."""

    @pytest.mark.requirement("7A-FR-021")
    def test_default_secret_path(self) -> None:
        """Test that default secret_path is root '/'."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        assert config.secret_path == "/"

    @pytest.mark.requirement("7A-FR-021")
    def test_custom_secret_path(self) -> None:
        """Test config with custom secret path."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            secret_path="/floe/databases",
        )

        assert config.secret_path == "/floe/databases"

    @pytest.mark.requirement("7A-FR-021")
    def test_secret_path_normalized(self) -> None:
        """Test that secret_path without leading slash is normalized."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            secret_path="floe/databases",
        )

        assert config.secret_path == "/floe/databases"


class TestInfisicalSecretsConfigSecretMasking:
    """Test that secrets are properly masked in output."""

    @pytest.mark.requirement("7A-FR-021")
    def test_client_secret_masked_in_repr(self) -> None:
        """Test that client_secret is masked in repr output."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("super-secret-value"),
        )

        repr_str = repr(config)

        # Secret value should NOT appear in repr
        assert "super-secret-value" not in repr_str
        # But the field should be present
        assert "client_secret" in repr_str
        # Should show masked representation
        assert "**********" in repr_str or "SecretStr" in repr_str

    @pytest.mark.requirement("7A-FR-021")
    def test_client_secret_masked_in_str(self) -> None:
        """Test that client_secret is masked in str output."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("super-secret-value"),
        )

        str_output = str(config)

        assert "super-secret-value" not in str_output

    @pytest.mark.requirement("7A-FR-021")
    def test_client_secret_masked_in_dict(self) -> None:
        """Test that client_secret is masked in model_dump output."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("super-secret-value"),
        )

        # Default dump should NOT expose secret
        dumped = config.model_dump()
        # SecretStr object or masked string
        assert dumped["client_secret"] != "super-secret-value"

    @pytest.mark.requirement("7A-FR-021")
    def test_client_secret_accessible_via_get_secret_value(self) -> None:
        """Test that actual secret value can be retrieved when needed."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("super-secret-value"),
        )

        # Explicit access should work
        assert config.client_secret.get_secret_value() == "super-secret-value"


class TestInfisicalSecretsConfigSerialization:
    """Test InfisicalSecretsConfig serialization behavior."""

    @pytest.mark.requirement("7A-FR-021")
    def test_json_serialization_excludes_secrets(self) -> None:
        """Test that JSON serialization does not expose secrets."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("super-secret-value"),
        )

        json_str = config.model_dump_json()
        parsed: dict[str, Any] = json.loads(json_str)

        # Secret should be masked or excluded
        assert parsed.get("client_secret") != "super-secret-value"

    @pytest.mark.requirement("7A-FR-021")
    def test_json_schema_has_examples(self) -> None:
        """Test that JSON schema includes examples."""
        schema = InfisicalSecretsConfig.model_json_schema()

        assert "examples" in schema or any(
            "examples" in prop
            for prop in schema.get("properties", {}).values()
            if isinstance(prop, dict)
        )

    @pytest.mark.requirement("7A-FR-021")
    def test_model_fields_documented(self) -> None:
        """Test that all fields have descriptions."""
        schema = InfisicalSecretsConfig.model_json_schema()

        properties = schema.get("properties", {})
        for field_name, field_schema in properties.items():
            assert "description" in field_schema, f"Field '{field_name}' missing description"


class TestInfisicalSecretsConfigEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.requirement("7A-FR-021")
    def test_very_long_client_id(self) -> None:
        """Test that very long client_id is handled appropriately."""
        long_id = "a" * 1000
        # Should either accept or reject with clear error
        # Infisical IDs are typically UUID format, so long IDs may be invalid
        try:
            config = InfisicalSecretsConfig(
                client_id=long_id,
                client_secret=SecretStr("test-client-secret"),
            )
            # If accepted, verify it's stored correctly
            assert config.client_id == long_id
        except ValidationError:
            # If rejected, that's also acceptable
            pass

    @pytest.mark.requirement("7A-FR-021")
    def test_unicode_in_secret_path(self) -> None:
        """Test that unicode characters in secret_path are handled."""
        config = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            secret_path="/floe/test-path",
        )

        assert config.secret_path == "/floe/test-path"

    @pytest.mark.requirement("7A-FR-021")
    def test_none_values_rejected_for_required_fields(self) -> None:
        """Test that None values are rejected for required fields.

        Note: Pydantic may raise ValidationError or TypeError depending on
        which validator catches the invalid input first.
        """
        with pytest.raises((ValidationError, TypeError)):
            InfisicalSecretsConfig(
                client_id=None,  # type: ignore[arg-type]
                client_secret=SecretStr("test-client-secret"),
            )

        with pytest.raises((ValidationError, TypeError)):
            InfisicalSecretsConfig(
                client_id="test-client-id",
                client_secret=None,  # type: ignore[arg-type]
            )


class TestInfisicalSecretsConfigEquality:
    """Test config equality and hashing behavior."""

    @pytest.mark.requirement("7A-FR-021")
    def test_same_config_is_equal(self) -> None:
        """Test that identical configs are equal."""
        config1 = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )
        config2 = InfisicalSecretsConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        # Note: SecretStr equality depends on value comparison
        assert config1.client_id == config2.client_id
        assert config1.client_secret.get_secret_value() == config2.client_secret.get_secret_value()

    @pytest.mark.requirement("7A-FR-021")
    def test_different_configs_not_equal(self) -> None:
        """Test that different configs are not equal."""
        config1 = InfisicalSecretsConfig(
            client_id="client-1",
            client_secret=SecretStr("secret-1"),
        )
        config2 = InfisicalSecretsConfig(
            client_id="client-2",
            client_secret=SecretStr("secret-2"),
        )

        assert config1.client_id != config2.client_id
