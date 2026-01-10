"""Unit tests for ComputePlugin ABC.

Tests the abstract base class behavior for compute engine plugins.
Verifies that incomplete implementations raise TypeError and that
all method signatures match the expected contract.

Requirements Covered:
- FR-001: ComputePlugin ABC cannot be instantiated without implementation
- FR-002: generate_dbt_profile method signature validation
- FR-003: validate_connection method signature validation
- FR-004: get_resource_requirements method signature validation
"""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

import pytest

from floe_core import (
    CatalogConfig,
    ComputeConfig,
    ComputePlugin,
    ConnectionResult,
    ConnectionStatus,
    ResourceSpec,
    WORKLOAD_PRESETS,
)


class TestComputePluginABCInstantiation:
    """Test that ComputePlugin ABC enforces abstract method implementation."""

    @pytest.mark.requirement("001-FR-001")
    def test_cannot_instantiate_compute_plugin_directly(self) -> None:
        """Test that ComputePlugin cannot be instantiated directly.

        The ABC must raise TypeError when any abstract methods are missing.
        """
        with pytest.raises(TypeError, match="abstract"):
            ComputePlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("001-FR-001")
    def test_missing_is_self_hosted_raises_type_error(self) -> None:
        """Test that missing is_self_hosted property raises TypeError."""

        class IncompletePlugin(ComputePlugin):
            """Plugin missing is_self_hosted."""

            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            # Missing is_self_hosted

            def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
                return {}

            def get_required_dbt_packages(self) -> list[str]:
                return []

            def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
                return ConnectionResult(
                    status=ConnectionStatus.HEALTHY, latency_ms=1.0
                )

            def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
                return WORKLOAD_PRESETS["medium"]

        with pytest.raises(TypeError, match="is_self_hosted"):
            IncompletePlugin()

    @pytest.mark.requirement("001-FR-001")
    def test_missing_generate_dbt_profile_raises_type_error(self) -> None:
        """Test that missing generate_dbt_profile method raises TypeError."""

        class IncompletePlugin(ComputePlugin):
            """Plugin missing generate_dbt_profile."""

            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            @property
            def is_self_hosted(self) -> bool:
                return True

            # Missing generate_dbt_profile

            def get_required_dbt_packages(self) -> list[str]:
                return []

            def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
                return ConnectionResult(
                    status=ConnectionStatus.HEALTHY, latency_ms=1.0
                )

            def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
                return WORKLOAD_PRESETS["medium"]

        with pytest.raises(TypeError, match="generate_dbt_profile"):
            IncompletePlugin()

    @pytest.mark.requirement("001-FR-001")
    def test_missing_validate_connection_raises_type_error(self) -> None:
        """Test that missing validate_connection method raises TypeError."""

        class IncompletePlugin(ComputePlugin):
            """Plugin missing validate_connection."""

            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            @property
            def is_self_hosted(self) -> bool:
                return True

            def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
                return {}

            def get_required_dbt_packages(self) -> list[str]:
                return []

            # Missing validate_connection

            def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
                return WORKLOAD_PRESETS["medium"]

        with pytest.raises(TypeError, match="validate_connection"):
            IncompletePlugin()

    @pytest.mark.requirement("001-FR-001")
    def test_missing_get_resource_requirements_raises_type_error(self) -> None:
        """Test that missing get_resource_requirements raises TypeError."""

        class IncompletePlugin(ComputePlugin):
            """Plugin missing get_resource_requirements."""

            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            @property
            def is_self_hosted(self) -> bool:
                return True

            def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
                return {}

            def get_required_dbt_packages(self) -> list[str]:
                return []

            def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
                return ConnectionResult(
                    status=ConnectionStatus.HEALTHY, latency_ms=1.0
                )

            # Missing get_resource_requirements

        with pytest.raises(TypeError, match="get_resource_requirements"):
            IncompletePlugin()

    @pytest.mark.requirement("001-FR-001")
    def test_missing_get_required_dbt_packages_raises_type_error(self) -> None:
        """Test that missing get_required_dbt_packages raises TypeError."""

        class IncompletePlugin(ComputePlugin):
            """Plugin missing get_required_dbt_packages."""

            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            @property
            def is_self_hosted(self) -> bool:
                return True

            def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
                return {}

            # Missing get_required_dbt_packages

            def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
                return ConnectionResult(
                    status=ConnectionStatus.HEALTHY, latency_ms=1.0
                )

            def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
                return WORKLOAD_PRESETS["medium"]

        with pytest.raises(TypeError, match="get_required_dbt_packages"):
            IncompletePlugin()


class TestComputePluginMethodSignatures:
    """Test that ComputePlugin method signatures match the contract."""

    @pytest.mark.requirement("001-FR-002")
    def test_generate_dbt_profile_accepts_compute_config(self) -> None:
        """Test generate_dbt_profile accepts ComputeConfig parameter."""
        method = ComputePlugin.generate_dbt_profile
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "config" in params, "Method must accept 'config' parameter"

        # Verify type hint
        hints = get_type_hints(method)
        assert hints.get("config") == ComputeConfig

    @pytest.mark.requirement("001-FR-002")
    def test_generate_dbt_profile_returns_dict(self) -> None:
        """Test generate_dbt_profile returns dict[str, Any]."""
        method = ComputePlugin.generate_dbt_profile
        hints = get_type_hints(method)

        assert hints.get("return") == dict[str, Any]

    @pytest.mark.requirement("001-FR-003")
    def test_validate_connection_accepts_compute_config(self) -> None:
        """Test validate_connection accepts ComputeConfig parameter."""
        method = ComputePlugin.validate_connection
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "config" in params, "Method must accept 'config' parameter"

        hints = get_type_hints(method)
        assert hints.get("config") == ComputeConfig

    @pytest.mark.requirement("001-FR-003")
    def test_validate_connection_returns_connection_result(self) -> None:
        """Test validate_connection returns ConnectionResult."""
        method = ComputePlugin.validate_connection
        hints = get_type_hints(method)

        assert hints.get("return") == ConnectionResult

    @pytest.mark.requirement("001-FR-004")
    def test_get_resource_requirements_accepts_workload_size(self) -> None:
        """Test get_resource_requirements accepts workload_size parameter."""
        method = ComputePlugin.get_resource_requirements
        sig = inspect.signature(method)

        params = list(sig.parameters.keys())
        assert "workload_size" in params, "Method must accept 'workload_size'"

        hints = get_type_hints(method)
        assert hints.get("workload_size") == str

    @pytest.mark.requirement("001-FR-004")
    def test_get_resource_requirements_returns_resource_spec(self) -> None:
        """Test get_resource_requirements returns ResourceSpec."""
        method = ComputePlugin.get_resource_requirements
        hints = get_type_hints(method)

        assert hints.get("return") == ResourceSpec

    @pytest.mark.requirement("001-FR-002")
    def test_get_required_dbt_packages_returns_list_str(self) -> None:
        """Test get_required_dbt_packages returns list[str]."""
        method = ComputePlugin.get_required_dbt_packages
        hints = get_type_hints(method)

        assert hints.get("return") == list[str]

    @pytest.mark.requirement("001-FR-001")
    def test_is_self_hosted_is_property(self) -> None:
        """Test is_self_hosted is a property returning bool."""
        prop = getattr(ComputePlugin, "is_self_hosted")
        assert isinstance(prop, property), "is_self_hosted must be a property"

        getter = prop.fget
        assert getter is not None
        hints = get_type_hints(getter)
        assert hints.get("return") == bool


class TestComputePluginOptionalMethods:
    """Test optional methods with default implementations."""

    @pytest.mark.requirement("001-FR-001")
    def test_get_catalog_attachment_sql_is_not_abstract(self) -> None:
        """Test get_catalog_attachment_sql has default implementation."""
        method = ComputePlugin.get_catalog_attachment_sql
        assert not getattr(method, "__isabstractmethod__", False)

    @pytest.mark.requirement("001-FR-001")
    def test_get_catalog_attachment_sql_signature(self) -> None:
        """Test get_catalog_attachment_sql signature."""
        method = ComputePlugin.get_catalog_attachment_sql
        hints = get_type_hints(method)

        assert hints.get("catalog_config") == CatalogConfig
        assert hints.get("return") == (list[str] | None)

    @pytest.mark.requirement("001-FR-001")
    def test_get_config_schema_is_not_abstract(self) -> None:
        """Test get_config_schema has default implementation."""
        method = ComputePlugin.get_config_schema
        assert not getattr(method, "__isabstractmethod__", False)


class TestCompletePluginImplementation:
    """Test a complete plugin implementation works correctly."""

    @pytest.fixture
    def complete_plugin(self) -> ComputePlugin:
        """Create a complete ComputePlugin implementation for testing."""

        class CompleteTestPlugin(ComputePlugin):
            """Complete test implementation of ComputePlugin."""

            @property
            def name(self) -> str:
                return "test-complete"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.1"

            @property
            def is_self_hosted(self) -> bool:
                return True

            def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
                return {
                    "type": "duckdb",
                    "path": config.connection.get("path", ":memory:"),
                    "threads": config.threads,
                }

            def get_required_dbt_packages(self) -> list[str]:
                return ["dbt-duckdb>=1.7.0"]

            def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
                return ConnectionResult(
                    status=ConnectionStatus.HEALTHY,
                    latency_ms=5.0,
                    message="Connection successful",
                )

            def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
                return WORKLOAD_PRESETS.get(workload_size, WORKLOAD_PRESETS["medium"])

        return CompleteTestPlugin()

    @pytest.mark.requirement("001-FR-001")
    def test_complete_plugin_instantiates(self, complete_plugin: ComputePlugin) -> None:
        """Test complete plugin can be instantiated with correct metadata."""
        # Verify plugin has correct name and version (not just existence)
        assert complete_plugin.name == "test-complete"
        assert complete_plugin.version == "1.0.0"
        assert complete_plugin.floe_api_version == "0.1"

    @pytest.mark.requirement("001-FR-001")
    def test_complete_plugin_is_self_hosted(
        self, complete_plugin: ComputePlugin
    ) -> None:
        """Test is_self_hosted property works."""
        assert complete_plugin.is_self_hosted is True

    @pytest.mark.requirement("001-FR-002")
    def test_complete_plugin_generate_dbt_profile(
        self, complete_plugin: ComputePlugin
    ) -> None:
        """Test generate_dbt_profile method works."""
        config = ComputeConfig(
            plugin="duckdb",
            threads=8,
            connection={"path": "/data/test.duckdb"},
        )

        profile = complete_plugin.generate_dbt_profile(config)

        assert isinstance(profile, dict)
        assert profile["type"] == "duckdb"
        assert profile["path"] == "/data/test.duckdb"
        assert profile["threads"] == 8

    @pytest.mark.requirement("001-FR-002")
    def test_complete_plugin_get_required_dbt_packages(
        self, complete_plugin: ComputePlugin
    ) -> None:
        """Test get_required_dbt_packages method works."""
        packages = complete_plugin.get_required_dbt_packages()

        assert isinstance(packages, list)
        assert "dbt-duckdb>=1.7.0" in packages

    @pytest.mark.requirement("001-FR-003")
    def test_complete_plugin_validate_connection(
        self, complete_plugin: ComputePlugin
    ) -> None:
        """Test validate_connection method works."""
        config = ComputeConfig(plugin="duckdb")

        result = complete_plugin.validate_connection(config)

        assert isinstance(result, ConnectionResult)
        assert result.status == ConnectionStatus.HEALTHY
        assert result.latency_ms == pytest.approx(5.0)
        assert result.message == "Connection successful"

    @pytest.mark.requirement("001-FR-004")
    def test_complete_plugin_get_resource_requirements(
        self, complete_plugin: ComputePlugin
    ) -> None:
        """Test get_resource_requirements method works."""
        spec = complete_plugin.get_resource_requirements("medium")

        assert isinstance(spec, ResourceSpec)
        assert spec == WORKLOAD_PRESETS["medium"]

    @pytest.mark.requirement("001-FR-001")
    def test_complete_plugin_default_catalog_attachment_sql(
        self, complete_plugin: ComputePlugin
    ) -> None:
        """Test default get_catalog_attachment_sql returns None."""
        catalog_config = CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="floe",
        )

        result = complete_plugin.get_catalog_attachment_sql(catalog_config)

        assert result is None  # Default implementation returns None

    @pytest.mark.requirement("001-FR-001")
    def test_complete_plugin_default_config_schema(
        self, complete_plugin: ComputePlugin
    ) -> None:
        """Test default get_config_schema returns None."""
        result = complete_plugin.get_config_schema()

        assert result is None  # Default implementation returns None
