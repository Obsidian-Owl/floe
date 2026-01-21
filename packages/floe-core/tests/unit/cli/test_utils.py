"""Unit tests for the CLI utility functions.

Task ID: T041
Phase: 4 - User Story 3 (CLI Utilities)
User Story: US3 - Error Handling and Output
Requirements: FR-005

Tests cover:
- ExitCode enum values
- error() function output format
- error_exit() behavior
- warn() function output format
- success() function output
- info() function output
- validate_file_exists() validation
- validate_directory_writable() validation
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestExitCodeEnum:
    """Tests for the ExitCode enum."""

    @pytest.mark.requirement("FR-005")
    def test_exit_code_values(self) -> None:
        """Test ExitCode enum has expected values."""
        from floe_core.cli.utils import ExitCode

        assert ExitCode.SUCCESS == 0
        assert ExitCode.GENERAL_ERROR == 1
        assert ExitCode.USAGE_ERROR == 2
        assert ExitCode.FILE_NOT_FOUND == 3
        assert ExitCode.PERMISSION_ERROR == 4
        assert ExitCode.VALIDATION_ERROR == 5
        assert ExitCode.COMPILATION_ERROR == 6
        assert ExitCode.NETWORK_ERROR == 7

    @pytest.mark.requirement("FR-005")
    def test_exit_code_is_int_enum(self) -> None:
        """Test ExitCode is an IntEnum for proper exit code usage."""
        from enum import IntEnum

        from floe_core.cli.utils import ExitCode

        assert issubclass(ExitCode, IntEnum)


class TestErrorFunction:
    """Tests for the error() function."""

    @pytest.mark.requirement("FR-005")
    def test_error_simple_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test error() outputs simple message to stderr."""
        from floe_core.cli.utils import error

        error("Something went wrong")

        captured = capsys.readouterr()
        assert "Error: Something went wrong" in captured.err
        assert captured.out == ""

    @pytest.mark.requirement("FR-005")
    def test_error_with_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test error() includes context in message."""
        from floe_core.cli.utils import error

        error("File not found", path="/path/to/file")

        captured = capsys.readouterr()
        assert "Error: File not found" in captured.err
        assert "path=/path/to/file" in captured.err

    @pytest.mark.requirement("FR-005")
    def test_error_with_multiple_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test error() includes multiple context values."""
        from floe_core.cli.utils import error

        error("Validation failed", line=10, column=5)

        captured = capsys.readouterr()
        assert "Error: Validation failed" in captured.err
        assert "line=10" in captured.err
        assert "column=5" in captured.err

    @pytest.mark.requirement("FR-005")
    def test_error_with_none_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test error() filters out None context values."""
        from floe_core.cli.utils import error

        error("Something failed", path=None, code=42)

        captured = capsys.readouterr()
        assert "path=None" not in captured.err
        assert "code=42" in captured.err


class TestErrorExitFunction:
    """Tests for the error_exit() function."""

    @pytest.mark.requirement("FR-005")
    def test_error_exit_raises_system_exit(self) -> None:
        """Test error_exit() raises SystemExit."""
        from floe_core.cli.utils import ExitCode, error_exit

        with pytest.raises(SystemExit) as exc_info:
            error_exit("Fatal error")

        assert exc_info.value.code == ExitCode.GENERAL_ERROR

    @pytest.mark.requirement("FR-005")
    def test_error_exit_with_custom_code(self) -> None:
        """Test error_exit() uses custom exit code."""
        from floe_core.cli.utils import ExitCode, error_exit

        with pytest.raises(SystemExit) as exc_info:
            error_exit("File missing", exit_code=ExitCode.FILE_NOT_FOUND)

        assert exc_info.value.code == ExitCode.FILE_NOT_FOUND

    @pytest.mark.requirement("FR-005")
    def test_error_exit_outputs_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test error_exit() outputs error message before exiting."""
        from floe_core.cli.utils import error_exit

        with pytest.raises(SystemExit):
            error_exit("Critical failure")

        captured = capsys.readouterr()
        assert "Error: Critical failure" in captured.err


class TestWarnFunction:
    """Tests for the warn() function."""

    @pytest.mark.requirement("FR-005")
    def test_warn_simple_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test warn() outputs simple warning to stderr."""
        from floe_core.cli.utils import warn

        warn("This feature is deprecated")

        captured = capsys.readouterr()
        assert "Warning: This feature is deprecated" in captured.err
        assert captured.out == ""

    @pytest.mark.requirement("FR-005")
    def test_warn_with_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test warn() includes context in message."""
        from floe_core.cli.utils import warn

        warn("Deprecated option", option="--old-flag")

        captured = capsys.readouterr()
        assert "Warning: Deprecated option" in captured.err
        assert "option=--old-flag" in captured.err

    @pytest.mark.requirement("FR-005")
    def test_warning_is_alias_for_warn(self) -> None:
        """Test warning is an alias for warn."""
        from floe_core.cli.utils import warn, warning

        assert warning is warn


class TestSuccessFunction:
    """Tests for the success() function."""

    @pytest.mark.requirement("FR-005")
    def test_success_outputs_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test success() outputs to stdout not stderr."""
        from floe_core.cli.utils import success

        success("Operation complete")

        captured = capsys.readouterr()
        assert "Operation complete" in captured.out
        assert captured.err == ""


class TestInfoFunction:
    """Tests for the info() function."""

    @pytest.mark.requirement("FR-005")
    def test_info_outputs_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test info() outputs to stderr for progress messages."""
        from floe_core.cli.utils import info

        info("Processing file...")

        captured = capsys.readouterr()
        assert "Processing file..." in captured.err
        assert captured.out == ""


class TestValidateFileExists:
    """Tests for the validate_file_exists() function."""

    @pytest.mark.requirement("FR-005")
    def test_validate_file_exists_passes_for_existing_file(self, tmp_path: Path) -> None:
        """Test validate_file_exists() passes for existing file."""
        from floe_core.cli.utils import validate_file_exists

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should not raise
        validate_file_exists(test_file)

    @pytest.mark.requirement("FR-005")
    def test_validate_file_exists_fails_for_missing_file(self, tmp_path: Path) -> None:
        """Test validate_file_exists() exits for missing file."""
        from floe_core.cli.utils import ExitCode, validate_file_exists

        missing_file = tmp_path / "missing.txt"

        with pytest.raises(SystemExit) as exc_info:
            validate_file_exists(missing_file)

        assert exc_info.value.code == ExitCode.FILE_NOT_FOUND

    @pytest.mark.requirement("FR-005")
    def test_validate_file_exists_fails_for_directory(self, tmp_path: Path) -> None:
        """Test validate_file_exists() exits for directory."""
        from floe_core.cli.utils import ExitCode, validate_file_exists

        with pytest.raises(SystemExit) as exc_info:
            validate_file_exists(tmp_path)  # tmp_path is a directory

        assert exc_info.value.code == ExitCode.VALIDATION_ERROR

    @pytest.mark.requirement("FR-005")
    def test_validate_file_exists_custom_description(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test validate_file_exists() uses custom description."""
        from floe_core.cli.utils import validate_file_exists

        missing_file = tmp_path / "config.yaml"

        with pytest.raises(SystemExit):
            validate_file_exists(missing_file, description="Configuration")

        captured = capsys.readouterr()
        assert "Configuration not found" in captured.err


class TestValidateDirectoryWritable:
    """Tests for the validate_directory_writable() function."""

    @pytest.mark.requirement("FR-005")
    def test_validate_directory_writable_creates_directory(self, tmp_path: Path) -> None:
        """Test validate_directory_writable() creates directory if needed."""
        from floe_core.cli.utils import validate_directory_writable

        new_dir = tmp_path / "new_directory"

        validate_directory_writable(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    @pytest.mark.requirement("FR-005")
    def test_validate_directory_writable_creates_nested_directory(self, tmp_path: Path) -> None:
        """Test validate_directory_writable() creates nested directories."""
        from floe_core.cli.utils import validate_directory_writable

        nested_dir = tmp_path / "a" / "b" / "c"

        validate_directory_writable(nested_dir)

        assert nested_dir.exists()
        assert nested_dir.is_dir()

    @pytest.mark.requirement("FR-005")
    def test_validate_directory_writable_passes_for_existing(self, tmp_path: Path) -> None:
        """Test validate_directory_writable() passes for existing directory."""
        from floe_core.cli.utils import validate_directory_writable

        # tmp_path already exists
        validate_directory_writable(tmp_path)

        assert tmp_path.exists()


__all__: list[str] = [
    "TestExitCodeEnum",
    "TestErrorFunction",
    "TestErrorExitFunction",
    "TestWarnFunction",
    "TestSuccessFunction",
    "TestInfoFunction",
    "TestValidateFileExists",
    "TestValidateDirectoryWritable",
]
