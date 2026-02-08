"""Unit tests for ops/drift.py - drift detection module.

Tests for drift detection functionality:
- DriftReport model and classification
- detect_deleted_files: Find indexed files no longer on filesystem
- detect_renamed_files: Find files renamed but content unchanged (via hash)
- detect_modified_files: Find files with content changes

This is TDD - tests written before implementation (T038: Create ops/drift.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestDriftReport:
    """Tests for DriftReport model."""

    @pytest.mark.requirement("FR-020")
    def test_drift_report_model_has_required_fields(self) -> None:
        """Test DriftReport model has all required fields."""
        from agent_memory.ops.drift import DriftReport

        report = DriftReport(
            deleted_files=[],
            renamed_files=[],
            modified_files=[],
            unchanged_files=[],
        )

        assert report.deleted_files == []
        assert report.renamed_files == []
        assert report.modified_files == []
        assert report.unchanged_files == []

    @pytest.mark.requirement("FR-020")
    def test_drift_report_has_drift_property(self) -> None:
        """Test DriftReport.has_drift property."""
        from agent_memory.ops.drift import DriftReport

        # No drift
        no_drift = DriftReport(
            deleted_files=[],
            renamed_files=[],
            modified_files=[],
            unchanged_files=["file1.py", "file2.py"],
        )
        assert no_drift.has_drift is False

        # Has deleted files
        with_deleted = DriftReport(
            deleted_files=["old.py"],
            renamed_files=[],
            modified_files=[],
            unchanged_files=[],
        )
        assert with_deleted.has_drift is True

        # Has renamed files
        with_renamed = DriftReport(
            deleted_files=[],
            renamed_files=[["old.py", "new.py"]],
            modified_files=[],
            unchanged_files=[],
        )
        assert with_renamed.has_drift is True

    @pytest.mark.requirement("FR-020")
    def test_drift_report_total_drifted(self) -> None:
        """Test DriftReport.total_drifted property."""
        from agent_memory.ops.drift import DriftReport

        report = DriftReport(
            deleted_files=["del1.py", "del2.py"],  # 2 deleted
            renamed_files=[["old.py", "new.py"]],  # 1 renamed
            modified_files=["mod.py"],  # 1 modified
            unchanged_files=["ok.py"],  # 1 unchanged
        )

        assert report.total_drifted == 4  # 2 + 1 + 1


class TestDetectDeletedFiles:
    """Tests for detect_deleted_files function."""

    @pytest.mark.requirement("FR-020")
    def test_drift_detects_deleted_files(self, tmp_path: Path) -> None:
        """Test drift correctly identifies deleted files."""
        from agent_memory.ops.drift import detect_deleted_files

        # Files currently on filesystem
        current_file = tmp_path / "current.py"
        current_file.write_text("# Current")

        filesystem_files = [str(current_file)]

        # Indexed files include a deleted one
        indexed_files = [
            str(current_file),
            str(tmp_path / "deleted.py"),  # No longer exists
        ]

        deleted = detect_deleted_files(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert len(deleted) == 1
        assert str(tmp_path / "deleted.py") in deleted

    @pytest.mark.requirement("FR-020")
    def test_detect_deleted_no_deletions(self, tmp_path: Path) -> None:
        """Test detect_deleted_files returns empty when no deletions."""
        from agent_memory.ops.drift import detect_deleted_files

        files = [str(tmp_path / f"file{i}.py") for i in range(3)]

        deleted = detect_deleted_files(
            filesystem_files=files,
            indexed_files=files,
        )

        assert deleted == []

    @pytest.mark.requirement("FR-020")
    def test_detect_deleted_all_files_deleted(self, tmp_path: Path) -> None:
        """Test detect_deleted_files when all indexed files are deleted."""
        from agent_memory.ops.drift import detect_deleted_files

        indexed_files = [
            str(tmp_path / "old1.py"),
            str(tmp_path / "old2.py"),
        ]

        deleted = detect_deleted_files(
            filesystem_files=[],
            indexed_files=indexed_files,
        )

        assert len(deleted) == 2
        assert str(tmp_path / "old1.py") in deleted
        assert str(tmp_path / "old2.py") in deleted


class TestDetectRenamedFiles:
    """Tests for detect_renamed_files function."""

    @pytest.mark.requirement("FR-020")
    def test_drift_detects_renamed_files(self, tmp_path: Path) -> None:
        """Test drift correctly identifies renamed files via content hash."""
        from agent_memory.ops.drift import detect_renamed_files

        # Create a file with specific content
        new_file = tmp_path / "new_name.py"
        content = "# Unique content for rename detection\nprint('hello')"
        new_file.write_text(content)

        # Simulate: old_name.py was indexed, now it's new_name.py
        # The content hash should match
        filesystem_files = {str(new_file): content}
        indexed_files = {str(tmp_path / "old_name.py"): content}

        renamed = detect_renamed_files(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert len(renamed) == 1
        old_path = renamed[0][0]
        new_path = renamed[0][1]
        assert old_path == str(tmp_path / "old_name.py")
        assert new_path == str(new_file)

    @pytest.mark.requirement("FR-020")
    def test_detect_renamed_no_renames(self, tmp_path: Path) -> None:
        """Test detect_renamed_files returns empty when no renames."""
        from agent_memory.ops.drift import detect_renamed_files

        # Same files with same content
        file1 = tmp_path / "file1.py"
        file1.write_text("content1")

        files = {str(file1): "content1"}

        renamed = detect_renamed_files(
            filesystem_files=files,
            indexed_files=files,
        )

        assert renamed == []

    @pytest.mark.requirement("FR-020")
    def test_detect_renamed_content_changed(self, tmp_path: Path) -> None:
        """Test that files with changed content are not flagged as renamed."""
        from agent_memory.ops.drift import detect_renamed_files

        # File exists but content is different
        file1 = tmp_path / "file1.py"
        file1.write_text("new content")

        filesystem_files = {str(file1): "new content"}
        indexed_files = {str(file1): "old content"}

        renamed = detect_renamed_files(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        # Not a rename - it's a modification (different content)
        assert renamed == []

    @pytest.mark.requirement("FR-020")
    def test_detect_renamed_multiple_renames(self, tmp_path: Path) -> None:
        """Test detecting multiple renamed files."""
        from agent_memory.ops.drift import detect_renamed_files

        content1 = "# File 1 unique content"
        content2 = "# File 2 unique content"

        filesystem_files = {
            str(tmp_path / "new1.py"): content1,
            str(tmp_path / "new2.py"): content2,
        }
        indexed_files = {
            str(tmp_path / "old1.py"): content1,
            str(tmp_path / "old2.py"): content2,
        }

        renamed = detect_renamed_files(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert len(renamed) == 2


class TestDetectModifiedFiles:
    """Tests for detect_modified_files function."""

    @pytest.mark.requirement("FR-020")
    def test_detect_modified_files(self, tmp_path: Path) -> None:
        """Test detecting files with modified content."""
        from agent_memory.ops.drift import detect_modified_files

        file1 = tmp_path / "file1.py"
        file1.write_text("modified content")

        filesystem_files = {str(file1): "modified content"}
        indexed_files = {str(file1): "original content"}

        modified = detect_modified_files(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert len(modified) == 1
        assert str(file1) in modified

    @pytest.mark.requirement("FR-020")
    def test_detect_modified_no_changes(self, tmp_path: Path) -> None:
        """Test detect_modified_files returns empty when content unchanged."""
        from agent_memory.ops.drift import detect_modified_files

        file1 = tmp_path / "file1.py"
        content = "unchanged content"

        files = {str(file1): content}

        modified = detect_modified_files(
            filesystem_files=files,
            indexed_files=files,
        )

        assert modified == []

    @pytest.mark.requirement("FR-020")
    def test_detect_modified_excludes_new_files(self, tmp_path: Path) -> None:
        """Test that new files (not previously indexed) are not flagged as modified."""
        from agent_memory.ops.drift import detect_modified_files

        file1 = tmp_path / "existing.py"
        file2 = tmp_path / "new_file.py"

        filesystem_files = {
            str(file1): "content",
            str(file2): "new content",
        }
        indexed_files = {
            str(file1): "content",
            # file2 not indexed previously
        }

        modified = detect_modified_files(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        # file2 is new, not modified
        assert modified == []


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    @pytest.mark.requirement("FR-020")
    def test_compute_hash_consistent(self) -> None:
        """Test hash is consistent for same content."""
        from agent_memory.ops.drift import compute_content_hash

        content = "test content"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)

        assert hash1 == hash2

    @pytest.mark.requirement("FR-020")
    def test_compute_hash_different_content(self) -> None:
        """Test hash differs for different content."""
        from agent_memory.ops.drift import compute_content_hash

        hash1 = compute_content_hash("content A")
        hash2 = compute_content_hash("content B")

        assert hash1 != hash2

    @pytest.mark.requirement("FR-020")
    def test_compute_hash_empty_content(self) -> None:
        """Test hash works with empty content."""
        from agent_memory.ops.drift import compute_content_hash

        hash_empty = compute_content_hash("")
        assert hash_empty is not None
        assert len(hash_empty) > 0


class TestDriftReportSerialization:
    """Tests for DriftReport serialization."""

    @pytest.mark.requirement("FR-020")
    def test_drift_report_to_dict(self) -> None:
        """Test DriftReport can be serialized to dict."""
        from agent_memory.ops.drift import DriftReport

        report = DriftReport(
            deleted_files=["del.py"],
            renamed_files=[["old.py", "new.py"]],
            modified_files=["mod.py"],
            unchanged_files=["ok.py"],
        )

        data = report.model_dump()

        assert data["deleted_files"] == ["del.py"]
        assert data["renamed_files"] == [["old.py", "new.py"]]
        assert data["modified_files"] == ["mod.py"]
        assert data["unchanged_files"] == ["ok.py"]

    @pytest.mark.requirement("FR-020")
    def test_drift_report_json_serializable(self) -> None:
        """Test DriftReport can be serialized to JSON."""
        import json

        from agent_memory.ops.drift import DriftReport

        report = DriftReport(
            deleted_files=[],
            renamed_files=[],
            modified_files=[],
            unchanged_files=["file.py"],
        )

        json_str = report.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["has_drift"] is False
        assert parsed["unchanged_files"] == ["file.py"]


class TestDetectDrift:
    """Tests for detect_drift function."""

    @pytest.mark.requirement("FR-020")
    def test_detect_drift_with_checksums(self, tmp_path: Path) -> None:
        """Test detect_drift uses stored checksums to detect drift."""
        import json
        from unittest.mock import MagicMock

        from agent_memory.ops.drift import compute_content_hash, detect_drift

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "unchanged.py").write_text("# Unchanged")
        (src_dir / "modified.py").write_text("# Modified - new content")

        # Create .cognee directory with checksums
        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()

        # Store original checksums
        unchanged_path = str((src_dir / "unchanged.py").resolve())
        modified_path = str((src_dir / "modified.py").resolve())
        deleted_path = str((src_dir / "deleted.py").resolve())

        stored_checksums = {
            unchanged_path: compute_content_hash("# Unchanged"),
            modified_path: compute_content_hash(
                "# Modified - old content"
            ),  # Different!
            deleted_path: compute_content_hash("# Deleted file"),  # No longer exists
        }
        (cognee_dir / "checksums.json").write_text(json.dumps(stored_checksums))

        # Create mock config
        mock_source = MagicMock()
        mock_source.path = src_dir
        mock_source.source_type = "directory"
        mock_source.file_extensions = [".py"]
        mock_source.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source]

        report = detect_drift(mock_config, base_path=tmp_path)

        assert len(report.modified_files) == 1
        assert modified_path in report.modified_files

        assert len(report.deleted_files) == 1
        assert deleted_path in report.deleted_files

        assert len(report.unchanged_files) == 1
        assert unchanged_path in report.unchanged_files

    @pytest.mark.requirement("FR-020")
    def test_detect_drift_no_checksums_file(self, tmp_path: Path) -> None:
        """Test detect_drift handles missing checksums.json gracefully."""
        from unittest.mock import MagicMock

        from agent_memory.ops.drift import detect_drift

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file.py").write_text("# Content")

        # No .cognee directory

        mock_source = MagicMock()
        mock_source.path = src_dir
        mock_source.source_type = "directory"
        mock_source.file_extensions = [".py"]
        mock_source.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source]

        report = detect_drift(mock_config, base_path=tmp_path)

        # With no stored checksums, nothing is deleted/modified/unchanged
        assert report.deleted_files == []
        assert report.modified_files == []
        assert report.unchanged_files == []
        assert report.has_drift is False

    @pytest.mark.requirement("FR-020")
    def test_detect_drift_with_provided_checksums(self, tmp_path: Path) -> None:
        """Test detect_drift with provided checksums (bypasses file loading)."""
        from unittest.mock import MagicMock

        from agent_memory.ops.drift import compute_content_hash, detect_drift

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file.py").write_text("# Current content")

        file_path = str((src_dir / "file.py").resolve())

        mock_source = MagicMock()
        mock_source.path = src_dir
        mock_source.source_type = "directory"
        mock_source.file_extensions = [".py"]
        mock_source.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source]

        # Provide checksums directly
        stored_checksums = {
            file_path: compute_content_hash("# Old content"),  # Different from current
        }

        report = detect_drift(
            mock_config,
            base_path=tmp_path,
            stored_checksums=stored_checksums,
        )

        assert len(report.modified_files) == 1
        assert file_path in report.modified_files

    @pytest.mark.requirement("FR-020")
    def test_detect_drift_detects_renames(self, tmp_path: Path) -> None:
        """Test detect_drift correctly identifies renamed files."""
        from unittest.mock import MagicMock

        from agent_memory.ops.drift import compute_content_hash, detect_drift

        # Create test file with specific content
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        content = "# Unique content that was renamed"
        (src_dir / "new_name.py").write_text(content)

        new_path = str((src_dir / "new_name.py").resolve())
        old_path = str((src_dir / "old_name.py").resolve())

        mock_source = MagicMock()
        mock_source.path = src_dir
        mock_source.source_type = "directory"
        mock_source.file_extensions = [".py"]
        mock_source.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source]

        # Old checksums have the same content at different path
        stored_checksums = {
            old_path: compute_content_hash(content),
        }

        report = detect_drift(
            mock_config,
            base_path=tmp_path,
            stored_checksums=stored_checksums,
        )

        assert len(report.renamed_files) == 1
        assert report.renamed_files[0] == [old_path, new_path]
