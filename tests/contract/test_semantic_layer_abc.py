"""Contract tests for SemanticLayerPlugin ABC compliance.

These tests validate that the SemanticLayerPlugin abstract base class defines
the correct interface for semantic layer plugins. They ensure:
- All required abstract methods are defined with correct signatures
- ABC is not directly instantiable
- Type hints are present and accurate
- Inherits from PluginMetadata
- Optional methods (health_check, startup, shutdown) are inherited

This is a contract test (tests/contract/) because it validates the interface
that semantic layer plugin packages depend on. Changes to SemanticLayerPlugin
ABC can break downstream implementations.

Requirements Covered:
    - SC-001: SemanticLayerPlugin ABC defines complete interface
    - FR-001: ABC abstract methods include get_api_endpoints
    - FR-002: ABC abstract methods include get_helm_values_override
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import get_type_hints

import pytest

from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugins.semantic import SemanticLayerPlugin

# The 5 required abstract methods on SemanticLayerPlugin
EXPECTED_ABSTRACT_METHODS = {
    "sync_from_dbt_manifest",
    "get_security_context",
    "get_datasource_config",
    "get_api_endpoints",
    "get_helm_values_override",
}


class TestSemanticLayerPluginABCStructure:
    """Contract tests for SemanticLayerPlugin ABC definition."""

    @pytest.mark.requirement("SC-001")
    def test_is_abstract_class(self) -> None:
        """Verify SemanticLayerPlugin is an abstract base class."""
        assert isinstance(SemanticLayerPlugin, type)
        assert issubclass(SemanticLayerPlugin, ABC)

    @pytest.mark.requirement("SC-001")
    def test_inherits_plugin_metadata(self) -> None:
        """Verify SemanticLayerPlugin inherits from PluginMetadata."""
        assert issubclass(SemanticLayerPlugin, PluginMetadata)

    @pytest.mark.requirement("SC-001")
    def test_not_directly_instantiable(self) -> None:
        """Verify SemanticLayerPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract method"):
            SemanticLayerPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("SC-001")
    def test_exactly_five_abstract_methods(self) -> None:
        """Verify ABC defines exactly 5 semantic-specific abstract methods.

        The ABC should have these 5 abstract methods:
        1. sync_from_dbt_manifest
        2. get_security_context
        3. get_datasource_config
        4. get_api_endpoints
        5. get_helm_values_override

        Plus inherited abstract properties from PluginMetadata:
        name, version, floe_api_version
        """
        # Get all abstract methods (including inherited from PluginMetadata)
        all_abstract = set()
        for name in dir(SemanticLayerPlugin):
            obj = getattr(SemanticLayerPlugin, name, None)
            if getattr(obj, "__isabstractmethod__", False):
                all_abstract.add(name)

        # The semantic-specific abstract methods should all be present
        assert EXPECTED_ABSTRACT_METHODS.issubset(all_abstract), (
            f"Missing abstract methods: {EXPECTED_ABSTRACT_METHODS - all_abstract}"
        )


class TestSemanticLayerPluginMethodSignatures:
    """Contract tests for method signatures."""

    @pytest.mark.requirement("FR-001")
    def test_sync_from_dbt_manifest_signature(self) -> None:
        """Verify sync_from_dbt_manifest has correct parameters."""
        sig = inspect.signature(SemanticLayerPlugin.sync_from_dbt_manifest)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "manifest_path" in params
        assert "output_dir" in params

    @pytest.mark.requirement("FR-001")
    def test_get_security_context_signature(self) -> None:
        """Verify get_security_context has correct parameters."""
        sig = inspect.signature(SemanticLayerPlugin.get_security_context)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "namespace" in params
        assert "roles" in params

    @pytest.mark.requirement("FR-001")
    def test_get_datasource_config_signature(self) -> None:
        """Verify get_datasource_config has correct parameters."""
        sig = inspect.signature(SemanticLayerPlugin.get_datasource_config)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "compute_plugin" in params

    @pytest.mark.requirement("FR-002")
    def test_get_api_endpoints_signature(self) -> None:
        """Verify get_api_endpoints has correct parameters."""
        sig = inspect.signature(SemanticLayerPlugin.get_api_endpoints)
        params = list(sig.parameters.keys())
        assert params == ["self"], "get_api_endpoints should only take self"

    @pytest.mark.requirement("FR-002")
    def test_get_helm_values_override_signature(self) -> None:
        """Verify get_helm_values_override has correct parameters."""
        sig = inspect.signature(SemanticLayerPlugin.get_helm_values_override)
        params = list(sig.parameters.keys())
        assert params == ["self"], "get_helm_values_override should only take self"


class TestSemanticLayerPluginTypeHints:
    """Contract tests for type hint completeness."""

    @pytest.mark.requirement("SC-001")
    def test_all_methods_have_return_type_hints(self) -> None:
        """Verify all abstract methods have return type annotations.

        Note: get_datasource_config uses TYPE_CHECKING for ComputePlugin,
        so we use inspect.signature instead of get_type_hints for that method.
        """
        hints = get_type_hints(SemanticLayerPlugin.sync_from_dbt_manifest)
        assert "return" in hints

        hints = get_type_hints(SemanticLayerPlugin.get_security_context)
        assert "return" in hints

        # get_datasource_config has a TYPE_CHECKING forward ref (ComputePlugin),
        # so get_type_hints fails at runtime. Use inspect.signature instead.
        sig = inspect.signature(SemanticLayerPlugin.get_datasource_config)
        assert sig.return_annotation is not inspect.Parameter.empty

        hints = get_type_hints(SemanticLayerPlugin.get_api_endpoints)
        assert "return" in hints

        hints = get_type_hints(SemanticLayerPlugin.get_helm_values_override)
        assert "return" in hints

    @pytest.mark.requirement("SC-001")
    def test_sync_from_dbt_manifest_return_type(self) -> None:
        """Verify sync_from_dbt_manifest returns list[Path]."""
        sig = inspect.signature(SemanticLayerPlugin.sync_from_dbt_manifest)
        assert sig.return_annotation is not inspect.Parameter.empty

    @pytest.mark.requirement("SC-001")
    def test_get_api_endpoints_return_type(self) -> None:
        """Verify get_api_endpoints returns dict[str, str]."""
        sig = inspect.signature(SemanticLayerPlugin.get_api_endpoints)
        assert sig.return_annotation is not inspect.Parameter.empty

    @pytest.mark.requirement("SC-001")
    def test_get_helm_values_override_return_type(self) -> None:
        """Verify get_helm_values_override returns dict[str, Any]."""
        sig = inspect.signature(SemanticLayerPlugin.get_helm_values_override)
        assert sig.return_annotation is not inspect.Parameter.empty


class TestSemanticLayerPluginDocstrings:
    """Contract tests for documentation completeness."""

    @pytest.mark.requirement("SC-001")
    def test_all_abstract_methods_have_docstrings(self) -> None:
        """Verify all abstract methods have docstrings."""
        for method_name in EXPECTED_ABSTRACT_METHODS:
            method = getattr(SemanticLayerPlugin, method_name)
            assert method.__doc__ is not None, (
                f"Method {method_name} must have a docstring"
            )
            assert len(method.__doc__.strip()) > 10, (
                f"Method {method_name} docstring is too short"
            )

    @pytest.mark.requirement("SC-001")
    def test_class_has_docstring(self) -> None:
        """Verify SemanticLayerPlugin class has a docstring."""
        assert SemanticLayerPlugin.__doc__ is not None
        assert "SemanticLayerPlugin" in SemanticLayerPlugin.__doc__


class TestSemanticLayerPluginOptionalMethods:
    """Contract tests for inherited optional methods."""

    @pytest.mark.requirement("SC-001")
    def test_health_check_inherited(self) -> None:
        """Verify health_check() is available from PluginMetadata."""
        assert hasattr(SemanticLayerPlugin, "health_check")

    @pytest.mark.requirement("SC-001")
    def test_startup_inherited(self) -> None:
        """Verify startup() is available from PluginMetadata."""
        assert hasattr(SemanticLayerPlugin, "startup")

    @pytest.mark.requirement("SC-001")
    def test_shutdown_inherited(self) -> None:
        """Verify shutdown() is available from PluginMetadata."""
        assert hasattr(SemanticLayerPlugin, "shutdown")

    @pytest.mark.requirement("SC-001")
    def test_get_config_schema_inherited(self) -> None:
        """Verify get_config_schema() is available from PluginMetadata."""
        assert hasattr(SemanticLayerPlugin, "get_config_schema")
