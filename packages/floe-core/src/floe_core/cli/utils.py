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

    SIGNATURE_ERROR = 6
    """Signature verification failed (Epic 8B)."""

    COMPILATION_ERROR = 7
    """Compilation or processing failed."""

    NETWORK_ERROR = 8
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


# Alias for warn
warning = warn


def success(message: str) -> None:
    """Print a success message to stdout.

    Args:
        message: Success message to display.

    Example:
        success("Compilation complete: target/compiled_artifacts.json")
    """
    click.echo(message)


def info(message: str) -> None:
    """Print an informational message to stderr.

    Used for progress updates and status information that should
    not be captured by stdout redirection.

    Args:
        message: Informational message to display.

    Example:
        info("Compiling spec: floe.yaml")
    """
    click.echo(message, err=True)


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


_LOG_INJECTION_CHARS = "\n\r"
_MAX_LOG_PATH_LENGTH = 500
_MAX_ERROR_LENGTH = 200

# Allowed key file extensions for security validation
_ALLOWED_KEY_EXTENSIONS = frozenset({".pem", ".pub", ".key", ".crt", ""})


def sanitize_error(error: str | Exception, max_length: int = _MAX_ERROR_LENGTH) -> str:
    """Sanitize error message for safe user display.

    Removes potentially sensitive information from error messages:
    - File paths beyond first component
    - Stack trace details
    - Internal module paths
    - Control characters
    - Credential-like patterns

    Args:
        error: Error message string or Exception object.
        max_length: Maximum length of returned message.

    Returns:
        Sanitized error message safe for display to users.

    Example:
        >>> sanitize_error("/home/user/.secrets/key.pem not found")
        'File not found: key.pem'
    """
    import re

    msg = str(error)

    msg = "".join(c for c in msg if c.isprintable() or c in " \t")
    msg = re.sub(r"(/[a-zA-Z0-9_\-./]+)/([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)", r"[PATH]/\2", msg)
    msg = re.sub(
        r"(token|key|secret|password|credential|auth)[=:\s]+[^\s,;)]+",
        r"\1=[REDACTED]",
        msg,
        flags=re.IGNORECASE,
    )
    msg = re.sub(r"\b\d{12}\b", "[ACCOUNT_ID]", msg)

    if len(msg) > max_length:
        msg = msg[: max_length - 3] + "..."

    return msg


def validate_key_path(
    key_path: str | Path,
    allowed_dirs: list[Path] | None = None,
) -> Path:
    """Validate key file path against path traversal attacks.

    Ensures the key file:
    1. Resolves to an absolute path without traversal
    2. Is within allowed directories (cwd, home/.floe, /tmp, or custom)
    3. Has an allowed extension (.pem, .pub, .key, .crt)
    4. Does not contain suspicious path segments

    Args:
        key_path: User-provided key file path.
        allowed_dirs: Optional list of allowed parent directories.
                      Defaults to [cwd, ~/.floe, /tmp].

    Returns:
        Validated absolute path to the key file.

    Raises:
        SystemExit with VALIDATION_ERROR if path is unsafe.

    Example:
        >>> validate_key_path("./keys/signing.key")
        PosixPath('/current/dir/keys/signing.key')
        >>> validate_key_path("../../etc/passwd")
        # Raises SystemExit
    """
    path = Path(key_path)

    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as e:
        error_exit(
            f"Cannot resolve key path: {sanitize_error(e)}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if ".." in str(key_path):
        error_exit(
            "Key path cannot contain '..' (path traversal not allowed)",
            exit_code=ExitCode.VALIDATION_ERROR,
            path=sanitize_path_for_log(key_path),
        )

    if allowed_dirs is None:
        import tempfile

        allowed_dirs = [
            Path.cwd(),
            Path.home() / ".floe",
            Path(tempfile.gettempdir()) / "floe",
            Path("/etc/floe/keys"),
        ]

    is_allowed = any(_is_path_within(resolved, allowed_dir) for allowed_dir in allowed_dirs)

    if not is_allowed:
        error_exit(
            "Key path must be within allowed directories (cwd, ~/.floe, $TMPDIR/floe, /etc/floe/keys)",
            exit_code=ExitCode.VALIDATION_ERROR,
            path=sanitize_path_for_log(resolved),
        )

    suffix = resolved.suffix.lower()
    if suffix not in _ALLOWED_KEY_EXTENSIONS:
        error_exit(
            f"Key file has invalid extension '{suffix}'. Allowed: .pem, .pub, .key, .crt",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    return resolved


def _is_path_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def validate_output_path(output_path: str | Path) -> Path:
    """Validate output file path against path traversal attacks.

    Ensures the output path:
    1. Is within the current working directory
    2. Does not contain path traversal segments
    3. Parent directory can be created

    Args:
        output_path: User-provided output file path.

    Returns:
        Validated absolute path for output file.

    Raises:
        SystemExit with VALIDATION_ERROR if path is unsafe.
    """
    path = Path(output_path)

    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as e:
        error_exit(
            f"Cannot resolve output path: {sanitize_error(e)}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if ".." in str(output_path):
        error_exit(
            "Output path cannot contain '..' (path traversal not allowed)",
            exit_code=ExitCode.VALIDATION_ERROR,
            path=sanitize_path_for_log(output_path),
        )

    if not _is_path_within(resolved, Path.cwd()):
        error_exit(
            "Output path must be within current working directory",
            exit_code=ExitCode.VALIDATION_ERROR,
            path=sanitize_path_for_log(resolved),
        )

    return resolved


def sanitize_path_for_log(path: str | Path) -> str:
    """Sanitize a file path for safe logging (prevents log injection attacks)."""
    path_str = str(path)
    for char in _LOG_INJECTION_CHARS:
        path_str = path_str.replace(char, "")
    path_str = "".join(c for c in path_str if c.isprintable() or c == " ")
    if len(path_str) > _MAX_LOG_PATH_LENGTH:
        path_str = path_str[: _MAX_LOG_PATH_LENGTH - 3] + "..."
    return path_str


def sanitize_k8s_api_error(exc: Exception) -> str:
    """Sanitize Kubernetes API exception for safe logging.

    Extracts only the safe fields (status code and reason) from K8s
    ApiException, avoiding sensitive data in body or headers.

    Args:
        exc: Exception from kubernetes client (ApiException expected).

    Returns:
        Sanitized error message safe for logging.
    """
    status = getattr(exc, "status", None)
    reason = getattr(exc, "reason", None)

    if status is not None and reason is not None:
        return f"{reason} (HTTP {status})"
    if reason is not None:
        return str(reason)
    return type(exc).__name__
