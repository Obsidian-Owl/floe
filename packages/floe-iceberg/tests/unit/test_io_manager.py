"""Unit tests for floe_iceberg.io_manager module.

Tests IcebergIOManager for Dagster asset integration.

Note:
    No __init__.py files in test directories - pytest uses importlib mode
    which causes namespace collisions with __init__.py files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_iceberg_manager() -> MagicMock:
    """Create a mock IcebergTableManager for testing.

    Returns:
        MagicMock configured as IcebergTableManager.
    """
    manager = MagicMock()
    manager.table_exists.return_value = True
    manager.load_table.return_value = MagicMock()
    manager.write_data.return_value = MagicMock()
    return manager


@pytest.fixture
def io_manager_config() -> Any:
    """Create IcebergIOManagerConfig for testing.

    Returns:
        IcebergIOManagerConfig instance.
    """
    from floe_iceberg.models import IcebergIOManagerConfig

    return IcebergIOManagerConfig(namespace="bronze")


@pytest.fixture
def io_manager(
    io_manager_config: Any, mock_iceberg_manager: MagicMock
) -> Generator[Any, None, None]:
    """Create IcebergIOManager for testing.

    Args:
        io_manager_config: Configuration for the IOManager.
        mock_iceberg_manager: Mock IcebergTableManager.

    Yields:
        IcebergIOManager instance.
    """
    from floe_iceberg.io_manager import IcebergIOManager

    yield IcebergIOManager(
        config=io_manager_config,
        iceberg_manager=mock_iceberg_manager,
    )


@pytest.fixture
def mock_output_context() -> MagicMock:
    """Create a mock Dagster OutputContext.

    Returns:
        MagicMock configured as OutputContext (non-partitioned).
    """
    context = MagicMock()
    context.asset_key = MagicMock()
    context.asset_key.path = ["customers"]
    context.metadata = {}
    # Explicitly set partition_key to None for non-partitioned assets
    context.partition_key = None
    return context


@pytest.fixture
def mock_pyarrow_table() -> MagicMock:
    """Create a mock PyArrow Table.

    Returns:
        MagicMock configured as PyArrow Table.
    """
    table = MagicMock()
    table.schema = MagicMock()
    table.num_rows = 100
    return table


# =============================================================================
# IcebergIOManager handle_output Tests
# =============================================================================


class TestIcebergIOManagerHandleOutput:
    """Tests for IcebergIOManager.handle_output() method."""

    @pytest.mark.requirement("FR-037")
    def test_handle_output_pyarrow_table(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test handle_output writes PyArrow Table to Iceberg.

        Acceptance criteria from T079:
        - Test PyArrow Table output
        """
        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Verify table was loaded
        mock_iceberg_manager.load_table.assert_called_once()

        # Verify data was written
        mock_iceberg_manager.write_data.assert_called_once()
        call_args = mock_iceberg_manager.write_data.call_args
        assert call_args[0][1] == mock_pyarrow_table  # Second arg is data

    @pytest.mark.requirement("FR-037")
    def test_handle_output_creates_table_on_first_write(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test handle_output creates table if it doesn't exist.

        Acceptance criteria from T079:
        - Test table creation on first write
        """
        import pyarrow as pa

        # Create real PyArrow table (needed for schema inference)
        pa_table = pa.table({"id": [1], "name": ["a"]})

        # Table doesn't exist initially
        mock_iceberg_manager.table_exists.return_value = False

        io_manager.handle_output(mock_output_context, pa_table)

        # Verify table existence was checked
        mock_iceberg_manager.table_exists.assert_called_once()

        # Verify create_table was called for schema inference
        mock_iceberg_manager.create_table.assert_called_once()

    @pytest.mark.requirement("FR-039")
    def test_handle_output_infers_schema_on_first_write(
        self,
        mock_iceberg_manager: MagicMock,
        mock_output_context: MagicMock,
    ) -> None:
        """Test handle_output infers schema from PyArrow Table on first write.

        Acceptance criteria from T087:
        - Detect if table exists
        - If not, infer schema from PyArrow Table
        - Create table with inferred schema
        - Then write data
        """
        import pyarrow as pa

        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        # Create real PyArrow table with schema
        pa_table = pa.table({
            "id": [1, 2, 3],
            "name": ["a", "b", "c"],
            "value": [1.1, 2.2, 3.3],
        })

        # Table doesn't exist initially
        mock_iceberg_manager.table_exists.return_value = False

        config = IcebergIOManagerConfig(namespace="bronze", infer_schema_from_data=True)
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.handle_output(mock_output_context, pa_table)

        # Verify create_table was called
        mock_iceberg_manager.create_table.assert_called_once()

        # Verify the TableConfig has correct namespace and table name
        call_args = mock_iceberg_manager.create_table.call_args
        table_config = call_args[0][0]
        assert table_config.namespace == "bronze"
        assert table_config.table_name == "customers"

        # Verify schema was inferred with 3 fields
        assert len(table_config.table_schema.fields) == 3

        # Verify write_data was called after table creation
        mock_iceberg_manager.write_data.assert_called_once()

    @pytest.mark.requirement("FR-038")
    def test_handle_output_appends_to_existing_table(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test handle_output appends data to existing table.

        Acceptance criteria from T079:
        - Test append to existing table
        """
        # Table exists
        mock_iceberg_manager.table_exists.return_value = True

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Verify write_data was called with APPEND mode (default)
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]  # Third arg is write_config
        from floe_iceberg.models import WriteMode

        assert write_config.mode == WriteMode.APPEND

    @pytest.mark.requirement("FR-038")
    def test_handle_output_metadata_write_mode_override(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test handle_output uses metadata to override write mode.

        Acceptance criteria from T079:
        - Test metadata-based write mode override
        """
        # Set metadata to override write mode
        mock_output_context.metadata = {"write_mode": "overwrite"}

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Verify write_data was called with OVERWRITE mode
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]  # Third arg is write_config
        from floe_iceberg.models import WriteMode

        assert write_config.mode == WriteMode.OVERWRITE

    @pytest.mark.requirement("FR-038")
    def test_handle_output_iceberg_write_mode_metadata(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test handle_output reads iceberg_write_mode from metadata.

        Acceptance criteria from T086:
        - Read write mode from asset metadata (iceberg_write_mode)
        """
        # Use iceberg_write_mode metadata key
        mock_output_context.metadata = {"iceberg_write_mode": "overwrite"}

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Verify write_data was called with OVERWRITE mode
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]
        from floe_iceberg.models import WriteMode

        assert write_config.mode == WriteMode.OVERWRITE

    @pytest.mark.requirement("FR-039")
    def test_handle_output_iceberg_partition_column_metadata(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test handle_output reads iceberg_partition_column from metadata.

        Acceptance criteria from T086:
        - Read partition column from metadata (iceberg_partition_column)
        """
        # Use iceberg_partition_column metadata key
        mock_output_context.metadata = {
            "iceberg_write_mode": "overwrite",
            "iceberg_partition_column": "date",
        }

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Verify write_data was called with overwrite_filter
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]

        assert write_config.overwrite_filter == "date"

    @pytest.mark.requirement("FR-037")
    def test_handle_output_generates_table_identifier(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test handle_output generates correct table identifier from asset key."""
        mock_output_context.asset_key.path = ["dim", "customers"]

        io_manager.handle_output(mock_output_context, mock_pyarrow_table)

        # Verify load_table was called with correct identifier
        # With default pattern {asset_key} and namespace bronze:
        # bronze.dim_customers
        call_args = mock_iceberg_manager.load_table.call_args
        table_identifier = call_args[0][0]
        assert table_identifier == "bronze.dim_customers"

    @pytest.mark.requirement("FR-037")
    def test_handle_output_uses_config_namespace(
        self,
        mock_iceberg_manager: MagicMock,
        mock_output_context: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test handle_output uses namespace from config."""
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        config = IcebergIOManagerConfig(namespace="silver")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.handle_output(mock_output_context, mock_pyarrow_table)

        # Verify correct namespace used
        call_args = mock_iceberg_manager.load_table.call_args
        table_identifier = call_args[0][0]
        assert table_identifier.startswith("silver.")


# =============================================================================
# IcebergIOManager Table Identifier Tests
# =============================================================================


class TestIcebergIOManagerTableIdentifier:
    """Tests for table identifier generation from asset keys."""

    @pytest.mark.requirement("FR-037")
    def test_get_table_identifier_simple_asset_key(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
    ) -> None:
        """Test table identifier for simple single-part asset key."""
        mock_output_context.asset_key.path = ["orders"]

        identifier = io_manager._get_table_identifier(mock_output_context)

        assert identifier == "bronze.orders"

    @pytest.mark.requirement("FR-037")
    def test_get_table_identifier_multi_part_asset_key(
        self,
        io_manager: Any,
        mock_output_context: MagicMock,
    ) -> None:
        """Test table identifier for multi-part asset key."""
        mock_output_context.asset_key.path = ["dim", "customers"]

        identifier = io_manager._get_table_identifier(mock_output_context)

        assert identifier == "bronze.dim_customers"

    @pytest.mark.requirement("FR-037")
    def test_get_table_identifier_custom_pattern(
        self,
        mock_iceberg_manager: MagicMock,
        mock_output_context: MagicMock,
    ) -> None:
        """Test table identifier with custom table name pattern."""
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        config = IcebergIOManagerConfig(
            namespace="bronze",
            table_name_pattern="raw_{asset_key}",
        )
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)
        mock_output_context.asset_key.path = ["orders"]

        identifier = io_mgr._get_table_identifier(mock_output_context)

        assert identifier == "bronze.raw_orders"


# =============================================================================
# IcebergIOManager load_input Tests
# =============================================================================


@pytest.fixture
def mock_input_context() -> MagicMock:
    """Create a mock Dagster InputContext.

    Returns:
        MagicMock configured as InputContext.
    """
    context = MagicMock()
    context.upstream_output = MagicMock()
    context.upstream_output.asset_key = MagicMock()
    context.upstream_output.asset_key.path = ["customers"]
    return context


class TestIcebergIOManagerLoadInput:
    """Tests for IcebergIOManager.load_input() method."""

    @pytest.mark.requirement("FR-039")
    def test_load_input_existing_table(
        self,
        io_manager: Any,
        mock_input_context: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test load_input loads existing table as PyArrow Table.

        Acceptance criteria from T080:
        - Test loading existing table as PyArrow Table
        """
        mock_table = MagicMock()
        mock_iceberg_manager.load_table.return_value = mock_table

        io_manager.load_input(mock_input_context)

        # Verify table was loaded
        mock_iceberg_manager.load_table.assert_called_once()
        call_args = mock_iceberg_manager.load_table.call_args
        table_identifier = call_args[0][0]
        assert table_identifier == "bronze.customers"

    @pytest.mark.requirement("FR-039")
    def test_load_input_no_such_table_error(
        self,
        io_manager: Any,
        mock_input_context: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test load_input raises NoSuchTableError for non-existent table.

        Acceptance criteria from T080:
        - Test NoSuchTableError handling
        """
        from floe_iceberg.errors import NoSuchTableError

        mock_iceberg_manager.load_table.side_effect = NoSuchTableError(
            "Table not found", table_identifier="bronze.missing"
        )

        with pytest.raises(NoSuchTableError, match="Table not found"):
            io_manager.load_input(mock_input_context)

    @pytest.mark.requirement("FR-039")
    def test_load_input_upstream_asset_key(
        self,
        io_manager: Any,
        mock_input_context: MagicMock,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test load_input uses upstream asset key for table identifier."""
        mock_input_context.upstream_output.asset_key.path = ["dim", "products"]

        io_manager.load_input(mock_input_context)

        # Verify load_table was called with correct identifier
        call_args = mock_iceberg_manager.load_table.call_args
        table_identifier = call_args[0][0]
        assert table_identifier == "bronze.dim_products"

    @pytest.mark.requirement("FR-039")
    def test_load_input_uses_config_namespace(
        self,
        mock_iceberg_manager: MagicMock,
        mock_input_context: MagicMock,
    ) -> None:
        """Test load_input uses namespace from config."""
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        config = IcebergIOManagerConfig(namespace="silver")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.load_input(mock_input_context)

        # Verify correct namespace used
        call_args = mock_iceberg_manager.load_table.call_args
        table_identifier = call_args[0][0]
        assert table_identifier.startswith("silver.")

    @pytest.mark.requirement("FR-040")
    def test_load_input_uses_scan_to_arrow(
        self,
        mock_iceberg_manager: MagicMock,
        mock_input_context: MagicMock,
    ) -> None:
        """Test load_input uses table.scan().to_arrow() pattern.

        Acceptance criteria from T084:
        - Return table.scan().to_arrow()
        """
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        # Create mock table with scan().to_arrow() chain
        mock_arrow_table = MagicMock()
        mock_scan = MagicMock()
        mock_scan.to_arrow.return_value = mock_arrow_table

        mock_table = MagicMock()
        mock_table.scan.return_value = mock_scan

        mock_iceberg_manager.load_table.return_value = mock_table

        config = IcebergIOManagerConfig(namespace="bronze")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        result = io_mgr.load_input(mock_input_context)

        # Verify scan().to_arrow() chain was called
        mock_table.scan.assert_called_once()
        mock_scan.to_arrow.assert_called_once()
        assert result == mock_arrow_table


# =============================================================================
# IcebergIOManager Partitioned Asset Tests
# =============================================================================


class TestIcebergIOManagerPartitionedAssets:
    """Tests for IcebergIOManager partitioned asset support."""

    @pytest.mark.requirement("FR-039")
    def test_detect_partitioned_asset_from_context(
        self,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test detecting partitioned asset from context.

        Acceptance criteria from T088:
        - Detect partitioned asset from context
        """
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        # Create partitioned context (has partition_key)
        partitioned_context = MagicMock()
        partitioned_context.partition_key = "2024-01-15"
        partitioned_context.asset_key = MagicMock()
        partitioned_context.asset_key.path = ["daily_events"]
        partitioned_context.metadata = {}

        # Create non-partitioned context (no partition_key)
        non_partitioned_context = MagicMock()
        non_partitioned_context.partition_key = None
        non_partitioned_context.asset_key = MagicMock()
        non_partitioned_context.asset_key.path = ["events"]
        non_partitioned_context.metadata = {}

        config = IcebergIOManagerConfig(namespace="bronze")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        # Partitioned asset should be detected
        assert io_mgr._is_partitioned_asset(partitioned_context) is True
        assert io_mgr._get_partition_key(partitioned_context) == "2024-01-15"

        # Non-partitioned asset should not be detected
        assert io_mgr._is_partitioned_asset(non_partitioned_context) is False
        assert io_mgr._get_partition_key(non_partitioned_context) is None

    @pytest.mark.requirement("FR-039")
    def test_partitioned_asset_auto_overwrite_mode(
        self,
        mock_iceberg_manager: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test partitioned asset automatically uses overwrite mode.

        Acceptance criteria from T088:
        - Use overwrite mode with partition filter for partitioned writes
        """
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig, WriteMode

        # Create partitioned context
        context = MagicMock()
        context.partition_key = "2024-01-15"
        context.asset_key = MagicMock()
        context.asset_key.path = ["daily_events"]
        context.metadata = {}

        config = IcebergIOManagerConfig(namespace="bronze")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.handle_output(context, mock_pyarrow_table)

        # Verify write_data was called with OVERWRITE mode
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]

        assert write_config.mode == WriteMode.OVERWRITE

    @pytest.mark.requirement("FR-040")
    def test_partition_key_to_filter_mapping(
        self,
        mock_iceberg_manager: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test mapping Dagster partition key to Iceberg partition filter.

        Acceptance criteria from T088:
        - Map Dagster partition key to Iceberg partition filter
        """
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        # Create partitioned context with partition column metadata
        context = MagicMock()
        context.partition_key = "2024-01-15"
        context.asset_key = MagicMock()
        context.asset_key.path = ["daily_events"]
        context.metadata = {"iceberg_partition_column": "date"}

        config = IcebergIOManagerConfig(namespace="bronze")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.handle_output(context, mock_pyarrow_table)

        # Verify overwrite_filter was built correctly
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]

        assert write_config.overwrite_filter == "date = '2024-01-15'"

    @pytest.mark.requirement("FR-040")
    def test_daily_partitions_definition_support(
        self,
        mock_iceberg_manager: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test support for DailyPartitionsDefinition.

        Acceptance criteria from T088:
        - Support DailyPartitionsDefinition
        """
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig, WriteMode

        # Simulate DailyPartitionsDefinition context
        # Dagster uses YYYY-MM-DD format for daily partitions
        context = MagicMock()
        context.partition_key = "2024-03-20"  # Daily partition key
        context.asset_key = MagicMock()
        context.asset_key.path = ["sales"]
        context.metadata = {
            "iceberg_partition_column": "event_date",
        }

        config = IcebergIOManagerConfig(namespace="silver")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.handle_output(context, mock_pyarrow_table)

        # Verify correct handling
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]

        # Should use overwrite mode
        assert write_config.mode == WriteMode.OVERWRITE

        # Should build correct filter
        assert write_config.overwrite_filter == "event_date = '2024-03-20'"

    @pytest.mark.requirement("FR-039")
    def test_partitioned_asset_explicit_write_mode_override(
        self,
        mock_iceberg_manager: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test explicit write mode overrides partitioned auto-overwrite.

        Verifies that explicit metadata write_mode takes precedence over
        the automatic overwrite mode for partitioned assets.
        """
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig, WriteMode

        # Create partitioned context with explicit append mode
        context = MagicMock()
        context.partition_key = "2024-01-15"
        context.asset_key = MagicMock()
        context.asset_key.path = ["events"]
        context.metadata = {"iceberg_write_mode": "append"}

        config = IcebergIOManagerConfig(namespace="bronze")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.handle_output(context, mock_pyarrow_table)

        # Verify explicit mode overrides auto-overwrite
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]

        assert write_config.mode == WriteMode.APPEND

    @pytest.mark.requirement("FR-040")
    def test_build_partition_filter(
        self,
        mock_iceberg_manager: MagicMock,
    ) -> None:
        """Test _build_partition_filter generates correct filter expression."""
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        config = IcebergIOManagerConfig(namespace="bronze")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        # Test with date partition
        filter_expr = io_mgr._build_partition_filter("date", "2024-01-15")
        assert filter_expr == "date = '2024-01-15'"

        # Test with month partition
        filter_expr = io_mgr._build_partition_filter("month", "2024-01")
        assert filter_expr == "month = '2024-01'"

        # Test with None partition key
        filter_expr = io_mgr._build_partition_filter("date", None)
        assert filter_expr is None

    @pytest.mark.requirement("FR-040")
    def test_auto_partition_column_metadata(
        self,
        mock_iceberg_manager: MagicMock,
        mock_pyarrow_table: MagicMock,
    ) -> None:
        """Test iceberg_auto_partition_column metadata for partitioned assets."""
        from floe_iceberg.io_manager import IcebergIOManager
        from floe_iceberg.models import IcebergIOManagerConfig

        # Create partitioned context with auto partition column
        context = MagicMock()
        context.partition_key = "2024-01-15"
        context.asset_key = MagicMock()
        context.asset_key.path = ["events"]
        context.metadata = {"iceberg_auto_partition_column": "processing_date"}

        config = IcebergIOManagerConfig(namespace="bronze")
        io_mgr = IcebergIOManager(config=config, iceberg_manager=mock_iceberg_manager)

        io_mgr.handle_output(context, mock_pyarrow_table)

        # Verify auto partition column was used
        call_args = mock_iceberg_manager.write_data.call_args
        write_config = call_args[0][2]

        assert write_config.overwrite_filter == "processing_date = '2024-01-15'"


__all__ = []
