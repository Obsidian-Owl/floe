"""Unit tests for CubeSemanticConfig Pydantic model.

Tests cover: valid creation, frozen immutability, extra field rejection,
SecretStr for api_secret, server_url validation, health_check_timeout
validation, default values, and edge cases.

Requirements Covered:
    - FR-007: CubeSemanticConfig fields and validation
    - FR-045: model_filter_tags
    - FR-046: model_filter_schemas
    - FR-047: health_check_timeout
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from floe_semantic_cube.config import CubeSemanticConfig


class TestCubeSemanticConfigCreation:
    """Tests for valid CubeSemanticConfig creation."""

    @pytest.mark.requirement("FR-007")
    def test_valid_creation_with_defaults(self) -> None:
        """Test config creation with only required field (api_secret)."""
        config = CubeSemanticConfig(api_secret="test-secret")
        assert config.server_url == "http://cube:4000"
        assert config.database_name == "analytics"
        assert config.schema_path is None
        assert config.health_check_timeout == pytest.approx(5.0)
        assert config.model_filter_tags == []
        assert config.model_filter_schemas == []

    @pytest.mark.requirement("FR-007")
    def test_valid_creation_with_all_fields(self) -> None:
        """Test config creation with all fields specified."""
        config = CubeSemanticConfig(
            server_url="https://cube.example.com",
            api_secret="my-secret",
            database_name="warehouse",
            schema_path=Path("/schemas"),
            health_check_timeout=10.0,
            model_filter_tags=["cube", "analytics"],
            model_filter_schemas=["gold", "silver"],
        )
        assert config.server_url == "https://cube.example.com"
        assert config.database_name == "warehouse"
        assert config.schema_path == Path("/schemas")
        assert config.health_check_timeout == pytest.approx(10.0)
        assert config.model_filter_tags == ["cube", "analytics"]
        assert config.model_filter_schemas == ["gold", "silver"]


class TestCubeSemanticConfigImmutability:
    """Tests for frozen model behavior."""

    @pytest.mark.requirement("FR-007")
    def test_frozen_immutability(self) -> None:
        """Test that config fields cannot be modified after creation."""
        config = CubeSemanticConfig(api_secret="test-secret")
        with pytest.raises(ValidationError):
            config.server_url = "http://other:4000"  # type: ignore[misc]

    @pytest.mark.requirement("FR-007")
    def test_extra_field_rejection(self) -> None:
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CubeSemanticConfig(
                api_secret="test-secret",
                unknown_field="value",  # type: ignore[call-arg]
            )


class TestCubeSemanticConfigSecretStr:
    """Tests for SecretStr behavior on api_secret."""

    @pytest.mark.requirement("FR-007")
    def test_api_secret_is_secret_str(self) -> None:
        """Test that api_secret is stored as SecretStr."""
        config = CubeSemanticConfig(api_secret="my-secret-key")
        assert isinstance(config.api_secret, SecretStr)

    @pytest.mark.requirement("FR-007")
    def test_api_secret_hidden_in_repr(self) -> None:
        """Test that api_secret is hidden in string representation."""
        config = CubeSemanticConfig(api_secret="my-secret-key")
        repr_str = repr(config)
        assert "my-secret-key" not in repr_str
        assert "**********" in repr_str

    @pytest.mark.requirement("FR-007")
    def test_api_secret_get_secret_value(self) -> None:
        """Test that api_secret value can be retrieved when needed."""
        config = CubeSemanticConfig(api_secret="my-secret-key")
        assert config.api_secret.get_secret_value() == "my-secret-key"

    @pytest.mark.requirement("FR-007")
    def test_api_secret_required(self) -> None:
        """Test that api_secret is required."""
        with pytest.raises(ValidationError, match="api_secret"):
            CubeSemanticConfig()  # type: ignore[call-arg]


class TestCubeSemanticConfigServerUrlValidation:
    """Tests for server_url validation."""

    @pytest.mark.requirement("FR-007")
    def test_server_url_http_valid(self) -> None:
        """Test that http:// URLs are accepted."""
        config = CubeSemanticConfig(
            server_url="http://localhost:4000",
            api_secret="test",
        )
        assert config.server_url == "http://localhost:4000"

    @pytest.mark.requirement("FR-007")
    def test_server_url_https_valid(self) -> None:
        """Test that https:// URLs are accepted."""
        config = CubeSemanticConfig(
            server_url="https://cube.example.com",
            api_secret="test",
        )
        assert config.server_url == "https://cube.example.com"

    @pytest.mark.requirement("FR-007")
    def test_server_url_trailing_slash_stripped(self) -> None:
        """Test that trailing slashes are stripped from server_url."""
        config = CubeSemanticConfig(
            server_url="http://cube:4000/",
            api_secret="test",
        )
        assert config.server_url == "http://cube:4000"

    @pytest.mark.requirement("FR-007")
    def test_server_url_invalid_scheme(self) -> None:
        """Test that non-HTTP schemes are rejected."""
        with pytest.raises(ValidationError, match="server_url must start with"):
            CubeSemanticConfig(
                server_url="ftp://cube:4000",
                api_secret="test",
            )

    @pytest.mark.requirement("FR-007")
    def test_server_url_no_scheme(self) -> None:
        """Test that URLs without scheme are rejected."""
        with pytest.raises(ValidationError, match="server_url must start with"):
            CubeSemanticConfig(
                server_url="cube:4000",
                api_secret="test",
            )


class TestCubeSemanticConfigHealthCheckTimeout:
    """Tests for health_check_timeout validation."""

    @pytest.mark.requirement("FR-047")
    def test_health_check_timeout_valid(self) -> None:
        """Test that positive timeout values are accepted."""
        config = CubeSemanticConfig(
            api_secret="test",
            health_check_timeout=10.0,
        )
        assert config.health_check_timeout == pytest.approx(10.0)

    @pytest.mark.requirement("FR-047")
    def test_health_check_timeout_zero_rejected(self) -> None:
        """Test that zero timeout is rejected."""
        with pytest.raises(
            ValidationError, match="health_check_timeout must be positive"
        ):
            CubeSemanticConfig(
                api_secret="test",
                health_check_timeout=0.0,
            )

    @pytest.mark.requirement("FR-047")
    def test_health_check_timeout_negative_rejected(self) -> None:
        """Test that negative timeout is rejected."""
        with pytest.raises(
            ValidationError, match="health_check_timeout must be positive"
        ):
            CubeSemanticConfig(
                api_secret="test",
                health_check_timeout=-1.0,
            )

    @pytest.mark.requirement("FR-047")
    def test_health_check_timeout_small_positive(self) -> None:
        """Test that very small positive timeout is accepted."""
        config = CubeSemanticConfig(
            api_secret="test",
            health_check_timeout=0.001,
        )
        assert config.health_check_timeout == pytest.approx(0.001)


class TestCubeSemanticConfigEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.requirement("FR-045")
    def test_empty_model_filter_tags(self) -> None:
        """Test that empty tags list is valid (no filtering)."""
        config = CubeSemanticConfig(api_secret="test", model_filter_tags=[])
        assert config.model_filter_tags == []

    @pytest.mark.requirement("FR-046")
    def test_empty_model_filter_schemas(self) -> None:
        """Test that empty schemas list is valid (no filtering)."""
        config = CubeSemanticConfig(api_secret="test", model_filter_schemas=[])
        assert config.model_filter_schemas == []

    @pytest.mark.requirement("FR-007")
    def test_none_schema_path(self) -> None:
        """Test that None schema_path is valid (use default)."""
        config = CubeSemanticConfig(api_secret="test", schema_path=None)
        assert config.schema_path is None

    @pytest.mark.requirement("FR-007")
    def test_schema_path_as_string(self) -> None:
        """Test that schema_path accepts string and converts to Path."""
        config = CubeSemanticConfig(
            api_secret="test",
            schema_path="/tmp/schemas",  # type: ignore[arg-type]
        )
        assert config.schema_path == Path("/tmp/schemas")
