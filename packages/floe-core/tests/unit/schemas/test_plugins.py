"""Unit tests for plugin selection and configuration.

Tests for plugin selection validation (US3) including:
- Valid plugin selection
- Invalid plugin name errors
- Plugin-specific configuration
- Domain plugin whitelist validation (3-tier mode)

Task: T038, T039, T040, T041
Requirements: FR-006, FR-007, FR-008, FR-018
"""

from __future__ import annotations

from typing import Any

import pytest


class TestValidPluginSelection:
    """Tests for valid plugin selection (T038)."""

    @pytest.mark.requirement("001-FR-006")
    def test_plugin_selection_with_type_only(self) -> None:
        """Test that PluginSelection accepts minimal valid input.

        Given a plugin selection with only the type field,
        When creating the selection,
        Then the selection is valid with config and connection_secret_ref as None.
        """
        from floe_core.schemas import PluginSelection

        selection = PluginSelection(type="duckdb")

        assert selection.type == "duckdb"
        assert selection.config is None
        assert selection.connection_secret_ref is None

    @pytest.mark.requirement("001-FR-006")
    def test_plugin_selection_with_config(self) -> None:
        """Test that PluginSelection accepts type with configuration."""
        from floe_core.schemas import PluginSelection

        selection = PluginSelection(
            type="duckdb",
            config={"threads": 4, "memory_limit": "8GB"},
        )

        assert selection.type == "duckdb"
        assert selection.config == {"threads": 4, "memory_limit": "8GB"}

    @pytest.mark.requirement("001-FR-006")
    def test_plugin_selection_with_secret_ref(self) -> None:
        """Test that PluginSelection accepts connection_secret_ref."""
        from floe_core.schemas import PluginSelection

        selection = PluginSelection(
            type="snowflake",
            connection_secret_ref="snowflake-credentials",
        )

        assert selection.type == "snowflake"
        assert selection.connection_secret_ref == "snowflake-credentials"

    @pytest.mark.requirement("001-FR-006")
    def test_plugin_selection_complete(self) -> None:
        """Test that PluginSelection accepts all fields."""
        from floe_core.schemas import PluginSelection

        selection = PluginSelection(
            type="snowflake",
            config={"warehouse": "COMPUTE_WH", "database": "ANALYTICS"},
            connection_secret_ref="snowflake-credentials",
        )

        assert selection.type == "snowflake"
        assert selection.config == {"warehouse": "COMPUTE_WH", "database": "ANALYTICS"}
        assert selection.connection_secret_ref == "snowflake-credentials"

    @pytest.mark.requirement("001-FR-006")
    def test_plugins_config_with_multiple_selections(self) -> None:
        """Test that PluginsConfig accepts multiple plugin selections."""
        from floe_core.schemas import PluginsConfig

        plugins = PluginsConfig(
            compute={"type": "duckdb"},
            orchestrator={"type": "dagster"},
            catalog={"type": "polaris"},
            storage={"type": "s3"},
        )

        assert plugins.compute is not None
        assert plugins.compute.type == "duckdb"
        assert plugins.orchestrator is not None
        assert plugins.orchestrator.type == "dagster"
        assert plugins.catalog is not None
        assert plugins.catalog.type == "polaris"
        assert plugins.storage is not None
        assert plugins.storage.type == "s3"

    @pytest.mark.requirement("001-FR-006")
    def test_plugins_config_all_12_categories(self) -> None:
        """Test that PluginsConfig supports all 12 plugin categories.

        Per ADR-0035, observability is split into telemetry_backend and lineage_backend.
        """
        from floe_core.schemas import PluginsConfig

        plugins = PluginsConfig(
            compute={"type": "duckdb"},
            orchestrator={"type": "dagster"},
            catalog={"type": "polaris"},
            storage={"type": "s3"},
            semantic_layer={"type": "cube"},
            ingestion={"type": "dlt"},
            secrets={"type": "k8s-secrets"},
            telemetry_backend={"type": "jaeger"},
            lineage_backend={"type": "marquez"},
            identity={"type": "k8s-rbac"},
            dbt={"type": "local"},
            quality={"provider": "great_expectations"},
        )

        assert plugins.compute is not None
        assert plugins.orchestrator is not None
        assert plugins.catalog is not None
        assert plugins.storage is not None
        assert plugins.semantic_layer is not None
        assert plugins.ingestion is not None
        assert plugins.secrets is not None
        assert plugins.telemetry_backend is not None
        assert plugins.lineage_backend is not None
        assert plugins.identity is not None
        assert plugins.dbt is not None
        assert plugins.quality is not None


class TestInvalidPluginName:
    """Tests for invalid plugin name errors (T039)."""

    @pytest.mark.requirement("001-FR-007")
    def test_plugin_selection_empty_type_rejected(self) -> None:
        """Test that empty plugin type is rejected.

        Given a plugin selection with an empty type,
        When creating the selection,
        Then validation fails with a clear error.
        """
        from pydantic import ValidationError

        from floe_core.schemas import PluginSelection

        with pytest.raises(ValidationError) as exc_info:
            PluginSelection(type="")

        assert "type" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-007")
    def test_plugin_selection_type_required(self) -> None:
        """Test that plugin type is required."""
        from pydantic import ValidationError

        from floe_core.schemas import PluginSelection

        with pytest.raises(ValidationError) as exc_info:
            PluginSelection()  # type: ignore[call-arg]

        assert "type" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-007")
    def test_validate_plugin_against_registry(self) -> None:
        """Test that plugin selection can be validated against registry.

        Given a plugin selection with an unknown plugin type,
        When validating against the registry,
        Then the system reports which plugins are available.
        """
        from floe_core.schemas.plugins import validate_plugin_selection

        # Valid plugins should pass
        validate_plugin_selection("compute", "duckdb")  # Should not raise

        # Invalid plugins should fail with helpful message
        with pytest.raises(ValueError) as exc_info:
            validate_plugin_selection("compute", "nonexistent-plugin")

        error_msg = str(exc_info.value).lower()
        assert "nonexistent-plugin" in error_msg
        assert "available" in error_msg or "valid" in error_msg

    @pytest.mark.requirement("001-FR-007")
    def test_get_available_plugins_for_category(self) -> None:
        """Test that available plugins can be listed for a category."""
        from floe_core.schemas.plugins import get_available_plugins

        compute_plugins = get_available_plugins("compute")

        assert isinstance(compute_plugins, list)
        assert "duckdb" in compute_plugins
        assert "snowflake" in compute_plugins

    @pytest.mark.requirement("001-FR-007")
    def test_get_available_plugins_unknown_category(self) -> None:
        """Test that unknown category raises helpful error."""
        from floe_core.schemas.plugins import get_available_plugins

        with pytest.raises(ValueError) as exc_info:
            get_available_plugins("unknown-category")

        error_msg = str(exc_info.value).lower()
        assert "unknown-category" in error_msg
        assert "compute" in error_msg or "valid" in error_msg


class TestPluginSpecificConfiguration:
    """Tests for plugin-specific configuration (T040)."""

    @pytest.mark.requirement("001-FR-008")
    def test_plugin_config_accepts_any_dict(self) -> None:
        """Test that plugin config accepts arbitrary dictionary.

        Given a plugin selection with custom configuration,
        When creating the selection,
        Then the configuration is preserved without validation.
        """
        from floe_core.schemas import PluginSelection

        config: dict[str, Any] = {
            "threads": 4,
            "memory_limit": "8GB",
            "nested": {"key": "value"},
            "list_value": [1, 2, 3],
        }

        selection = PluginSelection(type="duckdb", config=config)

        assert selection.config == config
        assert selection.config["nested"]["key"] == "value"

    @pytest.mark.requirement("001-FR-008")
    def test_plugin_config_empty_dict(self) -> None:
        """Test that empty config dict is valid."""
        from floe_core.schemas import PluginSelection

        selection = PluginSelection(type="duckdb", config={})

        assert selection.config == {}

    @pytest.mark.requirement("001-FR-008")
    def test_plugin_config_immutable(self) -> None:
        """Test that plugin selection is immutable (frozen)."""
        from pydantic import ValidationError

        from floe_core.schemas import PluginSelection

        selection = PluginSelection(type="duckdb", config={"threads": 4})

        with pytest.raises(ValidationError):
            selection.type = "snowflake"  # type: ignore[misc]

    @pytest.mark.requirement("001-FR-008")
    def test_plugin_selection_rejects_extra_fields(self) -> None:
        """Test that extra fields are rejected (extra='forbid')."""
        from pydantic import ValidationError

        from floe_core.schemas import PluginSelection

        with pytest.raises(ValidationError) as exc_info:
            PluginSelection(
                type="duckdb",
                config={"threads": 4},
                unknown_field="value",  # type: ignore[call-arg]
            )

        assert "unknown_field" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-008")
    def test_plugins_config_from_dict(self) -> None:
        """Test that PluginsConfig can be created from dict (YAML-style)."""
        from floe_core.schemas import PluginsConfig

        data = {
            "compute": {"type": "duckdb", "config": {"threads": 4}},
            "orchestrator": {"type": "dagster"},
        }

        plugins = PluginsConfig(**data)

        assert plugins.compute is not None
        assert plugins.compute.type == "duckdb"
        assert plugins.compute.config == {"threads": 4}


class TestDBTPluginDefaults:
    """Tests for dbt plugin default behavior (T065)."""

    @pytest.mark.requirement("FR-028")
    def test_dbt_defaults_to_core(self) -> None:
        """Test that dbt plugin defaults to 'core' when not specified.

        Given a PluginsConfig with no dbt specification,
        When the config is created,
        Then dbt.type should default to 'core'.
        """
        from floe_core.schemas import PluginsConfig

        plugins = PluginsConfig()

        assert plugins.dbt is not None
        assert plugins.dbt.type == "core"

    @pytest.mark.requirement("FR-028")
    def test_dbt_can_be_overridden_to_fusion(self) -> None:
        """Test that dbt plugin can be explicitly set to 'fusion'.

        Given a PluginsConfig with dbt explicitly set to 'fusion',
        When the config is created,
        Then dbt.type should be 'fusion'.
        """
        from floe_core.schemas import PluginsConfig, PluginSelection

        plugins = PluginsConfig(dbt=PluginSelection(type="fusion"))

        assert plugins.dbt is not None
        assert plugins.dbt.type == "fusion"

    @pytest.mark.requirement("FR-028")
    def test_dbt_default_in_yaml_style_dict(self) -> None:
        """Test that dbt defaults to 'core' when loaded from dict without dbt key."""
        from floe_core.schemas import PluginsConfig

        data = {
            "compute": {"type": "duckdb"},
            "orchestrator": {"type": "dagster"},
            # No dbt specified
        }

        plugins = PluginsConfig(**data)

        assert plugins.dbt is not None
        assert plugins.dbt.type == "core"


class TestDomainPluginWhitelist:
    """Tests for domain plugin whitelist validation (T041)."""

    @pytest.mark.requirement("001-FR-018")
    def test_domain_plugin_in_whitelist_accepted(self) -> None:
        """Test that domain plugin in enterprise whitelist is accepted.

        Given an enterprise manifest with approved_plugins whitelist,
        When a domain selects a plugin from the whitelist,
        Then the configuration is valid.
        """
        from floe_core.schemas.plugins import validate_domain_plugin_whitelist

        approved_plugins = {
            "compute": ["duckdb", "snowflake"],
            "orchestrator": ["dagster"],
        }

        # Should not raise - duckdb is in approved list
        validate_domain_plugin_whitelist(
            category="compute",
            plugin_type="duckdb",
            approved_plugins=approved_plugins,
        )

    @pytest.mark.requirement("001-FR-018")
    def test_domain_plugin_not_in_whitelist_rejected(self) -> None:
        """Test that domain plugin not in enterprise whitelist is rejected.

        Given an enterprise manifest with approved_plugins whitelist,
        When a domain selects a plugin NOT in the whitelist,
        Then the system rejects with a clear error.
        """
        from floe_core.schemas.plugins import (
            PluginWhitelistError,
            validate_domain_plugin_whitelist,
        )

        approved_plugins = {
            "compute": ["duckdb", "snowflake"],
            "orchestrator": ["dagster"],
        }

        with pytest.raises(PluginWhitelistError) as exc_info:
            validate_domain_plugin_whitelist(
                category="compute",
                plugin_type="spark",  # Not in approved list
                approved_plugins=approved_plugins,
            )

        error = exc_info.value
        assert error.category == "compute"
        assert error.plugin_type == "spark"
        assert "duckdb" in str(error) or "snowflake" in str(error)  # Shows approved

    @pytest.mark.requirement("001-FR-018")
    def test_domain_plugin_category_not_in_whitelist(self) -> None:
        """Test that category not in whitelist allows any plugin.

        Given an enterprise whitelist that doesn't include a category,
        When a domain selects any plugin for that category,
        Then the configuration is valid (category not restricted).
        """
        from floe_core.schemas.plugins import validate_domain_plugin_whitelist

        approved_plugins = {
            "compute": ["duckdb"],  # Only compute is restricted
        }

        # orchestrator not in whitelist, so any plugin allowed
        validate_domain_plugin_whitelist(
            category="orchestrator",
            plugin_type="airflow",  # Not restricted
            approved_plugins=approved_plugins,
        )

    @pytest.mark.requirement("001-FR-018")
    def test_domain_plugin_empty_whitelist_allows_all(self) -> None:
        """Test that empty whitelist allows all plugins."""
        from floe_core.schemas.plugins import validate_domain_plugin_whitelist

        # Should not raise - no restrictions
        validate_domain_plugin_whitelist(
            category="compute",
            plugin_type="spark",
            approved_plugins={},
        )

    @pytest.mark.requirement("001-FR-018")
    def test_plugin_whitelist_error_has_helpful_message(self) -> None:
        """Test that PluginWhitelistError contains helpful information."""
        from floe_core.schemas.plugins import PluginWhitelistError

        error = PluginWhitelistError(
            category="compute",
            plugin_type="spark",
            approved_plugins=["duckdb", "snowflake"],
        )

        error_str = str(error)
        assert "spark" in error_str
        assert "compute" in error_str
        assert "duckdb" in error_str or "snowflake" in error_str


class TestPluginSelectionValidation:
    """Additional tests for plugin selection edge cases."""

    @pytest.mark.requirement("001-FR-006")
    def test_plugins_config_optional_all_fields(self) -> None:
        """Test that all PluginsConfig fields are optional."""
        from floe_core.schemas import PluginsConfig

        plugins = PluginsConfig()

        assert plugins.compute is None
        assert plugins.orchestrator is None
        assert plugins.catalog is None

    @pytest.mark.requirement("001-FR-006")
    def test_plugin_selection_type_whitespace_only_rejected(self) -> None:
        """Test that whitespace-only type is rejected."""
        from pydantic import ValidationError

        from floe_core.schemas import PluginSelection

        with pytest.raises(ValidationError):
            PluginSelection(type="   ")

    @pytest.mark.requirement("001-FR-006")
    def test_connection_secret_ref_format(self) -> None:
        """Test that connection_secret_ref accepts K8s secret name format."""
        from floe_core.schemas import PluginSelection

        # Valid K8s secret names
        selection = PluginSelection(
            type="snowflake",
            connection_secret_ref="my-db-credentials",
        )
        assert selection.connection_secret_ref == "my-db-credentials"

        selection2 = PluginSelection(
            type="snowflake",
            connection_secret_ref="db-credentials-v1",
        )
        assert selection2.connection_secret_ref == "db-credentials-v1"
