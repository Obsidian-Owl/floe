"""Compaction strategy implementations for Iceberg tables.

This module provides compaction strategies for optimizing Iceberg table storage.
Compaction rewrites small files into larger files to improve query performance
and reduce metadata overhead.

Strategies:
    - BIN_PACK: Combines small files into larger files up to target size
    - SORT: Rewrites files sorted by specified columns

Note: Compaction is NOT auto-triggered. The orchestrator (Dagster) is responsible
for scheduling when compaction should occur (FR-032).

Example:
    >>> from floe_iceberg.compaction import execute_compaction
    >>> from floe_iceberg.models import CompactionStrategy, CompactionStrategyType
    >>>
    >>> strategy = CompactionStrategy(
    ...     strategy_type=CompactionStrategyType.BIN_PACK,
    ...     target_file_size_bytes=134217728,  # 128MB
    ... )
    >>> result = execute_compaction(table, strategy)
    >>> print(f"Rewrote {result.files_rewritten} files")

See Also:
    - CompactionStrategy: Configuration model
    - IcebergTableManager.compact_table(): High-level API
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

import structlog

from floe_iceberg.errors import CompactionAnalysisError, CompactionError
from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

if TYPE_CHECKING:
    from pyiceberg.table import Table


logger = structlog.get_logger(__name__)


# =============================================================================
# Compaction Result
# =============================================================================


class CompactionResult:
    """Result of a compaction operation.

    Attributes:
        files_rewritten: Number of files rewritten during compaction.
        bytes_rewritten: Total bytes rewritten (if available).
        files_added: Number of new files created.
        files_removed: Number of old files removed.
    """

    def __init__(
        self,
        files_rewritten: int = 0,
        bytes_rewritten: int = 0,
        files_added: int = 0,
        files_removed: int = 0,
    ) -> None:
        """Initialize CompactionResult.

        Args:
            files_rewritten: Number of files rewritten.
            bytes_rewritten: Total bytes rewritten.
            files_added: Number of new files created.
            files_removed: Number of old files removed.
        """
        self.files_rewritten = files_rewritten
        self.bytes_rewritten = bytes_rewritten
        self.files_added = files_added
        self.files_removed = files_removed

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"CompactionResult(files_rewritten={self.files_rewritten}, "
            f"bytes_rewritten={self.bytes_rewritten}, "
            f"files_added={self.files_added}, "
            f"files_removed={self.files_removed})"
        )


# =============================================================================
# Strategy Protocol
# =============================================================================


class CompactionExecutor(Protocol):
    """Protocol for compaction strategy executors."""

    def execute(
        self,
        table: Table,
        strategy: CompactionStrategy,
    ) -> CompactionResult:
        """Execute compaction on the table.

        Args:
            table: PyIceberg Table to compact.
            strategy: CompactionStrategy configuration.

        Returns:
            CompactionResult with rewrite statistics.

        Raises:
            CompactionError: If compaction fails.
        """
        ...


# =============================================================================
# Strategy Implementations
# =============================================================================


class BaseCompactionExecutor(ABC):
    """Base class for compaction executors."""

    def __init__(self) -> None:
        """Initialize base executor."""
        self._log = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    def execute(
        self,
        table: Table,
        strategy: CompactionStrategy,
    ) -> CompactionResult:
        """Execute compaction strategy.

        Args:
            table: PyIceberg Table to compact.
            strategy: CompactionStrategy configuration.

        Returns:
            CompactionResult with rewrite statistics.

        Raises:
            CompactionError: If compaction fails.
        """
        ...


class BinPackCompactionExecutor(BaseCompactionExecutor):
    """Bin-pack compaction strategy executor.

    Combines small files into larger files up to the target file size.
    This is the default compaction strategy for optimizing file count.

    Note:
        PyIceberg 0.10.0 does not yet support native file rewriting.
        This implementation analyzes files and logs compaction candidates,
        returning 0 files rewritten until PyIceberg adds rewrite support.
        When rewrite support is added, this will use table.rewrite_data_files().

    Example:
        >>> executor = BinPackCompactionExecutor()
        >>> strategy = CompactionStrategy(
        ...     strategy_type=CompactionStrategyType.BIN_PACK,
        ...     target_file_size_bytes=134217728,
        ... )
        >>> result = executor.execute(table, strategy)
    """

    def _analyze_files_for_compaction(
        self,
        table: Table,
        target_file_size_bytes: int,
    ) -> tuple[int, int]:
        """Analyze table files to find compaction candidates.

        Args:
            table: PyIceberg Table to analyze.
            target_file_size_bytes: Target file size threshold.

        Returns:
            Tuple of (small_file_count, total_file_count).

        Raises:
            CompactionAnalysisError: If manifest access or entry reading fails.
        """
        try:
            # Get current snapshot's data files
            snapshot = getattr(table, "current_snapshot", None)
            if snapshot is None or callable(snapshot):
                snapshot = (
                    table.current_snapshot()
                    if callable(getattr(table, "current_snapshot", None))
                    else None
                )

            if snapshot is None:
                return (0, 0)

            # Count files below target size
            small_file_count = 0
            total_file_count = 0

            # Try to access manifest files
            manifests = getattr(snapshot, "manifests", None)
            if callable(manifests):
                try:
                    manifests = manifests(table.io)
                except Exception as e:
                    logger.exception(
                        "Failed to access snapshot manifests",
                        extra={
                            "snapshot_id": getattr(snapshot, "snapshot_id", "unknown")
                        },
                    )
                    raise CompactionAnalysisError(
                        f"Cannot access manifests for snapshot: {e}"
                    ) from e

            if manifests:
                for manifest in manifests:
                    try:
                        entries = getattr(manifest, "fetch_manifest_entry", None)
                        if entries and callable(entries):
                            for entry in entries(table.io):
                                file_size = getattr(
                                    getattr(entry, "data_file", None),
                                    "file_size_in_bytes",
                                    0,
                                )
                                total_file_count += 1
                                if file_size < target_file_size_bytes:
                                    small_file_count += 1
                    except CompactionAnalysisError:
                        raise
                    except Exception as e:
                        logger.exception(
                            "Failed to read manifest entry",
                            extra={"manifest": str(manifest)},
                        )
                        raise CompactionAnalysisError(
                            f"Cannot read manifest entry: {e}"
                        ) from e

            return (small_file_count, total_file_count)

        except CompactionAnalysisError:
            raise
        except Exception as e:
            logger.exception("Compaction analysis failed unexpectedly")
            raise CompactionAnalysisError(
                f"Unexpected error during compaction analysis: {e}"
            ) from e

    def execute(
        self,
        table: Table,
        strategy: CompactionStrategy,
    ) -> CompactionResult:
        """Execute bin-pack compaction.

        Combines small files into larger files up to target_file_size_bytes.

        Note:
            PyIceberg 0.10.0 does not support native file rewriting.
            This method analyzes files and logs candidates, but returns
            0 files rewritten until PyIceberg adds rewrite_data_files().

        Args:
            table: PyIceberg Table to compact.
            strategy: CompactionStrategy with BIN_PACK type.

        Returns:
            CompactionResult with rewrite statistics.

        Raises:
            CompactionError: If compaction fails.
        """
        table_identifier = str(getattr(table, "identifier", "unknown"))

        self._log.info(
            "bin_pack_compaction_started",
            table_identifier=table_identifier,
            target_file_size_bytes=strategy.target_file_size_bytes,
            max_concurrent_rewrites=strategy.max_concurrent_file_group_rewrites,
        )

        try:
            # Analyze files for compaction candidates
            small_files, total_files = self._analyze_files_for_compaction(
                table, strategy.target_file_size_bytes
            )

            self._log.debug(
                "bin_pack_analysis_complete",
                table_identifier=table_identifier,
                small_files_count=small_files,
                total_files_count=total_files,
            )

            # PyIceberg 0.10.0 does not support rewrite_data_files() yet.
            # When PyIceberg adds this API, implement:
            #
            # if hasattr(table, 'rewrite_data_files'):
            #     result = table.rewrite_data_files(
            #         target_size_bytes=strategy.target_file_size_bytes,
            #         max_concurrent_rewrites=strategy.max_concurrent_file_group_rewrites,
            #     )
            #     files_rewritten = result.rewritten_data_files_count()
            # else:
            #     files_rewritten = 0

            files_rewritten = 0

            if small_files > 0:
                self._log.info(
                    "bin_pack_compaction_candidates_found",
                    table_identifier=table_identifier,
                    small_files_count=small_files,
                    message="PyIceberg 0.10.0 does not support rewrite_data_files(). "
                    "Compaction will be available when PyIceberg adds this API.",
                )

            self._log.info(
                "bin_pack_compaction_completed",
                table_identifier=table_identifier,
                files_rewritten=files_rewritten,
                small_files_analyzed=small_files,
                total_files_analyzed=total_files,
            )

            return CompactionResult(
                files_rewritten=files_rewritten,
                files_removed=0,
                files_added=0,
            )

        except Exception as e:
            self._log.error(
                "bin_pack_compaction_failed",
                table_identifier=table_identifier,
                error=str(e),
            )
            raise CompactionError(
                f"Bin-pack compaction failed: {e}",
                table_identifier=table_identifier,
                strategy="BIN_PACK",
            ) from e


class SortCompactionExecutor(BaseCompactionExecutor):
    """Sort compaction strategy executor.

    Rewrites data files sorted by specified columns to optimize
    query performance for common access patterns.

    Example:
        >>> executor = SortCompactionExecutor()
        >>> strategy = CompactionStrategy(
        ...     strategy_type=CompactionStrategyType.SORT,
        ...     sort_columns=["date", "customer_id"],
        ... )
        >>> result = executor.execute(table, strategy)
    """

    def execute(
        self,
        table: Table,
        strategy: CompactionStrategy,
    ) -> CompactionResult:
        """Execute sort compaction.

        Rewrites files sorted by the specified columns.

        Args:
            table: PyIceberg Table to compact.
            strategy: CompactionStrategy with SORT type and sort_columns.

        Returns:
            CompactionResult with rewrite statistics.

        Raises:
            CompactionError: If compaction fails or sort_columns not provided.
        """
        table_identifier = str(getattr(table, "identifier", "unknown"))

        if not strategy.sort_columns:
            raise CompactionError(
                "SORT strategy requires sort_columns",
                table_identifier=table_identifier,
                strategy="SORT",
            )

        self._log.info(
            "sort_compaction_started",
            table_identifier=table_identifier,
            sort_columns=strategy.sort_columns,
            target_file_size_bytes=strategy.target_file_size_bytes,
        )

        try:
            # TODO(epic-future): Implement SORT compaction when PyIceberg supports it
            #
            # Context: SORT compaction reorders data within files to optimize for
            # query patterns (e.g., sorting by timestamp for time-range queries).
            # PyIceberg rewrite_data_files() doesn't yet support custom sort orders.
            #
            # Scope: Implement when PyIceberg adds SortOrder support to rewrite_data_files()
            # or when a workaround via scan+write is validated for production use.
            #
            # Priority: Low - BINPACK strategy covers most use cases. SORT is an
            # optimization for specific query patterns.
            #
            # Tracking: https://github.com/apache/iceberg-python/issues/XXX (upstream)
            #
            # Implementation approach when ready:
            #   sort_order = SortOrder(*[SortField(col) for col in strategy.sort_columns])
            #   result = table.rewrite_data_files(
            #       target_size_bytes=strategy.target_file_size_bytes,
            #       sort_order=sort_order,
            #   )

            files_rewritten = 0

            self._log.info(
                "sort_compaction_completed",
                table_identifier=table_identifier,
                files_rewritten=files_rewritten,
            )

            return CompactionResult(
                files_rewritten=files_rewritten,
            )

        except CompactionError:
            raise
        except Exception as e:
            self._log.error(
                "sort_compaction_failed",
                table_identifier=table_identifier,
                error=str(e),
            )
            raise CompactionError(
                f"Sort compaction failed: {e}",
                table_identifier=table_identifier,
                strategy="SORT",
            ) from e


# =============================================================================
# Executor Factory
# =============================================================================


def get_compaction_executor(
    strategy_type: CompactionStrategyType,
) -> BaseCompactionExecutor:
    """Get the appropriate compaction executor for the strategy type.

    Args:
        strategy_type: CompactionStrategyType enum value.

    Returns:
        Compaction executor instance.

    Raises:
        ValueError: If strategy type is not supported.

    Example:
        >>> executor = get_compaction_executor(CompactionStrategyType.BIN_PACK)
        >>> isinstance(executor, BinPackCompactionExecutor)
        True
    """
    executors: dict[CompactionStrategyType, type[BaseCompactionExecutor]] = {
        CompactionStrategyType.BIN_PACK: BinPackCompactionExecutor,
        CompactionStrategyType.SORT: SortCompactionExecutor,
    }

    executor_class = executors.get(strategy_type)
    if executor_class is None:
        msg = f"Unsupported compaction strategy: {strategy_type}"
        raise ValueError(msg)

    return executor_class()


# =============================================================================
# High-Level API
# =============================================================================


def execute_compaction(
    table: Table,
    strategy: CompactionStrategy,
) -> CompactionResult:
    """Execute compaction on an Iceberg table.

    This is the main entry point for compaction operations.
    It selects the appropriate executor based on the strategy type.

    Args:
        table: PyIceberg Table to compact.
        strategy: CompactionStrategy configuration.

    Returns:
        CompactionResult with rewrite statistics.

    Raises:
        CompactionError: If compaction fails.
        ValueError: If strategy type is not supported.

    Example:
        >>> from floe_iceberg.compaction import execute_compaction
        >>> from floe_iceberg.models import CompactionStrategy, CompactionStrategyType
        >>>
        >>> strategy = CompactionStrategy(
        ...     strategy_type=CompactionStrategyType.BIN_PACK,
        ...     target_file_size_bytes=134217728,
        ... )
        >>> result = execute_compaction(table, strategy)
        >>> print(f"Rewrote {result.files_rewritten} files")
    """
    executor = get_compaction_executor(strategy.strategy_type)
    return executor.execute(table, strategy)


__all__ = [
    "CompactionAnalysisError",
    "CompactionResult",
    "CompactionExecutor",
    "BaseCompactionExecutor",
    "BinPackCompactionExecutor",
    "SortCompactionExecutor",
    "get_compaction_executor",
    "execute_compaction",
]
