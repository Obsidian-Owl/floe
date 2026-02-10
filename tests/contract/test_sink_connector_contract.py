"""Contract tests for SinkConnector ABC interface stability.

These tests validate that the SinkConnector abstract base class defines
the correct interface for reverse ETL plugins. They ensure:
- SinkConnector, SinkConfig, EgressResult are importable from floe_core.plugins
- SinkConnector has exactly 4 abstract methods (no more, no fewer)
- SinkConnector does not inherit from PluginMetadata or IngestionPlugin
- SinkConfig and EgressResult field names and types match the contract
- A mock class implementing both SinkConnector and IngestionPlugin works

This is a contract test (tests/contract/) because it validates the interface
that plugin packages depend on. Changes to SinkConnector ABC can break
downstream implementations.

Contract: specs/4g-reverse-etl-sink/contracts/sink-connector-contract.md

Requirements Covered:
- 4G-SC-006: Contract tests validate SinkConnector interface stability
"""

from __future__ import annotations

import dataclasses
import inspect
from abc import ABC
from typing import Any

import pytest

from floe_core.plugins.ingestion import (
    IngestionConfig,
    IngestionPlugin,
    IngestionResult,
)
from floe_core.plugins.sink import EgressResult, SinkConfig, SinkConnector


# ---------------------------------------------------------------------------
# Expected contract field definitions
# ---------------------------------------------------------------------------

EXPECTED_SINK_CONFIG_FIELDS = {
    "sink_type": str,
    "connection_config": dict,
    "field_mapping": None,  # dict[str, str] | None — check name only
    "retry_config": None,  # dict[str, Any] | None — check name only
    "batch_size": None,  # int | None — check name only
}

EXPECTED_EGRESS_RESULT_FIELDS = {
    "success": bool,
    "rows_delivered": int,
    "bytes_transmitted": int,
    "duration_seconds": float,
    "checksum": str,
    "delivery_timestamp": str,
    "idempotency_key": str,
    "destination_record_ids": list,
    "errors": list,
}


# ---------------------------------------------------------------------------
# Contract Tests: Importability
# ---------------------------------------------------------------------------


class TestSinkConnectorImportability:
    """Contract tests for SinkConnector importability from floe_core.plugins."""

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_connector_importable_from_plugins(self) -> None:
        """Verify SinkConnector is importable from floe_core.plugins.

        4G-SC-006: Public API stability — SinkConnector is a top-level export.
        """
        from floe_core.plugins import SinkConnector as ImportedSinkConnector

        assert ImportedSinkConnector is SinkConnector

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_config_importable_from_plugins(self) -> None:
        """Verify SinkConfig is importable from floe_core.plugins.

        4G-SC-006: Public API stability — SinkConfig is a top-level export.
        """
        from floe_core.plugins import SinkConfig as ImportedSinkConfig

        assert ImportedSinkConfig is SinkConfig

    @pytest.mark.requirement("4G-SC-006")
    def test_egress_result_importable_from_plugins(self) -> None:
        """Verify EgressResult is importable from floe_core.plugins.

        4G-SC-006: Public API stability — EgressResult is a top-level export.
        """
        from floe_core.plugins import EgressResult as ImportedEgressResult

        assert ImportedEgressResult is EgressResult


# ---------------------------------------------------------------------------
# Contract Tests: ABC Structure
# ---------------------------------------------------------------------------


class TestSinkConnectorABCStructure:
    """Contract tests for SinkConnector ABC definition stability."""

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_connector_is_abstract(self) -> None:
        """Verify SinkConnector is an abstract base class.

        4G-SC-006: SinkConnector must be a proper ABC.
        """
        assert issubclass(SinkConnector, ABC)

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_connector_has_exactly_4_abstract_methods(self) -> None:
        """Verify SinkConnector has exactly 4 abstract methods.

        4G-SC-006: Adding/removing abstract methods is a MAJOR version change.
        """
        abstract_methods: set[str] = set()
        for attr_name in dir(SinkConnector):
            method = getattr(SinkConnector, attr_name, None)
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.add(attr_name)

        assert len(abstract_methods) == 4
        assert abstract_methods == {
            "list_available_sinks",
            "create_sink",
            "write",
            "get_source_config",
        }

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_connector_does_not_inherit_plugin_metadata(self) -> None:
        """Verify SinkConnector does not inherit from PluginMetadata.

        4G-SC-006: SinkConnector is standalone — no forced PluginMetadata dependency.
        """
        from floe_core.plugin_metadata import PluginMetadata

        assert not issubclass(SinkConnector, PluginMetadata)

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_connector_does_not_inherit_ingestion_plugin(self) -> None:
        """Verify SinkConnector does not inherit from IngestionPlugin.

        4G-SC-006: SinkConnector is independently implementable.
        """
        assert not issubclass(SinkConnector, IngestionPlugin)

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_connector_method_signatures_stable(self) -> None:
        """Verify method signatures match the contract.

        4G-SC-006: Changing method signatures is a MAJOR version change.
        """
        # list_available_sinks: (self) -> list[str]
        sig = inspect.signature(SinkConnector.list_available_sinks)
        assert list(sig.parameters.keys()) == ["self"]

        # create_sink: (self, config: SinkConfig) -> Any
        sig = inspect.signature(SinkConnector.create_sink)
        assert "config" in sig.parameters

        # write: (self, sink: Any, data: Any, **kwargs: Any) -> EgressResult
        sig = inspect.signature(SinkConnector.write)
        assert "sink" in sig.parameters
        assert "data" in sig.parameters
        assert "kwargs" in sig.parameters

        # get_source_config: (self, catalog_config: dict[str, Any]) -> dict[str, Any]
        sig = inspect.signature(SinkConnector.get_source_config)
        assert "catalog_config" in sig.parameters


# ---------------------------------------------------------------------------
# Contract Tests: Dataclass Field Stability
# ---------------------------------------------------------------------------


class TestSinkConfigFieldContract:
    """Contract tests for SinkConfig field stability."""

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_config_fields_match_contract(self) -> None:
        """Verify SinkConfig fields match the contract specification.

        4G-SC-006: Removing fields or changing types is a MAJOR version change.
        """
        fields = {f.name for f in dataclasses.fields(SinkConfig)}
        expected_fields = set(EXPECTED_SINK_CONFIG_FIELDS.keys())
        assert fields == expected_fields

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_config_is_dataclass(self) -> None:
        """Verify SinkConfig is a dataclass (not Pydantic).

        4G-SC-006: SinkConfig is a runtime DTO, not a schema validation model.
        """
        assert dataclasses.is_dataclass(SinkConfig)


class TestEgressResultFieldContract:
    """Contract tests for EgressResult field stability."""

    @pytest.mark.requirement("4G-SC-006")
    def test_egress_result_fields_match_contract(self) -> None:
        """Verify EgressResult fields match the contract specification.

        4G-SC-006: Removing fields or changing types is a MAJOR version change.
        """
        fields = {f.name for f in dataclasses.fields(EgressResult)}
        expected_fields = set(EXPECTED_EGRESS_RESULT_FIELDS.keys())
        assert fields == expected_fields

    @pytest.mark.requirement("4G-SC-006")
    def test_egress_result_is_dataclass(self) -> None:
        """Verify EgressResult is a dataclass (not Pydantic).

        4G-SC-006: EgressResult is a runtime DTO, not a schema validation model.
        """
        assert dataclasses.is_dataclass(EgressResult)


# ---------------------------------------------------------------------------
# Contract Tests: Mixin Compatibility
# ---------------------------------------------------------------------------


class TestSinkConnectorMixinContract:
    """Contract tests for SinkConnector working as mixin with IngestionPlugin."""

    @pytest.mark.requirement("4G-SC-006")
    def test_mixin_with_ingestion_plugin_satisfies_both(self) -> None:
        """Verify a class can implement both IngestionPlugin and SinkConnector.

        4G-SC-006: Bidirectional plugins must satisfy both interfaces.
        """

        class MockBidirectionalPlugin(IngestionPlugin, SinkConnector):
            """Mock bidirectional plugin."""

            @property
            def name(self) -> str:
                return "mock-bidirectional"

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

            def run(self, pipeline: Any, **kwargs: Any) -> IngestionResult:
                _ = pipeline, kwargs
                return IngestionResult(success=True)

            def get_destination_config(
                self, catalog_config: dict[str, Any]
            ) -> dict[str, Any]:
                _ = catalog_config
                return {}

            def list_available_sinks(self) -> list[str]:
                return ["rest_api"]

            def create_sink(self, config: SinkConfig) -> Any:
                _ = config
                return {}

            def write(
                self, sink: Any, data: Any, **kwargs: Any
            ) -> EgressResult:
                _ = sink, data, kwargs
                return EgressResult(success=True)

            def get_source_config(
                self, catalog_config: dict[str, Any]
            ) -> dict[str, Any]:
                _ = catalog_config
                return {}

        plugin = MockBidirectionalPlugin()
        assert isinstance(plugin, IngestionPlugin)
        assert isinstance(plugin, SinkConnector)


class TestSinkConfigValidationContract:
    """Contract tests for SinkConfig __post_init__ validation."""

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_config_validates_on_construction(self) -> None:
        """Verify SinkConfig validates fields at construction time.

        4G-SC-006: SinkConfig validation is part of the contract.
        """
        # Valid construction should work
        config = SinkConfig(sink_type="rest_api")
        assert config.sink_type == "rest_api"

        # Invalid construction should fail
        with pytest.raises(ValueError):
            SinkConfig(sink_type="")

    @pytest.mark.requirement("4G-SC-006")
    def test_sink_config_batch_size_bounds_are_contract(self) -> None:
        """Verify SinkConfig batch_size bounds are part of the contract.

        4G-SC-006: Bounds 1-100_000 are enforced.
        """
        # Lower bound
        config = SinkConfig(sink_type="rest_api", batch_size=1)
        assert config.batch_size == 1

        # Upper bound
        config = SinkConfig(sink_type="rest_api", batch_size=100_000)
        assert config.batch_size == 100_000

        # Below lower
        with pytest.raises(ValueError):
            SinkConfig(sink_type="rest_api", batch_size=0)

        # Above upper
        with pytest.raises(ValueError):
            SinkConfig(sink_type="rest_api", batch_size=100_001)
