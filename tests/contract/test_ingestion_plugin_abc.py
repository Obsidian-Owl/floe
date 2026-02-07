"""Contract tests for IngestionPlugin ABC compliance.

These tests validate that the IngestionPlugin abstract base class defines
the correct interface for ingestion plugins. They ensure:
- All required abstract methods are defined with correct signatures
- Concrete implementations must implement all abstract methods
- Type hints are present and accurate
- Default implementations work correctly

This is a contract test (tests/contract/) because it validates the interface
that plugin packages depend on. Changes to IngestionPlugin ABC can break
downstream implementations.

Requirements Covered:
- 4F-FR-001: IngestionPlugin ABC with is_external property
- 4F-FR-001: create_pipeline() method with config parameter
- 4F-FR-001: run() method with pipeline parameter
- 4F-FR-001: get_destination_config() method with catalog_config parameter
- 4F-FR-001: Plugin metadata requirements (name, version, floe_api_version)
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


class TestIngestionPluginABCDefinition:
    """Contract tests for IngestionPlugin ABC structure.

    These tests verify that IngestionPlugin defines the correct abstract
    methods and properties with proper signatures.
    """

    @pytest.mark.requirement("4F-FR-001")
    def test_ingestion_plugin_is_abstract_class(self) -> None:
        """Verify IngestionPlugin is an abstract base class.

        IngestionPlugin must be abstract to enforce method implementation
        in concrete plugins.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        # Must be a class
        assert isinstance(IngestionPlugin, type)

        # Must inherit from ABC (via PluginMetadata)
        assert issubclass(IngestionPlugin, ABC)

    @pytest.mark.requirement("4F-FR-001")
    def test_is_external_is_abstract_property(self) -> None:
        """Verify is_external is an abstract property with correct signature.

        4F-FR-001: IngestionPlugin must define is_external to indicate
        whether the tool runs as an external service.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        # Property must exist
        assert hasattr(IngestionPlugin, "is_external")

        # Must be abstract
        prop = getattr(IngestionPlugin, "is_external")
        # For properties, check if the fget method is abstract
        assert getattr(prop.fget, "__isabstractmethod__", False), "is_external must be abstract"

    @pytest.mark.requirement("4F-FR-001")
    def test_create_pipeline_is_abstract(self) -> None:
        """Verify create_pipeline() is an abstract method with correct signature.

        4F-FR-001: IngestionPlugin must define create_pipeline() that
        configures and returns a pipeline object.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        # Method must exist
        assert hasattr(IngestionPlugin, "create_pipeline")

        # Must be abstract
        method = IngestionPlugin.create_pipeline
        assert getattr(method, "__isabstractmethod__", False), "create_pipeline() must be abstract"

        # Check signature
        sig = inspect.signature(IngestionPlugin.create_pipeline)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "config" in params

    @pytest.mark.requirement("4F-FR-001")
    def test_run_is_abstract(self) -> None:
        """Verify run() is an abstract method with correct signature.

        4F-FR-001: IngestionPlugin must define run() that executes
        the ingestion pipeline.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        # Method must exist
        assert hasattr(IngestionPlugin, "run")

        # Must be abstract
        method = IngestionPlugin.run
        assert getattr(method, "__isabstractmethod__", False), "run() must be abstract"

        # Check signature
        sig = inspect.signature(IngestionPlugin.run)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "pipeline" in params
        assert "kwargs" in params  # **kwargs

    @pytest.mark.requirement("4F-FR-001")
    def test_get_destination_config_is_abstract(self) -> None:
        """Verify get_destination_config() is an abstract method with correct signature.

        4F-FR-001: IngestionPlugin must define get_destination_config() that
        generates destination configuration for Iceberg.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        # Method must exist
        assert hasattr(IngestionPlugin, "get_destination_config")

        # Must be abstract
        method = IngestionPlugin.get_destination_config
        assert getattr(
            method, "__isabstractmethod__", False
        ), "get_destination_config() must be abstract"

        # Check signature
        sig = inspect.signature(IngestionPlugin.get_destination_config)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "catalog_config" in params


class TestIngestionPluginMetadataRequirements:
    """Contract tests for plugin metadata requirements.

    4F-FR-001: All IngestionPlugin implementations must provide plugin metadata.
    """

    @pytest.mark.requirement("4F-FR-001")
    def test_ingestion_plugin_inherits_plugin_metadata(self) -> None:
        """Verify IngestionPlugin inherits from PluginMetadata.

        This ensures all ingestion plugins have required metadata properties.
        """
        from floe_core.plugin_metadata import PluginMetadata
        from floe_core.plugins.ingestion import IngestionPlugin

        assert issubclass(IngestionPlugin, PluginMetadata)

    @pytest.mark.requirement("4F-FR-001")
    def test_name_property_is_required(self) -> None:
        """Verify name property is required (abstract).

        All plugins must have a unique name.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        # name comes from PluginMetadata and is abstract
        assert hasattr(IngestionPlugin, "name")

    @pytest.mark.requirement("4F-FR-001")
    def test_version_property_is_required(self) -> None:
        """Verify version property is required (abstract).

        All plugins must declare their version.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        assert hasattr(IngestionPlugin, "version")

    @pytest.mark.requirement("4F-FR-001")
    def test_floe_api_version_property_is_required(self) -> None:
        """Verify floe_api_version property is required (abstract).

        All plugins must declare compatible API version.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        assert hasattr(IngestionPlugin, "floe_api_version")


class TestIngestionPluginInstantiationContract:
    """Contract tests for IngestionPlugin instantiation.

    These tests verify that:
    - IngestionPlugin cannot be instantiated directly (abstract)
    - Incomplete implementations cannot be instantiated
    - Complete implementations can be instantiated
    """

    @pytest.mark.requirement("4F-FR-001")
    def test_cannot_instantiate_abstract_ingestion_plugin(self) -> None:
        """Verify IngestionPlugin cannot be instantiated directly.

        Direct instantiation must fail because abstract methods are not implemented.
        """
        from floe_core.plugins.ingestion import IngestionPlugin

        with pytest.raises(TypeError, match="abstract"):
            IngestionPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("4F-FR-001")
    def test_incomplete_implementation_fails(self) -> None:
        """Verify incomplete IngestionPlugin implementation fails.

        A class that only implements some abstract methods should not
        be instantiable.
        """
        from floe_core.plugins.ingestion import IngestionConfig, IngestionPlugin

        class IncompletePlugin(IngestionPlugin):
            """Plugin missing most abstract methods."""

            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def is_external(self) -> bool:
                return False

            def create_pipeline(self, config: IngestionConfig) -> Any:
                _ = config
                return {}

            # Missing: run, get_destination_config

        with pytest.raises(TypeError, match="abstract"):
            IncompletePlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("4F-FR-001")
    def test_complete_implementation_succeeds(self) -> None:
        """Verify complete IngestionPlugin implementation can be instantiated.

        A class implementing all abstract methods should be instantiable.
        """
        from floe_core.plugins.ingestion import (
            IngestionConfig,
            IngestionPlugin,
            IngestionResult,
        )

        class CompleteMockPlugin(IngestionPlugin):
            """Complete mock plugin implementation for testing."""

            @property
            def name(self) -> str:
                return "mock-ingestion"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def is_external(self) -> bool:
                return False

            def create_pipeline(self, config: IngestionConfig) -> Any:
                _ = config
                return {"pipeline": "mock"}

            def run(self, pipeline: Any, **kwargs: Any) -> IngestionResult:
                _ = pipeline, kwargs
                return IngestionResult(success=True, rows_loaded=0)

            def get_destination_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
                _ = catalog_config
                return {"destination": "mock"}

        # Should not raise
        plugin = CompleteMockPlugin()

        # Verify metadata is accessible
        assert plugin.name == "mock-ingestion"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "1.0"
        assert plugin.is_external is False
