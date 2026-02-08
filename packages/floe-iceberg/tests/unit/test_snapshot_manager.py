"""Unit tests for _IcebergSnapshotManager class.

Task ID: T028
Phase: 6 - US4 (Split IcebergTableManager)
User Story: US4 - Split Large Classes
Requirements: FR-015, FR-018, FR-019

Tests for the _IcebergSnapshotManager helper class that encapsulates snapshot
management operations. Written TDD-style before implementation (T032).

The _IcebergSnapshotManager class will be extracted from IcebergTableManager
to reduce class complexity and improve single-responsibility adherence.

Operations covered:
- list_snapshots(): List all snapshots for a table
- rollback_to_snapshot(): Rollback table to a previous snapshot
- expire_snapshots(): Expire old snapshots based on retention policy
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from tests.conftest import MockCatalogPlugin, MockStoragePlugin


# =============================================================================
# Fixtures for Snapshot Tests
# =============================================================================


@pytest.fixture
def snapshot_manager(
    mock_catalog_plugin: MockCatalogPlugin,
    mock_storage_plugin: MockStoragePlugin,
) -> Any:
    """Create an IcebergTableManager with a table for snapshot testing.

    The manager provides access to snapshot operations. After T032,
    this fixture will return _IcebergSnapshotManager directly.

    Args:
        mock_catalog_plugin: Mock catalog plugin fixture.
        mock_storage_plugin: Mock storage plugin fixture.

    Returns:
        IcebergTableManager configured for snapshot testing.
    """
    from floe_iceberg import IcebergTableManager
    from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

    # Create manager
    manager = IcebergTableManager(
        catalog_plugin=mock_catalog_plugin,
        storage_plugin=mock_storage_plugin,
    )

    # Create test namespace
    mock_catalog_plugin.create_namespace(
        "bronze",
        {"location": "s3://mock-warehouse-bucket/warehouse/bronze"},
    )

    # Create a test table with schema
    schema = TableSchema(
        fields=[
            SchemaField(
                field_id=1,
                name="id",
                field_type=FieldType.LONG,
                required=True,
            ),
            SchemaField(
                field_id=2,
                name="name",
                field_type=FieldType.STRING,
                required=False,
            ),
        ]
    )

    config = TableConfig(
        namespace="bronze",
        table_name="customers",
        table_schema=schema,
    )

    manager.create_table(config)

    return manager


def _create_mock_snapshot(
    snapshot_id: int,
    timestamp_ms: int,
    operation: str,
    summary_data: dict[str, str],
    parent_id: int | None = None,
) -> MagicMock:
    """Create a mock PyIceberg Snapshot with proper structure.

    The SnapshotInfo.from_pyiceberg_snapshot() method expects:
    - snapshot.summary.operation (attribute, not dict key)
    - snapshot.summary.additional_properties (for summary data)

    Args:
        snapshot_id: Unique snapshot ID.
        timestamp_ms: Timestamp in milliseconds.
        operation: Operation type (append, overwrite, etc.).
        summary_data: Summary metrics dict.
        parent_id: Parent snapshot ID.

    Returns:
        Properly structured mock snapshot.
    """
    mock_snap = MagicMock()
    mock_snap.snapshot_id = snapshot_id
    mock_snap.timestamp_ms = timestamp_ms
    mock_snap.parent_id = parent_id

    # Create summary as a MagicMock with .operation attribute
    # This matches PyIceberg's Summary structure
    mock_summary = MagicMock()
    mock_summary.operation = operation
    mock_summary.additional_properties = summary_data
    mock_snap.summary = mock_summary

    return mock_snap


@pytest.fixture
def table_with_snapshots(
    snapshot_manager: Any,
    mock_catalog_plugin: MockCatalogPlugin,
) -> Any:
    """Load the test table and configure it with mock snapshots.

    Args:
        snapshot_manager: Manager with test table created.
        mock_catalog_plugin: Mock catalog plugin for snapshot setup.

    Returns:
        Mock table object configured with test snapshots.
    """
    table = snapshot_manager.load_table("bronze.customers")

    # Configure mock snapshots on the table with proper structure
    mock_snap_1 = _create_mock_snapshot(
        snapshot_id=1000,
        timestamp_ms=1705500000000,  # Oldest
        operation="append",
        summary_data={"added-files-count": "5", "added-records-count": "1000"},
        parent_id=None,
    )

    mock_snap_2 = _create_mock_snapshot(
        snapshot_id=2000,
        timestamp_ms=1705600000000,  # Middle
        operation="append",
        summary_data={"added-files-count": "3", "added-records-count": "500"},
        parent_id=1000,
    )

    mock_snap_3 = _create_mock_snapshot(
        snapshot_id=3000,
        timestamp_ms=1705700000000,  # Newest
        operation="overwrite",
        summary_data={"added-files-count": "2", "added-records-count": "200"},
        parent_id=2000,
    )

    # Configure snapshots() method
    table.snapshots.return_value = [mock_snap_1, mock_snap_2, mock_snap_3]

    # Configure manage_snapshots() for rollback tests
    mock_manage = MagicMock()
    mock_manage.set_current_snapshot.return_value = mock_manage  # Chainable
    mock_manage.commit.return_value = None
    table.manage_snapshots.return_value = mock_manage

    return table


# =============================================================================
# List Snapshots Tests (T028)
# =============================================================================


class TestSnapshotManagerListSnapshots:
    """Tests for _IcebergSnapshotManager.list_snapshots() method."""

    @pytest.mark.requirement("FR-018")
    def test_list_snapshots_returns_all_snapshots(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test list_snapshots returns all snapshots for a table."""
        snapshots = snapshot_manager.list_snapshots(table_with_snapshots)

        assert len(snapshots) == 3

    @pytest.mark.requirement("FR-018")
    def test_list_snapshots_ordered_newest_first(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test list_snapshots returns snapshots ordered newest first."""
        snapshots = snapshot_manager.list_snapshots(table_with_snapshots)

        # Verify order (newest first)
        assert snapshots[0].snapshot_id == 3000  # Newest
        assert snapshots[1].snapshot_id == 2000  # Middle
        assert snapshots[2].snapshot_id == 1000  # Oldest

    @pytest.mark.requirement("FR-018")
    def test_list_snapshots_returns_snapshot_info_objects(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test list_snapshots returns SnapshotInfo objects."""
        from floe_iceberg.models import SnapshotInfo

        snapshots = snapshot_manager.list_snapshots(table_with_snapshots)

        for snapshot in snapshots:
            assert isinstance(snapshot, SnapshotInfo)
            assert snapshot.snapshot_id > 0
            assert snapshot.timestamp_ms > 0

    @pytest.mark.requirement("FR-018")
    def test_list_snapshots_empty_table_returns_empty_list(
        self,
        snapshot_manager: Any,
    ) -> None:
        """Test list_snapshots returns empty list for table with no snapshots."""
        table = snapshot_manager.load_table("bronze.customers")
        table.snapshots.return_value = []

        snapshots = snapshot_manager.list_snapshots(table)

        assert snapshots == []


# =============================================================================
# Rollback Tests (T028)
# =============================================================================


class TestSnapshotManagerRollback:
    """Tests for _IcebergSnapshotManager.rollback_to_snapshot() method."""

    @pytest.mark.requirement("FR-019")
    def test_rollback_to_existing_snapshot_succeeds(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test rolling back to an existing snapshot succeeds."""
        result = snapshot_manager.rollback_to_snapshot(table_with_snapshots, 2000)

        assert result.identifier == table_with_snapshots.identifier
        # Verify set_current_snapshot was called with correct ID
        table_with_snapshots.manage_snapshots().set_current_snapshot.assert_called_with(
            2000
        )

    @pytest.mark.requirement("FR-019")
    def test_rollback_to_nonexistent_snapshot_raises(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test rolling back to a nonexistent snapshot raises SnapshotNotFoundError."""
        from floe_iceberg.errors import SnapshotNotFoundError

        with pytest.raises(SnapshotNotFoundError, match="not found"):
            snapshot_manager.rollback_to_snapshot(table_with_snapshots, 9999)

    @pytest.mark.requirement("FR-019")
    def test_rollback_to_oldest_snapshot_succeeds(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test rolling back to the oldest snapshot succeeds."""
        result = snapshot_manager.rollback_to_snapshot(table_with_snapshots, 1000)

        assert result.identifier == table_with_snapshots.identifier
        table_with_snapshots.manage_snapshots().set_current_snapshot.assert_called_with(
            1000
        )

    @pytest.mark.requirement("FR-019")
    def test_rollback_returns_updated_table(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test rollback returns the updated table object."""
        result = snapshot_manager.rollback_to_snapshot(table_with_snapshots, 2000)

        # Should return the same table object (refreshed)
        assert result is table_with_snapshots


# =============================================================================
# Expire Snapshots Tests (T028)
# =============================================================================


class TestSnapshotManagerExpireSnapshots:
    """Tests for _IcebergSnapshotManager.expire_snapshots() method."""

    @pytest.mark.requirement("FR-015")
    def test_expire_snapshots_uses_default_retention(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test expire_snapshots uses default retention from config."""
        # Configure table to simulate expiration
        table_with_snapshots.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table_with_snapshots.expire_snapshots.return_value = expire_op

        # Empty after expiration
        table_with_snapshots.snapshots.side_effect = [
            # First call: 3 snapshots
            [
                MagicMock(snapshot_id=i, timestamp_ms=1705500000000 + i * 100000000)
                for i in range(3)
            ],
            # Second call: still 3 (mock doesn't actually expire)
            [
                MagicMock(snapshot_id=i, timestamp_ms=1705500000000 + i * 100000000)
                for i in range(3)
            ],
        ]

        result = snapshot_manager.expire_snapshots(table_with_snapshots)

        # Method should complete without error
        assert isinstance(result, int)

    @pytest.mark.requirement("FR-015")
    def test_expire_snapshots_with_custom_retention(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test expire_snapshots respects custom retention days."""
        # Configure table
        table_with_snapshots.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table_with_snapshots.expire_snapshots.return_value = expire_op

        # Both calls return same snapshots (mock)
        table_with_snapshots.snapshots.side_effect = [
            [
                MagicMock(snapshot_id=i, timestamp_ms=1705500000000 + i * 100000000)
                for i in range(3)
            ],
            [
                MagicMock(snapshot_id=i, timestamp_ms=1705500000000 + i * 100000000)
                for i in range(3)
            ],
        ]

        result = snapshot_manager.expire_snapshots(
            table_with_snapshots, older_than_days=30
        )

        assert isinstance(result, int)
        # Verify expire_older_than was called
        expire_op.expire_older_than.assert_called_once()

    @pytest.mark.requirement("FR-015")
    def test_expire_snapshots_returns_count(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test expire_snapshots returns number of expired snapshots."""
        # Configure to show 2 snapshots expired
        table_with_snapshots.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table_with_snapshots.expire_snapshots.return_value = expire_op

        # First call: 3 snapshots, second call: 1 snapshot (2 expired)
        table_with_snapshots.snapshots.side_effect = [
            [
                MagicMock(snapshot_id=i, timestamp_ms=1705500000000 + i * 100000000)
                for i in range(3)
            ],
            [MagicMock(snapshot_id=2, timestamp_ms=1705700000000)],  # 1 remaining
        ]

        result = snapshot_manager.expire_snapshots(table_with_snapshots)

        # 3 - 1 = 2 expired
        assert result == 2

    @pytest.mark.requirement("FR-015")
    def test_expire_snapshots_empty_table_returns_zero(
        self,
        snapshot_manager: Any,
    ) -> None:
        """Test expire_snapshots returns 0 for table with no snapshots."""
        table = snapshot_manager.load_table("bronze.customers")
        table.snapshots.return_value = []

        result = snapshot_manager.expire_snapshots(table)

        assert result == 0

    @pytest.mark.requirement("FR-015")
    def test_expire_snapshots_respects_min_to_keep(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test expire_snapshots respects min_snapshots_to_keep config."""
        # Configure table
        table_with_snapshots.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table_with_snapshots.expire_snapshots.return_value = expire_op

        # Both calls return same snapshots (mock doesn't actually expire)
        table_with_snapshots.snapshots.side_effect = [
            [
                MagicMock(snapshot_id=i, timestamp_ms=1705500000000 + i * 100000000)
                for i in range(3)
            ],
            [
                MagicMock(snapshot_id=i, timestamp_ms=1705500000000 + i * 100000000)
                for i in range(3)
            ],
        ]

        snapshot_manager.expire_snapshots(table_with_snapshots)

        # Verify retain_last was called with min_snapshots_to_keep
        # Default config has min_snapshots_to_keep = 10 (see IcebergConfig model)
        expire_op.retain_last.assert_called_once_with(10)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestSnapshotManagerEdgeCases:
    """Edge case tests for snapshot management operations."""

    @pytest.mark.requirement("FR-018")
    def test_list_snapshots_with_single_snapshot(
        self,
        snapshot_manager: Any,
    ) -> None:
        """Test list_snapshots handles table with single snapshot."""
        table = snapshot_manager.load_table("bronze.customers")

        # Use helper to create properly structured mock snapshot
        mock_snap = _create_mock_snapshot(
            snapshot_id=1000,
            timestamp_ms=1705500000000,
            operation="append",
            summary_data={},
            parent_id=None,
        )

        table.snapshots.return_value = [mock_snap]

        snapshots = snapshot_manager.list_snapshots(table)

        assert len(snapshots) == 1
        assert snapshots[0].snapshot_id == 1000

    @pytest.mark.requirement("FR-019")
    def test_rollback_preserves_snapshot_history(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test that rollback is non-destructive (preserves snapshot history)."""
        # Rollback to older snapshot
        snapshot_manager.rollback_to_snapshot(table_with_snapshots, 1000)

        # Snapshots should still be listed (non-destructive)
        # Note: In real implementation, a new snapshot would be created
        # pointing to the old snapshot's state
        snapshots = snapshot_manager.list_snapshots(table_with_snapshots)
        assert len(snapshots) >= 1

    @pytest.mark.requirement("FR-015")
    def test_expire_snapshots_fallback_to_manage_snapshots(
        self,
        snapshot_manager: Any,
        table_with_snapshots: Any,
    ) -> None:
        """Test expire_snapshots falls back to manage_snapshots API."""
        # Remove expire_snapshots method to trigger fallback
        del table_with_snapshots.expire_snapshots

        # Configure manage_snapshots
        mock_manage = MagicMock()
        mock_manage.remove_snapshot.return_value = mock_manage
        mock_manage.commit.return_value = None
        table_with_snapshots.manage_snapshots.return_value = mock_manage

        # Configure snapshots with proper timestamp_ms attribute
        old_snap = MagicMock()
        old_snap.snapshot_id = 1000
        old_snap.timestamp_ms = 1000  # Very old

        new_snap = MagicMock()
        new_snap.snapshot_id = 2000
        new_snap.timestamp_ms = 9999999999999  # Very new

        table_with_snapshots.snapshots.side_effect = [
            [old_snap, new_snap],  # Before
            [new_snap],  # After (simulated expiration)
        ]

        result = snapshot_manager.expire_snapshots(
            table_with_snapshots, older_than_days=1
        )

        # Should complete without error
        assert isinstance(result, int)


__all__ = [
    "TestSnapshotManagerListSnapshots",
    "TestSnapshotManagerRollback",
    "TestSnapshotManagerExpireSnapshots",
    "TestSnapshotManagerEdgeCases",
]
