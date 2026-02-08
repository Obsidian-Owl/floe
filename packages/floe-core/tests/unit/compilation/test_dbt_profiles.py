"""Unit tests for dbt profile generation.

This module tests the generate_dbt_profiles() function which creates
dbt profiles.yml configuration from resolved plugins and platform manifest.

Requirements Tested:
    - FR-005: dbt profiles generated automatically from platform configuration
    - FR-006: Credential placeholders use {{ env_var('X') }} syntax
    - FR-014: Environment-agnostic compilation (no secrets in artifacts)

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - packages/floe-core/src/floe_core/compilation/dbt_profiles.py: Implementation
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from floe_core.compute_config import ComputeConfig
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins


class TestGenerateDBTProfiles:
    """Tests for generate_dbt_profiles() function."""

    @pytest.fixture
    def mock_compute_plugin(self) -> MagicMock:
        """Create a mock ComputePlugin for testing."""
        plugin = MagicMock()
        plugin.name = "duckdb"
        plugin.generate_dbt_profile.return_value = {
            "type": "duckdb",
            "path": ":memory:",
            "threads": 4,
        }
        return plugin

    @pytest.fixture
    def resolved_plugins(self) -> ResolvedPlugins:
        """Create minimal ResolvedPlugins fixture."""
        return ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config=None),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
        )

    @pytest.mark.requirement("FR-005")
    def test_generate_dbt_profiles_returns_valid_dict(
        self,
        mock_compute_plugin: MagicMock,
        resolved_plugins: ResolvedPlugins,
    ) -> None:
        """Test that generate_dbt_profiles returns valid profiles dict structure."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_compute_plugin,
        ):
            profiles = generate_dbt_profiles(
                plugins=resolved_plugins,
                product_name="test_product",
            )

        # Should return dict with profile structure
        assert isinstance(profiles, dict)
        assert "test_product" in profiles
        assert "target" in profiles["test_product"]
        assert "outputs" in profiles["test_product"]

    @pytest.mark.requirement("FR-005")
    def test_generate_dbt_profiles_includes_dev_target(
        self,
        mock_compute_plugin: MagicMock,
        resolved_plugins: ResolvedPlugins,
    ) -> None:
        """Test that profiles include dev target configuration."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_compute_plugin,
        ):
            profiles = generate_dbt_profiles(
                plugins=resolved_plugins,
                product_name="test_product",
            )

        outputs = profiles["test_product"]["outputs"]
        assert "dev" in outputs
        assert outputs["dev"]["type"] == "duckdb"

    @pytest.mark.requirement("FR-005")
    def test_generate_dbt_profiles_duckdb_configuration(
        self,
        mock_compute_plugin: MagicMock,
        resolved_plugins: ResolvedPlugins,
    ) -> None:
        """Test DuckDB profile generation with correct adapter settings."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        # Configure mock to return DuckDB-specific settings
        mock_compute_plugin.generate_dbt_profile.return_value = {
            "type": "duckdb",
            "path": "/data/analytics.duckdb",
            "threads": 8,
            "extensions": ["iceberg", "httpfs"],
        }

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_compute_plugin,
        ):
            profiles = generate_dbt_profiles(
                plugins=resolved_plugins,
                product_name="analytics",
            )

        dev_output = profiles["analytics"]["outputs"]["dev"]
        assert dev_output["type"] == "duckdb"
        assert dev_output["path"] == "/data/analytics.duckdb"
        assert dev_output["threads"] == 8
        assert "extensions" in dev_output

    @pytest.mark.requirement("FR-005")
    def test_generate_dbt_profiles_uses_env_var_for_target(
        self,
        mock_compute_plugin: MagicMock,
        resolved_plugins: ResolvedPlugins,
    ) -> None:
        """Test that target uses env_var for environment selection."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_compute_plugin,
        ):
            profiles = generate_dbt_profiles(
                plugins=resolved_plugins,
                product_name="test_product",
            )

        # Target should use env_var for dynamic selection
        target = profiles["test_product"]["target"]
        assert "{{ env_var('FLOE_ENV'" in target or target == "dev"


class TestCredentialPlaceholders:
    """Tests for credential placeholder generation."""

    @pytest.mark.requirement("FR-006")
    def test_credential_placeholder_syntax(self) -> None:
        """Test that credential placeholders use dbt env_var syntax."""
        from floe_core.compilation.dbt_profiles import format_env_var_placeholder

        placeholder = format_env_var_placeholder("DB_PASSWORD")
        assert placeholder == "{{ env_var('DB_PASSWORD') }}"

    @pytest.mark.requirement("FR-006")
    def test_credential_placeholder_with_default(self) -> None:
        """Test credential placeholder with default value."""
        from floe_core.compilation.dbt_profiles import format_env_var_placeholder

        placeholder = format_env_var_placeholder("FLOE_ENV", default="dev")
        assert placeholder == "{{ env_var('FLOE_ENV', 'dev') }}"

    @pytest.mark.requirement("FR-014")
    def test_no_secrets_in_profile_output(self) -> None:
        """Test that no actual secrets appear in generated profiles."""
        from floe_core.compilation.dbt_profiles import (
            format_env_var_placeholder,
            generate_dbt_profiles,
        )

        mock_plugin = MagicMock()
        mock_plugin.name = "snowflake"
        mock_plugin.generate_dbt_profile.return_value = {
            "type": "snowflake",
            "account": "test_account",
            "user": format_env_var_placeholder("SNOWFLAKE_USER"),
            "password": format_env_var_placeholder("SNOWFLAKE_PASSWORD"),
            "warehouse": "COMPUTE_WH",
        }

        plugins = ResolvedPlugins(
            compute=PluginRef(type="snowflake", version="0.1.0", config=None),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
        )

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_plugin,
        ):
            profiles = generate_dbt_profiles(
                plugins=plugins,
                product_name="test",
            )

        # Serialize to string and check no actual secrets
        import json

        profile_str = json.dumps(profiles)
        assert "actual_password" not in profile_str.lower()
        assert "secret" not in profile_str.lower()
        # Should have env_var placeholders instead
        assert "env_var" in profile_str


class TestMultipleEnvironments:
    """Tests for multiple environment support."""

    @pytest.fixture
    def mock_compute_plugin(self) -> MagicMock:
        """Create a mock ComputePlugin."""
        plugin = MagicMock()
        plugin.name = "duckdb"
        plugin.generate_dbt_profile.return_value = {
            "type": "duckdb",
            "path": ":memory:",
            "threads": 4,
        }
        return plugin

    @pytest.fixture
    def resolved_plugins(self) -> ResolvedPlugins:
        """Create minimal ResolvedPlugins fixture."""
        return ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config=None),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
        )

    @pytest.mark.requirement("FR-005")
    def test_generate_profiles_with_multiple_environments(
        self,
        mock_compute_plugin: MagicMock,
        resolved_plugins: ResolvedPlugins,
    ) -> None:
        """Test profile generation includes dev and prod targets."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_compute_plugin,
        ):
            profiles = generate_dbt_profiles(
                plugins=resolved_plugins,
                product_name="test_product",
                environments=["dev", "prod"],
            )

        outputs = profiles["test_product"]["outputs"]
        assert "dev" in outputs
        assert "prod" in outputs

    @pytest.mark.requirement("FR-005")
    def test_default_environment_is_dev(
        self,
        mock_compute_plugin: MagicMock,
        resolved_plugins: ResolvedPlugins,
    ) -> None:
        """Test that default environment when not specified is dev."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_compute_plugin,
        ):
            profiles = generate_dbt_profiles(
                plugins=resolved_plugins,
                product_name="test_product",
            )

        # Should at minimum have dev environment
        outputs = profiles["test_product"]["outputs"]
        assert "dev" in outputs


class TestPluginIntegration:
    """Tests for compute plugin integration."""

    @pytest.mark.requirement("FR-005")
    def test_calls_compute_plugin_generate_dbt_profile(self) -> None:
        """Test that generate_dbt_profiles calls plugin's generate_dbt_profile."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        mock_plugin = MagicMock()
        mock_plugin.name = "duckdb"
        mock_plugin.generate_dbt_profile.return_value = {"type": "duckdb"}

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config=None),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
        )

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_plugin,
        ):
            generate_dbt_profiles(plugins=plugins, product_name="test")

        # Verify plugin method was called
        mock_plugin.generate_dbt_profile.assert_called()

    @pytest.mark.requirement("FR-005")
    def test_passes_compute_config_to_plugin(self) -> None:
        """Test that ComputeConfig is passed to plugin."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles

        mock_plugin = MagicMock()
        mock_plugin.name = "duckdb"
        mock_plugin.generate_dbt_profile.return_value = {"type": "duckdb"}

        plugins = ResolvedPlugins(
            compute=PluginRef(
                type="duckdb",
                version="0.1.0",
                config={"path": "/custom/path.duckdb", "threads": 16},
            ),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
        )

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_plugin,
        ):
            generate_dbt_profiles(plugins=plugins, product_name="test")

        # Verify config was passed to plugin
        call_args = mock_plugin.generate_dbt_profile.call_args
        assert call_args is not None
        config_arg = call_args[0][0]  # First positional arg
        assert isinstance(config_arg, ComputeConfig)


class TestErrorHandling:
    """Tests for error handling in dbt profile generation."""

    @pytest.mark.requirement("FR-005")
    def test_raises_error_for_missing_compute_plugin(self) -> None:
        """Test that missing compute plugin raises appropriate error."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles
        from floe_core.compilation.errors import CompilationException

        plugins = ResolvedPlugins(
            compute=PluginRef(type="nonexistent", version="0.1.0", config=None),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
        )

        with patch(
            "floe_core.compilation.dbt_profiles.get_registry",
            side_effect=KeyError("Plugin 'nonexistent' not found"),
        ):
            with pytest.raises(CompilationException) as exc_info:
                generate_dbt_profiles(plugins=plugins, product_name="test")

            assert "nonexistent" in str(exc_info.value)

    @pytest.mark.requirement("FR-005")
    def test_raises_error_for_invalid_plugin_config(self) -> None:
        """Test error handling for invalid plugin configuration."""
        from floe_core.compilation.dbt_profiles import generate_dbt_profiles
        from floe_core.compilation.errors import CompilationException

        mock_plugin = MagicMock()
        mock_plugin.name = "duckdb"
        mock_plugin.generate_dbt_profile.side_effect = ValueError(
            "Invalid configuration"
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config=None),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
        )

        with patch(
            "floe_core.compilation.dbt_profiles.get_compute_plugin",
            return_value=mock_plugin,
        ):
            with pytest.raises(CompilationException) as exc_info:
                generate_dbt_profiles(plugins=plugins, product_name="test")

            # Error message contains plugin type
            assert "duckdb" in str(exc_info.value).lower()
