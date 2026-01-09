"""Contract tests for ComputePlugin ABC.

These tests validate that the ComputePlugin ABC contract remains stable for
compute plugin implementations (DuckDB, Snowflake, Databricks, etc.).

Contract tests ensure:
- All abstract methods are present and required
- Method signatures match the documented contract
- Return types are enforced
- Configuration models are compatible

Requirements Covered:
- FR-001: ComputePlugin ABC defines compute engine interface
- FR-002: generate_dbt_profile method contract
- FR-003: validate_connection method contract
- FR-004: get_resource_requirements method contract
- FR-004a: is_self_hosted property contract
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, get_type_hints

import pytest

if TYPE_CHECKING:
    pass


class TestComputePluginABCContract:
    """Contract tests for ComputePlugin ABC stability.

    These tests ensure that the ComputePlugin ABC maintains backward
    compatibility for existing plugin implementations.
    """

    @pytest.mark.requirement("001-FR-001")
    def test_compute_plugin_is_abstract(self) -> None:
        """Verify ComputePlugin cannot be instantiated directly.

        Plugin implementations must subclass and implement all abstract methods.
        """
        from floe_core import ComputePlugin

        with pytest.raises(TypeError, match="abstract"):
            ComputePlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("001-FR-001")
    def test_compute_plugin_has_required_abstract_methods(self) -> None:
        """Verify ComputePlugin declares all required abstract methods.

        The following methods MUST be abstract (part of the contract):
        - is_self_hosted (property)
        - generate_dbt_profile
        - get_required_dbt_packages
        - validate_connection
        - get_resource_requirements
        """
        from floe_core import ComputePlugin

        # Get abstract methods
        abstract_methods = set()
        for name, method in inspect.getmembers(ComputePlugin):
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.add(name)

        expected_abstract = {
            "is_self_hosted",
            "generate_dbt_profile",
            "get_required_dbt_packages",
            "validate_connection",
            "get_resource_requirements",
            # From PluginMetadata base class
            "name",
            "version",
            "floe_api_version",
        }

        # All expected abstract methods must be present
        for method in expected_abstract:
            assert method in abstract_methods, (
                f"Missing abstract method: {method}. "
                "Removing abstract methods is a breaking change."
            )

    @pytest.mark.requirement("001-FR-002")
    def test_generate_dbt_profile_signature(self) -> None:
        """Verify generate_dbt_profile has correct signature.

        Contract:
            def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]

        Plugin implementations depend on this exact signature.
        """
        from floe_core import ComputeConfig, ComputePlugin

        method = ComputePlugin.generate_dbt_profile
        sig = inspect.signature(method)

        # Check parameters
        params = list(sig.parameters.keys())
        assert "self" in params, "Method must be instance method"
        assert "config" in params, "Method must accept 'config' parameter"

        # Check type hints
        hints = get_type_hints(method)
        assert hints.get("config") == ComputeConfig, (
            f"config parameter type changed from ComputeConfig to {hints.get('config')}"
        )
        assert hints.get("return") == dict[str, Any], (
            f"return type changed from dict[str, Any] to {hints.get('return')}"
        )

    @pytest.mark.requirement("001-FR-003")
    def test_validate_connection_signature(self) -> None:
        """Verify validate_connection has correct signature.

        Contract:
            def validate_connection(self, config: ComputeConfig) -> ConnectionResult

        Plugin implementations depend on this exact signature.
        """
        from floe_core import ComputeConfig, ComputePlugin, ConnectionResult

        method = ComputePlugin.validate_connection
        sig = inspect.signature(method)

        # Check parameters
        params = list(sig.parameters.keys())
        assert "self" in params, "Method must be instance method"
        assert "config" in params, "Method must accept 'config' parameter"

        # Check type hints
        hints = get_type_hints(method)
        assert hints.get("config") == ComputeConfig, (
            f"config parameter type changed from ComputeConfig to {hints.get('config')}"
        )
        assert hints.get("return") == ConnectionResult, (
            f"return type changed from ConnectionResult to {hints.get('return')}"
        )

    @pytest.mark.requirement("001-FR-004")
    def test_get_resource_requirements_signature(self) -> None:
        """Verify get_resource_requirements has correct signature.

        Contract:
            def get_resource_requirements(self, workload_size: str) -> ResourceSpec

        Plugin implementations depend on this exact signature.
        """
        from floe_core import ComputePlugin, ResourceSpec

        method = ComputePlugin.get_resource_requirements
        sig = inspect.signature(method)

        # Check parameters
        params = list(sig.parameters.keys())
        assert "self" in params, "Method must be instance method"
        assert "workload_size" in params, "Method must accept 'workload_size' parameter"

        # Check type hints
        hints = get_type_hints(method)
        assert hints.get("workload_size") == str, (
            f"workload_size type changed from str to {hints.get('workload_size')}"
        )
        assert hints.get("return") == ResourceSpec, (
            f"return type changed from ResourceSpec to {hints.get('return')}"
        )

    @pytest.mark.requirement("001-FR-004a")
    def test_is_self_hosted_property_signature(self) -> None:
        """Verify is_self_hosted is a property with correct return type.

        Contract:
            @property
            def is_self_hosted(self) -> bool

        This property determines K8s resource provisioning behavior.
        """
        from floe_core import ComputePlugin

        # Verify it's a property
        assert hasattr(ComputePlugin, "is_self_hosted")
        prop = getattr(ComputePlugin, "is_self_hosted")
        assert isinstance(prop, property), "is_self_hosted must be a property"

        # Check type hint on the getter
        getter = prop.fget
        assert getter is not None, "Property must have a getter"
        hints = get_type_hints(getter)
        assert hints.get("return") == bool, (
            f"return type changed from bool to {hints.get('return')}"
        )

    @pytest.mark.requirement("001-FR-002")
    def test_get_required_dbt_packages_signature(self) -> None:
        """Verify get_required_dbt_packages has correct signature.

        Contract:
            def get_required_dbt_packages(self) -> list[str]

        Returns pip package specifiers for dbt adapter installation.
        """
        from floe_core import ComputePlugin

        method = ComputePlugin.get_required_dbt_packages
        sig = inspect.signature(method)

        # Check parameters (only self)
        params = list(sig.parameters.keys())
        assert params == ["self"], "Method should only have 'self' parameter"

        # Check type hints
        hints = get_type_hints(method)
        assert hints.get("return") == list[str], (
            f"return type changed from list[str] to {hints.get('return')}"
        )


class TestComputePluginOptionalMethods:
    """Contract tests for optional ComputePlugin methods.

    These methods have default implementations but can be overridden.
    """

    @pytest.mark.requirement("001-FR-001")
    def test_get_catalog_attachment_sql_has_default(self) -> None:
        """Verify get_catalog_attachment_sql has default implementation.

        This method is optional - defaults to returning None.
        Engines that need catalog attachment (like DuckDB) override it.
        """
        from floe_core import CatalogConfig, ComputePlugin

        # Verify method exists and is not abstract
        assert hasattr(ComputePlugin, "get_catalog_attachment_sql")
        method = ComputePlugin.get_catalog_attachment_sql
        assert not getattr(method, "__isabstractmethod__", False), (
            "get_catalog_attachment_sql should not be abstract"
        )

        # Check signature
        hints = get_type_hints(method)
        assert hints.get("catalog_config") == CatalogConfig
        # Return type should allow None
        assert hints.get("return") == (list[str] | None)

    @pytest.mark.requirement("001-FR-001")
    def test_get_config_schema_has_default(self) -> None:
        """Verify get_config_schema has default implementation.

        This method is optional - defaults to returning None.
        Plugins can override to provide Pydantic validation schema.
        """
        from floe_core import ComputePlugin

        # Verify method exists and is not abstract
        assert hasattr(ComputePlugin, "get_config_schema")
        method = ComputePlugin.get_config_schema
        assert not getattr(method, "__isabstractmethod__", False), (
            "get_config_schema should not be abstract"
        )


class TestComputePluginInheritance:
    """Contract tests for ComputePlugin inheritance chain.

    ComputePlugin must extend PluginMetadata to be part of the plugin system.
    """

    @pytest.mark.requirement("001-FR-001")
    def test_compute_plugin_extends_plugin_metadata(self) -> None:
        """Verify ComputePlugin inherits from PluginMetadata.

        This is required for registry integration and lifecycle management.
        """
        from floe_core import ComputePlugin, PluginMetadata

        assert issubclass(ComputePlugin, PluginMetadata), (
            "ComputePlugin must inherit from PluginMetadata"
        )

    @pytest.mark.requirement("001-FR-001")
    def test_compute_plugin_inherits_lifecycle_methods(self) -> None:
        """Verify ComputePlugin has lifecycle methods from PluginMetadata.

        Plugins should have startup() and shutdown() for lifecycle management.
        """
        from floe_core import ComputePlugin

        assert hasattr(ComputePlugin, "startup")
        assert hasattr(ComputePlugin, "shutdown")
        assert hasattr(ComputePlugin, "health_check")


class TestComputeConfigurationModelsContract:
    """Contract tests for compute configuration models.

    These models are used by plugin implementations and must remain stable.
    """

    @pytest.mark.requirement("001-FR-002")
    def test_compute_config_required_fields(self) -> None:
        """Verify ComputeConfig has all required fields.

        Plugin implementations depend on these fields being available.
        """
        from floe_core import ComputeConfig

        # Create minimal config
        config = ComputeConfig(plugin="test")

        # Verify required fields exist
        assert hasattr(config, "plugin")
        assert hasattr(config, "timeout_seconds")
        assert hasattr(config, "threads")
        assert hasattr(config, "connection")
        assert hasattr(config, "credentials")

    @pytest.mark.requirement("001-FR-003")
    def test_connection_result_fields(self) -> None:
        """Verify ConnectionResult has all required fields.

        validate_connection implementations return this model.
        """
        from floe_core import ConnectionResult, ConnectionStatus

        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=10.0,
        )

        assert hasattr(result, "status")
        assert hasattr(result, "latency_ms")
        assert hasattr(result, "message")
        assert hasattr(result, "warnings")

    @pytest.mark.requirement("001-FR-003")
    def test_connection_status_enum_values(self) -> None:
        """Verify ConnectionStatus has all required values.

        Plugin implementations use these enum values.
        """
        from floe_core import ConnectionStatus

        # These exact values are part of the contract
        assert hasattr(ConnectionStatus, "HEALTHY")
        assert hasattr(ConnectionStatus, "DEGRADED")
        assert hasattr(ConnectionStatus, "UNHEALTHY")

        # String values should be stable (used in serialization)
        assert ConnectionStatus.HEALTHY.value == "healthy"
        assert ConnectionStatus.DEGRADED.value == "degraded"
        assert ConnectionStatus.UNHEALTHY.value == "unhealthy"

    @pytest.mark.requirement("001-FR-004")
    def test_resource_spec_fields(self) -> None:
        """Verify ResourceSpec has all required fields.

        K8s resource specifications depend on these fields.
        """
        from floe_core import ResourceSpec

        spec = ResourceSpec()

        # Verify required fields exist
        assert hasattr(spec, "cpu_request")
        assert hasattr(spec, "cpu_limit")
        assert hasattr(spec, "memory_request")
        assert hasattr(spec, "memory_limit")

    @pytest.mark.requirement("001-FR-004")
    def test_workload_presets_available(self) -> None:
        """Verify WORKLOAD_PRESETS has standard sizes.

        Plugins reference these preset names for resource allocation.
        """
        from floe_core import ResourceSpec, WORKLOAD_PRESETS

        # These preset names are part of the contract
        assert "small" in WORKLOAD_PRESETS
        assert "medium" in WORKLOAD_PRESETS
        assert "large" in WORKLOAD_PRESETS

        # All presets should be ResourceSpec instances
        for name, spec in WORKLOAD_PRESETS.items():
            assert isinstance(spec, ResourceSpec), f"{name} should be ResourceSpec"
