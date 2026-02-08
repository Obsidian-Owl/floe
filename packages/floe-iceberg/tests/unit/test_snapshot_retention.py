"""Unit tests for snapshot retention configuration in _IcebergSnapshotManager.

Task: T035
Epic: 13 - E2E Demo Platform
Requirements: FR-032

These tests verify the keep_last parameter integration for demo retention
scenarios where we want to maintain a rolling window of recent snapshots
regardless of age.

Test coverage:
- expire_snapshots respects keep_last parameter
- keep_last overrides min_snapshots_to_keep config
- Demo use case: keep_last=6 maintains 6 most recent snapshots
- Fallback to config when keep_last not specified
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from tests.conftest import MockCatalogPlugin, MockStoragePlugin


@pytest.fixture
def snapshot_manager_for_retention(
    mock_catalog_plugin: MockCatalogPlugin,
    mock_storage_plugin: MockStoragePlugin,
) -> Any:
    """Create IcebergTableManager with custom retention config for testing.

    Args:
        mock_catalog_plugin: Mock catalog plugin fixture.
        mock_storage_plugin: Mock storage plugin fixture.

    Returns:
        IcebergTableManager configured for retention testing.
    """
    from floe_iceberg import IcebergTableManager
    from floe_iceberg.models import (
        FieldType,
        IcebergTableManagerConfig,
        SchemaField,
        TableConfig,
        TableSchema,
    )

    # Create manager with custom config
    config = IcebergTableManagerConfig(
        default_retention_days=7,
        min_snapshots_to_keep=10,  # Default minimum
    )

    manager = IcebergTableManager(
        catalog_plugin=mock_catalog_plugin,
        storage_plugin=mock_storage_plugin,
        config=config,
    )

    # Create test namespace and table
    mock_catalog_plugin.create_namespace(
        "demo",
        {"location": "s3://mock-warehouse-bucket/warehouse/demo"},
    )

    schema = TableSchema(
        fields=[
            SchemaField(
                field_id=1,
                name="id",
                field_type=FieldType.LONG,
                required=True,
            ),
        ]
    )

    table_config = TableConfig(
        namespace="demo",
        table_name="pipeline_data",
        table_schema=schema,
    )

    manager.create_table(table_config)

    return manager


def _create_mock_snapshot_simple(
    snapshot_id: int,
    timestamp_ms: int,
) -> MagicMock:
    """Create a minimal mock snapshot for retention tests.

    Args:
        snapshot_id: Unique snapshot ID.
        timestamp_ms: Timestamp in milliseconds.

    Returns:
        Mock snapshot object.
    """
    mock_snap = MagicMock()
    mock_snap.snapshot_id = snapshot_id
    mock_snap.timestamp_ms = timestamp_ms
    return mock_snap


class TestSnapshotRetentionKeepLast:
    """Test keep_last parameter for snapshot retention."""

    @pytest.mark.requirement("FR-032")
    def test_expire_snapshots_respects_keep_last_parameter(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test expire_snapshots uses keep_last parameter when provided."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        # Configure table with expire_snapshots method
        table.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table.expire_snapshots.return_value = expire_op

        # Create 10 snapshots
        snapshots = [
            _create_mock_snapshot_simple(i, 1705500000000 + i * 100000000)
            for i in range(10)
        ]

        # First call: 10 snapshots, second call: 6 snapshots (4 expired)
        table.snapshots.side_effect = [
            snapshots,
            snapshots[-6:],  # Keep last 6
        ]

        # Expire with keep_last=6 (demo mode)
        result = snapshot_manager_for_retention.expire_snapshots(
            table,
            keep_last=6,
        )

        # Verify retain_last was called with 6
        expire_op.retain_last.assert_called_once_with(6)

        # Should report 4 snapshots expired (10 - 6)
        assert result == 4

    @pytest.mark.requirement("FR-032")
    def test_keep_last_overrides_config_min_snapshots(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test keep_last parameter overrides min_snapshots_to_keep from config."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        # Manager config has min_snapshots_to_keep=10
        # But keep_last=6 should override it

        table.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table.expire_snapshots.return_value = expire_op

        snapshots = [
            _create_mock_snapshot_simple(i, 1705500000000 + i * 100000000)
            for i in range(10)
        ]

        table.snapshots.side_effect = [
            snapshots,
            snapshots[-6:],
        ]

        # Use keep_last=6 instead of config's min_snapshots_to_keep=10
        snapshot_manager_for_retention.expire_snapshots(table, keep_last=6)

        # Should use 6, not 10
        expire_op.retain_last.assert_called_once_with(6)

    @pytest.mark.requirement("FR-032")
    def test_expire_without_keep_last_uses_config_default(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test expire_snapshots uses config min_snapshots_to_keep when keep_last not provided."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        table.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table.expire_snapshots.return_value = expire_op

        snapshots = [
            _create_mock_snapshot_simple(i, 1705500000000 + i * 100000000)
            for i in range(10)
        ]

        table.snapshots.side_effect = [
            snapshots,
            snapshots,  # No expiry
        ]

        # Don't pass keep_last - should use config default (10)
        snapshot_manager_for_retention.expire_snapshots(table)

        # Should use config value: min_snapshots_to_keep=10
        expire_op.retain_last.assert_called_once_with(10)

    @pytest.mark.requirement("FR-032")
    def test_demo_retention_scenario_keep_last_6(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test demo scenario: keep_last=6 maintains rolling window of 6 snapshots."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        table.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table.expire_snapshots.return_value = expire_op

        # Create 12 snapshots (simulating multiple pipeline runs)
        snapshots = [
            _create_mock_snapshot_simple(i, 1705500000000 + i * 100000000)
            for i in range(12)
        ]

        # After expiry: keep last 6 (IDs 6-11)
        table.snapshots.side_effect = [
            snapshots,
            snapshots[-6:],
        ]

        # Demo mode: keep only last 6 snapshots
        result = snapshot_manager_for_retention.expire_snapshots(
            table,
            keep_last=6,
        )

        # Should expire 6 snapshots (12 - 6)
        assert result == 6

        # Verify retain_last(6) was called
        expire_op.retain_last.assert_called_once_with(6)


class TestSnapshotRetentionFallback:
    """Test fallback behavior when expire_snapshots method not available."""

    @pytest.mark.requirement("FR-032")
    def test_manage_snapshots_fallback_respects_keep_last(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test manage_snapshots fallback uses keep_last parameter."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        # Remove expire_snapshots method to trigger fallback
        del table.expire_snapshots

        # Configure manage_snapshots
        mock_manage = MagicMock()
        mock_manage.remove_snapshot.return_value = mock_manage
        mock_manage.commit.return_value = None
        table.manage_snapshots.return_value = mock_manage

        # Create 10 snapshots, all old
        old_time = 1000000  # Very old
        snapshots = [
            _create_mock_snapshot_simple(i, old_time + i * 1000) for i in range(10)
        ]

        # After expiry: keep last 6
        table.snapshots.side_effect = [
            snapshots,
            snapshots[-6:],
        ]

        # Expire with keep_last=6
        result = snapshot_manager_for_retention.expire_snapshots(
            table,
            keep_last=6,
            older_than_days=1,  # All snapshots are older than 1 day
        )

        # Should expire 4 snapshots (10 - 6)
        assert result == 4

        # Verify remove_snapshot was called for the 4 oldest snapshots
        # (IDs 0-3, keeping 6-9)
        assert mock_manage.remove_snapshot.call_count == 4


class TestSnapshotRetentionEdgeCases:
    """Test edge cases for snapshot retention configuration."""

    @pytest.mark.requirement("FR-032")
    def test_keep_last_zero_invalid(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test keep_last=0 is handled (keep at least 1 snapshot)."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        table.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table.expire_snapshots.return_value = expire_op

        snapshots = [_create_mock_snapshot_simple(1, 1705500000000)]

        table.snapshots.side_effect = [
            snapshots,
            snapshots,
        ]

        # Even with keep_last=0, PyIceberg should retain at least current snapshot
        snapshot_manager_for_retention.expire_snapshots(table, keep_last=0)

        # Should call retain_last with 0 (PyIceberg handles minimum)
        expire_op.retain_last.assert_called_once_with(0)

    @pytest.mark.requirement("FR-032")
    def test_keep_last_greater_than_snapshot_count(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test keep_last > snapshot count keeps all snapshots."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        table.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table.expire_snapshots.return_value = expire_op

        # Only 3 snapshots
        snapshots = [
            _create_mock_snapshot_simple(i, 1705500000000 + i * 100000000)
            for i in range(3)
        ]

        table.snapshots.side_effect = [
            snapshots,
            snapshots,  # All kept
        ]

        # Request keep_last=6, but only 3 exist
        result = snapshot_manager_for_retention.expire_snapshots(table, keep_last=6)

        # Should expire 0 snapshots (3 - 3 = 0)
        assert result == 0

        # retain_last(6) still called, PyIceberg keeps all 3
        expire_op.retain_last.assert_called_once_with(6)

    @pytest.mark.requirement("FR-032")
    def test_keep_last_with_custom_retention_days(
        self,
        snapshot_manager_for_retention: Any,
    ) -> None:
        """Test keep_last works with custom older_than_days."""
        table = snapshot_manager_for_retention.load_table("demo.pipeline_data")

        table.expire_snapshots = MagicMock()
        expire_op = MagicMock()
        expire_op.expire_older_than.return_value = expire_op
        expire_op.retain_last.return_value = expire_op
        expire_op.commit.return_value = None
        table.expire_snapshots.return_value = expire_op

        snapshots = [
            _create_mock_snapshot_simple(i, 1705500000000 + i * 100000000)
            for i in range(10)
        ]

        table.snapshots.side_effect = [
            snapshots,
            snapshots[-6:],
        ]

        # Both parameters: custom retention days + keep_last
        result = snapshot_manager_for_retention.expire_snapshots(
            table,
            older_than_days=30,
            keep_last=6,
        )

        # Should use keep_last=6
        expire_op.retain_last.assert_called_once_with(6)

        # Should also set retention days
        expire_op.expire_older_than.assert_called_once()

        assert result == 4


__all__ = [
    "TestSnapshotRetentionKeepLast",
    "TestSnapshotRetentionFallback",
    "TestSnapshotRetentionEdgeCases",
]
