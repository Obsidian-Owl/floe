"""CLI utility functions and error handling.

This module provides shared utilities for the floe CLI, including:
- Error handling and formatting
- Exit code constants
- Output helpers for consistent stderr/stdout usage

Requirement: FR-005 - Errors output as plain text to stderr with appropriate
non-zero exit codes for CI/CD integration.

Example:
    from floe_core.cli.utils import error_exit, ExitCode

    if not path.exists():
        error_exit("File not found", path=str(path))
"""

from __future__ import annotations

import sys
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from typing import NoReturn


class ExitCode(IntEnum):
    """Standard exit codes for CLI commands.

    These codes align with common Unix conventions and provide
    meaningful feedback for CI/CD pipelines.
    """

    SUCCESS = 0
    """Command completed successfully."""

    GENERAL_ERROR = 1
    """General error (catch-all for failures)."""

    USAGE_ERROR = 2
    """Invalid usage (bad arguments, missing required options)."""

    FILE_NOT_FOUND = 3
    """Required file or directory not found."""

    PERMISSION_ERROR = 4
    """Permission denied accessing file or resource."""

    VALIDATION_ERROR = 5
    """Input validation failed."""

    COMPILATION_ERROR = 6
    """Compilation or processing failed."""

    NETWORK_ERROR = 7
    """Network or remote service error."""


def error(message: str, **context: str | int | bool | None) -> None:
    """Print an error message to stderr.

    Args:
        message: Error message to display.
        **context: Optional context key-value pairs to include.

    Example:
        error("File not found", path="/path/to/file")
        # Output: Error: File not found (path=/path/to/file)
    """
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        full_message = f"Error: {message} ({context_str})"
    else:
        full_message = f"Error: {message}"

    click.echo(full_message, err=True)


def error_exit(
    message: str,
    exit_code: ExitCode = ExitCode.GENERAL_ERROR,
    **context: str | int | bool | None,
) -> NoReturn:
    """Print an error message to stderr and exit with a code.

    Args:
        message: Error message to display.
        exit_code: Exit code to use (default: GENERAL_ERROR).
        **context: Optional context key-value pairs to include.

    Raises:
        SystemExit: Always exits with the specified code.

    Example:
        error_exit("Compilation failed", exit_code=ExitCode.COMPILATION_ERROR)
    """
    error(message, **context)
    sys.exit(exit_code)


def warn(message: str, **context: str | int | bool | None) -> None:
    """Print a warning message to stderr.

    Args:
        message: Warning message to display.
        **context: Optional context key-value pairs to include.

    Example:
        warn("Deprecated option", option="--old-flag")
    """
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        full_message = f"Warning: {message} ({context_str})"
    else:
        full_message = f"Warning: {message}"

    click.echo(full_message, err=True)


def success(message: str) -> None:
    """Print a success message to stdout.

    Args:
        message: Success message to display.

    Example:
        success("Compilation complete: target/compiled_artifacts.json")
    """
    click.echo(message)


def validate_file_exists(path: Path, description: str = "File") -> None:
    """Validate that a file exists and is readable.

    Args:
        path: Path to validate.
        description: Human-readable description for error messages.

    Raises:
        SystemExit: If file does not exist or is not readable.
    """
    if not path.exists():
        error_exit(
            f"{description} not found",
            exit_code=ExitCode.FILE_NOT_FOUND,
            path=str(path),
        )
    if not path.is_file():
        error_exit(
            f"{description} is not a file",
            exit_code=ExitCode.VALIDATION_ERROR,
            path=str(path),
        )


def validate_directory_writable(path: Path, description: str = "Directory") -> None:
    """Validate that a directory exists and is writable, creating it if needed.

    Args:
        path: Directory path to validate.
        description: Human-readable description for error messages.

    Raises:
        SystemExit: If directory cannot be created or is not writable.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        error_exit(
            f"Cannot create {description}",
            exit_code=ExitCode.PERMISSION_ERROR,
            path=str(path),
        )
    except OSError as e:
        error_exit(
            f"Cannot create {description}: {e}",
            exit_code=ExitCode.GENERAL_ERROR,
            path=str(path),
        )
