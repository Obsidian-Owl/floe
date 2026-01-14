"""Unit tests for ops/batch.py - batch operations module.

Tests for batch loading functionality:
- BatchResult model and metrics
- BatchProgress model
- BatchCheckpoint for resume support
- batch_load: Batch file loading with checkpointing
- load_checkpoint/save_checkpoint: Checkpoint persistence
- clear_checkpoint: Checkpoint cleanup

Implementation: T039 (FLO-624)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    pass


class TestBatchResult:
    """Tests for BatchResult model."""

    @pytest.mark.requirement("FR-018")
    def test_batch_result_has_required_fields(self) -> None:
        """Test BatchResult model has all required fields."""
        from agent_memory.ops.batch import BatchResult

        result = BatchResult(
            total_files=10,
            successful_files=8,
            failed_files=["file1.py", "file2.py"],
            batches_completed=2,
            duration_seconds=5.5,
            resumed_from_checkpoint=False,
        )

        assert result.total_files == 10
        assert result.successful_files == 8
        assert result.failed_files == ["file1.py", "file2.py"]
        assert result.batches_completed == 2
        assert result.duration_seconds == pytest.approx(5.5)
        assert result.resumed_from_checkpoint is False

    @pytest.mark.requirement("FR-018")
    def test_batch_result_success_rate(self) -> None:
        """Test BatchResult.success_rate property."""
        from agent_memory.ops.batch import BatchResult

        result = BatchResult(
            total_files=10,
            successful_files=8,
            failed_files=[],
            batches_completed=1,
            duration_seconds=1.0,
        )

        assert result.success_rate == pytest.approx(80.0)

    @pytest.mark.requirement("FR-018")
    def test_batch_result_success_rate_zero_files(self) -> None:
        """Test BatchResult.success_rate with zero files."""
        from agent_memory.ops.batch import BatchResult

        result = BatchResult(
            total_files=0,
            successful_files=0,
            failed_files=[],
            batches_completed=0,
            duration_seconds=0.0,
        )

        assert result.success_rate == pytest.approx(100.0)

    @pytest.mark.requirement("FR-018")
    def test_batch_result_has_failures_property(self) -> None:
        """Test BatchResult.has_failures property."""
        from agent_memory.ops.batch import BatchResult

        no_failures = BatchResult(
            total_files=5,
            successful_files=5,
            failed_files=[],
            batches_completed=1,
            duration_seconds=1.0,
        )
        assert no_failures.has_failures is False

        with_failures = BatchResult(
            total_files=5,
            successful_files=4,
            failed_files=["failed.py"],
            batches_completed=1,
            duration_seconds=1.0,
        )
        assert with_failures.has_failures is True


class TestBatchProgress:
    """Tests for BatchProgress model."""

    @pytest.mark.requirement("FR-018")
    def test_batch_progress_model(self) -> None:
        """Test BatchProgress model has all required fields."""
        from agent_memory.ops.batch import BatchProgress

        progress = BatchProgress(
            current_batch=2,
            total_batches=5,
            files_processed=40,
            total_files=100,
            current_file="test.py",
        )

        assert progress.current_batch == 2
        assert progress.total_batches == 5
        assert progress.files_processed == 40
        assert progress.total_files == 100
        assert progress.current_file == "test.py"

    @pytest.mark.requirement("FR-018")
    def test_batch_progress_percentage(self) -> None:
        """Test BatchProgress.progress_percentage property."""
        from agent_memory.ops.batch import BatchProgress

        progress = BatchProgress(
            current_batch=1,
            total_batches=2,
            files_processed=50,
            total_files=100,
            current_file="test.py",
        )

        assert progress.progress_percentage == pytest.approx(50.0)

    @pytest.mark.requirement("FR-018")
    def test_batch_progress_zero_files(self) -> None:
        """Test BatchProgress.progress_percentage with zero files."""
        from agent_memory.ops.batch import BatchProgress

        progress = BatchProgress(
            current_batch=1,
            total_batches=1,
            files_processed=0,
            total_files=0,
            current_file="",
        )

        assert progress.progress_percentage == pytest.approx(100.0)


class TestBatchCheckpoint:
    """Tests for BatchCheckpoint model."""

    @pytest.mark.requirement("FR-018")
    def test_batch_checkpoint_model(self) -> None:
        """Test BatchCheckpoint model has all required fields."""
        from datetime import datetime

        from agent_memory.ops.batch import BatchCheckpoint

        checkpoint = BatchCheckpoint(
            processed_files=["file1.py", "file2.py"],
            last_batch=2,
            started_at=datetime(2024, 1, 15),
            updated_at=datetime(2024, 1, 15),
        )

        assert checkpoint.processed_files == ["file1.py", "file2.py"]
        assert checkpoint.last_batch == 2
        assert checkpoint.started_at.year == 2024


class TestCheckpointPersistence:
    """Tests for checkpoint load/save/clear functions."""

    @pytest.mark.requirement("FR-018")
    def test_save_and_load_checkpoint(self, tmp_path: Path) -> None:
        """Test checkpoint can be saved and loaded."""
        from agent_memory.ops.batch import (
            BatchCheckpoint,
            load_checkpoint,
            save_checkpoint,
        )

        # Create checkpoint
        checkpoint = BatchCheckpoint(
            processed_files=["file1.py", "file2.py"],
            last_batch=3,
        )

        # Save it
        save_checkpoint(checkpoint, tmp_path)

        # Verify file exists
        checkpoint_path = tmp_path / ".cognee" / "checkpoint.json"
        assert checkpoint_path.exists()

        # Load it back
        loaded = load_checkpoint(tmp_path)
        assert loaded is not None
        assert loaded.processed_files == ["file1.py", "file2.py"]
        assert loaded.last_batch == 3

    @pytest.mark.requirement("FR-018")
    def test_load_checkpoint_not_exists(self, tmp_path: Path) -> None:
        """Test load_checkpoint returns None when no checkpoint exists."""
        from agent_memory.ops.batch import load_checkpoint

        loaded = load_checkpoint(tmp_path)
        assert loaded is None

    @pytest.mark.requirement("FR-018")
    def test_clear_checkpoint(self, tmp_path: Path) -> None:
        """Test clear_checkpoint removes checkpoint file."""
        from agent_memory.ops.batch import (
            BatchCheckpoint,
            clear_checkpoint,
            save_checkpoint,
        )

        # Create and save checkpoint
        checkpoint = BatchCheckpoint(processed_files=["file.py"])
        save_checkpoint(checkpoint, tmp_path)

        # Verify it exists
        checkpoint_path = tmp_path / ".cognee" / "checkpoint.json"
        assert checkpoint_path.exists()

        # Clear it
        result = clear_checkpoint(tmp_path)
        assert result is True
        assert not checkpoint_path.exists()

    @pytest.mark.requirement("FR-018")
    def test_clear_checkpoint_not_exists(self, tmp_path: Path) -> None:
        """Test clear_checkpoint returns False when no checkpoint exists."""
        from agent_memory.ops.batch import clear_checkpoint

        result = clear_checkpoint(tmp_path)
        assert result is False


class TestBatchLoad:
    """Tests for batch_load function."""

    @pytest.mark.requirement("FR-018")
    @pytest.mark.asyncio
    async def test_batch_load_processes_all_files(self, tmp_path: Path) -> None:
        """Test batch_load processes all files."""
        from agent_memory.ops.batch import batch_load

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file1.py").write_text("# File 1")
        (src_dir / "file2.py").write_text("# File 2")
        (src_dir / "file3.py").write_text("# File 3")

        files = [
            str(src_dir / "file1.py"),
            str(src_dir / "file2.py"),
            str(src_dir / "file3.py"),
        ]

        # Mock config and client
        mock_config = MagicMock()
        mock_config.batch_size = 2
        mock_config.codebase_dataset = "test"

        mock_client = AsyncMock()
        mock_client.add_content = AsyncMock()

        result = await batch_load(
            mock_config,
            mock_client,
            files,
            base_path=tmp_path,
            resume=False,
        )

        assert result.total_files == 3
        assert result.successful_files == 3
        assert result.has_failures is False
        assert result.batches_completed == 2  # 3 files, batch_size=2

    @pytest.mark.requirement("FR-018")
    @pytest.mark.asyncio
    async def test_batch_load_with_failures(self, tmp_path: Path) -> None:
        """Test batch_load handles file failures correctly."""
        from agent_memory.ops.batch import batch_load

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "good.py").write_text("# Good")
        (src_dir / "bad.py").write_text("# Bad")

        files = [
            str(src_dir / "good.py"),
            str(src_dir / "bad.py"),
        ]

        mock_config = MagicMock()
        mock_config.batch_size = 10
        mock_config.codebase_dataset = "test"

        mock_client = AsyncMock()
        # First call succeeds, second fails
        mock_client.add_content = AsyncMock(
            side_effect=[None, Exception("API error")]
        )

        result = await batch_load(
            mock_config,
            mock_client,
            files,
            base_path=tmp_path,
            resume=False,
        )

        assert result.total_files == 2
        assert result.successful_files == 1
        assert len(result.failed_files) == 1
        assert result.has_failures is True

    @pytest.mark.requirement("FR-018")
    @pytest.mark.asyncio
    async def test_batch_load_calls_progress_callback(self, tmp_path: Path) -> None:
        """Test batch_load calls progress callback."""
        from agent_memory.ops.batch import batch_load

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file1.py").write_text("# File 1")
        (src_dir / "file2.py").write_text("# File 2")

        files = [
            str(src_dir / "file1.py"),
            str(src_dir / "file2.py"),
        ]

        mock_config = MagicMock()
        mock_config.batch_size = 10
        mock_config.codebase_dataset = "test"

        mock_client = AsyncMock()
        mock_client.add_content = AsyncMock()

        progress_reports: list = []

        def progress_callback(progress) -> None:
            progress_reports.append(progress)

        await batch_load(
            mock_config,
            mock_client,
            files,
            base_path=tmp_path,
            progress_callback=progress_callback,
            resume=False,
        )

        assert len(progress_reports) == 2
        assert progress_reports[0].current_file == "file1.py"
        assert progress_reports[1].current_file == "file2.py"

    @pytest.mark.requirement("FR-018")
    @pytest.mark.asyncio
    async def test_batch_load_saves_checkpoints(self, tmp_path: Path) -> None:
        """Test batch_load saves checkpoints after each batch."""
        from agent_memory.ops.batch import batch_load, load_checkpoint

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"file{i}.py").write_text(f"# File {i}")

        files = [str(src_dir / f"file{i}.py") for i in range(5)]

        mock_config = MagicMock()
        mock_config.batch_size = 2
        mock_config.codebase_dataset = "test"

        mock_client = AsyncMock()
        # Fail on third file to leave checkpoint
        mock_client.add_content = AsyncMock(
            side_effect=[None, None, Exception("Fail"), None, None]
        )

        await batch_load(
            mock_config,
            mock_client,
            files,
            base_path=tmp_path,
            resume=False,
        )

        # Checkpoint should exist because there were failures
        checkpoint = load_checkpoint(tmp_path)
        assert checkpoint is not None
        assert len(checkpoint.processed_files) == 4  # 4 successful

    @pytest.mark.requirement("FR-018")
    @pytest.mark.asyncio
    async def test_batch_load_resumes_from_checkpoint(self, tmp_path: Path) -> None:
        """Test batch_load resumes from existing checkpoint."""
        from agent_memory.ops.batch import (
            BatchCheckpoint,
            batch_load,
            save_checkpoint,
        )

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file1.py").write_text("# File 1")
        (src_dir / "file2.py").write_text("# File 2")
        (src_dir / "file3.py").write_text("# File 3")

        files = [
            str(src_dir / "file1.py"),
            str(src_dir / "file2.py"),
            str(src_dir / "file3.py"),
        ]

        # Create checkpoint with first file already processed
        checkpoint = BatchCheckpoint(
            processed_files=[str(src_dir / "file1.py")],
            last_batch=1,
        )
        save_checkpoint(checkpoint, tmp_path)

        mock_config = MagicMock()
        mock_config.batch_size = 10
        mock_config.codebase_dataset = "test"

        mock_client = AsyncMock()
        mock_client.add_content = AsyncMock()

        result = await batch_load(
            mock_config,
            mock_client,
            files,
            base_path=tmp_path,
            resume=True,
        )

        # Should process remaining 2 files
        assert result.resumed_from_checkpoint is True
        assert result.total_files == 3
        assert result.successful_files == 3  # 1 from checkpoint + 2 processed
        assert mock_client.add_content.call_count == 2  # Only 2 new files

    @pytest.mark.requirement("FR-018")
    @pytest.mark.asyncio
    async def test_batch_load_clears_checkpoint_on_success(
        self, tmp_path: Path
    ) -> None:
        """Test batch_load clears checkpoint when all files succeed."""
        from agent_memory.ops.batch import batch_load, load_checkpoint

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file1.py").write_text("# File 1")

        files = [str(src_dir / "file1.py")]

        mock_config = MagicMock()
        mock_config.batch_size = 10
        mock_config.codebase_dataset = "test"

        mock_client = AsyncMock()
        mock_client.add_content = AsyncMock()

        await batch_load(
            mock_config,
            mock_client,
            files,
            base_path=tmp_path,
            resume=False,
        )

        # Checkpoint should be cleared on success
        checkpoint = load_checkpoint(tmp_path)
        assert checkpoint is None

    @pytest.mark.requirement("FR-018")
    @pytest.mark.asyncio
    async def test_batch_load_empty_files(self, tmp_path: Path) -> None:
        """Test batch_load handles empty file list."""
        from agent_memory.ops.batch import batch_load

        mock_config = MagicMock()
        mock_config.batch_size = 10
        mock_config.codebase_dataset = "test"

        mock_client = AsyncMock()

        result = await batch_load(
            mock_config,
            mock_client,
            [],
            base_path=tmp_path,
            resume=False,
        )

        assert result.total_files == 0
        assert result.successful_files == 0
        assert result.batches_completed == 0


class TestBatchResultSerialization:
    """Tests for BatchResult serialization."""

    @pytest.mark.requirement("FR-018")
    def test_batch_result_to_dict(self) -> None:
        """Test BatchResult can be serialized to dict."""
        from agent_memory.ops.batch import BatchResult

        result = BatchResult(
            total_files=10,
            successful_files=8,
            failed_files=["fail.py"],
            batches_completed=2,
            duration_seconds=5.0,
        )

        data = result.model_dump()

        assert data["total_files"] == 10
        assert data["successful_files"] == 8
        assert data["failed_files"] == ["fail.py"]

    @pytest.mark.requirement("FR-018")
    def test_batch_result_json_serializable(self) -> None:
        """Test BatchResult can be serialized to JSON."""
        import json

        from agent_memory.ops.batch import BatchResult

        result = BatchResult(
            total_files=5,
            successful_files=5,
            failed_files=[],
            batches_completed=1,
            duration_seconds=2.5,
        )

        json_str = result.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["success_rate"] == pytest.approx(100.0)
        assert parsed["has_failures"] is False
