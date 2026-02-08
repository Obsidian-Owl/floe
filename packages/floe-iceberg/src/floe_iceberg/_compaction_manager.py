"""Internal helper class for Iceberg compaction operations.

Task ID: T033
Phase: 6 - US4 (Split IcebergTableManager)
User Story: US4 - Split Large Classes
Requirements: FR-016

This module contains the _IcebergCompactionManager helper class that encapsulates
compaction operations. Extracted from IcebergTableManager to improve
single-responsibility adherence.

The class is internal (underscore-prefixed) and should only be used by
IcebergTableManager. External consumers should use the public API.

Operations covered:
- compact_table(): Compact table data files to optimize query performance

Note: Compaction is NOT auto-triggered. The orchestrator (Dagster) is responsible
for scheduling when compaction should occur (FR-032).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from floe_iceberg.errors import CompactionError
from floe_iceberg.models import CompactionStrategy
from floe_iceberg.telemetry import traced

if TYPE_CHECKING:
    # Type alias for PyIceberg Table (Any due to missing type stubs)
    Table = Any


class _IcebergCompactionManager:
    """Internal helper class for compaction operations.

    Encapsulates compaction operations for Iceberg tables.
    Maintains single-responsibility by focusing only on compaction.

    This class is internal and should not be used directly by external consumers.
    Use IcebergTableManager's public API instead.

    Note: The orchestrator (Dagster) is responsible for scheduling when
    to call compact_table(). This class only performs the execution.

    Attributes:
        _log: Structured logger instance.

    Example:
        >>> # Internal usage in IcebergTableManager
        >>> compaction_mgr = _IcebergCompactionManager()
        >>> files_rewritten = compaction_mgr.compact_table(table, strategy)
    """

    def __init__(self) -> None:
        """Initialize _IcebergCompactionManager."""
        self._log = structlog.get_logger(__name__)

    # =========================================================================
    # Compaction Operations
    # =========================================================================

    @traced(operation_name="iceberg.compaction.compact_table")
    def compact_table(
        self,
        table: Table,
        strategy: CompactionStrategy | None = None,
    ) -> int:
        """Compact table data files to optimize query performance.

        Rewrites small files into larger files using the specified strategy.
        This reduces metadata overhead and improves query performance.

        Note: The orchestrator (Dagster) is responsible for scheduling when
        to call this method. This method only performs the execution.

        Args:
            table: PyIceberg Table object.
            strategy: CompactionStrategy configuration. Defaults to BIN_PACK
                with 128MB target file size.

        Returns:
            Number of files rewritten during compaction.

        Raises:
            CompactionError: If compaction fails.

        Example:
            >>> from floe_iceberg.models import CompactionStrategy, CompactionStrategyType
            >>> strategy = CompactionStrategy(
            ...     strategy_type=CompactionStrategyType.BIN_PACK,
            ...     target_file_size_bytes=134217728,  # 128MB
            ... )
            >>> files_rewritten = compaction_mgr.compact_table(table, strategy)
            >>> print(f"Rewrote {files_rewritten} files")
        """
        from floe_iceberg.compaction import execute_compaction

        # Use default strategy if not provided
        if strategy is None:
            strategy = CompactionStrategy()

        table_identifier = str(getattr(table, "identifier", "unknown"))

        # Set span attributes for observability
        from opentelemetry import trace

        span = trace.get_current_span()
        span.set_attribute("table.identifier", table_identifier)
        span.set_attribute("strategy.type", strategy.strategy_type.value)
        span.set_attribute(
            "strategy.target_file_size_bytes", strategy.target_file_size_bytes
        )
        span.set_attribute(
            "strategy.max_concurrent_rewrites",
            strategy.max_concurrent_file_group_rewrites,
        )

        self._log.debug(
            "compact_table_requested",
            table_identifier=table_identifier,
            strategy_type=strategy.strategy_type.value,
            target_file_size_bytes=strategy.target_file_size_bytes,
        )

        try:
            # Execute compaction using the compaction module
            result = execute_compaction(table, strategy)
            files_rewritten = result.files_rewritten

            # Set files rewritten span attribute
            span.set_attribute("files.rewritten", files_rewritten)

            self._log.info(
                "compact_table_completed",
                table_identifier=table_identifier,
                strategy_type=strategy.strategy_type.value,
                files_rewritten=files_rewritten,
            )

            return files_rewritten

        except CompactionError as e:
            # Record error on OTel span and re-raise
            from opentelemetry.trace import Status, StatusCode

            span.set_status(Status(StatusCode.ERROR, "Compaction failed"))
            span.record_exception(e)

            self._log.error(
                "compact_table_failed",
                table_identifier=table_identifier,
                strategy_type=strategy.strategy_type.value,
                error=str(e),
            )
            raise


__all__ = ["_IcebergCompactionManager"]
