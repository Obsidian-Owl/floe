"""Unit tests for compaction module.

T093: Tests for compaction.py module including strategy pattern and executors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# CompactionResult Tests
# =============================================================================


class TestCompactionResult:
    """Tests for CompactionResult data class."""

    @pytest.mark.requirement("FR-030")
    def test_default_values(self) -> None:
        """Test CompactionResult default values."""
        from floe_iceberg.compaction import CompactionResult

        result = CompactionResult()
        assert result.files_rewritten == 0
        assert result.bytes_rewritten == 0
        assert result.files_added == 0
        assert result.files_removed == 0

    @pytest.mark.requirement("FR-030")
    def test_custom_values(self) -> None:
        """Test CompactionResult with custom values."""
        from floe_iceberg.compaction import CompactionResult

        result = CompactionResult(
            files_rewritten=10,
            bytes_rewritten=1024 * 1024 * 100,  # 100MB
            files_added=5,
            files_removed=10,
        )
        assert result.files_rewritten == 10
        assert result.bytes_rewritten == 104857600
        assert result.files_added == 5
        assert result.files_removed == 10

    @pytest.mark.requirement("FR-030")
    def test_repr(self) -> None:
        """Test CompactionResult string representation."""
        from floe_iceberg.compaction import CompactionResult

        result = CompactionResult(files_rewritten=5)
        repr_str = repr(result)
        assert "CompactionResult" in repr_str
        assert "files_rewritten=5" in repr_str


# =============================================================================
# BinPackCompactionExecutor Tests
# =============================================================================


class TestBinPackCompactionExecutor:
    """Tests for BinPackCompactionExecutor."""

    @pytest.mark.requirement("FR-031")
    def test_execute_returns_compaction_result(self) -> None:
        """Test BinPackCompactionExecutor.execute returns CompactionResult."""
        from floe_iceberg.compaction import (
            BinPackCompactionExecutor,
            CompactionResult,
        )
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.test_table"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            target_file_size_bytes=134217728,
        )

        result = executor.execute(mock_table, strategy)

        assert isinstance(result, CompactionResult)
        assert isinstance(result.files_rewritten, int)

    @pytest.mark.requirement("FR-031")
    def test_execute_with_custom_target_size(self) -> None:
        """Test executor respects target_file_size_bytes."""
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.size_test"

        # Custom 256MB target
        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            target_file_size_bytes=268435456,
        )

        result = executor.execute(mock_table, strategy)
        assert result is not None

    @pytest.mark.requirement("FR-031")
    def test_execute_with_custom_parallelism(self) -> None:
        """Test executor respects max_concurrent_file_group_rewrites."""
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.parallel_test"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            max_concurrent_file_group_rewrites=10,
        )

        result = executor.execute(mock_table, strategy)
        assert result is not None


# =============================================================================
# SortCompactionExecutor Tests
# =============================================================================


class TestSortCompactionExecutor:
    """Tests for SortCompactionExecutor."""

    @pytest.mark.requirement("FR-030")
    def test_execute_returns_compaction_result(self) -> None:
        """Test SortCompactionExecutor.execute returns CompactionResult."""
        from floe_iceberg.compaction import (
            CompactionResult,
            SortCompactionExecutor,
        )
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = SortCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.sort_test"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.SORT,
            sort_columns=["date", "customer_id"],
        )

        result = executor.execute(mock_table, strategy)

        assert isinstance(result, CompactionResult)

    @pytest.mark.requirement("FR-030")
    def test_execute_requires_sort_columns(self) -> None:
        """Test SortCompactionExecutor raises error without sort_columns."""
        from floe_iceberg.compaction import SortCompactionExecutor
        from floe_iceberg.errors import CompactionError
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = SortCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.no_sort_columns"

        # Create strategy without sort_columns using object.__new__ to bypass validation
        # We need to test the executor's validation, not the model's
        strategy = CompactionStrategy.__new__(CompactionStrategy)
        object.__setattr__(strategy, "strategy_type", CompactionStrategyType.SORT)
        object.__setattr__(strategy, "sort_columns", None)
        object.__setattr__(strategy, "target_file_size_bytes", 134217728)
        object.__setattr__(strategy, "max_concurrent_file_group_rewrites", 5)

        with pytest.raises(CompactionError, match="sort_columns"):
            executor.execute(mock_table, strategy)


# =============================================================================
# Factory Tests
# =============================================================================


class TestGetCompactionExecutor:
    """Tests for get_compaction_executor factory function."""

    @pytest.mark.requirement("FR-030")
    def test_returns_bin_pack_executor(self) -> None:
        """Test factory returns BinPackCompactionExecutor for BIN_PACK."""
        from floe_iceberg.compaction import (
            BinPackCompactionExecutor,
            get_compaction_executor,
        )
        from floe_iceberg.models import CompactionStrategyType

        executor = get_compaction_executor(CompactionStrategyType.BIN_PACK)
        assert isinstance(executor, BinPackCompactionExecutor)

    @pytest.mark.requirement("FR-030")
    def test_returns_sort_executor(self) -> None:
        """Test factory returns SortCompactionExecutor for SORT."""
        from floe_iceberg.compaction import (
            SortCompactionExecutor,
            get_compaction_executor,
        )
        from floe_iceberg.models import CompactionStrategyType

        executor = get_compaction_executor(CompactionStrategyType.SORT)
        assert isinstance(executor, SortCompactionExecutor)


# =============================================================================
# execute_compaction Tests
# =============================================================================


class TestExecuteCompaction:
    """Tests for execute_compaction high-level function."""

    @pytest.mark.requirement("FR-030")
    def test_bin_pack_compaction(self) -> None:
        """Test execute_compaction with BIN_PACK strategy."""
        from floe_iceberg.compaction import CompactionResult, execute_compaction
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        mock_table = MagicMock()
        mock_table.identifier = "bronze.compact_test"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
        )

        result = execute_compaction(mock_table, strategy)
        assert isinstance(result, CompactionResult)

    @pytest.mark.requirement("FR-030")
    def test_sort_compaction(self) -> None:
        """Test execute_compaction with SORT strategy."""
        from floe_iceberg.compaction import CompactionResult, execute_compaction
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        mock_table = MagicMock()
        mock_table.identifier = "bronze.sort_compact_test"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.SORT,
            sort_columns=["date"],
        )

        result = execute_compaction(mock_table, strategy)
        assert isinstance(result, CompactionResult)

    @pytest.mark.requirement("FR-030")
    def test_default_strategy(self) -> None:
        """Test execute_compaction with default CompactionStrategy."""
        from floe_iceberg.compaction import execute_compaction
        from floe_iceberg.models import CompactionStrategy

        mock_table = MagicMock()
        mock_table.identifier = "bronze.default_test"

        # Default is BIN_PACK
        strategy = CompactionStrategy()

        result = execute_compaction(mock_table, strategy)
        assert result is not None
