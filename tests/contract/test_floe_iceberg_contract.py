"""Contract tests for floe-iceberg package.

These tests validate that floe-iceberg correctly consumes interfaces from
floe-core (CatalogPlugin, StoragePlugin) and that the public API is stable.

Contract tests ensure:
1. IcebergTableManager accepts CatalogPlugin and StoragePlugin interfaces
2. Public exports from floe_iceberg are stable
3. Model schemas are backwards compatible
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# Interface Protocol Tests
# =============================================================================


@runtime_checkable
class CatalogPluginProtocol(Protocol):
    """Minimal protocol that CatalogPlugin must satisfy.

    This protocol defines the methods IcebergTableManager requires from
    CatalogPlugin. Any implementation satisfying this protocol can be
    used with IcebergTableManager.
    """

    @property
    def name(self) -> str:
        """Plugin name."""
        ...

    def connect(self, config: dict[str, Any]) -> Any:
        """Connect to the catalog."""
        ...


@runtime_checkable
class StoragePluginProtocol(Protocol):
    """Minimal protocol that StoragePlugin must satisfy.

    This protocol defines the methods IcebergTableManager requires from
    StoragePlugin. Any implementation satisfying this protocol can be
    used with IcebergTableManager.
    """

    @property
    def name(self) -> str:
        """Plugin name."""
        ...

    def get_pyiceberg_fileio(self) -> Any:
        """Get PyIceberg FileIO instance."""
        ...


class TestCatalogPluginContract:
    """Tests that CatalogPlugin from floe-core satisfies IcebergTableManager requirements."""

    @pytest.mark.requirement("FR-004")
    def test_catalog_plugin_has_required_methods(self) -> None:
        """Test CatalogPlugin ABC has methods required by IcebergTableManager."""
        from floe_core.plugins.catalog import CatalogPlugin

        # Verify required abstract methods exist
        assert hasattr(CatalogPlugin, "connect")
        assert hasattr(CatalogPlugin, "name")

        # Verify connect is abstract
        assert getattr(CatalogPlugin.connect, "__isabstractmethod__", False)

    @pytest.mark.requirement("FR-004")
    def test_catalog_protocol_defines_connect(self) -> None:
        """Test Catalog protocol from floe-core has load_table method."""
        from floe_core.plugins.catalog import Catalog

        # Catalog protocol must have load_table for IcebergTableManager
        assert hasattr(Catalog, "load_table")
        assert hasattr(Catalog, "list_tables")
        assert hasattr(Catalog, "list_namespaces")


class TestStoragePluginContract:
    """Tests that StoragePlugin from floe-core satisfies IcebergTableManager requirements."""

    @pytest.mark.requirement("FR-004")
    def test_storage_plugin_has_required_methods(self) -> None:
        """Test StoragePlugin ABC has methods required by IcebergTableManager."""
        from floe_core.plugins.storage import StoragePlugin

        # Verify required abstract methods exist
        assert hasattr(StoragePlugin, "get_pyiceberg_fileio")
        assert hasattr(StoragePlugin, "name")

        # Verify get_pyiceberg_fileio is abstract
        assert getattr(StoragePlugin.get_pyiceberg_fileio, "__isabstractmethod__", False)

    @pytest.mark.requirement("FR-004")
    def test_fileio_protocol_defines_required_methods(self) -> None:
        """Test FileIO protocol from floe-core has required methods."""
        from floe_core.plugins.storage import FileIO

        # FileIO protocol must have these for Iceberg operations
        assert hasattr(FileIO, "new_input")
        assert hasattr(FileIO, "new_output")
        assert hasattr(FileIO, "delete")


# =============================================================================
# Public API Stability Tests
# =============================================================================


class TestFloeIcebergPublicApi:
    """Tests that floe-iceberg public API exports are stable."""

    @pytest.mark.requirement("FR-001")
    def test_package_exports_iceberg_table_manager(self) -> None:
        """Test IcebergTableManager is exported from package."""
        from floe_iceberg import __all__

        assert "IcebergTableManager" in __all__

    @pytest.mark.requirement("FR-001")
    def test_package_exports_config(self) -> None:
        """Test IcebergTableManagerConfig is exported from package."""
        from floe_iceberg import __all__

        assert "IcebergTableManagerConfig" in __all__

    @pytest.mark.requirement("FR-037")
    def test_package_exports_io_manager(self) -> None:
        """Test IcebergIOManager is exported from package."""
        from floe_iceberg import __all__

        assert "IcebergIOManager" in __all__
        assert "IcebergIOManagerConfig" in __all__

    @pytest.mark.requirement("FR-001")
    def test_models_module_exports(self) -> None:
        """Test models module exports expected types."""
        from floe_iceberg.models import __all__ as models_all

        # Enumerations
        assert "FieldType" in models_all
        assert "PartitionTransform" in models_all
        assert "WriteMode" in models_all
        assert "CommitStrategy" in models_all
        assert "SchemaChangeType" in models_all
        assert "OperationType" in models_all
        assert "CompactionStrategyType" in models_all

        # Configuration models
        assert "IcebergTableManagerConfig" in models_all
        assert "IcebergIOManagerConfig" in models_all

        # Constants
        assert "IDENTIFIER_PATTERN" in models_all

    @pytest.mark.requirement("FR-001")
    def test_errors_module_exports(self) -> None:
        """Test errors module exports expected exception types."""
        from floe_iceberg.errors import __all__ as errors_all

        # Base exception
        assert "IcebergError" in errors_all

        # Table errors
        assert "TableAlreadyExistsError" in errors_all
        assert "NoSuchTableError" in errors_all
        assert "NoSuchNamespaceError" in errors_all

        # Schema errors
        assert "SchemaEvolutionError" in errors_all
        assert "IncompatibleSchemaChangeError" in errors_all

        # Write errors
        assert "WriteError" in errors_all
        assert "CommitConflictError" in errors_all

        # Snapshot errors
        assert "SnapshotNotFoundError" in errors_all
        assert "RollbackError" in errors_all
        assert "CompactionError" in errors_all


# =============================================================================
# Model Schema Stability Tests
# =============================================================================


class TestModelSchemaStability:
    """Tests that model schemas are stable for backwards compatibility."""

    @pytest.mark.requirement("FR-045")
    def test_iceberg_table_manager_config_has_required_fields(self) -> None:
        """Test IcebergTableManagerConfig has all required fields."""
        from floe_iceberg.models import IcebergTableManagerConfig

        # Get model fields
        field_names = set(IcebergTableManagerConfig.model_fields.keys())

        # Required fields from data-model.md
        expected_fields = {
            "max_commit_retries",
            "retry_base_delay_seconds",
            "default_retention_days",
            "min_snapshots_to_keep",
            "default_commit_strategy",
            "default_table_properties",
        }

        assert expected_fields <= field_names, f"Missing fields: {expected_fields - field_names}"

    @pytest.mark.requirement("FR-045")
    def test_iceberg_table_manager_config_field_types(self) -> None:
        """Test IcebergTableManagerConfig field types are correct."""
        from floe_iceberg.models import CommitStrategy, IcebergTableManagerConfig

        # Create default config
        config = IcebergTableManagerConfig()

        # Verify field types
        assert isinstance(config.max_commit_retries, int)
        assert isinstance(config.retry_base_delay_seconds, float)
        assert isinstance(config.default_retention_days, int)
        assert isinstance(config.min_snapshots_to_keep, int)
        assert isinstance(config.default_commit_strategy, CommitStrategy)
        assert isinstance(config.default_table_properties, dict)

    @pytest.mark.requirement("FR-037")
    def test_iceberg_io_manager_config_has_required_fields(self) -> None:
        """Test IcebergIOManagerConfig has all required fields."""
        from floe_iceberg.models import IcebergIOManagerConfig

        # Get model fields
        field_names = set(IcebergIOManagerConfig.model_fields.keys())

        # Required fields from data-model.md
        expected_fields = {
            "default_write_mode",
            "default_commit_strategy",
            "namespace",
            "table_name_pattern",
            "infer_schema_from_data",
        }

        assert expected_fields <= field_names, f"Missing fields: {expected_fields - field_names}"


# =============================================================================
# Cross-Package Integration Tests
# =============================================================================


class TestCrossPackageIntegration:
    """Tests that floe-iceberg integrates correctly with floe-core."""

    @pytest.mark.requirement("FR-004")
    def test_mock_catalog_plugin_satisfies_protocol(self) -> None:
        """Test that a mock CatalogPlugin satisfies the expected protocol."""

        class MockCatalogPlugin:
            """Mock implementation for testing."""

            @property
            def name(self) -> str:
                return "mock"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def connect(self, config: dict[str, Any]) -> Any:
                return None

        mock = MockCatalogPlugin()
        assert isinstance(mock, CatalogPluginProtocol)

    @pytest.mark.requirement("FR-004")
    def test_mock_storage_plugin_satisfies_protocol(self) -> None:
        """Test that a mock StoragePlugin satisfies the expected protocol."""

        class MockStoragePlugin:
            """Mock implementation for testing."""

            @property
            def name(self) -> str:
                return "mock"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_pyiceberg_fileio(self) -> Any:
                return None

        mock = MockStoragePlugin()
        assert isinstance(mock, StoragePluginProtocol)

    @pytest.mark.requirement("FR-001")
    def test_identifier_pattern_is_valid_regex(self) -> None:
        """Test IDENTIFIER_PATTERN is a valid regex that works correctly."""
        import re

        from floe_iceberg.models import IDENTIFIER_PATTERN

        pattern = re.compile(IDENTIFIER_PATTERN)

        # Valid identifiers
        assert pattern.match("customers")
        assert pattern.match("dim_product")
        assert pattern.match("bronze")

        # Invalid identifiers
        assert not pattern.match("123_table")
        assert not pattern.match("_private")
        assert not pattern.match("")
