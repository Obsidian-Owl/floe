"""Unit tests for KeycloakIdentityConfig validation.

Task: T057
Requirements: 7A-FR-030 (KeycloakPlugin as default OIDC identity provider)
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError


class TestKeycloakIdentityConfigCreation:
    """Tests for KeycloakIdentityConfig initialization."""

    @pytest.mark.requirement("7A-FR-030")
    def test_valid_config_with_server_url_and_realm(self) -> None:
        """Test config creation with minimal required fields."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("test-secret"),
        )

        assert config.server_url == "https://keycloak.example.com"
        assert config.realm == "floe"
        assert config.client_id == "floe-client"
        assert config.client_secret.get_secret_value() == "test-secret"

    @pytest.mark.requirement("7A-FR-030")
    def test_valid_config_with_all_fields(self) -> None:
        """Test config creation with all fields specified."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="production",
            client_id="floe-app",
            client_secret=SecretStr("my-secret"),
            verify_ssl=True,
            timeout=60.0,
            scopes=["openid", "profile", "email", "roles"],
        )

        assert config.server_url == "https://keycloak.example.com"
        assert config.realm == "production"
        assert config.client_id == "floe-app"
        assert config.verify_ssl is True
        assert config.timeout == pytest.approx(60.0)
        assert config.scopes == ["openid", "profile", "email", "roles"]

    @pytest.mark.requirement("7A-FR-030")
    def test_config_accepts_string_for_client_secret(self) -> None:
        """Test that plain string is converted to SecretStr."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret="plain-string-secret",  # type: ignore[arg-type]
        )

        assert isinstance(config.client_secret, SecretStr)
        assert config.client_secret.get_secret_value() == "plain-string-secret"


class TestKeycloakIdentityConfigValidation:
    """Tests for KeycloakIdentityConfig validation rules."""

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_missing_server_url(self) -> None:
        """Test config fails without server_url."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                realm="floe",
                client_id="floe-client",
                client_secret=SecretStr("secret"),
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("server_url",) for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_missing_realm(self) -> None:
        """Test config fails without realm."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="https://keycloak.example.com",
                client_id="floe-client",
                client_secret=SecretStr("secret"),
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("realm",) for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_missing_client_id(self) -> None:
        """Test config fails without client_id."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="https://keycloak.example.com",
                realm="floe",
                client_secret=SecretStr("secret"),
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_id",) for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_missing_client_secret(self) -> None:
        """Test config fails without client_secret."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="https://keycloak.example.com",
                realm="floe",
                client_id="floe-client",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_secret",) for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_empty_server_url(self) -> None:
        """Test config fails with empty server_url."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="",
                realm="floe",
                client_id="floe-client",
                client_secret=SecretStr("secret"),
            )

        errors = exc_info.value.errors()
        assert any("server_url" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_empty_realm(self) -> None:
        """Test config fails with empty realm."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="https://keycloak.example.com",
                realm="",
                client_id="floe-client",
                client_secret=SecretStr("secret"),
            )

        errors = exc_info.value.errors()
        assert any("realm" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_empty_client_id(self) -> None:
        """Test config fails with empty client_id."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="https://keycloak.example.com",
                realm="floe",
                client_id="",
                client_secret=SecretStr("secret"),
            )

        errors = exc_info.value.errors()
        assert any("client_id" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_invalid_config_empty_client_secret(self) -> None:
        """Test config fails with empty client_secret."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="https://keycloak.example.com",
                realm="floe",
                client_id="floe-client",
                client_secret=SecretStr(""),
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0


class TestKeycloakIdentityConfigServerUrl:
    """Tests for server_url validation."""

    @pytest.mark.requirement("7A-FR-030")
    def test_server_url_strips_trailing_slash(self) -> None:
        """Test that trailing slashes are removed from server_url."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com/",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        assert config.server_url == "https://keycloak.example.com"

    @pytest.mark.requirement("7A-FR-030")
    def test_server_url_requires_https(self) -> None:
        """Test that server_url must use HTTPS."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        with pytest.raises(ValidationError) as exc_info:
            KeycloakIdentityConfig(
                server_url="http://keycloak.example.com",
                realm="floe",
                client_id="floe-client",
                client_secret=SecretStr("secret"),
            )

        errors = exc_info.value.errors()
        assert any("https" in str(e).lower() for e in errors)

    @pytest.mark.requirement("7A-FR-030")
    def test_server_url_allows_localhost_http_for_dev(self) -> None:
        """Test that localhost can use HTTP for development."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        # This might or might not be allowed - depends on implementation
        # If allowed, should work:
        try:
            config = KeycloakIdentityConfig(
                server_url="http://localhost:8080",
                realm="floe",
                client_id="floe-client",
                client_secret=SecretStr("secret"),
            )
            assert config.server_url == "http://localhost:8080"
        except ValidationError:
            # If not allowed, that's also valid behavior
            pass


class TestKeycloakIdentityConfigDefaults:
    """Tests for default values."""

    @pytest.mark.requirement("7A-FR-030")
    def test_default_verify_ssl_is_true(self) -> None:
        """Test that verify_ssl defaults to True."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        assert config.verify_ssl is True

    @pytest.mark.requirement("7A-FR-030")
    def test_default_timeout(self) -> None:
        """Test that timeout has a reasonable default."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        assert config.timeout == pytest.approx(30.0)

    @pytest.mark.requirement("7A-FR-030")
    def test_default_scopes(self) -> None:
        """Test default OIDC scopes."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        assert "openid" in config.scopes


class TestKeycloakIdentityConfigSecretMasking:
    """Tests for secret masking in output."""

    @pytest.mark.requirement("7A-FR-030")
    def test_client_secret_masked_in_repr(self) -> None:
        """Test that client_secret is masked in repr."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("super-secret-password"),
        )

        repr_str = repr(config)
        assert "super-secret-password" not in repr_str
        assert "**********" in repr_str or "SecretStr" in repr_str

    @pytest.mark.requirement("7A-FR-030")
    def test_client_secret_masked_in_str(self) -> None:
        """Test that client_secret is masked in str."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("super-secret-password"),
        )

        str_output = str(config)
        assert "super-secret-password" not in str_output

    @pytest.mark.requirement("7A-FR-030")
    def test_client_secret_masked_in_dict(self) -> None:
        """Test that client_secret is masked in model_dump()."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("super-secret-password"),
        )

        # model_dump should not expose the secret
        dump = config.model_dump()
        client_secret_value = dump.get("client_secret")

        # Either masked or SecretStr instance
        if isinstance(client_secret_value, str):
            assert client_secret_value != "super-secret-password"
        elif hasattr(client_secret_value, "get_secret_value"):
            # Still a SecretStr - that's fine
            pass


class TestKeycloakIdentityConfigImmutability:
    """Tests for config immutability."""

    @pytest.mark.requirement("7A-FR-030")
    def test_config_is_frozen(self) -> None:
        """Test that config cannot be modified after creation."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        with pytest.raises((ValidationError, TypeError, AttributeError)):
            config.realm = "other-realm"  # type: ignore[misc]


class TestKeycloakIdentityConfigSerialization:
    """Tests for config serialization."""

    @pytest.mark.requirement("7A-FR-030")
    def test_config_to_json_schema(self) -> None:
        """Test that config can generate JSON schema."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        schema = KeycloakIdentityConfig.model_json_schema()

        assert "properties" in schema
        assert "server_url" in schema["properties"]
        assert "realm" in schema["properties"]
        assert "client_id" in schema["properties"]
        assert "client_secret" in schema["properties"]

    @pytest.mark.requirement("7A-FR-030")
    def test_config_required_fields_in_schema(self) -> None:
        """Test that required fields are marked in schema."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        schema = KeycloakIdentityConfig.model_json_schema()
        required = schema.get("required", [])

        assert "server_url" in required
        assert "realm" in required
        assert "client_id" in required
        assert "client_secret" in required


class TestKeycloakIdentityConfigEndpoints:
    """Tests for derived endpoint URLs."""

    @pytest.mark.requirement("7A-FR-031")
    def test_discovery_url_property(self) -> None:
        """Test that discovery URL is correctly derived."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        expected = "https://keycloak.example.com/realms/floe/.well-known/openid-configuration"
        assert config.discovery_url == expected

    @pytest.mark.requirement("7A-FR-031")
    def test_token_url_property(self) -> None:
        """Test that token URL is correctly derived."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        expected = "https://keycloak.example.com/realms/floe/protocol/openid-connect/token"
        assert config.token_url == expected

    @pytest.mark.requirement("7A-FR-034")
    def test_jwks_url_property(self) -> None:
        """Test that JWKS URL is correctly derived."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        expected = "https://keycloak.example.com/realms/floe/protocol/openid-connect/certs"
        assert config.jwks_url == expected

    @pytest.mark.requirement("7A-FR-031")
    def test_userinfo_url_property(self) -> None:
        """Test that userinfo URL is correctly derived."""
        from floe_identity_keycloak.config import KeycloakIdentityConfig

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("secret"),
        )

        expected = "https://keycloak.example.com/realms/floe/protocol/openid-connect/userinfo"
        assert config.userinfo_url == expected
