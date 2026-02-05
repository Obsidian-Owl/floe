"""Unit tests for IcebergIOManager.

Tests the IcebergIOManager class with mocked IcebergTableManager.
These tests validate the IOManager's handling of output/input contexts
and correct delegation to the table manager.

Requirements tested:
    FR-037: Handle asset outputs by writing to Iceberg tables
    FR-038: Support configurable write modes
    FR-039: Load asset inputs from Iceberg tables
    FR-040: Support partitioned assets
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_table_manager() -> MagicMock:
    """Create mock IcebergTableManager with required interface."""
    manager = MagicMock()
    manager.load_table = MagicMock()
    manager.table_exists = MagicMock(return_value=True)
    manager.write_data = MagicMock()
    manager.create_table = MagicMock()

    # Mock table for load_table return
    mock_table = MagicMock()
    mock_table.scan = MagicMock(return_value=MagicMock())
    mock_table.scan.return_value.filter = MagicMock(return_value=mock_table.scan.return_value)
    mock_table.scan.return_value.to_arrow = MagicMock(return_value=MagicMock())
    manager.load_table.return_value = mock_table

    return manager


@pytest.fixture
def io_manager_config() -> Any:
    """Create IcebergIOManagerConfig for tests."""
    from floe_orchestrator_dagster.io_manager import IcebergIOManagerConfig

    return IcebergIOManagerConfig(
        namespace="test_namespace",
        default_write_mode="append",
        infer_schema_from_data=True,
    )


@pytest.fixture
def io_manager(
    mock_table_manager: MagicMock,
    io_manager_config: Any,
) -> Any:
    """Create IcebergIOManager with mocked dependencies."""
    from floe_orchestrator_dagster.io_manager import IcebergIOManager

    return IcebergIOManager(
        table_manager=mock_table_manager,
        config=io_manager_config,
    )


@pytest.fixture
def mock_output_context() -> MagicMock:
    """Create mock Dagster OutputContext."""
    context = MagicMock()
    context.asset_key = MagicMock()
    context.asset_key.path = ["customers_silver"]
    context.definition_metadata = {}
    context.output_metadata = {}
    context.partition_key = None
    return context


@pytest.fixture
def mock_input_context() -> MagicMock:
    """Create mock Dagster InputContext."""
    context = MagicMock()
    context.upstream_output = MagicMock()
    context.upstream_output.asset_key = MagicMock()
    context.upstream_output.asset_key.path = ["customers_bronze"]
    context.upstream_output.definition_metadata = {}
    context.partition_key = None
    return context


@pytest.fixture
def mock_pyarrow_table() -> MagicMock:
    """Create mock PyArrow table."""
    table = MagicMock()
    table.__len__ = MagicMock(return_value=100)

    # Mock schema for schema inference
    mock_field = MagicMock()
    mock_field.name = "id"
    mock_field.type = "int64"
    mock_field.nullable = False

    table.schema = [mock_field]

    return table


# =============================================================================
# Configuration Tests
# =============================================================================


class TestIcebergIOManagerConfig:
    """Tests for IcebergIOManagerConfig."""

    @pytest.mark.requirement("FLO-813")
    def test_config_creation_valid(self) -> None:
        """Test config creation with valid values."""
        from floe_orchestrator_dagster.io_manager import IcebergIOManagerConfig

        config = IcebergIOManagerConfig(
            namespace="silver",
            default_write_mode="append",
            infer_schema_from_data=True,
        )

        assert config.namespace == "silver"
        assert config.default_write_mode == "append"
        assert config.infer_schema_from_data is True

    @pytest.mark.requirement("FLO-813")
    def test_config_default_write_mode_values(self) -> None:
        """Test config accepts valid write mode values."""
        from floe_orchestrator_dagster.io_manager import IcebergIOManagerConfig

        for mode in ["append", "overwrite", "upsert"]:
            config = IcebergIOManagerConfig(namespace="test", default_write_mode=mode)
            assert config.default_write_mode == mode

    @pytest.mark.requirement("FLO-813")
    def test_config_invalid_write_mode(self) -> None:
        """Test config rejects invalid write mode."""
        from pydantic import ValidationError

        from floe_orchestrator_dagster.io_manager import IcebergIOManagerConfig

        with pytest.raises(ValidationError, match="default_write_mode"):
            IcebergIOManagerConfig(namespace="test", default_write_mode="invalid")

    @pytest.mark.requirement("FLO-813")
    def test_config_empty_namespace_rejected(self) -> None:
        """Test config rejects empty namespace."""
        from pydantic import ValidationError

        from floe_orchestrator_dagster.io_manager import IcebergIOManagerConfig

        with pytest.raises(ValidationError, match="namespace"):
            IcebergIOManagerConfig(namespace="", default_write_mode="append")


# =============================================================================
# IOManager Initialization Tests
# =============================================================================


class TestIcebergIOManagerInit:
    """Tests for IcebergIOManager initialization."""

    @pytest.mark.requirement("FLO-813")
    def test_initialization_success(
        self,
        mock_table_manager: MagicMock,
        io_manager_config: Any,
    ) -> None:
        """Test IOManager initializes successfully with valid dependencies."""
        from floe_orchestrator_dagster.io_manager import IcebergIOManager

        manager = IcebergIOManager(
            table_manager=mock_table_manager,
            config=io_manager_config,
        )

        assert manager.table_manager is mock_table_manager
        assert manager.config is io_manager_config

    @pytest.mark.requirement("FLO-813")
    def test_initialization_invalid_table_manager(
        self,
        io_manager_config: Any,
    ) -> None:
        """Test IOManager rejects table manager without required methods."""
        from floe_orchestrator_dagster.io_manager import IcebergIOManager

        invalid_manager = Mock(spec=[])  # No methods

        # Security: Error message is generic to avoid exposing internal details
        with pytest.raises(TypeError, match="missing required interface methods"):
            IcebergIOManager(
                table_manager=invalid_manager,
                config=io_manager_config,
            )

    @pytest.mark.requirement("FLO-813")
    def test_initialization_partial_table_manager(
        self,
        io_manager_config: Any,
    ) -> None:
        """Test IOManager rejects table manager missing some methods."""
        from floe_orchestrator_dagster.io_manager import IcebergIOManager

        partial_manager = Mock(spec=["load_table", "table_exists"])  # Missing write_data

        # Security: Error message is generic to avoid exposing internal details
        with pytest.raises(TypeError, match="missing required interface methods"):
            IcebergIOManager(
                table_manager=partial_manager,
                config=io_manager_config,
            )


# =============================================================================
# Handle Output Tests
# =============================================================================


class TestHandleOutput:
    """Tests for IcebergIOManager.handle_output method."""

    @pytest.mark.requirement("FR-037")
    def test_handle_output_writes_to_existing_table(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test handle_output writes data to existing table."""
        mock_table_manager.table_exists.return_value = True

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Should load table and write data
        mock_table_manager.load_table.assert_called_once()
        mock_table_manager.write_data.assert_called_once()

    @pytest.mark.requirement("FR-037")
    def test_handle_output_creates_table_when_not_exists(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test handle_output creates table when it doesn't exist."""
        # First call returns False (table doesn't exist), subsequent calls return True
        mock_table_manager.table_exists.side_effect = [False, True]

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Should create table then write
        mock_table_manager.create_table.assert_called_once()
        mock_table_manager.write_data.assert_called_once()

    @pytest.mark.requirement("FR-037")
    def test_handle_output_uses_custom_table_name(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test handle_output uses custom table name from metadata."""
        from floe_orchestrator_dagster.io_manager import ICEBERG_TABLE_KEY

        mock_output_context.definition_metadata = {ICEBERG_TABLE_KEY: "custom_table"}
        mock_table_manager.table_exists.return_value = True

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Should use custom table name with configured namespace
        call_args = mock_table_manager.load_table.call_args
        assert call_args[0][0] == "test_namespace.custom_table"

    @pytest.mark.requirement("FR-037")
    def test_handle_output_uses_custom_namespace(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test handle_output uses custom namespace from metadata."""
        from floe_orchestrator_dagster.io_manager import ICEBERG_NAMESPACE_KEY

        mock_output_context.definition_metadata = {ICEBERG_NAMESPACE_KEY: "custom_namespace"}
        mock_table_manager.table_exists.return_value = True

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Should use custom namespace with default table name from asset key
        call_args = mock_table_manager.load_table.call_args
        assert call_args[0][0] == "custom_namespace.customers_silver"

    @pytest.mark.requirement("FR-038")
    def test_handle_output_uses_write_mode_from_metadata(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test handle_output uses write mode from metadata."""
        from floe_orchestrator_dagster.io_manager import ICEBERG_WRITE_MODE_KEY

        mock_output_context.definition_metadata = {ICEBERG_WRITE_MODE_KEY: "overwrite"}
        mock_table_manager.table_exists.return_value = True

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Check write_data was called with overwrite mode
        write_call = mock_table_manager.write_data.call_args
        write_config = write_call[0][2]  # Third positional arg
        assert write_config.mode.value == "overwrite"


# =============================================================================
# Load Input Tests
# =============================================================================


class TestLoadInput:
    """Tests for IcebergIOManager.load_input method."""

    @pytest.mark.requirement("FR-039")
    def test_load_input_reads_from_table(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_input_context: MagicMock,
    ) -> None:
        """Test load_input reads data from Iceberg table."""
        result = io_manager.load_input(mock_input_context)

        # Should load table and scan
        mock_table_manager.load_table.assert_called_once()
        assert result is not None

    @pytest.mark.requirement("FR-039")
    def test_load_input_uses_upstream_asset_key(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_input_context: MagicMock,
    ) -> None:
        """Test load_input derives table name from upstream asset key."""
        io_manager.load_input(mock_input_context)

        # Should use upstream asset key for table name with configured namespace
        call_args = mock_table_manager.load_table.call_args
        assert call_args[0][0] == "test_namespace.customers_bronze"

    @pytest.mark.requirement("FR-039")
    def test_load_input_uses_custom_table_name(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_input_context: MagicMock,
    ) -> None:
        """Test load_input uses custom table name from upstream metadata."""
        from floe_orchestrator_dagster.io_manager import ICEBERG_TABLE_KEY

        mock_input_context.upstream_output.definition_metadata = {ICEBERG_TABLE_KEY: "custom_upstream"}

        io_manager.load_input(mock_input_context)

        # Should use custom table name with configured namespace
        call_args = mock_table_manager.load_table.call_args
        assert call_args[0][0] == "test_namespace.custom_upstream"


# =============================================================================
# Partitioned Asset Tests
# =============================================================================


class TestPartitionedAssets:
    """Tests for partitioned asset handling."""

    @pytest.mark.requirement("FR-040")
    def test_handle_output_partitioned_asset(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test handle_output with partitioned asset sets correct filter.

        The filter is built using PyIceberg's expression API for type safety,
        then converted to string for WriteConfig compatibility.
        """
        from floe_orchestrator_dagster.io_manager import (
            ICEBERG_PARTITION_COLUMN_KEY,
            ICEBERG_WRITE_MODE_KEY,
        )

        mock_output_context.partition_key = "2026-01-17"
        mock_output_context.definition_metadata = {
            ICEBERG_WRITE_MODE_KEY: "overwrite",
            ICEBERG_PARTITION_COLUMN_KEY: "date",
        }
        mock_table_manager.table_exists.return_value = True

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Check write_data was called with partition filter
        write_call = mock_table_manager.write_data.call_args
        write_config = write_call[0][2]

        # Filter is a string built from PyIceberg expression
        assert isinstance(write_config.overwrite_filter, str)
        assert "date" in write_config.overwrite_filter
        assert "2026-01-17" in write_config.overwrite_filter

    @pytest.mark.requirement("FR-040")
    def test_load_input_partitioned_asset(
        self,
        io_manager: Any,
        mock_table_manager: MagicMock,
        mock_input_context: MagicMock,
    ) -> None:
        """Test load_input with partitioned asset applies filter."""
        from pyiceberg.expressions import EqualTo

        from floe_orchestrator_dagster.io_manager import ICEBERG_PARTITION_COLUMN_KEY

        mock_input_context.partition_key = "2026-01-17"
        mock_input_context.upstream_output.definition_metadata = {ICEBERG_PARTITION_COLUMN_KEY: "date"}

        io_manager.load_input(mock_input_context)

        # Should apply filter on scan with PyIceberg expression
        mock_table = mock_table_manager.load_table.return_value
        mock_table.scan.return_value.filter.assert_called_once()

        # Verify the filter is a PyIceberg EqualTo expression
        filter_arg = mock_table.scan.return_value.filter.call_args[0][0]
        assert isinstance(filter_arg, EqualTo)
        expr_str = str(filter_arg)
        assert "date" in expr_str
        assert "2026-01-17" in expr_str


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_iceberg_io_manager factory function."""

    @pytest.mark.requirement("FLO-813")
    def test_create_iceberg_io_manager(
        self,
        mock_table_manager: MagicMock,
    ) -> None:
        """Test factory function creates IOManager correctly."""
        from floe_orchestrator_dagster.io_manager import create_iceberg_io_manager

        manager = create_iceberg_io_manager(
            table_manager=mock_table_manager,
            namespace="silver",
            default_write_mode="append",
            infer_schema_from_data=True,
        )

        assert manager.config.namespace == "silver"
        assert manager.config.default_write_mode == "append"
        assert manager.config.infer_schema_from_data is True

    @pytest.mark.requirement("FLO-813")
    def test_create_iceberg_io_manager_defaults(
        self,
        mock_table_manager: MagicMock,
    ) -> None:
        """Test factory function uses sensible defaults."""
        from floe_orchestrator_dagster.io_manager import create_iceberg_io_manager

        manager = create_iceberg_io_manager(
            table_manager=mock_table_manager,
            namespace="gold",
        )

        assert manager.config.namespace == "gold"
        assert manager.config.default_write_mode == "append"
        assert manager.config.infer_schema_from_data is True


# =============================================================================
# Table Identifier Tests
# =============================================================================


class TestTableIdentifier:
    """Tests for table identifier generation."""

    @pytest.mark.requirement("FLO-813")
    def test_identifier_from_asset_key(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
    ) -> None:
        """Test identifier is generated from asset key."""
        mock_output_context.asset_key.path = ["my_asset"]

        identifier = io_manager._get_table_identifier(mock_output_context)

        assert identifier == "test_namespace.my_asset"

    @pytest.mark.requirement("FLO-813")
    def test_identifier_with_hierarchical_asset_key(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
    ) -> None:
        """Test identifier uses last part of hierarchical asset key."""
        mock_output_context.asset_key.path = ["group", "subgroup", "my_asset"]

        identifier = io_manager._get_table_identifier(mock_output_context)

        assert identifier == "test_namespace.my_asset"

    @pytest.mark.requirement("FLO-813")
    def test_identifier_no_asset_key_raises(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
    ) -> None:
        """Test error when no asset key or metadata."""
        del mock_output_context.asset_key

        with pytest.raises(ValueError, match="Cannot determine table name"):
            io_manager._get_table_identifier(mock_output_context)
