"""Unit tests for sync command helper functions.

Tests for helper functions used by the sync command, including:
- _get_all_source_files: Retrieve files from configured sources
- _filter_by_dataset: Filter files by dataset name
- _is_under_path: Check if file is under a directory
- _get_dataset_for_file: Determine dataset for a file
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from agent_memory.cli import (
    _filter_by_dataset,
    _get_all_source_files,
    _get_dataset_for_file,
    _is_under_path,
)
from agent_memory.config import AgentMemoryConfig, ContentSource

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def mock_config_env_vars(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Set mock environment variables for all tests in this module.

    AgentMemoryConfig requires cognee_api_key and openai_api_key (when
    llm_provider is 'openai'). This fixture provides mock values for
    unit tests that don't need real API access.
    """
    monkeypatch.setenv("COGNEE_API_KEY", "test-api-key-for-unit-tests")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-for-unit-tests")
    yield


@pytest.fixture
def temp_source_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with test files."""
    # Create directory structure
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text("# Readme")
    (docs_dir / "guide.md").write_text("# Guide")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text('"""Main module."""\nprint("hello")')
    (src_dir / "utils.py").write_text('"""Utilities."""\ndef foo(): pass')

    return tmp_path


class TestGetAllSourceFiles:
    """Tests for _get_all_source_files function."""

    @pytest.mark.requirement("FR-012")
    def test_get_file_source(self, tmp_path: Path) -> None:
        """Test getting files from file-type source."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=test_file,
                    source_type="file",
                    dataset="test-dataset",
                    file_extensions=[".md"],
                )
            ]
        )

        files = _get_all_source_files(config)
        assert len(files) == 1
        assert files[0] == test_file

    @pytest.mark.requirement("FR-012")
    def test_get_directory_source(self, temp_source_dir: Path) -> None:
        """Test getting files from directory-type source."""
        docs_dir = temp_source_dir / "docs"

        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=docs_dir,
                    source_type="directory",
                    dataset="docs",
                    file_extensions=[".md"],
                )
            ]
        )

        files = _get_all_source_files(config)
        assert len(files) == 2
        file_names = {f.name for f in files}
        assert "readme.md" in file_names
        assert "guide.md" in file_names

    @pytest.mark.requirement("FR-012")
    def test_get_nonexistent_source(self, tmp_path: Path) -> None:
        """Test handling of non-existent source paths."""
        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=tmp_path / "nonexistent",
                    source_type="directory",
                    dataset="test",
                    file_extensions=[".md"],
                )
            ]
        )

        files = _get_all_source_files(config)
        assert files == []

    @pytest.mark.requirement("FR-012")
    def test_get_multiple_sources(self, temp_source_dir: Path) -> None:
        """Test getting files from multiple sources."""
        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=temp_source_dir / "docs",
                    source_type="directory",
                    dataset="docs",
                    file_extensions=[".md"],
                ),
                ContentSource(
                    path=temp_source_dir / "src",
                    source_type="directory",
                    dataset="code",
                    file_extensions=[".py"],
                ),
            ]
        )

        files = _get_all_source_files(config)
        assert len(files) == 4
        file_names = {f.name for f in files}
        assert "readme.md" in file_names
        assert "guide.md" in file_names
        assert "main.py" in file_names
        assert "utils.py" in file_names


class TestFilterByDataset:
    """Tests for _filter_by_dataset function."""

    @pytest.mark.requirement("FR-012")
    def test_filter_single_dataset(self, temp_source_dir: Path) -> None:
        """Test filtering files to a single dataset."""
        docs_dir = temp_source_dir / "docs"
        src_dir = temp_source_dir / "src"

        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=docs_dir,
                    source_type="directory",
                    dataset="docs",
                    file_extensions=[".md"],
                ),
                ContentSource(
                    path=src_dir,
                    source_type="directory",
                    dataset="code",
                    file_extensions=[".py"],
                ),
            ]
        )

        all_files = _get_all_source_files(config)
        docs_files = _filter_by_dataset(all_files, config, "docs")

        assert len(docs_files) == 2
        assert all(f.suffix == ".md" for f in docs_files)

    @pytest.mark.requirement("FR-012")
    def test_filter_nonexistent_dataset(self, temp_source_dir: Path) -> None:
        """Test filtering with non-existent dataset returns empty list."""
        docs_dir = temp_source_dir / "docs"

        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=docs_dir,
                    source_type="directory",
                    dataset="docs",
                    file_extensions=[".md"],
                )
            ]
        )

        all_files = _get_all_source_files(config)
        filtered = _filter_by_dataset(all_files, config, "nonexistent")

        assert filtered == []


class TestIsUnderPath:
    """Tests for _is_under_path function."""

    @pytest.mark.requirement("FR-012")
    def test_file_under_directory(self, tmp_path: Path) -> None:
        """Test file is correctly identified as under directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file_path = subdir / "test.txt"
        file_path.write_text("test")

        result = _is_under_path(file_path, {tmp_path})
        assert result is True

    @pytest.mark.requirement("FR-012")
    def test_file_not_under_directory(self, tmp_path: Path) -> None:
        """Test file not under directory."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("test")

        other_dir = tmp_path / "other"
        other_dir.mkdir()

        result = _is_under_path(file_path, {other_dir})
        assert result is False

    @pytest.mark.requirement("FR-012")
    def test_empty_paths_set(self, tmp_path: Path) -> None:
        """Test with empty paths set."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("test")

        result = _is_under_path(file_path, set())
        assert result is False


class TestGetDatasetForFile:
    """Tests for _get_dataset_for_file function."""

    @pytest.mark.requirement("FR-012")
    def test_file_matches_source(self, tmp_path: Path) -> None:
        """Test file directly matching a file-type source."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=test_file,
                    source_type="file",
                    dataset="specific-dataset",
                    file_extensions=[".md"],
                )
            ]
        )

        dataset = _get_dataset_for_file(test_file, config)
        assert dataset == "specific-dataset"

    @pytest.mark.requirement("FR-012")
    def test_file_under_directory_source(self, temp_source_dir: Path) -> None:
        """Test file under a directory-type source."""
        docs_dir = temp_source_dir / "docs"
        readme = docs_dir / "readme.md"

        config = AgentMemoryConfig(
            content_sources=[
                ContentSource(
                    path=docs_dir,
                    source_type="directory",
                    dataset="documentation",
                    file_extensions=[".md"],
                )
            ]
        )

        dataset = _get_dataset_for_file(readme, config)
        assert dataset == "documentation"

    @pytest.mark.requirement("FR-012")
    def test_all_files_default_to_unified_dataset(self, tmp_path: Path) -> None:
        """Test all file types default to unified default_dataset.

        Since we use a single unified dataset for maximum knowledge graph
        connectivity, all files not matched by a ContentSource should
        default to config.default_dataset.
        """
        # Create various file types
        py_file = tmp_path / "main.py"
        py_file.write_text("print('hello')")

        arch_dir = tmp_path / "architecture"
        arch_dir.mkdir()
        arch_file = arch_dir / "design.md"
        arch_file.write_text("# Architecture")

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_file = claude_dir / "config.md"
        claude_file.write_text("# Claude Config")

        unknown_file = tmp_path / "random.txt"
        unknown_file.write_text("random content")

        config = AgentMemoryConfig(
            content_sources=[],
            default_dataset="unified-knowledge",
        )

        # All files should default to the unified dataset
        assert _get_dataset_for_file(py_file, config) == "unified-knowledge"
        assert _get_dataset_for_file(arch_file, config) == "unified-knowledge"
        assert _get_dataset_for_file(claude_file, config) == "unified-knowledge"
        assert _get_dataset_for_file(unknown_file, config) == "unified-knowledge"
