"""DBTPlugin ABC for dbt execution environment plugins.

This module defines the abstract base class for dbt plugins that provide
dbt compilation and execution environments. DBT plugins are responsible for:
- Compiling dbt projects (Jinja to SQL)
- Executing dbt commands (run, test, snapshot)
- Providing SQL linting (optional, dialect-aware)
- Retrieving dbt artifacts (manifest, run results)

Note: This plugins WHERE dbt executes (local/cloud/fusion), NOT the SQL
transformation framework itself (which is enforced).

Example:
    >>> from floe_core.plugins.dbt import DBTPlugin
    >>> class LocalDBTPlugin(DBTPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "local"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from floe_core.plugin_metadata import PluginMetadata

# =============================================================================
# Error Classes (shared between plugins)
# =============================================================================


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
    """Raised when dbt compilation fails.

    This error indicates Jinja parsing, SQL generation, or other
    compilation-phase failures.

    Example:
        >>> raise DBTCompilationError(
        ...     message="Undefined ref: 'stg_orders'",
        ...     file_path="models/marts/dim_customers.sql",
        ...     line_number=23,
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        original_message: str | None = None,
    ) -> None:
        """Initialize DBTCompilationError."""
        super().__init__(
            f"Compilation failed: {message}",
            file_path=file_path,
            line_number=line_number,
            original_message=original_message,
        )


class DBTExecutionError(DBTError):
    """Raised when dbt model execution fails.

    This error indicates runtime failures during model materialization
    or test execution.

    Example:
        >>> raise DBTExecutionError(
        ...     message="Column 'customer_id' does not exist",
        ...     model_name="model.analytics.dim_customers",
        ... )
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
        """Initialize DBTExecutionError."""
        self.model_name = model_name
        self.adapter = adapter

        # Build execution-specific message
        full_message = f"Execution failed: {message}"
        if model_name:
            adapter_info = f" (adapter: {adapter})" if adapter else ""
            full_message += f"\n    Model: {model_name}{adapter_info}"

        super().__init__(
            full_message,
            file_path=file_path,
            line_number=line_number,
            original_message=original_message,
        )
        self.message = full_message


# =============================================================================
# Linting Types (shared between plugins)
# =============================================================================


class LintViolation(BaseModel):
    """A single linting violation detected in a SQL file.

    Represents a rule violation found by SQLFluff or Fusion static analysis.

    Attributes:
        file_path: Path to the SQL file containing the violation.
        line: Line number where the violation occurs (1-based).
        column: Column number where the violation occurs.
        code: Rule code (e.g., "L001", "ST01", "AM01").
        message: Human-readable description of the violation.
        severity: Severity level of the violation.

    Example:
        >>> violation = LintViolation(
        ...     file_path="models/customers.sql",
        ...     line=10,
        ...     column=5,
        ...     code="L001",
        ...     message="Trailing whitespace",
        ...     severity="warning",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(..., description="Path to the SQL file")
    line: int = Field(..., ge=1, description="Line number (1-based)")
    column: int = Field(..., ge=0, description="Column number")
    code: str = Field(..., min_length=1, description="Rule code (e.g., L001)")
    message: str = Field(..., description="Human-readable violation description")
    severity: Literal["error", "warning", "info"] = Field(
        default="warning",
        description="Severity level",
    )


# =============================================================================
# Result Data Classes
# =============================================================================


@dataclass
class DBTRunResult:
    """Result of a dbt command execution.

    Attributes:
        success: Whether the dbt command succeeded.
        manifest_path: Path to compiled manifest.json.
        run_results_path: Path to run_results.json.
        catalog_path: Path to catalog.json (if generated).
        execution_time_seconds: Total execution time.
        models_run: Number of models executed.
        tests_run: Number of tests executed.
        failures: Number of failures.
        metadata: Additional execution metadata.

    Example:
        >>> result = DBTRunResult(
        ...     success=True,
        ...     manifest_path=Path("target/manifest.json"),
        ...     run_results_path=Path("target/run_results.json"),
        ...     execution_time_seconds=45.2,
        ...     models_run=15,
        ...     tests_run=0,
        ...     failures=0
        ... )
    """

    success: bool
    manifest_path: Path
    run_results_path: Path
    catalog_path: Path | None = None
    execution_time_seconds: float = 0.0
    models_run: int = 0
    tests_run: int = 0
    failures: int = 0
    metadata: dict[str, Any] = field(default_factory=lambda: {})


@dataclass
class LintResult:
    """Result of SQL linting.

    Attributes:
        success: Whether all files passed linting.
        violations: List of linting violations (preferred).
        files_checked: Number of files checked.
        files_fixed: Number of files auto-fixed (if fix=True).

    Note:
        The `issues` property is deprecated. Use `violations` instead.

    Example:
        >>> v = LintViolation(
        ...     file_path="models/stg.sql", line=10, column=0,
        ...     code="L001", message="Issue"
        ... )
        >>> result = LintResult(success=False, violations=[v], files_checked=15)
    """

    success: bool
    violations: list[LintViolation] = field(default_factory=list)
    files_checked: int = 0
    files_fixed: int = 0

    @property
    def issues(self) -> list[dict[str, Any]]:
        """Deprecated: Use violations instead.

        Returns violations as list of dicts for backwards compatibility.
        """
        return [
            {
                "file": v.file_path,
                "line": v.line,
                "column": v.column,
                "code": v.code,
                "description": v.message,
            }
            for v in self.violations
        ]


class DBTPlugin(PluginMetadata):
    """Abstract base class for dbt execution environment plugins.

    DBTPlugin extends PluginMetadata with dbt-specific methods for
    compilation and execution. Implementations include LocalDBTPlugin
    (dbt-core), FusionDBTPlugin (dbt Fusion), and CloudDBTPlugin (dbt Cloud).

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - compile_project() method
        - run_models() method
        - test_models() method
        - lint_project() method
        - get_manifest() method
        - get_run_results() method
        - supports_parallel_execution() method
        - supports_sql_linting() method
        - get_runtime_metadata() method

    Example:
        >>> class LocalDBTPlugin(DBTPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "local"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def compile_project(self, project_dir, profiles_dir, target) -> Path:
        ...         from dbt.cli.main import dbtRunner
        ...         dbt = dbtRunner()
        ...         dbt.invoke(["compile", "--project-dir", str(project_dir)])
        ...         return project_dir / "target" / "manifest.json"

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
        - ADR-0043: dbt plugin architecture
    """

    @abstractmethod
    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project and return path to manifest.json.

        Compiles the dbt project (Jinja to SQL) without executing.
        Generates manifest.json with compiled model information.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name (e.g., "dev", "prod").

        Returns:
            Path to compiled manifest.json (typically target/manifest.json).

        Raises:
            CompilationError: If dbt compilation fails.

        Example:
            >>> manifest_path = plugin.compile_project(
            ...     project_dir=Path("dbt_project"),
            ...     profiles_dir=Path("~/.dbt"),
            ...     target="dev"
            ... )
            >>> manifest_path
            PosixPath('dbt_project/target/manifest.json')
        """
        ...

    @abstractmethod
    def run_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTRunResult:
        """Execute dbt models.

        Runs selected dbt models against the target database.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax (e.g., "tag:daily", "stg_*").
            exclude: dbt exclusion syntax.
            full_refresh: If True, rebuild incremental models from scratch.

        Returns:
            DBTRunResult with execution status and artifact paths.

        Example:
            >>> result = plugin.run_models(
            ...     project_dir=Path("dbt_project"),
            ...     profiles_dir=Path("~/.dbt"),
            ...     target="dev",
            ...     select="tag:daily"
            ... )
            >>> result.success
            True
            >>> result.models_run
            5
        """
        ...

    @abstractmethod
    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult:
        """Execute dbt tests.

        Runs dbt tests (schema tests and data tests) against the target.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax for tests.

        Returns:
            DBTRunResult with test results and failure count.

        Example:
            >>> result = plugin.test_models(
            ...     project_dir=Path("dbt_project"),
            ...     profiles_dir=Path("~/.dbt"),
            ...     target="dev"
            ... )
            >>> result.tests_run
            42
            >>> result.failures
            0
        """
        ...

    @abstractmethod
    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> LintResult:
        """Lint SQL files with dialect-aware validation.

        Runs SQL linting on the dbt project using SQLFluff or built-in
        linters (for dbt Fusion).

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name (used for dialect detection).
            fix: If True, auto-fix issues (if linter supports it).

        Returns:
            LintResult with all detected linting issues.

        Raises:
            DBTLintError: If linting process fails (not if SQL has issues).

        Example:
            >>> result = plugin.lint_project(
            ...     project_dir=Path("dbt_project"),
            ...     profiles_dir=Path("~/.dbt"),
            ...     target="dev",
            ...     fix=True
            ... )
            >>> result.files_fixed
            3
        """
        ...

    @abstractmethod
    def get_manifest(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt manifest.json.

        Loads and returns the dbt manifest from filesystem or API
        (for cloud runtimes).

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Parsed manifest.json as dictionary.

        Raises:
            FileNotFoundError: If manifest doesn't exist (not yet compiled).

        Example:
            >>> manifest = plugin.get_manifest(Path("dbt_project"))
            >>> len(manifest["nodes"])
            42
        """
        ...

    @abstractmethod
    def get_run_results(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt run_results.json.

        Loads and returns the latest dbt run results from filesystem
        or API (for cloud runtimes).

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Parsed run_results.json as dictionary.

        Raises:
            FileNotFoundError: If run_results doesn't exist (no runs yet).

        Example:
            >>> results = plugin.get_run_results(Path("dbt_project"))
            >>> results["elapsed_time"]
            45.2
        """
        ...

    @abstractmethod
    def supports_parallel_execution(self) -> bool:
        """Indicate whether runtime supports parallel model execution.

        Returns:
            True if runtime can execute models in parallel, False otherwise.

        Example:
            >>> plugin.supports_parallel_execution()
            True  # Local runtime supports --threads
        """
        ...

    @abstractmethod
    def supports_sql_linting(self) -> bool:
        """Indicate whether this execution environment provides SQL linting.

        Returns:
            True if lint_project() is implemented, False otherwise.

        Example:
            >>> plugin.supports_sql_linting()
            True  # Local runtime uses SQLFluff
        """
        ...

    @abstractmethod
    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime-specific metadata for observability.

        Provides metadata about the dbt execution environment for
        logging and monitoring purposes.

        Returns:
            Dictionary with runtime metadata (version, capabilities, etc.).

        Example:
            >>> metadata = plugin.get_runtime_metadata()
            >>> metadata
            {
                'runtime': 'local',
                'dbt_version': '1.7.0',
                'python_version': '3.11.0',
                'adapter': 'duckdb'
            }
        """
        ...


__all__ = [
    # Core classes
    "DBTPlugin",
    "DBTRunResult",
    "LintResult",
    "LintViolation",
    # Error classes
    "DBTError",
    "DBTCompilationError",
    "DBTExecutionError",
]
