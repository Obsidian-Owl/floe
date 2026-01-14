"""Batch operations module for agent-memory.

Provides functionality for batch loading files into Cognee
with checkpointing and resume support.

Implementation: T039 (FLO-624)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient
    from agent_memory.config import AgentMemoryConfig


class BatchProgress(BaseModel):
    """Progress report for batch operations.

    Attributes:
        current_batch: Current batch number (1-indexed).
        total_batches: Total number of batches.
        files_processed: Total files processed so far.
        total_files: Total files to process.
        current_file: Name of file currently being processed.
    """

    current_batch: int = Field(ge=1, description="Current batch number")
    total_batches: int = Field(ge=1, description="Total batch count")
    files_processed: int = Field(ge=0, description="Files processed so far")
    total_files: int = Field(ge=0, description="Total files to process")
    current_file: str = Field(default="", description="Current file being processed")

    @computed_field
    @property
    def progress_percentage(self) -> float:
        """Calculate progress as percentage.

        Returns:
            Progress percentage (0-100).
        """
        if self.total_files == 0:
            return 100.0
        return (self.files_processed / self.total_files) * 100


class BatchResult(BaseModel):
    """Result of batch load operation.

    Attributes:
        total_files: Total number of files processed.
        successful_files: Number of files successfully loaded.
        failed_files: List of files that failed to load.
        batches_completed: Number of batches completed.
        duration_seconds: Total time taken in seconds.
        resumed_from_checkpoint: Whether operation resumed from checkpoint.
    """

    total_files: int = Field(ge=0, description="Total files processed")
    successful_files: int = Field(ge=0, description="Successfully loaded files")
    failed_files: list[str] = Field(default_factory=list, description="Failed file paths")
    batches_completed: int = Field(ge=0, description="Batches completed")
    duration_seconds: float = Field(ge=0, description="Duration in seconds")
    resumed_from_checkpoint: bool = Field(default=False, description="Resumed from checkpoint")

    @computed_field
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage.

        Returns:
            Success rate (0-100).
        """
        if self.total_files == 0:
            return 100.0
        return (self.successful_files / self.total_files) * 100

    @computed_field
    @property
    def has_failures(self) -> bool:
        """Check if any files failed.

        Returns:
            True if there are failed files.
        """
        return len(self.failed_files) > 0


class BatchCheckpoint(BaseModel):
    """Checkpoint for resumable batch operations.

    Attributes:
        processed_files: List of files already processed.
        last_batch: Last completed batch number.
        started_at: When the batch operation started.
        updated_at: When checkpoint was last updated.
    """

    processed_files: list[str] = Field(default_factory=list)
    last_batch: int = Field(default=0, ge=0)
    started_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# Type alias for progress callback
ProgressCallback = Callable[[BatchProgress], None]


def load_checkpoint(base_path: Path) -> BatchCheckpoint | None:
    """Load checkpoint from file.

    Args:
        base_path: Base path for .cognee directory.

    Returns:
        BatchCheckpoint if exists, None otherwise.
    """
    checkpoint_path = base_path / ".cognee" / "checkpoint.json"
    if not checkpoint_path.exists():
        return None

    with checkpoint_path.open() as f:
        data = json.load(f)
        return BatchCheckpoint(**data)


def save_checkpoint(checkpoint: BatchCheckpoint, base_path: Path) -> None:
    """Save checkpoint to file.

    Args:
        checkpoint: Checkpoint data to save.
        base_path: Base path for .cognee directory.
    """
    cognee_dir = base_path / ".cognee"
    cognee_dir.mkdir(parents=True, exist_ok=True)

    checkpoint.updated_at = datetime.now()
    checkpoint_path = cognee_dir / "checkpoint.json"

    with checkpoint_path.open("w") as f:
        json.dump(checkpoint.model_dump(mode="json"), f, indent=2, default=str)


def clear_checkpoint(base_path: Path) -> bool:
    """Clear checkpoint file if it exists.

    Args:
        base_path: Base path for .cognee directory.

    Returns:
        True if checkpoint was cleared, False if it didn't exist.
    """
    checkpoint_path = base_path / ".cognee" / "checkpoint.json"
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        return True
    return False


async def batch_load(
    config: AgentMemoryConfig,
    client: CogneeClient,
    files: list[str],
    *,
    base_path: Path | None = None,
    progress_callback: ProgressCallback | None = None,
    resume: bool = True,
) -> BatchResult:
    """Load files in batches with checkpointing.

    Processes files in configurable batches (batch_size from config).
    Saves checkpoints after each batch to support resume.
    Reports progress via optional callback.

    Args:
        config: Agent memory configuration with batch_size.
        client: Cognee client for loading files.
        files: List of file paths to load.
        base_path: Base path for checkpoint storage. Defaults to cwd.
        progress_callback: Optional callback for progress updates.
        resume: Whether to resume from checkpoint if available.

    Returns:
        BatchResult with operation summary.

    Example:
        >>> config = get_config()
        >>> client = CogneeClient(config)
        >>> files = get_all_configured_files(config)
        >>> result = await batch_load(config, client, files)
        >>> print(f"Loaded {result.successful_files}/{result.total_files} files")
    """
    import time

    if base_path is None:
        base_path = Path.cwd()

    start_time = time.monotonic()
    batch_size = config.batch_size
    total_files = len(files)
    total_batches = (total_files + batch_size - 1) // batch_size if total_files > 0 else 1

    # Check for existing checkpoint
    checkpoint: BatchCheckpoint | None = None
    resumed = False
    if resume:
        checkpoint = load_checkpoint(base_path)
        if checkpoint:
            resumed = True

    if checkpoint is None:
        checkpoint = BatchCheckpoint(started_at=datetime.now())

    # Filter out already processed files
    processed_set = set(checkpoint.processed_files)
    remaining_files = [f for f in files if f not in processed_set]

    successful: list[str] = list(checkpoint.processed_files)
    failed: list[str] = []

    # Process in batches
    current_batch = checkpoint.last_batch
    files_processed = len(checkpoint.processed_files)

    for i in range(0, len(remaining_files), batch_size):
        current_batch += 1
        batch_files = remaining_files[i : i + batch_size]

        for file_path in batch_files:
            # Report progress
            if progress_callback:
                progress = BatchProgress(
                    current_batch=current_batch,
                    total_batches=total_batches,
                    files_processed=files_processed,
                    total_files=total_files,
                    current_file=Path(file_path).name,
                )
                progress_callback(progress)

            # Load file via client
            try:
                path_obj = Path(file_path)
                content = path_obj.read_text(encoding="utf-8", errors="replace")
                # Use default dataset - caller can customize via ContentSource
                await client.add_content(content, config.codebase_dataset)
                successful.append(file_path)
            except Exception:
                failed.append(file_path)

            files_processed += 1

        # Save checkpoint after each batch
        checkpoint.processed_files = successful.copy()
        checkpoint.last_batch = current_batch
        save_checkpoint(checkpoint, base_path)

    # Clear checkpoint on successful completion
    if not failed:
        clear_checkpoint(base_path)

    duration = time.monotonic() - start_time

    return BatchResult(
        total_files=total_files,
        successful_files=len(successful),
        failed_files=failed,
        batches_completed=current_batch,
        duration_seconds=duration,
        resumed_from_checkpoint=resumed,
    )
