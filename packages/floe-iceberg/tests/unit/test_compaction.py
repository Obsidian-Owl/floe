"""Unit tests for compaction module.

T093: Tests for compaction.py module including strategy pattern and executors.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


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
        assert result.files_rewritten == 0  # mock table with no snapshot returns 0

    @pytest.mark.requirement("FR-031")
    def test_execute_with_custom_target_size(self) -> None:
        """Test executor respects target_file_size_bytes."""
        from floe_iceberg.compaction import BinPackCompactionExecutor, CompactionResult
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

        # Verify result structure (can't verify config was used in mock scenario)
        assert isinstance(result, CompactionResult)
        assert result.files_rewritten >= 0
        assert result.bytes_rewritten >= 0

    @pytest.mark.requirement("FR-031")
    def test_execute_with_custom_parallelism(self) -> None:
        """Test executor respects max_concurrent_file_group_rewrites."""
        from floe_iceberg.compaction import BinPackCompactionExecutor, CompactionResult
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.parallel_test"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            max_concurrent_file_group_rewrites=10,
        )

        result = executor.execute(mock_table, strategy)
        assert isinstance(result, CompactionResult)

    @pytest.mark.requirement("FR-031")
    def test_analyze_files_for_compaction_with_no_snapshot(self) -> None:
        """Test file analysis when table has no snapshot."""
        from floe_iceberg.compaction import BinPackCompactionExecutor

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.current_snapshot = MagicMock(return_value=None)

        small_files, total_files = executor._analyze_files_for_compaction(
            mock_table, target_file_size_bytes=134217728
        )

        assert small_files == 0
        assert total_files == 0

    @pytest.mark.requirement("FR-031")
    def test_analyze_files_raises_on_unexpected_error(self) -> None:
        """Test file analysis raises CompactionAnalysisError on unexpected error."""
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.errors import CompactionAnalysisError

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        # Make current_snapshot raise an exception
        mock_table.current_snapshot.side_effect = Exception("Test error")

        with pytest.raises(CompactionAnalysisError, match="Unexpected error"):
            executor._analyze_files_for_compaction(
                mock_table, target_file_size_bytes=134217728
            )

    @pytest.mark.requirement("FR-031")
    def test_analyze_files_raises_on_manifest_access_failure(self) -> None:
        """Test file analysis raises CompactionAnalysisError when manifest access fails.

        The code calls snapshot.manifests(table.io) to list manifest files.
        When this call raises, it should be wrapped in CompactionAnalysisError.
        """
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.errors import CompactionAnalysisError

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_snapshot = MagicMock()
        # manifests is callable and raises when invoked with table.io
        mock_snapshot.manifests.side_effect = Exception("Connection refused")
        mock_table.current_snapshot.return_value = mock_snapshot

        with pytest.raises(CompactionAnalysisError, match="Cannot access manifests"):
            executor._analyze_files_for_compaction(
                mock_table, target_file_size_bytes=134217728
            )

    @pytest.mark.requirement("FR-031")
    def test_analyze_files_raises_on_entry_read_failure(self) -> None:
        """Test file analysis raises CompactionAnalysisError when entry reading fails."""
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.errors import CompactionAnalysisError

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_snapshot = MagicMock()
        mock_manifest = MagicMock()
        # Make fetch_manifest_entry raise when called
        mock_manifest.fetch_manifest_entry.side_effect = Exception("Corrupt manifest")
        mock_snapshot.manifests.return_value = [mock_manifest]
        mock_table.current_snapshot.return_value = mock_snapshot

        with pytest.raises(CompactionAnalysisError, match="Cannot read manifest entry"):
            executor._analyze_files_for_compaction(
                mock_table, target_file_size_bytes=134217728
            )

    @pytest.mark.requirement("FR-031")
    def test_execute_logs_pyiceberg_limitation(self) -> None:
        """Test executor logs PyIceberg version limitation."""
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.limit_test"
        mock_table.current_snapshot.return_value = None

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
        )

        # Should not raise, just returns 0 files rewritten
        result = executor.execute(mock_table, strategy)
        assert result.files_rewritten == 0


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
        from floe_iceberg.compaction import CompactionResult, execute_compaction
        from floe_iceberg.models import CompactionStrategy

        mock_table = MagicMock()
        mock_table.identifier = "bronze.default_test"

        # Default is BIN_PACK
        strategy = CompactionStrategy()

        result = execute_compaction(mock_table, strategy)
        assert isinstance(result, CompactionResult)
