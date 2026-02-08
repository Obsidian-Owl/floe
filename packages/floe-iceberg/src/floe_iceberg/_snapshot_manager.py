"""Internal helper class for Iceberg snapshot management operations.

Task ID: T032
Phase: 6 - US4 (Split IcebergTableManager)
User Story: US4 - Split Large Classes
Requirements: FR-015

This module contains the _IcebergSnapshotManager helper class that encapsulates
snapshot management operations. Extracted from IcebergTableManager to improve
single-responsibility adherence.

The class is internal (underscore-prefixed) and should only be used by
IcebergTableManager. External consumers should use the public API.

Operations covered:
- list_snapshots(): List all snapshots for a table
- rollback_to_snapshot(): Rollback table to a previous snapshot
- expire_snapshots(): Expire old snapshots based on retention policy
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from floe_iceberg.errors import SnapshotNotFoundError
from floe_iceberg.models import SnapshotInfo
from floe_iceberg.telemetry import traced

if TYPE_CHECKING:
    from floe_iceberg.models import IcebergTableManagerConfig

    # Type alias for PyIceberg Table (Any due to missing type stubs)
    Table = Any


class _IcebergSnapshotManager:
    """Internal helper class for snapshot management operations.

    Encapsulates snapshot listing, rollback, and expiration operations for
    Iceberg tables. Maintains single-responsibility by focusing only on
    snapshot management.

    This class is internal and should not be used directly by external consumers.
    Use IcebergTableManager's public API instead.

    Attributes:
        _config: IcebergTableManagerConfig for retention settings.
        _log: Structured logger instance.

    Example:
        >>> # Internal usage in IcebergTableManager
        >>> snapshot_mgr = _IcebergSnapshotManager(config)
        >>> snapshots = snapshot_mgr.list_snapshots(table)
    """

    def __init__(self, config: IcebergTableManagerConfig) -> None:
        """Initialize _IcebergSnapshotManager.

        Args:
            config: IcebergTableManagerConfig for retention settings.
        """
        self._config = config
        self._log = structlog.get_logger(__name__)

    # =========================================================================
    # Snapshot Management Operations
    # =========================================================================

    @traced(operation_name="iceberg.snapshot.list_snapshots")
    def list_snapshots(self, table: Table) -> list[SnapshotInfo]:
        """List all snapshots for a table, ordered by timestamp (newest first).

        Retrieves snapshot metadata from the table and converts to SnapshotInfo
        objects for a consistent API.

        Args:
            table: PyIceberg Table object.

        Returns:
            List of SnapshotInfo objects, ordered newest first.

        Example:
            >>> snapshots = snapshot_mgr.list_snapshots(table)
            >>> for snapshot in snapshots:
            ...     print(f"ID: {snapshot.snapshot_id}, Records: {snapshot.added_records}")
        """
        self._log.debug(
            "list_snapshots_requested",
            table_identifier=getattr(table, "identifier", None),
        )

        # Get snapshots from PyIceberg table
        snapshots: list[SnapshotInfo] = []
        for snap in table.snapshots():
            snapshot_info = SnapshotInfo.from_pyiceberg_snapshot(snap)
            snapshots.append(snapshot_info)

        # Sort by timestamp_ms (newest first)
        snapshots.sort(key=lambda s: s.timestamp_ms, reverse=True)

        self._log.info(
            "snapshots_listed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_count=len(snapshots),
        )
        return snapshots

    @traced(operation_name="iceberg.snapshot.rollback")
    def rollback_to_snapshot(self, table: Table, snapshot_id: int) -> Table:
        """Rollback table to a previous snapshot.

        Creates a new snapshot pointing to the specified historical snapshot.
        This is a non-destructive operation - previous snapshots are preserved.

        Args:
            table: PyIceberg Table object.
            snapshot_id: ID of the snapshot to rollback to.

        Returns:
            Updated Table object with new current snapshot.

        Raises:
            SnapshotNotFoundError: If snapshot_id doesn't exist.

        Example:
            >>> snapshots = snapshot_mgr.list_snapshots(table)
            >>> old_snapshot = snapshots[-1]  # Oldest snapshot
            >>> table = snapshot_mgr.rollback_to_snapshot(table, old_snapshot.snapshot_id)
        """
        from opentelemetry import trace

        # Add span attributes
        span = trace.get_current_span()
        span.set_attribute("table.identifier", getattr(table, "identifier", "unknown"))
        span.set_attribute("target.snapshot_id", snapshot_id)

        self._log.debug(
            "rollback_to_snapshot_requested",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=snapshot_id,
        )

        # Validate snapshot exists
        snapshots = self.list_snapshots(table)
        snapshot_ids = [s.snapshot_id for s in snapshots]

        if snapshot_id not in snapshot_ids:
            msg = f"Snapshot {snapshot_id} not found in table"
            self._log.error(
                "snapshot_not_found",
                table_identifier=getattr(table, "identifier", None),
                snapshot_id=snapshot_id,
                available_snapshots=snapshot_ids,
            )
            raise SnapshotNotFoundError(msg)

        # Use PyIceberg ManageSnapshots API for rollback
        manage_snapshots = table.manage_snapshots()

        # Check if set_current_snapshot is available (PyIceberg 0.11+)
        if hasattr(manage_snapshots, "set_current_snapshot"):
            manage_snapshots.set_current_snapshot(snapshot_id).commit()
        elif hasattr(manage_snapshots, "rollback_to_snapshot"):
            # Alternative API if available
            manage_snapshots.rollback_to_snapshot(snapshot_id).commit()
        else:
            # PyIceberg 0.10.0 doesn't support snapshot rollback yet
            import pyiceberg

            msg = (
                "Snapshot rollback not supported in PyIceberg "
                f"{pyiceberg.__version__}. "
                "Upgrade to PyIceberg 0.11+ for this feature."
            )
            self._log.error(
                "rollback_not_supported",
                table_identifier=getattr(table, "identifier", None),
                pyiceberg_version=pyiceberg.__version__,
            )
            raise NotImplementedError(msg)

        # Refresh to get the updated state
        if hasattr(table, "refresh"):
            table.refresh()

        self._log.info(
            "snapshot_rollback_completed",
            table_identifier=getattr(table, "identifier", None),
            target_snapshot_id=snapshot_id,
        )
        return table

    @traced(operation_name="iceberg.snapshot.expire_snapshots")
    def expire_snapshots(
        self,
        table: Table,
        older_than_days: int | None = None,
        keep_last: int | None = None,
    ) -> int:
        """Expire snapshots older than the specified retention period.

        Removes old snapshots while respecting min_snapshots_to_keep from config.
        This helps manage storage costs and metadata overhead.

        For demo environments, use keep_last=6 to maintain a rolling window of
        recent snapshots regardless of age (FR-032).

        Args:
            table: PyIceberg Table object.
            older_than_days: Days to retain snapshots. Defaults to config value.
            keep_last: Number of most recent snapshots to keep. Overrides
                min_snapshots_to_keep from config. For demo: use keep_last=6.

        Returns:
            Number of snapshots expired.

        Example:
            >>> # Expire with default retention
            >>> expired_count = snapshot_mgr.expire_snapshots(table, older_than_days=30)
            >>> # Demo mode: keep last 6 snapshots
            >>> expired_count = snapshot_mgr.expire_snapshots(table, keep_last=6)

        Requirements:
            FR-032: Iceberg snapshot expiry with keep_last=6 for demo retention
        """
        if older_than_days is not None:
            retention_days = older_than_days
        else:
            retention_days = self._config.default_retention_days

        # Determine snapshots to keep
        if keep_last is not None:
            min_to_keep = keep_last
            self._log.debug(
                "snapshot_retention_override",
                keep_last=keep_last,
            )
        else:
            min_to_keep = self._config.min_snapshots_to_keep

        # Set span attributes for observability
        from opentelemetry import trace

        span = trace.get_current_span()
        span.set_attribute("table.identifier", str(getattr(table, "identifier", "unknown")))
        span.set_attribute("retention.keep_last", min_to_keep)

        self._log.debug(
            "expire_snapshots_requested",
            table_identifier=getattr(table, "identifier", None),
            retention_days=retention_days,
            min_to_keep=min_to_keep,
        )

        # Get current snapshots to count before/after
        snapshots_before = list(table.snapshots())

        if not snapshots_before:
            span.set_attribute("expired.count", 0)
            self._log.info(
                "no_snapshots_to_expire",
                table_identifier=getattr(table, "identifier", None),
            )
            return 0

        # Calculate cutoff timestamp
        import time
        from datetime import datetime, timezone

        cutoff_ms = int((time.time() - (retention_days * 24 * 60 * 60)) * 1000)
        cutoff_datetime = datetime.fromtimestamp(cutoff_ms / 1000, tz=timezone.utc)

        # Use PyIceberg ExpireSnapshots API
        # Note: PyIceberg's expire_snapshots is available via table operations
        if hasattr(table, "expire_snapshots"):
            # PyIceberg 0.11+ has expire_snapshots method
            expire_op = table.expire_snapshots()
            expire_op.expire_older_than(cutoff_datetime)
            expire_op.retain_last(min_to_keep)
            expire_op.commit()
        elif hasattr(table, "manage_snapshots"):
            # Alternative: use ManageSnapshots API
            manage_snapshots = table.manage_snapshots()
            # Identify snapshots to expire
            snapshots_sorted = sorted(
                snapshots_before,
                key=lambda s: s.timestamp_ms,
                reverse=True,
            )

            # Keep minimum snapshots
            snapshots_to_consider = snapshots_sorted[min_to_keep:]

            # Expire snapshots older than cutoff
            for snap in snapshots_to_consider:
                if snap.timestamp_ms < cutoff_ms:
                    if hasattr(manage_snapshots, "remove_snapshot"):
                        manage_snapshots.remove_snapshot(snap.snapshot_id)

            manage_snapshots.commit()
        else:
            # PyIceberg version doesn't support snapshot expiration
            self._log.warning(
                "expire_snapshots_not_supported",
                table_identifier=getattr(table, "identifier", None),
                message="PyIceberg version does not support snapshot expiration",
            )
            span.set_attribute("expired.count", 0)
            return 0

        # Refresh and count snapshots after
        if hasattr(table, "refresh"):
            table.refresh()

        snapshots_after = list(table.snapshots())
        expired_count = len(snapshots_before) - len(snapshots_after)

        # Set expired count span attribute
        span.set_attribute("expired.count", expired_count)

        self._log.info(
            "snapshots_expired",
            table_identifier=getattr(table, "identifier", None),
            expired_count=expired_count,
            remaining_count=len(snapshots_after),
            retention_days=retention_days,
        )

        return expired_count


__all__ = ["_IcebergSnapshotManager"]
