"""Unit tests for SinkConnector ABC, SinkConfig, and EgressResult.

These tests validate:
- SinkConnector ABC enforces 4 abstract methods (T004)
- SinkConnector works standalone and as mixin with IngestionPlugin (T005)
- SinkConfig and EgressResult dataclasses have correct defaults and behaviour (T006)

Requirements Covered:
- 4G-FR-001: SinkConnector ABC with 4 abstract methods
- 4G-FR-002: SinkConfig dataclass with field_mapping support
- 4G-FR-003: EgressResult dataclass with rich delivery receipt fields
- 4G-FR-004: Runtime capability detection via isinstance()
- 4G-FR-014: Field mapping configuration in SinkConfig
- 4G-FR-015: SinkConnector independently implementable (standalone)
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from floe_core.plugins.ingestion import (
    IngestionConfig,
    IngestionPlugin,
    IngestionResult,
)
from floe_core.plugins.sink import EgressResult, SinkConfig, SinkConnector

# ---------------------------------------------------------------------------
# Mock implementations for testing
# ---------------------------------------------------------------------------


class CompleteSinkPlugin(SinkConnector):
    """Complete SinkConnector implementation for testing."""

    def list_available_sinks(self) -> list[str]:
        return ["rest_api", "sql_database"]

    def create_sink(self, config: SinkConfig) -> Any:
        _ = config
        return {"sink": "mock"}

    def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult:
        _ = sink, data, kwargs
        return EgressResult(success=True, rows_delivered=100)

    def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        _ = catalog_config
        return {"catalog_uri": "mock"}


class IncompleteSinkPlugin(SinkConnector):
    """Incomplete implementation missing write() and get_source_config()."""

    def list_available_sinks(self) -> list[str]:
        return ["rest_api"]

    def create_sink(self, config: SinkConfig) -> Any:
        _ = config
        return {"sink": "mock"}


class BidirectionalPlugin(IngestionPlugin, SinkConnector):
    """Plugin implementing both IngestionPlugin and SinkConnector."""

    @property
    def name(self) -> str:
        return "bidirectional"

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

    def list_available_sinks(self) -> list[str]:
        return ["rest_api"]

    def create_sink(self, config: SinkConfig) -> Any:
        _ = config
        return {"sink": "mock"}

    def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult:
        _ = sink, data, kwargs
        return EgressResult(success=True)

    def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        _ = catalog_config
        return {"source": "mock"}


class PlainIngestionPlugin(IngestionPlugin):
    """IngestionPlugin WITHOUT SinkConnector mixin."""

    @property
    def name(self) -> str:
        return "plain-ingestion"

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


# ---------------------------------------------------------------------------
# T004: ABC Enforcement Tests
# ---------------------------------------------------------------------------


class TestSinkConnectorABCEnforcement:
    """Test that SinkConnector ABC enforces abstract method implementation."""

    @pytest.mark.requirement("4G-FR-001")
    def test_cannot_instantiate_abstract_directly(self) -> None:
        """Verify SinkConnector cannot be instantiated directly.

        4G-FR-001: SinkConnector is an ABC with abstract methods.
        """
        with pytest.raises(TypeError, match="abstract"):
            SinkConnector()  # type: ignore[abstract]

    @pytest.mark.requirement("4G-FR-001")
    def test_incomplete_implementation_raises_type_error(self) -> None:
        """Verify incomplete implementation raises TypeError.

        4G-FR-001: All 4 abstract methods must be implemented.
        """
        with pytest.raises(TypeError, match="abstract"):
            IncompleteSinkPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("4G-FR-001")
    def test_complete_implementation_succeeds(self) -> None:
        """Verify complete implementation can be instantiated.

        4G-FR-001: A class implementing all 4 methods succeeds.
        """
        plugin = CompleteSinkPlugin()
        assert isinstance(plugin, SinkConnector)

    @pytest.mark.requirement("4G-FR-001")
    def test_sink_connector_has_exactly_4_abstract_methods(self) -> None:
        """Verify SinkConnector defines exactly 4 abstract methods.

        4G-FR-001: list_available_sinks, create_sink, write, get_source_config.
        """
        abstract_methods: set[str] = set()
        for attr_name in dir(SinkConnector):
            method = getattr(SinkConnector, attr_name, None)
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.add(attr_name)

        assert abstract_methods == {
            "list_available_sinks",
            "create_sink",
            "write",
            "get_source_config",
        }

    @pytest.mark.requirement("4G-FR-001")
    def test_list_available_sinks_signature(self) -> None:
        """Verify list_available_sinks() has correct signature.

        4G-FR-001: Returns list[str], takes no parameters beyond self.
        """
        sig = inspect.signature(SinkConnector.list_available_sinks)
        params = list(sig.parameters.keys())
        assert params == ["self"]

    @pytest.mark.requirement("4G-FR-001")
    def test_create_sink_signature(self) -> None:
        """Verify create_sink(config) has correct signature.

        4G-FR-001: Takes SinkConfig, returns Any.
        """
        sig = inspect.signature(SinkConnector.create_sink)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "config" in params

    @pytest.mark.requirement("4G-FR-001")
    def test_write_signature(self) -> None:
        """Verify write(sink, data, **kwargs) has correct signature.

        4G-FR-001: Takes sink, data, **kwargs, returns EgressResult.
        """
        sig = inspect.signature(SinkConnector.write)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "sink" in params
        assert "data" in params
        assert "kwargs" in params

    @pytest.mark.requirement("4G-FR-001")
    def test_get_source_config_signature(self) -> None:
        """Verify get_source_config(catalog_config) has correct signature.

        4G-FR-001: Takes catalog_config dict, returns dict.
        """
        sig = inspect.signature(SinkConnector.get_source_config)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "catalog_config" in params


# ---------------------------------------------------------------------------
# T005: Standalone and Mixin Tests
# ---------------------------------------------------------------------------


class TestSinkConnectorStandaloneAndMixin:
    """Test SinkConnector works standalone and as mixin with IngestionPlugin."""

    @pytest.mark.requirement("4G-FR-015")
    def test_standalone_without_ingestion_plugin(self) -> None:
        """Verify SinkConnector works without IngestionPlugin.

        4G-FR-015: SinkConnector is independently implementable.
        """
        plugin = CompleteSinkPlugin()
        assert isinstance(plugin, SinkConnector)
        assert not isinstance(plugin, IngestionPlugin)
        sinks = plugin.list_available_sinks()
        assert sinks == ["rest_api", "sql_database"]

    @pytest.mark.requirement("4G-FR-004")
    @pytest.mark.requirement("4G-FR-015")
    def test_mixin_with_ingestion_plugin(self) -> None:
        """Verify mixin works and isinstance() detects both interfaces.

        4G-FR-004: isinstance(plugin, SinkConnector) returns True.
        4G-FR-015: Works as mixin with IngestionPlugin.
        """
        plugin = BidirectionalPlugin()
        assert isinstance(plugin, SinkConnector)
        assert isinstance(plugin, IngestionPlugin)

    @pytest.mark.requirement("4G-FR-004")
    def test_plain_ingestion_plugin_not_sink_connector(self) -> None:
        """Verify IngestionPlugin-only plugin is not a SinkConnector.

        4G-FR-004: isinstance() returns False for non-SinkConnector plugins.
        """
        plugin = PlainIngestionPlugin()
        assert isinstance(plugin, IngestionPlugin)
        assert not isinstance(plugin, SinkConnector)

    @pytest.mark.requirement("4G-FR-015")
    def test_sink_connector_does_not_inherit_plugin_metadata(self) -> None:
        """Verify SinkConnector does not inherit from PluginMetadata.

        4G-FR-015: SinkConnector is standalone — no PluginMetadata dependency.
        """
        from floe_core.plugin_metadata import PluginMetadata

        assert not issubclass(SinkConnector, PluginMetadata)


# ---------------------------------------------------------------------------
# T006: Dataclass Tests
# ---------------------------------------------------------------------------


class TestSinkConfigDataclass:
    """Test SinkConfig dataclass defaults and field validation."""

    @pytest.mark.requirement("4G-FR-002")
    def test_sink_config_defaults(self) -> None:
        """Verify SinkConfig has correct default values.

        4G-FR-002: SinkConfig has sink_type (required) and optional fields.
        """
        config = SinkConfig(sink_type="rest_api")
        assert config.sink_type == "rest_api"
        assert config.connection_config == {}
        assert config.field_mapping is None
        assert config.retry_config is None
        assert config.batch_size is None

    @pytest.mark.requirement("4G-FR-002")
    @pytest.mark.requirement("4G-FR-014")
    def test_sink_config_with_all_fields(self) -> None:
        """Verify SinkConfig accepts all optional fields.

        4G-FR-002: All fields populate correctly.
        4G-FR-014: Field mapping configuration supported.
        """
        config = SinkConfig(
            sink_type="sql_database",
            connection_config={"host": "db.example.com", "port": 5432},
            field_mapping={"customer_id": "Id", "email": "Email"},
            retry_config={"max_retries": 3, "backoff_factor": 2.0},
            batch_size=500,
        )
        assert config.sink_type == "sql_database"
        assert config.connection_config == {"host": "db.example.com", "port": 5432}
        assert config.field_mapping == {"customer_id": "Id", "email": "Email"}
        assert config.retry_config == {"max_retries": 3, "backoff_factor": 2.0}
        assert config.batch_size == 500


class TestEgressResultDataclass:
    """Test EgressResult dataclass defaults, edge cases, and isolation."""

    @pytest.mark.requirement("4G-FR-003")
    def test_egress_result_defaults(self) -> None:
        """Verify EgressResult has correct default values.

        4G-FR-003: success is required; all other fields have defaults.
        """
        result = EgressResult(success=True)
        assert result.success is True
        assert result.rows_delivered == 0
        assert result.bytes_transmitted == 0
        assert result.duration_seconds == pytest.approx(0.0)
        assert result.checksum == ""
        assert result.delivery_timestamp == ""
        assert result.idempotency_key == ""
        assert result.destination_record_ids == []
        assert result.errors == []

    @pytest.mark.requirement("4G-FR-003")
    def test_egress_result_with_empty_rows(self) -> None:
        """Verify EgressResult with rows_delivered=0 is valid.

        4G-FR-003: Empty dataset egress should succeed with 0 rows.
        """
        result = EgressResult(success=True, rows_delivered=0)
        assert result.success is True
        assert result.rows_delivered == 0

    @pytest.mark.requirement("4G-FR-003")
    def test_egress_result_with_all_fields(self) -> None:
        """Verify EgressResult accepts all fields with values.

        4G-FR-003: Rich delivery receipt with load-assurance fields.
        """
        result = EgressResult(
            success=True,
            rows_delivered=1000,
            bytes_transmitted=524288,
            duration_seconds=2.5,
            checksum="sha256:abc123",
            delivery_timestamp="2026-01-15T10:30:00Z",
            idempotency_key="batch-001",
            destination_record_ids=["id-1", "id-2", "id-3"],
            errors=[],
        )
        assert result.rows_delivered == 1000
        assert result.bytes_transmitted == 524288
        assert result.duration_seconds == pytest.approx(2.5)
        assert result.checksum == "sha256:abc123"
        assert result.delivery_timestamp == "2026-01-15T10:30:00Z"
        assert result.idempotency_key == "batch-001"
        assert result.destination_record_ids == ["id-1", "id-2", "id-3"]
        assert result.errors == []

    @pytest.mark.requirement("4G-FR-003")
    def test_egress_result_failure_with_errors(self) -> None:
        """Verify EgressResult captures failure information.

        4G-FR-003: Errors list captures failure details.
        """
        result = EgressResult(
            success=False,
            rows_delivered=0,
            errors=["connection timeout", "retry exhausted"],
        )
        assert result.success is False
        assert len(result.errors) == 2
        assert "connection timeout" in result.errors

    @pytest.mark.requirement("4G-FR-003")
    def test_egress_result_mutable_default_isolation(self) -> None:
        """Verify list fields don't share state between instances.

        4G-FR-003: Mutable defaults must be isolated per instance.
        """
        result1 = EgressResult(success=True)
        result2 = EgressResult(success=True)

        result1.destination_record_ids.append("id-1")
        result1.errors.append("error-1")

        assert result1.destination_record_ids == ["id-1"]
        assert result2.destination_record_ids == []
        assert result1.errors == ["error-1"]
        assert result2.errors == []


class TestSinkConfigValidation:
    """Test SinkConfig __post_init__ validation (security remediation)."""

    @pytest.mark.requirement("4G-SEC-002")
    def test_empty_sink_type_raises_value_error(self) -> None:
        """Test that empty sink_type raises ValueError.

        Validates input validation prevents empty sink identifiers.
        """
        with pytest.raises(ValueError, match="sink_type must be a non-empty string"):
            SinkConfig(sink_type="")

    @pytest.mark.requirement("4G-SEC-002")
    def test_whitespace_only_sink_type_raises_value_error(self) -> None:
        """Test that whitespace-only sink_type raises ValueError.

        Validates whitespace strings are rejected.
        """
        with pytest.raises(ValueError, match="sink_type must be a non-empty string"):
            SinkConfig(sink_type="   ")

    @pytest.mark.requirement("4G-SEC-003")
    def test_batch_size_zero_raises_value_error(self) -> None:
        """Test batch_size=0 raises ValueError.

        Validates lower bound enforcement.
        """
        with pytest.raises(ValueError, match="batch_size must be >= 1"):
            SinkConfig(sink_type="rest_api", batch_size=0)

    @pytest.mark.requirement("4G-SEC-003")
    def test_batch_size_negative_raises_value_error(self) -> None:
        """Test batch_size=-1 raises ValueError.

        Validates negative values are rejected.
        """
        with pytest.raises(ValueError, match="batch_size must be >= 1"):
            SinkConfig(sink_type="rest_api", batch_size=-1)

    @pytest.mark.requirement("4G-SEC-003")
    def test_batch_size_exceeds_max_raises_value_error(self) -> None:
        """Test batch_size=100_001 raises ValueError.

        Validates upper bound enforcement.
        """
        with pytest.raises(ValueError, match="batch_size must be <= 100_000"):
            SinkConfig(sink_type="rest_api", batch_size=100_001)

    @pytest.mark.requirement("4G-SEC-003")
    def test_batch_size_at_max_boundary_succeeds(self) -> None:
        """Test batch_size=100_000 is accepted.

        Validates upper boundary is inclusive.
        """
        config = SinkConfig(sink_type="rest_api", batch_size=100_000)
        assert config.batch_size == 100_000

    @pytest.mark.requirement("4G-SEC-003")
    def test_batch_size_at_min_boundary_succeeds(self) -> None:
        """Test batch_size=1 is accepted.

        Validates lower boundary is inclusive.
        """
        config = SinkConfig(sink_type="rest_api", batch_size=1)
        assert config.batch_size == 1

    @pytest.mark.requirement("4G-SEC-002")
    def test_connection_config_exceeds_max_keys_raises_value_error(self) -> None:
        """Test connection_config with 51 keys raises ValueError.

        Validates dictionary size limits for DoS prevention.
        """
        big_config = {f"key_{i}": f"value_{i}" for i in range(51)}
        with pytest.raises(ValueError, match="connection_config has 51 keys"):
            SinkConfig(sink_type="rest_api", connection_config=big_config)

    @pytest.mark.requirement("4G-SEC-002")
    def test_connection_config_at_max_keys_succeeds(self) -> None:
        """Test connection_config with 50 keys succeeds.

        Validates boundary is inclusive.
        """
        config_50 = {f"key_{i}": f"value_{i}" for i in range(50)}
        config = SinkConfig(sink_type="rest_api", connection_config=config_50)
        assert len(config.connection_config) == 50

    @pytest.mark.requirement("4G-SEC-011")
    def test_field_mapping_valid_identifiers_succeeds(self) -> None:
        """Test field_mapping with valid identifier values succeeds.

        Validates clean identifier mapping passes validation.
        """
        config = SinkConfig(
            sink_type="rest_api",
            field_mapping={"customer_id": "Id", "email": "Email_Address"},
        )
        assert config.field_mapping == {"customer_id": "Id", "email": "Email_Address"}

    @pytest.mark.requirement("4G-SEC-011")
    def test_field_mapping_sql_injection_raises_value_error(self) -> None:
        """Test field_mapping with SQL injection payload raises ValueError.

        Validates injection prevention via identifier validation.
        """
        with pytest.raises(ValueError, match="must be a valid identifier"):
            SinkConfig(
                sink_type="rest_api",
                field_mapping={"email": "Email; DROP TABLE users;--"},
            )

    @pytest.mark.requirement("4G-SEC-011")
    def test_field_mapping_special_chars_raises_value_error(self) -> None:
        """Test field_mapping with special characters raises ValueError.

        Validates non-alphanumeric characters in destinations are rejected.
        """
        with pytest.raises(ValueError, match="must be a valid identifier"):
            SinkConfig(
                sink_type="rest_api",
                field_mapping={"name": "user.name"},
            )
