"""Integration tests for IcebergIOManager with real Polaris + MinIO.

Tests the IcebergIOManager through Dagster's materialize() pipeline
with real Polaris catalog and MinIO storage. No mocks.

These tests validate end-to-end functionality:
  Dagster materialize() -> IcebergIOManager -> IcebergTableManager -> real Polaris + real MinIO

Requirements tested:
    FR-037: Handle asset outputs by writing to Iceberg tables
    FR-038: Support configurable write modes (append, overwrite)
    FR-039: Load asset inputs from Iceberg tables
    FR-040: Support partitioned assets

Note:
    These tests require K8s services running:
    - polaris (port 8181)
    - minio (port 9000)

    Run with:
        .venv/bin/python -m pytest \
            plugins/floe-orchestrator-dagster/tests/integration/ \
            -v -c pyproject.toml
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import pyarrow as pa
import pytest
from dagster import (
    IOManagerDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
    materialize,
)
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_orchestrator_dagster.io_manager import (
    ICEBERG_PARTITION_COLUMN_KEY,
    ICEBERG_WRITE_MODE_KEY,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Integration Test Class — Real Services
# =============================================================================


@pytest.mark.integration
class TestIcebergIOManagerRealIntegration(IntegrationTestBase):
    """Integration tests for IcebergIOManager with real Polaris + MinIO.

    Every test uses Dagster's materialize() to exercise the full pipeline:
    @asset -> materialize() -> IcebergIOManager -> IcebergTableManager -> Polaris + MinIO.

    No MagicMock. No skips. Tests FAIL if services are unavailable.
    """

    required_services: ClassVar[list[tuple[str, int]]] = [
        ("polaris", 8181),
        ("minio", 9000),
    ]

    # =========================================================================
    # Test 1: Basic write via materialize()
    # =========================================================================

    @pytest.mark.requirement("FR-037")
    def test_materialize_writes_real_data(
        self,
        real_io_manager: Any,
        real_table_manager: Any,
        unique_namespace: str,
    ) -> None:
        """Test Dagster materialize() writes real data to Iceberg table.

        Validates end-to-end write flow:
        1. Define @asset returning PyArrow table
        2. materialize() with real IcebergIOManager
        3. Verify table exists in real Polaris catalog
        4. Scan real data and assert actual values
        """

        def _io_manager_resource(_context: Any) -> Any:
            return real_io_manager

        io_manager_def = IOManagerDefinition(resource_fn=_io_manager_resource)

        @asset
        def test_customers() -> pa.Table:
            """Asset producing customer data."""
            return pa.table(
                {
                    "id": pa.array([1, 2, 3], type=pa.int64()),
                    "name": pa.array(["Alice", "Bob", "Charlie"], type=pa.string()),
                    "amount": pa.array([100.0, 200.0, 300.0], type=pa.float64()),
                }
            )

        result = materialize(
            assets=[test_customers],
            resources={"io_manager": io_manager_def},
        )

        assert result.success, "Materialization should succeed"

        # Verify via real table scan
        identifier = f"{unique_namespace}.test_customers"
        assert real_table_manager.table_exists(identifier), (
            f"Table '{identifier}' should exist in Polaris"
        )

        table = real_table_manager.load_table(identifier)
        scanned = table.scan().to_arrow()
        assert scanned.num_rows == 3
        assert set(scanned["name"].to_pylist()) == {"Alice", "Bob", "Charlie"}
        assert set(scanned["id"].to_pylist()) == {1, 2, 3}

    # =========================================================================
    # Test 2: Downstream asset reads real data
    # =========================================================================

    @pytest.mark.requirement("FR-039")
    def test_materialize_downstream_reads_real_data(
        self,
        real_io_manager: Any,
        real_table_manager: Any,
        unique_namespace: str,
    ) -> None:
        """Test downstream asset receives real data from upstream via IOManager.

        Validates full read-write pipeline:
        1. Upstream @asset writes PyArrow table to Iceberg
        2. Downstream @asset depends on upstream, receives loaded data
        3. Both materializations succeed
        4. Downstream receives actual data (not None, not mock)
        """
        # Capture downstream input for verification
        downstream_received: dict[str, Any] = {}

        def _io_manager_resource(_context: Any) -> Any:
            return real_io_manager

        io_manager_def = IOManagerDefinition(resource_fn=_io_manager_resource)

        @asset
        def upstream_data() -> pa.Table:
            """Upstream asset writing customer data."""
            return pa.table(
                {
                    "id": pa.array([10, 20], type=pa.int64()),
                    "value": pa.array(["hello", "world"], type=pa.string()),
                }
            )

        @asset
        def downstream_data(upstream_data: pa.Table) -> pa.Table:
            """Downstream asset that receives upstream data."""
            downstream_received["data"] = upstream_data
            downstream_received["num_rows"] = upstream_data.num_rows
            # Pass through with transformation
            return upstream_data

        result = materialize(
            assets=[upstream_data, downstream_data],
            resources={"io_manager": io_manager_def},
        )

        assert result.success, "Both materializations should succeed"

        # Verify downstream received real data
        assert "data" in downstream_received, "Downstream should have received data"
        assert downstream_received["num_rows"] == 2
        received_table = downstream_received["data"]
        assert set(received_table["value"].to_pylist()) == {"hello", "world"}

        # Verify both tables exist in Polaris
        upstream_id = f"{unique_namespace}.upstream_data"
        downstream_id = f"{unique_namespace}.downstream_data"
        assert real_table_manager.table_exists(upstream_id)
        assert real_table_manager.table_exists(downstream_id)

    # =========================================================================
    # Test 3: Overwrite mode replaces data
    # =========================================================================

    @pytest.mark.requirement("FR-038")
    def test_materialize_overwrite_replaces_data(
        self,
        real_io_manager: Any,
        real_table_manager: Any,
        unique_namespace: str,
    ) -> None:
        """Test overwrite mode replaces existing data instead of appending.

        1. First materialize: write 3 rows
        2. Second materialize with overwrite: write 1 row
        3. Verify table has exactly 1 row (not 4)
        """
        call_count: dict[str, int] = {"n": 0}

        def _io_manager_resource(_context: Any) -> Any:
            return real_io_manager

        io_manager_def = IOManagerDefinition(resource_fn=_io_manager_resource)

        @asset
        def overwrite_test() -> Output:
            """Asset that writes different data on each call."""
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: 3 rows, default append
                data = pa.table(
                    {
                        "id": pa.array([1, 2, 3], type=pa.int64()),
                        "name": pa.array(["a", "b", "c"], type=pa.string()),
                    }
                )
                return Output(data)
            else:
                # Second call: 1 row, overwrite
                data = pa.table(
                    {
                        "id": pa.array([99], type=pa.int64()),
                        "name": pa.array(["replaced"], type=pa.string()),
                    }
                )
                return Output(data, metadata={ICEBERG_WRITE_MODE_KEY: "overwrite"})

        # First materialization: append 3 rows
        result1 = materialize(
            assets=[overwrite_test],
            resources={"io_manager": io_manager_def},
        )
        assert result1.success

        identifier = f"{unique_namespace}.overwrite_test"
        table = real_table_manager.load_table(identifier)
        assert table.scan().to_arrow().num_rows == 3

        # Second materialization: overwrite with 1 row
        result2 = materialize(
            assets=[overwrite_test],
            resources={"io_manager": io_manager_def},
        )
        assert result2.success

        table = real_table_manager.load_table(identifier)
        scanned = table.scan().to_arrow()
        assert scanned.num_rows == 1, f"Expected 1 row after overwrite, got {scanned.num_rows}"
        assert scanned["name"].to_pylist() == ["replaced"]

    # =========================================================================
    # Test 4: Append adds rows
    # =========================================================================

    @pytest.mark.requirement("FR-038")
    def test_materialize_append_adds_rows(
        self,
        real_io_manager: Any,
        real_table_manager: Any,
        unique_namespace: str,
    ) -> None:
        """Test default append mode adds rows to existing data.

        1. First materialize: write 3 rows
        2. Second materialize: write 2 more rows (default append)
        3. Verify table has exactly 5 rows
        """
        call_count: dict[str, int] = {"n": 0}

        def _io_manager_resource(_context: Any) -> Any:
            return real_io_manager

        io_manager_def = IOManagerDefinition(resource_fn=_io_manager_resource)

        @asset
        def append_test() -> pa.Table:
            """Asset producing different data on each call."""
            call_count["n"] += 1
            if call_count["n"] == 1:
                return pa.table(
                    {
                        "id": pa.array([1, 2, 3], type=pa.int64()),
                        "value": pa.array(["a", "b", "c"], type=pa.string()),
                    }
                )
            else:
                return pa.table(
                    {
                        "id": pa.array([4, 5], type=pa.int64()),
                        "value": pa.array(["d", "e"], type=pa.string()),
                    }
                )

        # First materialization: 3 rows
        result1 = materialize(
            assets=[append_test],
            resources={"io_manager": io_manager_def},
        )
        assert result1.success

        identifier = f"{unique_namespace}.append_test"
        table = real_table_manager.load_table(identifier)
        assert table.scan().to_arrow().num_rows == 3

        # Second materialization: append 2 more rows
        result2 = materialize(
            assets=[append_test],
            resources={"io_manager": io_manager_def},
        )
        assert result2.success

        table = real_table_manager.load_table(identifier)
        scanned = table.scan().to_arrow()
        assert scanned.num_rows == 5, f"Expected 5 rows after append, got {scanned.num_rows}"
        assert set(scanned["value"].to_pylist()) == {"a", "b", "c", "d", "e"}

    # =========================================================================
    # Test 5: Partitioned asset
    # =========================================================================

    @pytest.mark.requirement("FR-040")
    def test_materialize_partitioned_asset(
        self,
        real_io_manager: Any,
        real_table_manager: Any,
        unique_namespace: str,
    ) -> None:
        """Test partitioned asset writes data with partition metadata.

        Validates that partition_key is correctly passed through
        the Dagster pipeline and the IOManager writes data to the table.
        """

        def _io_manager_resource(_context: Any) -> Any:
            return real_io_manager

        io_manager_def = IOManagerDefinition(resource_fn=_io_manager_resource)

        @asset(
            partitions_def=StaticPartitionsDefinition(["2026-01-17", "2026-01-18", "2026-01-19"]),
        )
        def partitioned_orders() -> Output:
            """Partitioned asset with date partition column."""
            data = pa.table(
                {
                    "id": pa.array([1, 2], type=pa.int64()),
                    "date": pa.array(["2026-01-17", "2026-01-17"], type=pa.string()),
                    "amount": pa.array([50.0, 75.0], type=pa.float64()),
                }
            )
            return Output(
                data,
                metadata={
                    ICEBERG_WRITE_MODE_KEY: "overwrite",
                    ICEBERG_PARTITION_COLUMN_KEY: "date",
                },
            )

        result = materialize(
            assets=[partitioned_orders],
            resources={"io_manager": io_manager_def},
            partition_key="2026-01-17",
        )

        assert result.success, "Partitioned materialization should succeed"

        # Verify table exists and has data
        identifier = f"{unique_namespace}.partitioned_orders"
        assert real_table_manager.table_exists(identifier)

        table = real_table_manager.load_table(identifier)
        scanned = table.scan().to_arrow()
        assert scanned.num_rows == 2
        assert set(scanned["date"].to_pylist()) == {"2026-01-17"}

    # =========================================================================
    # Test 6: Schema inference from PyArrow
    # =========================================================================

    @pytest.mark.requirement("FR-037")
    def test_schema_inference_from_pyarrow(
        self,
        real_io_manager: Any,
        real_table_manager: Any,
        unique_namespace: str,
    ) -> None:
        """Test IOManager auto-creates table with schema inferred from PyArrow.

        Validates that when infer_schema_from_data=True (default):
        1. Table is auto-created on first write
        2. Schema fields match the PyArrow table schema
        3. Types are correctly mapped (int64, string, float64, bool)
        """

        def _io_manager_resource(_context: Any) -> Any:
            return real_io_manager

        io_manager_def = IOManagerDefinition(resource_fn=_io_manager_resource)

        @asset
        def mixed_types_table() -> pa.Table:
            """Asset with mixed column types."""
            return pa.table(
                {
                    "int_col": pa.array([1, 2], type=pa.int64()),
                    "str_col": pa.array(["x", "y"], type=pa.string()),
                    "float_col": pa.array([1.1, 2.2], type=pa.float64()),
                    "bool_col": pa.array([True, False], type=pa.bool_()),
                }
            )

        result = materialize(
            assets=[mixed_types_table],
            resources={"io_manager": io_manager_def},
        )

        assert result.success

        # Verify table was created with correct schema
        identifier = f"{unique_namespace}.mixed_types_table"
        assert real_table_manager.table_exists(identifier)

        table = real_table_manager.load_table(identifier)
        schema = table.schema()
        field_names = {f.name for f in schema.fields}
        assert field_names == {"int_col", "str_col", "float_col", "bool_col"}

        # Verify data roundtrips correctly
        scanned = table.scan().to_arrow()
        assert scanned.num_rows == 2
        assert scanned["int_col"].to_pylist() == [1, 2]
        assert scanned["str_col"].to_pylist() == ["x", "y"]
        assert scanned["bool_col"].to_pylist() == [True, False]
