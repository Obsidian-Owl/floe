"""Unit tests for _IcebergCompactionManager class.

Task ID: T029
Phase: 6 - US4 (Split IcebergTableManager)
User Story: US4 - Split Large Classes
Requirements: FR-016

Tests for the _IcebergCompactionManager helper class that encapsulates compaction
operations. Written TDD-style before implementation (T033).

The _IcebergCompactionManager class will be extracted from IcebergTableManager
to reduce class complexity and improve single-responsibility adherence.

Operations covered:
- compact_table(): Compact table data files
- execute_compaction(): Low-level compaction execution
- BinPackCompactionExecutor: Bin-pack strategy implementation
- SortCompactionExecutor: Sort strategy implementation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from tests.conftest import MockCatalogPlugin, MockStoragePlugin


# =============================================================================
# Fixtures for Compaction Tests
# =============================================================================


@pytest.fixture
def compaction_manager(
    mock_catalog_plugin: MockCatalogPlugin,
    mock_storage_plugin: MockStoragePlugin,
) -> Any:
    """Create an IcebergTableManager with a table for compaction testing.

    The manager provides access to compaction operations. After T033,
    this fixture will return _IcebergCompactionManager directly.

    Args:
        mock_catalog_plugin: Mock catalog plugin fixture.
        mock_storage_plugin: Mock storage plugin fixture.

    Returns:
        IcebergTableManager configured for compaction testing.
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


@pytest.fixture
def table_for_compaction(compaction_manager: Any) -> Any:
    """Load test table configured for compaction testing.

    Args:
        compaction_manager: Manager with test table created.

    Returns:
        Mock table object configured for compaction tests.
    """
    table = compaction_manager.load_table("bronze.customers")

    # Configure current_snapshot for compaction analysis
    mock_snapshot = MagicMock()
    mock_snapshot.manifests.return_value = []  # Empty manifests (no files)
    table.current_snapshot.return_value = mock_snapshot

    return table


# =============================================================================
# Compact Table Tests (T029)
# =============================================================================


class TestCompactionManagerCompactTable:
    """Tests for _IcebergCompactionManager.compact_table() method."""

    @pytest.mark.requirement("FR-016")
    def test_compact_table_with_default_strategy(
        self,
        compaction_manager: Any,
        table_for_compaction: Any,
    ) -> None:
        """Test compact_table uses default BIN_PACK strategy."""
        from floe_iceberg.models import CompactionStrategyType

        with patch("floe_iceberg.compaction.execute_compaction") as mock_exec:
            mock_result = MagicMock()
            mock_result.files_rewritten = 5
            mock_exec.return_value = mock_result

            result = compaction_manager.compact_table(table_for_compaction)

            assert result == 5
            # Verify default strategy was used
            call_args = mock_exec.call_args
            strategy = call_args[0][1]
            assert strategy.strategy_type == CompactionStrategyType.BIN_PACK

    @pytest.mark.requirement("FR-016")
    def test_compact_table_with_custom_strategy(
        self,
        compaction_manager: Any,
        table_for_compaction: Any,
    ) -> None:
        """Test compact_table uses provided custom strategy."""
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        custom_strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            target_file_size_bytes=256 * 1024 * 1024,  # 256MB
            max_concurrent_file_group_rewrites=4,
        )

        with patch("floe_iceberg.compaction.execute_compaction") as mock_exec:
            mock_result = MagicMock()
            mock_result.files_rewritten = 10
            mock_exec.return_value = mock_result

            result = compaction_manager.compact_table(
                table_for_compaction, strategy=custom_strategy
            )

            assert result == 10
            # Verify custom strategy was passed
            call_args = mock_exec.call_args
            strategy = call_args[0][1]
            assert strategy.target_file_size_bytes == 256 * 1024 * 1024

    @pytest.mark.requirement("FR-016")
    def test_compact_table_returns_files_rewritten_count(
        self,
        compaction_manager: Any,
        table_for_compaction: Any,
    ) -> None:
        """Test compact_table returns the number of files rewritten."""
        with patch("floe_iceberg.compaction.execute_compaction") as mock_exec:
            mock_result = MagicMock()
            mock_result.files_rewritten = 15
            mock_exec.return_value = mock_result

            result = compaction_manager.compact_table(table_for_compaction)

            assert result == 15
            assert isinstance(result, int)

    @pytest.mark.requirement("FR-016")
    def test_compact_table_raises_compaction_error_on_failure(
        self,
        compaction_manager: Any,
        table_for_compaction: Any,
    ) -> None:
        """Test compact_table raises CompactionError when compaction fails."""
        from floe_iceberg.errors import CompactionError

        with patch("floe_iceberg.compaction.execute_compaction") as mock_exec:
            mock_exec.side_effect = CompactionError(
                "Compaction failed: disk full",
                table_identifier="bronze.customers",
                strategy="BIN_PACK",
            )

            with pytest.raises(CompactionError, match="disk full"):
                compaction_manager.compact_table(table_for_compaction)

    @pytest.mark.requirement("FR-016")
    def test_compact_table_with_sort_strategy(
        self,
        compaction_manager: Any,
        table_for_compaction: Any,
    ) -> None:
        """Test compact_table with SORT strategy."""
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        sort_strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.SORT,
            sort_columns=["id", "name"],
        )

        with patch("floe_iceberg.compaction.execute_compaction") as mock_exec:
            mock_result = MagicMock()
            mock_result.files_rewritten = 8
            mock_exec.return_value = mock_result

            result = compaction_manager.compact_table(table_for_compaction, strategy=sort_strategy)

            assert result == 8
            # Verify SORT strategy was used
            call_args = mock_exec.call_args
            strategy = call_args[0][1]
            assert strategy.strategy_type == CompactionStrategyType.SORT


# =============================================================================
# Execute Compaction Tests (T029)
# =============================================================================


class TestExecuteCompaction:
    """Tests for execute_compaction() function."""

    @pytest.mark.requirement("FR-016")
    def test_execute_compaction_with_bin_pack_strategy(self) -> None:
        """Test execute_compaction with BIN_PACK strategy."""
        from floe_iceberg.compaction import execute_compaction
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        mock_table = MagicMock()
        mock_table.identifier = "bronze.test"
        mock_table.current_snapshot.return_value = None

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            target_file_size_bytes=128 * 1024 * 1024,
        )

        result = execute_compaction(mock_table, strategy)

        # Verify result has expected attributes from CompactionResult
        assert isinstance(result.files_rewritten, int)
        assert result.files_rewritten >= 0
        assert isinstance(result.bytes_rewritten, int)
        assert result.bytes_rewritten >= 0

    @pytest.mark.requirement("FR-016")
    def test_execute_compaction_with_sort_strategy(self) -> None:
        """Test execute_compaction with SORT strategy and sort_columns."""
        from floe_iceberg.compaction import execute_compaction
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        mock_table = MagicMock()
        mock_table.identifier = "bronze.test"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.SORT,
            sort_columns=["date", "customer_id"],
        )

        result = execute_compaction(mock_table, strategy)

        # Verify result has expected attributes from CompactionResult
        assert isinstance(result.files_rewritten, int)
        assert result.files_rewritten >= 0
        assert isinstance(result.bytes_rewritten, int)
        assert result.bytes_rewritten >= 0

    @pytest.mark.requirement("FR-016")
    def test_execute_compaction_sort_without_columns_rejected_by_pydantic(self) -> None:
        """Test SORT strategy without sort_columns is rejected by Pydantic validation."""
        from pydantic import ValidationError

        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        # The CompactionStrategy model validates that SORT requires sort_columns
        with pytest.raises(ValidationError, match="sort_columns"):
            CompactionStrategy(
                strategy_type=CompactionStrategyType.SORT,
                # sort_columns=None (missing) - Pydantic rejects this
            )


# =============================================================================
# Compaction Executor Tests (T029)
# =============================================================================


class TestBinPackCompactionExecutor:
    """Tests for BinPackCompactionExecutor."""

    @pytest.mark.requirement("FR-016")
    def test_bin_pack_executor_returns_compaction_result(self) -> None:
        """Test BinPackCompactionExecutor returns CompactionResult."""
        from floe_iceberg.compaction import (
            BinPackCompactionExecutor,
            CompactionResult,
        )
        from floe_iceberg.models import CompactionStrategy

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.test"
        mock_table.current_snapshot.return_value = None

        strategy = CompactionStrategy()

        result = executor.execute(mock_table, strategy)

        assert isinstance(result, CompactionResult)

    @pytest.mark.requirement("FR-016")
    def test_bin_pack_executor_analyzes_file_sizes(self) -> None:
        """Test BinPackCompactionExecutor analyzes files below target size."""
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.models import CompactionStrategy

        executor = BinPackCompactionExecutor()

        # Create mock table with snapshot and manifests
        mock_table = MagicMock()
        mock_table.identifier = "bronze.test"
        mock_table.io = MagicMock()

        # Configure snapshot with small files
        mock_snapshot = MagicMock()
        mock_manifest = MagicMock()

        mock_entry = MagicMock()
        mock_entry.data_file.file_size_in_bytes = 10 * 1024 * 1024  # 10MB (small)

        mock_manifest.fetch_manifest_entry.return_value = [mock_entry]
        mock_snapshot.manifests.return_value = [mock_manifest]
        mock_table.current_snapshot.return_value = mock_snapshot

        strategy = CompactionStrategy(
            target_file_size_bytes=128 * 1024 * 1024  # 128MB target
        )

        # Execute should complete without error and return a valid result
        result = executor.execute(mock_table, strategy)

        # Verify result has expected structure
        assert isinstance(result.files_rewritten, int)
        assert isinstance(result.bytes_rewritten, int)

    @pytest.mark.requirement("FR-016")
    def test_bin_pack_executor_handles_empty_table(self) -> None:
        """Test BinPackCompactionExecutor handles table with no files."""
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.models import CompactionStrategy

        executor = BinPackCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.empty"
        mock_table.current_snapshot.return_value = None  # No snapshot

        strategy = CompactionStrategy()

        result = executor.execute(mock_table, strategy)

        assert result.files_rewritten == 0


class TestSortCompactionExecutor:
    """Tests for SortCompactionExecutor."""

    @pytest.mark.requirement("FR-016")
    def test_sort_executor_requires_sort_columns_validated_by_pydantic(self) -> None:
        """Test SORT strategy without sort_columns is rejected by Pydantic.

        The CompactionStrategy model has a @model_validator that requires
        sort_columns when strategy_type is SORT. This validation happens
        at model construction, before the executor is ever invoked.
        """
        from pydantic import ValidationError

        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        # Pydantic model validation rejects SORT without sort_columns
        with pytest.raises(ValidationError, match="sort_columns"):
            CompactionStrategy(
                strategy_type=CompactionStrategyType.SORT,
                # sort_columns is None - rejected by model validator
            )

    @pytest.mark.requirement("FR-016")
    def test_sort_executor_with_valid_sort_columns(self) -> None:
        """Test SortCompactionExecutor succeeds with valid sort_columns."""
        from floe_iceberg.compaction import CompactionResult, SortCompactionExecutor
        from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

        executor = SortCompactionExecutor()
        mock_table = MagicMock()
        mock_table.identifier = "bronze.test"

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.SORT,
            sort_columns=["date", "customer_id"],
        )

        result = executor.execute(mock_table, strategy)

        assert isinstance(result, CompactionResult)


# =============================================================================
# Get Compaction Executor Tests (T029)
# =============================================================================


class TestGetCompactionExecutor:
    """Tests for get_compaction_executor() factory function."""

    @pytest.mark.requirement("FR-016")
    def test_get_executor_returns_bin_pack_for_bin_pack_strategy(self) -> None:
        """Test get_compaction_executor returns BinPackCompactionExecutor."""
        from floe_iceberg.compaction import (
            BinPackCompactionExecutor,
            get_compaction_executor,
        )
        from floe_iceberg.models import CompactionStrategyType

        executor = get_compaction_executor(CompactionStrategyType.BIN_PACK)

        assert isinstance(executor, BinPackCompactionExecutor)

    @pytest.mark.requirement("FR-016")
    def test_get_executor_returns_sort_for_sort_strategy(self) -> None:
        """Test get_compaction_executor returns SortCompactionExecutor."""
        from floe_iceberg.compaction import (
            SortCompactionExecutor,
            get_compaction_executor,
        )
        from floe_iceberg.models import CompactionStrategyType

        executor = get_compaction_executor(CompactionStrategyType.SORT)

        assert isinstance(executor, SortCompactionExecutor)


# =============================================================================
# Compaction Result Tests (T029)
# =============================================================================


class TestCompactionResult:
    """Tests for CompactionResult data class."""

    @pytest.mark.requirement("FR-016")
    def test_compaction_result_default_values(self) -> None:
        """Test CompactionResult has sensible defaults."""
        from floe_iceberg.compaction import CompactionResult

        result = CompactionResult()

        assert result.files_rewritten == 0
        assert result.bytes_rewritten == 0
        assert result.files_added == 0
        assert result.files_removed == 0

    @pytest.mark.requirement("FR-016")
    def test_compaction_result_with_values(self) -> None:
        """Test CompactionResult stores provided values."""
        from floe_iceberg.compaction import CompactionResult

        result = CompactionResult(
            files_rewritten=10,
            bytes_rewritten=1024 * 1024 * 100,  # 100MB
            files_added=3,
            files_removed=10,
        )

        assert result.files_rewritten == 10
        assert result.bytes_rewritten == 104857600
        assert result.files_added == 3
        assert result.files_removed == 10

    @pytest.mark.requirement("FR-016")
    def test_compaction_result_repr(self) -> None:
        """Test CompactionResult has useful repr."""
        from floe_iceberg.compaction import CompactionResult

        result = CompactionResult(files_rewritten=5)

        repr_str = repr(result)
        assert "CompactionResult" in repr_str
        assert "files_rewritten=5" in repr_str


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestCompactionEdgeCases:
    """Edge case tests for compaction operations."""

    @pytest.mark.requirement("FR-016")
    def test_compact_table_with_no_files_returns_zero(
        self,
        compaction_manager: Any,
        table_for_compaction: Any,
    ) -> None:
        """Test compacting table with no files returns 0."""
        with patch("floe_iceberg.compaction.execute_compaction") as mock_exec:
            mock_result = MagicMock()
            mock_result.files_rewritten = 0
            mock_exec.return_value = mock_result

            result = compaction_manager.compact_table(table_for_compaction)

            assert result == 0

    @pytest.mark.requirement("FR-016")
    def test_compaction_strategy_model_validation(self) -> None:
        """Test CompactionStrategy validates field constraints."""
        from pydantic import ValidationError

        from floe_iceberg.models import CompactionStrategy

        # target_file_size_bytes must be >= 1MB
        with pytest.raises(ValidationError, match="target_file_size_bytes"):
            CompactionStrategy(target_file_size_bytes=100)  # 100 bytes < 1MB min

        # target_file_size_bytes must be <= 1GB
        with pytest.raises(ValidationError, match="target_file_size_bytes"):
            CompactionStrategy(
                target_file_size_bytes=2 * 1024 * 1024 * 1024  # 2GB > 1GB max
            )

    @pytest.mark.requirement("FR-016")
    def test_bin_pack_executor_raises_compaction_error_on_analysis_failure(
        self,
    ) -> None:
        """Test BinPackCompactionExecutor raises CompactionError when analysis fails.

        When _analyze_files_for_compaction raises CompactionAnalysisError,
        execute() wraps it in CompactionError and propagates rather than
        silently returning (0, 0).
        """
        from floe_iceberg.compaction import BinPackCompactionExecutor
        from floe_iceberg.errors import CompactionError
        from floe_iceberg.models import CompactionStrategy

        executor = BinPackCompactionExecutor()

        # Create table that raises exception on current_snapshot
        mock_table = MagicMock()
        mock_table.identifier = "bronze.test"
        mock_table.current_snapshot.side_effect = RuntimeError("Connection lost")

        strategy = CompactionStrategy()

        # Executor wraps analysis errors in CompactionError
        with pytest.raises(CompactionError, match="Bin-pack compaction failed"):
            executor.execute(mock_table, strategy)


__all__ = [
    "TestCompactionManagerCompactTable",
    "TestExecuteCompaction",
    "TestBinPackCompactionExecutor",
    "TestSortCompactionExecutor",
    "TestGetCompactionExecutor",
    "TestCompactionResult",
    "TestCompactionEdgeCases",
]
