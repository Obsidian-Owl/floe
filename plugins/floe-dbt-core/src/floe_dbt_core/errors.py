"""DBT error hierarchy for floe-dbt-core.

This module defines custom exceptions for dbt-core plugin operations.
All exceptions inherit from DBTError, the base exception class.

Exception Hierarchy:
    DBTError (base)
    ├── DBTCompilationError  # Jinja/SQL compilation failed (FR-033)
    ├── DBTExecutionError    # Model execution failed (FR-034)
    ├── DBTConfigurationError # Invalid profiles/project config (FR-035)
    └── DBTLintError         # Linting process failed (FR-041)

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


class DBTError(Exception):
    """Base exception for all dbt plugin errors.

    All dbt exceptions inherit from this class, allowing callers
    to catch all dbt errors with a single except clause.

    Attributes:
        message: Human-readable error description.
        file_path: Path to the file where error occurred (if available).
        line_number: Line number in the file (if available).
        original_message: The original dbt error message (for debugging).

    Example:
        >>> try:
        ...     plugin.compile_project(...)
        ... except DBTError as e:
        ...     print(f"dbt operation failed: {e}")
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        original_message: str | None = None,
    ) -> None:
        """Initialize DBTError.

        Args:
            message: Human-readable error description.
            file_path: Path to the file where error occurred.
            line_number: Line number in the file.
            original_message: The original dbt error message.
        """
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        self.original_message = original_message or message

        # Build formatted message with location if available
        formatted = f"{message}"
        if file_path:
            formatted += f"\n    at {file_path}"
            if line_number is not None:
                formatted += f":{line_number}"

        super().__init__(formatted)


class DBTCompilationError(DBTError):
    """Raised when dbt compilation fails (FR-033).

    This error indicates Jinja parsing, SQL generation, or other
    compilation-phase failures. Typically caused by:
    - Undefined Jinja variables
    - Invalid ref() or source() calls
    - Syntax errors in SQL templates

    Attributes:
        message: Human-readable error description.
        file_path: Path to the model file with the error.
        line_number: Line number where compilation failed.
        original_message: The original dbt error message.

    Example:
        >>> raise DBTCompilationError(
        ...     message="Undefined ref: 'stg_orders'",
        ...     file_path="models/marts/dim_customers.sql",
        ...     line_number=23,
        ... )
        Traceback (most recent call last):
            ...
        DBTCompilationError: Compilation failed: Undefined ref: 'stg_orders'
            at models/marts/dim_customers.sql:23
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        original_message: str | None = None,
    ) -> None:
        """Initialize DBTCompilationError.

        Args:
            message: Human-readable error description.
            file_path: Path to the model file with the error.
            line_number: Line number where compilation failed.
            original_message: The original dbt error message.
        """
        super().__init__(
            f"Compilation failed: {message}",
            file_path=file_path,
            line_number=line_number,
            original_message=original_message,
        )


class DBTExecutionError(DBTError):
    """Raised when dbt model execution fails (FR-034).

    This error indicates runtime failures during model materialization
    or test execution. Typically caused by:
    - SQL syntax errors (dialect-specific)
    - Database connection issues
    - Data quality violations
    - Permission errors

    Attributes:
        message: Human-readable error description.
        model_name: The unique_id of the failed model (e.g., 'model.my_project.dim_customers').
        adapter: The dbt adapter in use (e.g., 'duckdb', 'snowflake').
        file_path: Path to the model file.
        line_number: Line number (if available from adapter error).
        original_message: The original dbt/adapter error message.

    Example:
        >>> raise DBTExecutionError(
        ...     message="Column 'customer_id' does not exist",
        ...     model_name="model.analytics.dim_customers",
        ...     adapter="snowflake",
        ... )
        Traceback (most recent call last):
            ...
        DBTExecutionError: Execution failed: Column 'customer_id' does not exist
            Model: model.analytics.dim_customers (adapter: snowflake)
    """

    def __init__(
        self,
        message: str,
        *,
        model_name: str | None = None,
        adapter: str | None = None,
        file_path: str | None = None,
        line_number: int | None = None,
        original_message: str | None = None,
    ) -> None:
        """Initialize DBTExecutionError.

        Args:
            message: Human-readable error description.
            model_name: The unique_id of the failed model.
            adapter: The dbt adapter in use.
            file_path: Path to the model file.
            line_number: Line number (if available from adapter error).
            original_message: The original dbt/adapter error message.
        """
        self.model_name = model_name
        self.adapter = adapter

        # Build execution-specific message
        full_message = f"Execution failed: {message}"
        if model_name:
            adapter_info = f" (adapter: {adapter})" if adapter else ""
            full_message += f"\n    Model: {model_name}{adapter_info}"

        # Store original for later formatting
        super().__init__(
            full_message,
            file_path=file_path,
            line_number=line_number,
            original_message=original_message,
        )
        # Override message since we already formatted it
        self.message = full_message


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
