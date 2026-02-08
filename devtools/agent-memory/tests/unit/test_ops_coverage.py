"""Unit tests for ops/coverage.py - coverage analysis module.

Tests for coverage analysis functionality:
- CoverageReport model and metrics
- compare_filesystem_vs_indexed: Compare files on disk vs indexed in Cognee
- identify_missing_files: Find files that should be indexed but aren't

This is TDD - tests written before implementation (T037: Create ops/coverage.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestCoverageReport:
    """Tests for CoverageReport model."""

    @pytest.mark.requirement("FR-019")
    def test_coverage_report_model_has_required_fields(self) -> None:
        """Test CoverageReport model has all required fields."""
        # Import deferred to avoid errors before implementation
        from agent_memory.ops.coverage import CoverageReport

        # Create a report with minimum required data
        report = CoverageReport(
            total_files=100,
            indexed_files=95,
            missing_files=[],
            extra_files=[],
        )

        assert report.total_files == 100
        assert report.indexed_files == 95
        assert report.missing_files == []
        assert report.extra_files == []

    @pytest.mark.requirement("FR-019")
    def test_coverage_report_calculates_percentage(self) -> None:
        """Test CoverageReport correctly calculates coverage percentage."""
        from agent_memory.ops.coverage import CoverageReport

        report = CoverageReport(
            total_files=100,
            indexed_files=80,
            missing_files=["file1.py", "file2.py"],
            extra_files=[],
        )

        # Coverage should be indexed_files / total_files * 100
        assert report.coverage_percentage == pytest.approx(80.0)

    @pytest.mark.requirement("FR-019")
    def test_coverage_report_handles_zero_total(self) -> None:
        """Test CoverageReport handles zero total files without division error."""
        from agent_memory.ops.coverage import CoverageReport

        report = CoverageReport(
            total_files=0,
            indexed_files=0,
            missing_files=[],
            extra_files=[],
        )

        # Should be 100% when no files expected
        assert report.coverage_percentage == pytest.approx(100.0)

    @pytest.mark.requirement("FR-019")
    def test_coverage_report_is_complete_property(self) -> None:
        """Test CoverageReport.is_complete property."""
        from agent_memory.ops.coverage import CoverageReport

        # Complete coverage
        complete_report = CoverageReport(
            total_files=10,
            indexed_files=10,
            missing_files=[],
            extra_files=[],
        )
        assert complete_report.is_complete is True

        # Incomplete coverage
        incomplete_report = CoverageReport(
            total_files=10,
            indexed_files=8,
            missing_files=["file1.py", "file2.py"],
            extra_files=[],
        )
        assert incomplete_report.is_complete is False


class TestCompareFilesystemVsIndexed:
    """Tests for compare_filesystem_vs_indexed function."""

    @pytest.mark.requirement("FR-019")
    def test_coverage_report_accuracy(self, tmp_path: Path) -> None:
        """Test coverage report accurately reflects filesystem vs indexed state."""
        from agent_memory.ops.coverage import compare_filesystem_vs_indexed

        # Create test files on filesystem
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# README")
        (docs_dir / "guide.md").write_text("# Guide")
        (docs_dir / "api.md").write_text("# API")

        # Simulate indexed files (only 2 of 3 indexed)
        filesystem_files = [
            str(docs_dir / "readme.md"),
            str(docs_dir / "guide.md"),
            str(docs_dir / "api.md"),
        ]
        indexed_files = [
            str(docs_dir / "readme.md"),
            str(docs_dir / "guide.md"),
        ]

        report = compare_filesystem_vs_indexed(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert report.total_files == 3
        assert report.indexed_files == 2
        assert report.coverage_percentage == pytest.approx(66.67, rel=0.01)
        assert str(docs_dir / "api.md") in report.missing_files
        assert len(report.missing_files) == 1

    @pytest.mark.requirement("FR-019")
    def test_coverage_handles_missing_files(self, tmp_path: Path) -> None:
        """Test coverage correctly identifies missing files."""
        from agent_memory.ops.coverage import compare_filesystem_vs_indexed

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# Main")
        (src_dir / "utils.py").write_text("# Utils")
        (src_dir / "helpers.py").write_text("# Helpers")
        (src_dir / "config.py").write_text("# Config")

        filesystem_files = [
            str(src_dir / "main.py"),
            str(src_dir / "utils.py"),
            str(src_dir / "helpers.py"),
            str(src_dir / "config.py"),
        ]
        # Only main.py is indexed
        indexed_files = [str(src_dir / "main.py")]

        report = compare_filesystem_vs_indexed(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert report.total_files == 4
        assert report.indexed_files == 1
        assert len(report.missing_files) == 3
        assert str(src_dir / "utils.py") in report.missing_files
        assert str(src_dir / "helpers.py") in report.missing_files
        assert str(src_dir / "config.py") in report.missing_files

    @pytest.mark.requirement("FR-019")
    def test_coverage_detects_extra_indexed_files(self, tmp_path: Path) -> None:
        """Test coverage detects files indexed but no longer on filesystem."""
        from agent_memory.ops.coverage import compare_filesystem_vs_indexed

        # Files currently on filesystem
        filesystem_files = [str(tmp_path / "current.py")]

        # Indexed includes a file that was deleted
        indexed_files = [
            str(tmp_path / "current.py"),
            str(tmp_path / "deleted.py"),  # No longer exists
        ]

        report = compare_filesystem_vs_indexed(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert report.total_files == 1
        assert report.indexed_files == 1  # Only counts valid indexed files
        assert len(report.extra_files) == 1
        assert str(tmp_path / "deleted.py") in report.extra_files

    @pytest.mark.requirement("FR-019")
    def test_coverage_empty_filesystem(self) -> None:
        """Test coverage handles empty filesystem gracefully."""
        from agent_memory.ops.coverage import compare_filesystem_vs_indexed

        report = compare_filesystem_vs_indexed(
            filesystem_files=[],
            indexed_files=[],
        )

        assert report.total_files == 0
        assert report.indexed_files == 0
        assert report.coverage_percentage == pytest.approx(100.0)
        assert report.is_complete is True

    @pytest.mark.requirement("FR-019")
    def test_coverage_full_coverage(self, tmp_path: Path) -> None:
        """Test coverage report for 100% coverage."""
        from agent_memory.ops.coverage import compare_filesystem_vs_indexed

        files = [str(tmp_path / f"file{i}.py") for i in range(5)]

        report = compare_filesystem_vs_indexed(
            filesystem_files=files,
            indexed_files=files,
        )

        assert report.total_files == 5
        assert report.indexed_files == 5
        assert report.coverage_percentage == pytest.approx(100.0)
        assert report.missing_files == []
        assert report.is_complete is True


class TestIdentifyMissingFiles:
    """Tests for identify_missing_files function."""

    @pytest.mark.requirement("FR-019")
    def test_identify_missing_returns_sorted_list(self, tmp_path: Path) -> None:
        """Test identify_missing_files returns sorted list of missing files."""
        from agent_memory.ops.coverage import identify_missing_files

        filesystem_files = [
            str(tmp_path / "z_file.py"),
            str(tmp_path / "a_file.py"),
            str(tmp_path / "m_file.py"),
        ]
        indexed_files = [str(tmp_path / "a_file.py")]

        missing = identify_missing_files(
            filesystem_files=filesystem_files,
            indexed_files=indexed_files,
        )

        assert len(missing) == 2
        # Should be sorted alphabetically
        assert missing[0] == str(tmp_path / "m_file.py")
        assert missing[1] == str(tmp_path / "z_file.py")

    @pytest.mark.requirement("FR-019")
    def test_identify_missing_no_missing_files(self, tmp_path: Path) -> None:
        """Test identify_missing_files returns empty list when all indexed."""
        from agent_memory.ops.coverage import identify_missing_files

        files = [str(tmp_path / f"file{i}.py") for i in range(3)]

        missing = identify_missing_files(
            filesystem_files=files,
            indexed_files=files,
        )

        assert missing == []

    @pytest.mark.requirement("FR-019")
    def test_identify_missing_all_missing(self, tmp_path: Path) -> None:
        """Test identify_missing_files when no files are indexed."""
        from agent_memory.ops.coverage import identify_missing_files

        filesystem_files = [
            str(tmp_path / "file1.py"),
            str(tmp_path / "file2.py"),
        ]

        missing = identify_missing_files(
            filesystem_files=filesystem_files,
            indexed_files=[],
        )

        assert len(missing) == 2
        assert str(tmp_path / "file1.py") in missing
        assert str(tmp_path / "file2.py") in missing


class TestCoverageReportSerialization:
    """Tests for CoverageReport serialization."""

    @pytest.mark.requirement("FR-019")
    def test_coverage_report_to_dict(self) -> None:
        """Test CoverageReport can be serialized to dict."""
        from agent_memory.ops.coverage import CoverageReport

        report = CoverageReport(
            total_files=10,
            indexed_files=8,
            missing_files=["file1.py", "file2.py"],
            extra_files=["old.py"],
        )

        # model_dump is Pydantic v2 method
        data = report.model_dump()

        assert data["total_files"] == 10
        assert data["indexed_files"] == 8
        assert data["missing_files"] == ["file1.py", "file2.py"]
        assert data["extra_files"] == ["old.py"]

    @pytest.mark.requirement("FR-019")
    def test_coverage_report_json_serializable(self) -> None:
        """Test CoverageReport can be serialized to JSON."""
        import json

        from agent_memory.ops.coverage import CoverageReport

        report = CoverageReport(
            total_files=5,
            indexed_files=5,
            missing_files=[],
            extra_files=[],
        )

        # Should not raise
        json_str = report.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["total_files"] == 5
        assert parsed["coverage_percentage"] == pytest.approx(100.0)


class TestGetFilesFromSource:
    """Tests for get_files_from_source function."""

    @pytest.mark.requirement("FR-019")
    def test_get_files_from_file_source(self, tmp_path: Path) -> None:
        """Test get_files_from_source with file source type."""
        from agent_memory.ops.coverage import get_files_from_source

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("# Test")

        files = get_files_from_source(
            source_path=test_file,
            source_type="file",
            file_extensions=[".py"],
            exclude_patterns=[],
            base_path=tmp_path,
        )

        assert len(files) == 1
        assert str(test_file.resolve()) in files

    @pytest.mark.requirement("FR-019")
    def test_get_files_from_directory_source(self, tmp_path: Path) -> None:
        """Test get_files_from_source with directory source type."""
        from agent_memory.ops.coverage import get_files_from_source

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# Main")
        (src_dir / "utils.py").write_text("# Utils")
        (src_dir / "readme.md").write_text("# README")

        files = get_files_from_source(
            source_path=src_dir,
            source_type="directory",
            file_extensions=[".py"],
            exclude_patterns=[],
            base_path=tmp_path,
        )

        assert len(files) == 2
        assert str((src_dir / "main.py").resolve()) in files
        assert str((src_dir / "utils.py").resolve()) in files
        # .md file not included
        assert str((src_dir / "readme.md").resolve()) not in files

    @pytest.mark.requirement("FR-019")
    def test_get_files_from_source_with_exclude(self, tmp_path: Path) -> None:
        """Test get_files_from_source respects exclude patterns."""
        from agent_memory.ops.coverage import get_files_from_source

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# Main")
        (src_dir / "test_main.py").write_text("# Test")

        files = get_files_from_source(
            source_path=src_dir,
            source_type="directory",
            file_extensions=[".py"],
            exclude_patterns=["**/test_*.py"],
            base_path=tmp_path,
        )

        assert len(files) == 1
        assert str((src_dir / "main.py").resolve()) in files

    @pytest.mark.requirement("FR-019")
    def test_get_files_from_nonexistent_path(self, tmp_path: Path) -> None:
        """Test get_files_from_source returns empty for nonexistent path."""
        from agent_memory.ops.coverage import get_files_from_source

        files = get_files_from_source(
            source_path=tmp_path / "nonexistent",
            source_type="directory",
            file_extensions=[".py"],
            exclude_patterns=[],
            base_path=tmp_path,
        )

        assert files == []


class TestGetAllConfiguredFiles:
    """Tests for get_all_configured_files function."""

    @pytest.mark.requirement("FR-019")
    def test_get_all_configured_files_empty_sources(self, tmp_path: Path) -> None:
        """Test get_all_configured_files with no sources."""
        from unittest.mock import MagicMock

        from agent_memory.ops.coverage import get_all_configured_files

        mock_config = MagicMock()
        mock_config.content_sources = []

        files = get_all_configured_files(mock_config, base_path=tmp_path)

        assert files == []

    @pytest.mark.requirement("FR-019")
    def test_get_all_configured_files_multiple_sources(self, tmp_path: Path) -> None:
        """Test get_all_configured_files with multiple sources."""
        from unittest.mock import MagicMock

        from agent_memory.ops.coverage import get_all_configured_files

        # Create test files
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# README")

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# Main")

        # Create mock sources
        mock_source1 = MagicMock()
        mock_source1.path = docs_dir
        mock_source1.source_type = "directory"
        mock_source1.file_extensions = [".md"]
        mock_source1.exclude_patterns = []

        mock_source2 = MagicMock()
        mock_source2.path = src_dir
        mock_source2.source_type = "directory"
        mock_source2.file_extensions = [".py"]
        mock_source2.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source1, mock_source2]

        files = get_all_configured_files(mock_config, base_path=tmp_path)

        assert len(files) == 2
        assert str((docs_dir / "readme.md").resolve()) in files
        assert str((src_dir / "main.py").resolve()) in files


class TestAnalyzeCoverage:
    """Tests for analyze_coverage async function."""

    @pytest.mark.requirement("FR-019")
    @pytest.mark.asyncio
    async def test_analyze_coverage_with_checksums(self, tmp_path: Path) -> None:
        """Test analyze_coverage uses checksums.json when present."""
        import json
        from unittest.mock import AsyncMock, MagicMock

        from agent_memory.ops.coverage import analyze_coverage

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# Main")
        (src_dir / "utils.py").write_text("# Utils")

        # Create .cognee directory with checksums
        cognee_dir = tmp_path / ".cognee"
        cognee_dir.mkdir()
        checksums = {str((src_dir / "main.py").resolve()): "abc123"}
        (cognee_dir / "checksums.json").write_text(json.dumps(checksums))

        # Create mock config
        mock_source = MagicMock()
        mock_source.path = src_dir
        mock_source.source_type = "directory"
        mock_source.file_extensions = [".py"]
        mock_source.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source]

        # Create mock client
        mock_client = AsyncMock()
        mock_client.list_datasets = AsyncMock(return_value=["codebase"])

        report = await analyze_coverage(mock_config, mock_client, base_path=tmp_path)

        # main.py is indexed, utils.py is not
        assert report.total_files == 2
        assert report.indexed_files == 1
        assert len(report.missing_files) == 1

    @pytest.mark.requirement("FR-019")
    @pytest.mark.asyncio
    async def test_analyze_coverage_no_checksums(self, tmp_path: Path) -> None:
        """Test analyze_coverage handles missing checksums.json."""
        from unittest.mock import AsyncMock, MagicMock

        from agent_memory.ops.coverage import analyze_coverage

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# Main")

        # No .cognee directory

        # Create mock config
        mock_source = MagicMock()
        mock_source.path = src_dir
        mock_source.source_type = "directory"
        mock_source.file_extensions = [".py"]
        mock_source.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source]

        # Create mock client
        mock_client = AsyncMock()
        mock_client.list_datasets = AsyncMock(return_value=[])

        report = await analyze_coverage(mock_config, mock_client, base_path=tmp_path)

        # All files are missing since no checksums
        assert report.total_files == 1
        assert report.indexed_files == 0
        assert len(report.missing_files) == 1

    @pytest.mark.requirement("FR-019")
    @pytest.mark.asyncio
    async def test_analyze_coverage_with_provided_indexed_files(self, tmp_path: Path) -> None:
        """Test analyze_coverage accepts indexed_files parameter."""
        from unittest.mock import AsyncMock, MagicMock

        from agent_memory.ops.coverage import analyze_coverage

        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        main_file = src_dir / "main.py"
        main_file.write_text("# Main")
        utils_file = src_dir / "utils.py"
        utils_file.write_text("# Utils")

        # Create mock config
        mock_source = MagicMock()
        mock_source.path = src_dir
        mock_source.source_type = "directory"
        mock_source.file_extensions = [".py"]
        mock_source.exclude_patterns = []

        mock_config = MagicMock()
        mock_config.content_sources = [mock_source]

        # Create mock client
        mock_client = AsyncMock()
        mock_client.list_datasets = AsyncMock(return_value=["codebase"])

        # Provide indexed files directly
        indexed = [str(main_file.resolve()), str(utils_file.resolve())]
        report = await analyze_coverage(
            mock_config, mock_client, base_path=tmp_path, indexed_files=indexed
        )

        # Both files are indexed
        assert report.total_files == 2
        assert report.indexed_files == 2
        assert report.missing_files == []
        assert report.is_complete is True
