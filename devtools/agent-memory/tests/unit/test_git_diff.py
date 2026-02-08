"""Unit tests for git_diff module.

Tests git change detection with mocked subprocess calls.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from agent_memory.git_diff import (
    GitError,
    _matches_any_pattern,
    _matches_double_star_pattern,
    _validate_git_ref,
    get_changed_files,
    get_repo_root,
    get_staged_files,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_repo_root(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a mock repo root directory."""
    yield tmp_path


class TestGetRepoRoot:
    """Tests for get_repo_root function."""

    @pytest.mark.requirement("FR-012")
    def test_get_repo_root_success(self, tmp_path: Path) -> None:
        """Test successful repo root detection."""
        mock_result = MagicMock()
        mock_result.stdout = str(tmp_path) + "\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = get_repo_root()
            assert result == tmp_path
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )

    @pytest.mark.requirement("FR-012")
    def test_get_repo_root_not_git_repo(self) -> None:
        """Test error when not in a git repository."""
        mock_error = subprocess.CalledProcessError(
            128, ["git"], stderr="fatal: not a git repository"
        )

        with patch("subprocess.run", side_effect=mock_error):
            with pytest.raises(GitError, match="Failed to get repo root"):
                get_repo_root()

    @pytest.mark.requirement("FR-012")
    def test_get_repo_root_git_not_found(self) -> None:
        """Test error when git command is not available."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(GitError, match="git command not found"):
                get_repo_root()


class TestGetChangedFiles:
    """Tests for get_changed_files function."""

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_basic(self, tmp_path: Path) -> None:
        """Test basic changed file detection."""
        # Create test files
        (tmp_path / "file1.py").write_text("content")
        (tmp_path / "file2.md").write_text("content")

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            elif "diff" in cmd and "--cached" in cmd:
                result.stdout = ""  # No staged changes
            elif "diff" in cmd and "--name-only" in cmd:
                if cmd[-1] == "HEAD~1":
                    result.stdout = "file1.py\nfile2.md\n"
                else:
                    result.stdout = ""  # No unstaged changes
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            changed = get_changed_files(since="HEAD~1")

        assert len(changed) == 2
        assert Path("file1.py") in changed
        assert Path("file2.md") in changed

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_with_include_pattern(self, tmp_path: Path) -> None:
        """Test filtering with include patterns."""
        # Create test files
        (tmp_path / "file1.py").write_text("content")
        (tmp_path / "file2.md").write_text("content")
        (tmp_path / "file3.txt").write_text("content")

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            elif "diff" in cmd and cmd[-1] == "HEAD~1":
                result.stdout = "file1.py\nfile2.md\nfile3.txt\n"
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            changed = get_changed_files(
                since="HEAD~1",
                include_patterns=["*.py"],
            )

        assert len(changed) == 1
        assert Path("file1.py") in changed

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_with_exclude_pattern(self, tmp_path: Path) -> None:
        """Test filtering with exclude patterns."""
        # Create test files
        (tmp_path / "file1.py").write_text("content")
        (tmp_path / "test_file.py").write_text("content")

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            elif "diff" in cmd and cmd[-1] == "HEAD~1":
                result.stdout = "file1.py\ntest_file.py\n"
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            changed = get_changed_files(
                since="HEAD~1",
                exclude_patterns=["test_*.py"],
            )

        assert len(changed) == 1
        assert Path("file1.py") in changed

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_skips_deleted(self, tmp_path: Path) -> None:
        """Test that deleted files are skipped."""
        # Only create file1.py - file2.py is "deleted"
        (tmp_path / "file1.py").write_text("content")

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            elif "diff" in cmd and cmd[-1] == "HEAD~1":
                result.stdout = "file1.py\nfile2.py\n"  # file2.py doesn't exist
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            changed = get_changed_files(since="HEAD~1")

        assert len(changed) == 1
        assert Path("file1.py") in changed

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_includes_staged(self, tmp_path: Path) -> None:
        """Test that staged changes are included."""
        (tmp_path / "staged.py").write_text("content")

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            elif "diff" in cmd and "--cached" in cmd:
                result.stdout = "staged.py\n"
            elif "diff" in cmd:
                result.stdout = ""
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            changed = get_changed_files(since="HEAD~1", include_staged=True)

        assert Path("staged.py") in changed

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_bad_revision(self, tmp_path: Path) -> None:
        """Test handling of unknown revision reference."""
        call_count = 0

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1

            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result = MagicMock()
                result.stdout = str(tmp_path) + "\n"
                return result

            # First diff call fails with bad revision
            raise subprocess.CalledProcessError(
                128, cmd, stderr="unknown revision or path not in the working tree"
            )

        with patch("subprocess.run", side_effect=mock_run):
            changed = get_changed_files(since="nonexistent-ref")

        assert changed == []

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_git_error(self, tmp_path: Path) -> None:
        """Test handling of git command failure."""

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result = MagicMock()
                result.stdout = str(tmp_path) + "\n"
                return result
            raise subprocess.CalledProcessError(
                1, cmd, stderr="fatal: some other error"
            )

        with patch("subprocess.run", side_effect=mock_run):
            with pytest.raises(GitError, match="Git diff failed"):
                get_changed_files(since="HEAD~1")


class TestGetStagedFiles:
    """Tests for get_staged_files function."""

    @pytest.mark.requirement("FR-012")
    def test_get_staged_files_basic(self, tmp_path: Path) -> None:
        """Test basic staged file detection."""
        (tmp_path / "staged.py").write_text("content")

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            elif "diff" in cmd and "--cached" in cmd:
                result.stdout = "staged.py\n"
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            staged = get_staged_files()

        assert len(staged) == 1
        assert Path("staged.py") in staged

    @pytest.mark.requirement("FR-012")
    def test_get_staged_files_empty(self, tmp_path: Path) -> None:
        """Test when no files are staged."""

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            staged = get_staged_files()

        assert staged == []

    @pytest.mark.requirement("FR-012")
    def test_get_staged_files_with_patterns(self, tmp_path: Path) -> None:
        """Test staged files with include/exclude patterns."""
        (tmp_path / "file.py").write_text("content")
        (tmp_path / "test_file.py").write_text("content")

        def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                result.stdout = str(tmp_path) + "\n"
            elif "--cached" in cmd:
                result.stdout = "file.py\ntest_file.py\n"
            else:
                result.stdout = ""
            return result

        with patch("subprocess.run", side_effect=mock_run):
            staged = get_staged_files(
                include_patterns=["*.py"],
                exclude_patterns=["test_*.py"],
            )

        assert len(staged) == 1
        assert Path("file.py") in staged


class TestPatternMatching:
    """Tests for pattern matching utilities."""

    @pytest.mark.requirement("FR-012")
    def test_matches_simple_pattern(self) -> None:
        """Test simple glob pattern matching."""
        assert _matches_any_pattern("file.py", ["*.py"])
        assert _matches_any_pattern("test.md", ["*.md"])
        assert not _matches_any_pattern("file.py", ["*.md"])

    @pytest.mark.requirement("FR-012")
    def test_matches_double_star_pattern(self) -> None:
        """Test ** glob pattern matching."""
        assert _matches_any_pattern("tests/unit/test_foo.py", ["**/test_*.py"])
        assert _matches_any_pattern(
            "src/module/__pycache__/file.pyc", ["**/__pycache__/*"]
        )
        assert not _matches_any_pattern("src/main.py", ["**/test_*.py"])

    @pytest.mark.requirement("FR-012")
    def test_matches_directory_prefix(self) -> None:
        """Test pattern with directory prefix."""
        assert _matches_any_pattern("src/file.py", ["src/*.py"])
        assert not _matches_any_pattern("tests/file.py", ["src/*.py"])

    @pytest.mark.requirement("FR-012")
    def test_double_star_anywhere(self) -> None:
        """Test _matches_double_star_pattern directly."""
        # **/pattern matches at any depth
        assert _matches_double_star_pattern("deep/nested/test_foo.py", "**/test_*.py")
        assert _matches_double_star_pattern("test_foo.py", "**/test_*.py")

        # Doesn't match wrong pattern
        assert not _matches_double_star_pattern("foo.py", "**/test_*.py")


class TestGitRefValidation:
    """Tests for git reference validation (security hardening)."""

    @pytest.mark.requirement("FR-012")
    def test_valid_git_refs(self) -> None:
        """Test that valid git references pass validation."""
        valid_refs = [
            "HEAD",
            "HEAD~1",
            "HEAD^2",
            "main",
            "master",
            "feature/my-branch",
            "origin/main",
            "v1.0.0",
            "abc123def",
            "refs/heads/main",
            "HEAD~10",
            "main..HEAD",
            "main...HEAD",
        ]
        for ref in valid_refs:
            # Should not raise
            _validate_git_ref(ref)

    @pytest.mark.requirement("FR-012")
    def test_invalid_git_refs_special_chars(self) -> None:
        """Test that refs with shell metacharacters are rejected."""
        invalid_refs = [
            "HEAD; rm -rf /",  # Command injection attempt
            "$(whoami)",  # Command substitution
            "`id`",  # Backtick command substitution
            "main && echo pwned",  # Command chaining
            "HEAD | cat /etc/passwd",  # Pipe injection
            "branch>output",  # Redirection
            "branch<input",  # Input redirection
            "branch$VAR",  # Variable expansion
            "branch'quoted",  # Single quote
            'branch"quoted',  # Double quote
            "branch\\escaped",  # Backslash
            "branch\nnewline",  # Newline
            "branch\ttab",  # Tab
            "branch space",  # Space
        ]
        for ref in invalid_refs:
            with pytest.raises(GitError, match="Invalid git reference"):
                _validate_git_ref(ref)

    @pytest.mark.requirement("FR-012")
    def test_empty_git_ref(self) -> None:
        """Test that empty refs are rejected."""
        with pytest.raises(GitError, match="cannot be empty"):
            _validate_git_ref("")

    @pytest.mark.requirement("FR-012")
    def test_get_changed_files_validates_since(self, tmp_path: Path) -> None:
        """Test that get_changed_files validates the since parameter."""
        # Should fail validation before even trying to run git
        with pytest.raises(GitError, match="Invalid git reference"):
            get_changed_files(since="HEAD; rm -rf /")
