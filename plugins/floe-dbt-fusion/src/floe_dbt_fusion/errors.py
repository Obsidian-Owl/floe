"""DBT Fusion error hierarchy for floe-dbt-fusion.

This module defines custom exceptions for dbt Fusion plugin operations.
All exceptions inherit from DBTFusionError, the base exception class.

Exception Hierarchy:
    DBTFusionError (base)
    ├── DBTFusionNotFoundError   # Fusion CLI binary not found (FR-020)
    └── DBTAdapterUnavailableError # Rust adapter not available (FR-021)

These errors are specific to the Fusion plugin. For general dbt errors
(compilation, execution, configuration), use floe_dbt_core.errors.

Example:
    >>> from floe_dbt_fusion.errors import DBTFusionNotFoundError
    >>> raise DBTFusionNotFoundError(
    ...     searched_paths=["/usr/local/bin", "/opt/dbt-fusion/bin"],
    ... )
    Traceback (most recent call last):
        ...
    DBTFusionNotFoundError: dbt Fusion CLI not found
        Searched paths: /usr/local/bin, /opt/dbt-fusion/bin
        Install from: https://github.com/dbt-labs/dbt-fusion
"""

from __future__ import annotations


class DBTFusionError(Exception):
    """Base exception for all dbt Fusion plugin errors.

    All Fusion-specific exceptions inherit from this class, allowing
    callers to catch all Fusion errors with a single except clause.

    Attributes:
        message: Human-readable error description.

    Example:
        >>> try:
        ...     plugin.compile_project(...)
        ... except DBTFusionError as e:
        ...     print(f"Fusion operation failed: {e}")
    """

    def __init__(self, message: str) -> None:
        """Initialize DBTFusionError.

        Args:
            message: Human-readable error description.
        """
        self.message = message
        super().__init__(message)


class DBTFusionNotFoundError(DBTFusionError):
    """Raised when dbt Fusion CLI binary is not found (FR-020).

    This error indicates that the dbt Fusion CLI (dbt-sa-cli) could not
    be located on the system. The plugin searches standard paths and
    the PATH environment variable.

    Attributes:
        message: Human-readable error description.
        searched_paths: List of paths that were searched.
        install_url: URL for installation instructions.

    Example:
        >>> raise DBTFusionNotFoundError(
        ...     searched_paths=["/usr/local/bin", "~/.local/bin"],
        ... )
        Traceback (most recent call last):
            ...
        DBTFusionNotFoundError: dbt Fusion CLI not found
            Searched paths: /usr/local/bin, ~/.local/bin
            Install from: https://github.com/dbt-labs/dbt-fusion
    """

    INSTALL_URL = "https://github.com/dbt-labs/dbt-fusion"

    def __init__(
        self,
        searched_paths: list[str] | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize DBTFusionNotFoundError.

        Args:
            searched_paths: List of paths that were searched for the binary.
            message: Optional custom message. If not provided, a default
                message is generated.
        """
        self.searched_paths = searched_paths or []
        self.install_url = self.INSTALL_URL

        if message is None:
            message = "dbt Fusion CLI not found"
            if self.searched_paths:
                message += f"\n    Searched paths: {', '.join(self.searched_paths)}"
            message += f"\n    Install from: {self.install_url}"

        super().__init__(message)


class DBTAdapterUnavailableError(DBTFusionError):
    """Raised when Rust adapter is not available for target database (FR-021).

    This error indicates that dbt Fusion does not have a Rust-native
    adapter for the specified database. Fusion requires Rust adapters
    for high-performance execution; not all databases are supported.

    When this error occurs, the plugin should fall back to dbt-core
    (if floe-dbt-core is installed) or fail with a helpful message.

    Supported Rust Adapters:
        - DuckDB (duckdb-rs)
        - Snowflake (snowflake-connector-rust)

    Unsupported (requires fallback):
        - BigQuery
        - Databricks
        - Redshift
        - PostgreSQL

    Attributes:
        message: Human-readable error description.
        adapter: The adapter/database type that was requested.
        available_adapters: List of adapters that Fusion supports.
        fallback_available: Whether floe-dbt-core is installed for fallback.

    Example:
        >>> raise DBTAdapterUnavailableError(
        ...     adapter="bigquery",
        ...     available_adapters=["duckdb", "snowflake"],
        ...     fallback_available=True,
        ... )
        Traceback (most recent call last):
            ...
        DBTAdapterUnavailableError: Rust adapter unavailable for 'bigquery'
            Available Fusion adapters: duckdb, snowflake
            Fallback to dbt-core: available
    """

    # Adapters with Rust implementations in dbt Fusion
    SUPPORTED_ADAPTERS = ["duckdb", "snowflake"]

    def __init__(
        self,
        adapter: str,
        available_adapters: list[str] | None = None,
        fallback_available: bool = False,
        message: str | None = None,
    ) -> None:
        """Initialize DBTAdapterUnavailableError.

        Args:
            adapter: The adapter/database type that was requested.
            available_adapters: List of adapters that Fusion supports.
                Defaults to SUPPORTED_ADAPTERS if not provided.
            fallback_available: Whether floe-dbt-core is installed.
            message: Optional custom message. If not provided, a default
                message is generated.
        """
        self.adapter = adapter
        self.available_adapters = available_adapters or self.SUPPORTED_ADAPTERS
        self.fallback_available = fallback_available

        if message is None:
            message = f"Rust adapter unavailable for '{adapter}'"
            message += (
                f"\n    Available Fusion adapters: {', '.join(self.available_adapters)}"
            )
            fallback_status = "available" if fallback_available else "not installed"
            message += f"\n    Fallback to dbt-core: {fallback_status}"

        super().__init__(message)


def check_fallback_available() -> bool:
    """Check if floe-dbt-core is installed for fallback.

    Returns:
        True if floe-dbt-core is installed, False otherwise.

    Example:
        >>> if not check_fallback_available():
        ...     print("Install floe-dbt-core for automatic fallback")
    """
    try:
        import importlib.util

        return importlib.util.find_spec("floe_dbt_core") is not None
    except ImportError:
        return False
