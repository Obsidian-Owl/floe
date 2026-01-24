"""DBT error hierarchy for floe-dbt-core.

This module defines custom exceptions for dbt-core plugin operations.
Base error classes (DBTError, DBTCompilationError, DBTExecutionError) are
imported from floe-core. Plugin-specific errors are defined here.

Exception Hierarchy:
    DBTError (base, from floe-core)
    ├── DBTCompilationError  # From floe-core
    ├── DBTExecutionError    # From floe-core
    ├── DBTConfigurationError # Plugin-specific (FR-035)
    └── DBTLintError         # Plugin-specific (FR-041)

All errors preserve file/line information when available per FR-036.

Example:
    >>> from floe_dbt_core.errors import DBTCompilationError
    >>> raise DBTCompilationError(
    ...     message="Jinja variable 'undefined_var' is undefined",
    ...     file_path="models/staging/stg_customers.sql",
    ...     line_number=15,
    ... )
    Traceback (most recent call last):
        ...
    DBTCompilationError: Compilation failed: Jinja variable 'undefined_var' is undefined
        at models/staging/stg_customers.sql:15
"""

from __future__ import annotations

# Import base error classes from floe-core (ARCH-001: avoid plugin cross-imports)
from floe_core.plugins.dbt import (
    DBTCompilationError,
    DBTError,
    DBTExecutionError,
)

# =============================================================================
# Plugin-specific error classes (extend floe-core base classes)
# =============================================================================


class DBTConfigurationError(DBTError):
    """Raised when dbt configuration is invalid (FR-035).

    This error indicates issues with profiles.yml, dbt_project.yml,
    or other configuration files. Typically caused by:
    - Missing required configuration keys
    - Invalid target name
    - Missing profiles.yml file
    - packages.yml dependency resolution failures

    Attributes:
        message: Human-readable error description.
        config_file: Path to the problematic config file.
        missing_keys: List of missing required keys (if applicable).
        available_targets: List of available targets (for target errors).

    Example:
        >>> raise DBTConfigurationError(
        ...     message="Target 'production' not found",
        ...     config_file="~/.dbt/profiles.yml",
        ...     available_targets=["dev", "staging"],
        ... )
        Traceback (most recent call last):
            ...
        DBTConfigurationError: Configuration error: Target 'production' not found
            File: ~/.dbt/profiles.yml
            Available targets: dev, staging
    """

    def __init__(
        self,
        message: str,
        *,
        config_file: str | None = None,
        missing_keys: list[str] | None = None,
        available_targets: list[str] | None = None,
        original_message: str | None = None,
    ) -> None:
        """Initialize DBTConfigurationError.

        Args:
            message: Human-readable error description.
            config_file: Path to the problematic config file.
            missing_keys: List of missing required keys.
            available_targets: List of available targets (for target errors).
            original_message: The original dbt error message.
        """
        self.config_file = config_file
        self.missing_keys = missing_keys
        self.available_targets = available_targets

        # Build configuration-specific message
        full_message = f"Configuration error: {message}"
        if config_file:
            full_message += f"\n    File: {config_file}"
        if missing_keys:
            full_message += f"\n    Missing keys: {', '.join(missing_keys)}"
        if available_targets:
            full_message += f"\n    Available targets: {', '.join(available_targets)}"

        super().__init__(
            full_message,
            original_message=original_message,
        )
        self.message = full_message


class DBTLintError(DBTError):
    """Raised when the linting process itself fails (FR-041).

    This error indicates that the linting tool (SQLFluff) encountered
    an error during execution, NOT that SQL issues were found.

    For SQL linting violations, the plugin returns LintResult with
    violations list. This exception is for when SQLFluff itself fails.

    Attributes:
        message: Human-readable error description.
        linter: The linting tool that failed (e.g., 'sqlfluff').
        dialect: The SQL dialect being used.
        original_message: The original linter error message.

    Example:
        >>> raise DBTLintError(
        ...     message="SQLFluff config parse error",
        ...     linter="sqlfluff",
        ...     dialect="snowflake",
        ... )
        Traceback (most recent call last):
            ...
        DBTLintError: Lint error: SQLFluff config parse error
            Linter: sqlfluff (dialect: snowflake)
    """

    def __init__(
        self,
        message: str,
        *,
        linter: str = "sqlfluff",
        dialect: str | None = None,
        file_path: str | None = None,
        original_message: str | None = None,
    ) -> None:
        """Initialize DBTLintError.

        Args:
            message: Human-readable error description.
            linter: The linting tool that failed.
            dialect: The SQL dialect being used.
            file_path: Path to the file being linted (if applicable).
            original_message: The original linter error message.
        """
        self.linter = linter
        self.dialect = dialect

        # Build lint-specific message
        full_message = f"Lint error: {message}"
        dialect_info = f" (dialect: {dialect})" if dialect else ""
        full_message += f"\n    Linter: {linter}{dialect_info}"

        super().__init__(
            full_message,
            file_path=file_path,
            original_message=original_message,
        )
        self.message = full_message


def parse_dbt_error_location(error_message: str) -> tuple[str | None, int | None]:
    """Parse file path and line number from dbt error message.

    dbt error messages often contain file location information in
    various formats. This function extracts that information.

    Args:
        error_message: The raw dbt error message.

    Returns:
        Tuple of (file_path, line_number). Either or both may be None
        if the location cannot be parsed.

    Example:
        >>> parse_dbt_error_location("Error in model.project.dim at models/dim.sql:15")
        ('models/dim.sql', 15)

        >>> parse_dbt_error_location("Some error without location info")
        (None, None)
    """
    import re

    # Try common dbt error formats
    patterns = [
        # Format: "at /path/to/file.sql:123"
        r"at (\S+\.sql):(\d+)",
        # Format: "in file '/path/to/file.sql' at line 123"
        r"in file ['\"]([^'\"]+)['\"] at line (\d+)",
        # Format: "Error in /path/to/file.sql line 123"
        r"Error in (\S+\.sql) line (\d+)",
        # Format: "/path/to/file.sql:123:45" (path:line:col)
        r"(\S+\.sql):(\d+):\d+",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            file_path = match.group(1)
            line_number = int(match.group(2))
            return file_path, line_number

    return None, None


__all__ = [
    # Re-exported from floe-core for backwards compatibility
    "DBTError",
    "DBTCompilationError",
    "DBTExecutionError",
    # Plugin-specific error classes
    "DBTConfigurationError",
    "DBTLintError",
    "parse_dbt_error_location",
]
