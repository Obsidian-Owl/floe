"""Unit tests for manifest quality provider validation.

Tests:
    - T034: Manifest quality provider validation
    - T035: FLOE-DQ001 error on invalid provider
"""

from __future__ import annotations

import pytest

from floe_core.quality_errors import QualityProviderNotFoundError
from floe_core.schemas.plugins import PLUGIN_REGISTRY, PluginsConfig
from floe_core.schemas.quality_config import QualityConfig, QualityGates
from floe_core.validation.quality_validation import (
    get_available_quality_providers,
    validate_quality_provider,
)


class TestQualityProviderRegistry:
    """Tests for quality provider registry."""

    @pytest.mark.requirement("FR-041")
    def test_quality_providers_in_registry(self) -> None:
        """Quality providers are registered in PLUGIN_REGISTRY."""
        assert "quality" in PLUGIN_REGISTRY
        providers = PLUGIN_REGISTRY["quality"]
        assert "great_expectations" in providers
        assert "dbt_expectations" in providers
        assert "soda" in providers

    @pytest.mark.requirement("FR-041")
    def test_get_available_quality_providers(self) -> None:
        """get_available_quality_providers returns registered providers."""
        providers = get_available_quality_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 3
        assert "great_expectations" in providers
        assert "dbt_expectations" in providers


class TestValidateQualityProvider:
    """Tests for validate_quality_provider function."""

    @pytest.mark.requirement("FR-041")
    def test_validate_great_expectations_valid(self) -> None:
        """great_expectations is a valid provider."""
        validate_quality_provider("great_expectations")

    @pytest.mark.requirement("FR-041")
    def test_validate_dbt_expectations_valid(self) -> None:
        """dbt_expectations is a valid provider."""
        validate_quality_provider("dbt_expectations")

    @pytest.mark.requirement("FR-041")
    def test_validate_soda_valid(self) -> None:
        """soda is a valid provider."""
        validate_quality_provider("soda")

    @pytest.mark.requirement("FR-041")
    def test_invalid_provider_raises_floe_dq001(self) -> None:
        """Invalid provider raises QualityProviderNotFoundError (FLOE-DQ001)."""
        with pytest.raises(QualityProviderNotFoundError) as exc_info:
            validate_quality_provider("invalid_provider")

        error = exc_info.value
        assert error.error_code == "FLOE-DQ001"
        assert error.provider == "invalid_provider"
        assert "great_expectations" in error.available_providers

    @pytest.mark.requirement("FR-041")
    def test_floe_dq001_error_message_format(self) -> None:
        """FLOE-DQ001 error message includes code, provider, and resolution."""
        with pytest.raises(QualityProviderNotFoundError) as exc_info:
            validate_quality_provider("unknown")

        message = str(exc_info.value)
        assert "[FLOE-DQ001]" in message
        assert "unknown" in message
        assert "Available providers:" in message
        assert "Resolution:" in message

    @pytest.mark.requirement("FR-041")
    def test_empty_provider_raises_error(self) -> None:
        """Empty provider string raises FLOE-DQ001."""
        with pytest.raises(QualityProviderNotFoundError) as exc_info:
            validate_quality_provider("")

        assert exc_info.value.error_code == "FLOE-DQ001"


class TestPluginsConfigQuality:
    """Tests for PluginsConfig.quality field."""

    @pytest.mark.requirement("FR-041")
    def test_plugins_config_quality_none_by_default(self) -> None:
        """PluginsConfig.quality is None by default."""
        config = PluginsConfig()
        assert config.quality is None

    @pytest.mark.requirement("FR-041")
    def test_plugins_config_with_quality_config(self) -> None:
        """PluginsConfig accepts QualityConfig for quality field."""
        quality = QualityConfig(provider="great_expectations")
        config = PluginsConfig(quality=quality)

        assert config.quality is not None
        assert config.quality.provider == "great_expectations"
        assert config.quality.enabled is True

    @pytest.mark.requirement("FR-041")
    def test_plugins_config_quality_with_gates(self) -> None:
        """PluginsConfig accepts QualityConfig with quality_gates."""
        quality = QualityConfig(
            provider="dbt_expectations",
            quality_gates=QualityGates(),
        )
        config = PluginsConfig(quality=quality)

        assert config.quality is not None
        assert config.quality.provider == "dbt_expectations"
        assert config.quality.quality_gates is not None
        assert config.quality.quality_gates.silver.min_test_coverage == 80

    @pytest.mark.requirement("FR-041")
    def test_plugins_config_quality_frozen(self) -> None:
        """PluginsConfig.quality is frozen (immutable)."""
        quality = QualityConfig(provider="great_expectations")
        config = PluginsConfig(quality=quality)

        with pytest.raises(Exception):
            config.quality = None  # type: ignore[misc]


class TestQualityProviderNotFoundError:
    """Tests for QualityProviderNotFoundError attributes."""

    @pytest.mark.requirement("FR-041")
    def test_error_attributes(self) -> None:
        """QualityProviderNotFoundError has correct attributes."""
        error = QualityProviderNotFoundError(
            provider="test_provider",
            available_providers=["a", "b", "c"],
        )

        assert error.error_code == "FLOE-DQ001"
        assert error.provider == "test_provider"
        assert error.available_providers == ["a", "b", "c"]
        assert "a, b, c" in error.resolution
        assert "manifest.yaml" in error.resolution

    @pytest.mark.requirement("FR-041")
    def test_error_is_quality_error_subclass(self) -> None:
        """QualityProviderNotFoundError is a QualityError subclass."""
        from floe_core.quality_errors import QualityError

        error = QualityProviderNotFoundError("x", ["y"])
        assert isinstance(error, QualityError)
        assert isinstance(error, Exception)
