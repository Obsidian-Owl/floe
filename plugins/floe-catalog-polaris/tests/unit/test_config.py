"""Unit tests for Polaris catalog plugin configuration models.

This module tests the Pydantic configuration models for OAuth2 and
Polaris catalog connections, ensuring proper validation and constraints.

Requirements Covered:
    - FR-034: Configuration through Pydantic models with validation
    - FR-036: Configuration validation at plugin initialization
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig


class TestOAuth2ConfigValidation:
    """Unit tests for OAuth2Config validation."""

    @pytest.mark.requirement("FR-034")
    def test_valid_oauth2_config(self) -> None:
        """Test OAuth2Config creation with valid parameters."""
        config = OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        )

        assert config.client_id == "test-client"
        assert isinstance(config.client_secret, SecretStr)
        assert config.token_url == "https://auth.example.com/oauth/token"
        assert config.scope is None
        assert config.refresh_margin_seconds == 60  # default

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_with_all_fields(self) -> None:
        """Test OAuth2Config with all optional fields specified."""
        config = OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
            scope="PRINCIPAL_ROLE:ALL",
            refresh_margin_seconds=120,
        )

        assert config.scope == "PRINCIPAL_ROLE:ALL"
        assert config.refresh_margin_seconds == 120

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_empty_client_id_fails(self) -> None:
        """Test OAuth2Config rejects empty client_id."""
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_id",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_missing_client_id_fails(self) -> None:
        """Test OAuth2Config requires client_id."""
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_id",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_missing_client_secret_fails(self) -> None:
        """Test OAuth2Config requires client_secret."""
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="test-client",
                token_url="https://auth.example.com/oauth/token",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("client_secret",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_invalid_token_url_fails(self) -> None:
        """Test OAuth2Config rejects invalid token_url (not http/https)."""
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="ftp://invalid.example.com/token",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("token_url",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_http_token_url_allowed(self) -> None:
        """Test OAuth2Config accepts http:// URL (for dev environments)."""
        config = OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="http://localhost:8181/oauth/token",
        )

        assert config.token_url == "http://localhost:8181/oauth/token"

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_refresh_margin_too_low(self) -> None:
        """Test OAuth2Config rejects refresh_margin_seconds below minimum."""
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
                refresh_margin_seconds=5,  # min is 10
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("refresh_margin_seconds",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_refresh_margin_too_high(self) -> None:
        """Test OAuth2Config rejects refresh_margin_seconds above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
                refresh_margin_seconds=500,  # max is 300
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("refresh_margin_seconds",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_is_frozen(self) -> None:
        """Test OAuth2Config is immutable (frozen)."""
        config = OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        )

        with pytest.raises(ValidationError):
            config.client_id = "new-client"

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_forbids_extra_fields(self) -> None:
        """Test OAuth2Config rejects unknown fields."""
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
                unknown_field="value",
            )

        errors = exc_info.value.errors()
        assert any("extra" in str(e).lower() for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_oauth2_config_secret_str_hides_value(self) -> None:
        """Test client_secret is hidden in string representation."""
        config = OAuth2Config(
            client_id="test-client",
            client_secret="super-secret-value",
            token_url="https://auth.example.com/oauth/token",
        )

        # SecretStr hides value in repr/str
        config_str = str(config)
        assert "super-secret-value" not in config_str
        assert "**********" in config_str or "SecretStr" in config_str


class TestPolarisCatalogConfigValidation:
    """Unit tests for PolarisCatalogConfig validation."""

    def _create_valid_oauth2(self) -> OAuth2Config:
        """Create a valid OAuth2Config for testing."""
        return OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        )

    @pytest.mark.requirement("FR-034")
    def test_valid_polaris_config(self) -> None:
        """Test PolarisCatalogConfig creation with valid parameters."""
        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default_warehouse",
            oauth2=self._create_valid_oauth2(),
        )

        assert config.uri == "https://polaris.example.com/api/catalog"
        assert config.warehouse == "default_warehouse"
        assert isinstance(config.oauth2, OAuth2Config)
        # Check defaults
        assert config.connect_timeout_seconds == 10
        assert config.read_timeout_seconds == 30
        assert config.max_retries == 5
        assert config.credential_vending_enabled is True

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_with_all_fields(self) -> None:
        """Test PolarisCatalogConfig with all optional fields specified."""
        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="prod_warehouse",
            oauth2=self._create_valid_oauth2(),
            connect_timeout_seconds=15,
            read_timeout_seconds=60,
            max_retries=3,
            credential_vending_enabled=False,
        )

        assert config.connect_timeout_seconds == 15
        assert config.read_timeout_seconds == 60
        assert config.max_retries == 3
        assert config.credential_vending_enabled is False

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_invalid_uri_fails(self) -> None:
        """Test PolarisCatalogConfig rejects invalid URI (not http/https)."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="ftp://polaris.example.com/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("uri",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_http_uri_allowed(self) -> None:
        """Test PolarisCatalogConfig accepts http:// URI (for dev)."""
        config = PolarisCatalogConfig(
            uri="http://localhost:8181/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
        )

        assert config.uri == "http://localhost:8181/api/catalog"

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_empty_warehouse_fails(self) -> None:
        """Test PolarisCatalogConfig rejects empty warehouse."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="",
                oauth2=self._create_valid_oauth2(),
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("warehouse",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_missing_uri_fails(self) -> None:
        """Test PolarisCatalogConfig requires uri."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("uri",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_missing_warehouse_fails(self) -> None:
        """Test PolarisCatalogConfig requires warehouse."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                oauth2=self._create_valid_oauth2(),
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("warehouse",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_missing_oauth2_fails(self) -> None:
        """Test PolarisCatalogConfig requires oauth2."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("oauth2",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_connect_timeout_too_low(self) -> None:
        """Test PolarisCatalogConfig rejects connect_timeout below minimum."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
                connect_timeout_seconds=0,  # min is 1
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("connect_timeout_seconds",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_connect_timeout_too_high(self) -> None:
        """Test PolarisCatalogConfig rejects connect_timeout above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
                connect_timeout_seconds=120,  # max is 60
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("connect_timeout_seconds",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_read_timeout_too_low(self) -> None:
        """Test PolarisCatalogConfig rejects read_timeout below minimum."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
                read_timeout_seconds=0,  # min is 1
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("read_timeout_seconds",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_read_timeout_too_high(self) -> None:
        """Test PolarisCatalogConfig rejects read_timeout above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
                read_timeout_seconds=500,  # max is 300
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("read_timeout_seconds",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_max_retries_negative_fails(self) -> None:
        """Test PolarisCatalogConfig rejects negative max_retries."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
                max_retries=-1,  # min is 0
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("max_retries",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_max_retries_too_high(self) -> None:
        """Test PolarisCatalogConfig rejects max_retries above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
                max_retries=20,  # max is 10
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("max_retries",) for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_is_frozen(self) -> None:
        """Test PolarisCatalogConfig is immutable (frozen)."""
        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
        )

        with pytest.raises(ValidationError):
            config.uri = "https://other.example.com"

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_forbids_extra_fields(self) -> None:
        """Test PolarisCatalogConfig rejects unknown fields."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=self._create_valid_oauth2(),
                extra_field="value",
            )

        errors = exc_info.value.errors()
        assert any("extra" in str(e).lower() for e in errors)

    @pytest.mark.requirement("FR-034")
    def test_polaris_config_nested_oauth2_validation(self) -> None:
        """Test nested OAuth2Config validation through PolarisCatalogConfig."""
        with pytest.raises(ValidationError) as exc_info:
            PolarisCatalogConfig(
                uri="https://polaris.example.com/api/catalog",
                warehouse="default",
                oauth2=OAuth2Config(
                    client_id="",  # Empty - should fail validation
                    client_secret="secret",
                    token_url="https://auth.example.com/token",
                ),
            )

        errors = exc_info.value.errors()
        # Error should be in nested oauth2.client_id
        assert any("client_id" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("FR-036")
    def test_polaris_config_boundary_values_connect_timeout(self) -> None:
        """Test connect_timeout boundary values (1 and 60)."""
        # Minimum boundary
        config_min = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
            connect_timeout_seconds=1,
        )
        assert config_min.connect_timeout_seconds == 1

        # Maximum boundary
        config_max = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
            connect_timeout_seconds=60,
        )
        assert config_max.connect_timeout_seconds == 60

    @pytest.mark.requirement("FR-036")
    def test_polaris_config_boundary_values_read_timeout(self) -> None:
        """Test read_timeout boundary values (1 and 300)."""
        # Minimum boundary
        config_min = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
            read_timeout_seconds=1,
        )
        assert config_min.read_timeout_seconds == 1

        # Maximum boundary
        config_max = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
            read_timeout_seconds=300,
        )
        assert config_max.read_timeout_seconds == 300

    @pytest.mark.requirement("FR-036")
    def test_polaris_config_boundary_values_max_retries(self) -> None:
        """Test max_retries boundary values (0 and 10)."""
        # Minimum boundary (zero retries allowed)
        config_min = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
            max_retries=0,
        )
        assert config_min.max_retries == 0

        # Maximum boundary
        config_max = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="default",
            oauth2=self._create_valid_oauth2(),
            max_retries=10,
        )
        assert config_max.max_retries == 10


class TestOAuth2ConfigRefreshMarginBoundaries:
    """Additional boundary tests for OAuth2Config refresh_margin_seconds."""

    @pytest.mark.requirement("FR-036")
    def test_refresh_margin_boundary_minimum(self) -> None:
        """Test refresh_margin_seconds minimum boundary (10)."""
        config = OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
            refresh_margin_seconds=10,
        )
        assert config.refresh_margin_seconds == 10

    @pytest.mark.requirement("FR-036")
    def test_refresh_margin_boundary_maximum(self) -> None:
        """Test refresh_margin_seconds maximum boundary (300)."""
        config = OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
            refresh_margin_seconds=300,
        )
        assert config.refresh_margin_seconds == 300


class TestJsonSchemaExport:
    """Tests for JSON Schema export functionality."""

    def test_get_json_schema_returns_dict(self) -> None:
        """Test get_json_schema returns a dictionary."""
        from floe_catalog_polaris.config import get_json_schema

        schema = get_json_schema()
        assert isinstance(schema, dict)
        assert "title" in schema
        assert schema["title"] == "PolarisCatalogConfig"

    def test_get_json_schema_includes_properties(self) -> None:
        """Test schema includes expected properties."""
        from floe_catalog_polaris.config import get_json_schema

        schema = get_json_schema()
        assert "properties" in schema
        props = schema["properties"]
        assert "uri" in props
        assert "warehouse" in props
        assert "oauth2" in props
        assert "connect_timeout_seconds" in props
        assert "read_timeout_seconds" in props
        assert "max_retries" in props
        assert "credential_vending_enabled" in props

    def test_get_json_schema_includes_required(self) -> None:
        """Test schema includes required fields."""
        from floe_catalog_polaris.config import get_json_schema

        schema = get_json_schema()
        assert "required" in schema
        required = schema["required"]
        assert "uri" in required
        assert "warehouse" in required
        assert "oauth2" in required

    def test_get_json_schema_includes_nested_oauth2(self) -> None:
        """Test schema includes nested OAuth2Config definition."""
        from floe_catalog_polaris.config import get_json_schema

        schema = get_json_schema()
        assert "$defs" in schema
        assert "OAuth2Config" in schema["$defs"]
        oauth2_schema = schema["$defs"]["OAuth2Config"]
        assert "properties" in oauth2_schema
        assert "client_id" in oauth2_schema["properties"]
        assert "client_secret" in oauth2_schema["properties"]
        assert "token_url" in oauth2_schema["properties"]

    def test_export_json_schema_returns_string(self) -> None:
        """Test export_json_schema returns JSON string."""
        from floe_catalog_polaris.config import export_json_schema

        schema_str = export_json_schema()
        assert isinstance(schema_str, str)
        assert "PolarisCatalogConfig" in schema_str

    def test_export_json_schema_is_valid_json(self) -> None:
        """Test export_json_schema returns valid JSON."""
        import json

        from floe_catalog_polaris.config import export_json_schema

        schema_str = export_json_schema()
        # Should not raise
        schema = json.loads(schema_str)
        assert isinstance(schema, dict)

    def test_export_json_schema_to_file(self, tmp_path: str) -> None:
        """Test export_json_schema writes to file."""
        import json
        from pathlib import Path

        from floe_catalog_polaris.config import export_json_schema

        output_file = Path(tmp_path) / "test-schema.json"
        export_json_schema(str(output_file))

        assert output_file.exists()
        content = json.loads(output_file.read_text())
        assert content["title"] == "PolarisCatalogConfig"

    def test_export_json_schema_creates_parent_dirs(self, tmp_path: str) -> None:
        """Test export_json_schema creates parent directories."""
        from pathlib import Path

        from floe_catalog_polaris.config import export_json_schema

        output_file = Path(tmp_path) / "nested" / "dir" / "schema.json"
        export_json_schema(str(output_file))

        assert output_file.exists()
