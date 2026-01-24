"""SQLFluff integration for dbt SQL linting (FR-013).

This module provides SQLFluff integration for dialect-aware SQL linting
in dbt projects. It maps dbt adapter types to SQLFluff dialects.

Supported Dialects:
    - DuckDB: duckdb
    - Snowflake: snowflake
    - BigQuery: bigquery
    - PostgreSQL: postgres
    - Redshift: redshift
    - Databricks: sparksql

Functions:
    get_sqlfluff_dialect: Map dbt adapter to SQLFluff dialect.
    lint_sql_files: Lint SQL files in a dbt project.

Example:
    >>> from floe_dbt_core.linting import lint_sql_files
    >>> result = lint_sql_files(
    ...     project_dir=Path("my_project"),
    ...     dialect="duckdb",
    ...     fix=False,
    ... )
    >>> if not result.success:
    ...     for issue in result.issues:
    ...         print(f"{issue['code']}: {issue['description']}")

Requirements:
    FR-013: Dialect-specific SQL linting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Map dbt adapter types to SQLFluff dialects
DIALECT_MAP: dict[str, str] = {
    "duckdb": "duckdb",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "postgres": "postgres",
    "redshift": "redshift",
    "databricks": "sparksql",
    "spark": "sparksql",
    "trino": "trino",
    "athena": "athena",
}

# Default dialect when adapter not recognized
DEFAULT_DIALECT = "ansi"


@dataclass
class LintResult:
    """Result of SQL linting operation.

    Attributes:
        success: True if no issues found.
        issues: List of linting issues.
        files_checked: Number of SQL files checked.
        files_fixed: Number of files fixed (if fix=True).
    """

    success: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    files_checked: int = 0
    files_fixed: int = 0


def get_sqlfluff_dialect(adapter: str) -> str:
    """Map dbt adapter type to SQLFluff dialect.

    Args:
        adapter: dbt adapter type (e.g., "duckdb", "snowflake").

    Returns:
        SQLFluff dialect name. Defaults to "ansi" for unknown adapters.

    Requirements:
        FR-013: Dialect-specific linting

    Example:
        >>> get_sqlfluff_dialect("duckdb")
        'duckdb'
        >>> get_sqlfluff_dialect("unknown")
        'ansi'
    """
    normalized = adapter.lower()
    dialect = DIALECT_MAP.get(normalized, DEFAULT_DIALECT)

    if dialect == DEFAULT_DIALECT and normalized not in DIALECT_MAP:
        logger.warning(
            "unknown_adapter_dialect",
            adapter=adapter,
            default_dialect=DEFAULT_DIALECT,
        )

    return dialect


def lint_sql_files(
    project_dir: Path,
    dialect: str,
    fix: bool = False,
) -> LintResult:
    """Lint SQL files in a dbt project using SQLFluff.

    Args:
        project_dir: Path to dbt project directory.
        dialect: SQLFluff dialect to use.
        fix: If True, auto-fix issues.

    Returns:
        LintResult with detected issues.

    Requirements:
        FR-013: Dialect-specific SQL linting

    Example:
        >>> result = lint_sql_files(
        ...     project_dir=Path("my_project"),
        ...     dialect="duckdb",
        ...     fix=False,
        ... )
        >>> print(f"Checked {result.files_checked} files")
    """
    log = logger.bind(
        project_dir=str(project_dir),
        dialect=dialect,
        fix=fix,
    )

    # Find SQL files in models directory
    models_dir = project_dir / "models"
    if not models_dir.exists():
        log.debug("models_dir_not_found")
        return LintResult(success=True, files_checked=0)

    sql_files = list(models_dir.rglob("*.sql"))
    if not sql_files:
        log.debug("no_sql_files_found")
        return LintResult(success=True, files_checked=0)

    log.info("linting_started", file_count=len(sql_files))

    try:
        import sqlfluff

        # Check for project .sqlfluff config
        config_path = project_dir / ".sqlfluff"
        config_kwargs = {}
        if config_path.exists():
            config_kwargs["config_path"] = str(config_path)

        if fix:
            # Fix mode
            fixed_files = 0
            for sql_file in sql_files:
                try:
                    result = sqlfluff.fix(
                        str(sql_file),
                        dialect=dialect,
                        **config_kwargs,
                    )
                    if result:
                        fixed_files += 1
                except Exception as e:
                    log.warning("file_fix_failed", file=str(sql_file), error=str(e))

            log.info("fixing_completed", files_fixed=fixed_files)
            return LintResult(
                success=True,
                issues=[],
                files_checked=len(sql_files),
                files_fixed=fixed_files,
            )

        else:
            # Lint mode
            all_violations: list[dict[str, Any]] = []

            for sql_file in sql_files:
                try:
                    violations = sqlfluff.lint(
                        str(sql_file),
                        dialect=dialect,
                        **config_kwargs,
                    )
                    all_violations.extend(violations)
                except Exception as e:
                    log.warning("file_lint_failed", file=str(sql_file), error=str(e))

            # Convert violations to issue format
            issues = [
                {
                    "file": v.get("filepath", ""),
                    "line": v.get("start_line_no", 0),
                    "column": v.get("start_line_pos", 0),
                    "code": v.get("code", ""),
                    "description": v.get("description", ""),
                }
                for v in all_violations
            ]

            success = len(issues) == 0
            log.info(
                "linting_completed",
                files_checked=len(sql_files),
                issues_found=len(issues),
            )

            return LintResult(
                success=success,
                issues=issues,
                files_checked=len(sql_files),
                files_fixed=0,
            )

    except ImportError:
        log.error("sqlfluff_not_installed")
        raise ImportError(
            "SQLFluff is required for SQL linting. "
            "Install with: pip install sqlfluff"
        )


def get_adapter_from_profiles(
    profiles_dir: Path,
    profile_name: str,
    target: str,
) -> str | None:
    """Extract adapter type from profiles.yml.

    Args:
        profiles_dir: Path to directory containing profiles.yml.
        profile_name: Name of the profile.
        target: Name of the target.

    Returns:
        Adapter type (e.g., "duckdb") or None if not found.
    """
    import yaml

    profiles_path = profiles_dir / "profiles.yml"
    if not profiles_path.exists():
        return None

    try:
        with profiles_path.open() as f:
            profiles = yaml.safe_load(f)

        if profile_name not in profiles:
            return None

        profile = profiles[profile_name]
        outputs = profile.get("outputs", {})

        if target not in outputs:
            return None

        return outputs[target].get("type")

    except Exception as e:
        logger.warning("profiles_parse_failed", error=str(e))
        return None


__all__ = [
    "LintResult",
    "get_sqlfluff_dialect",
    "lint_sql_files",
    "get_adapter_from_profiles",
    "DIALECT_MAP",
    "DEFAULT_DIALECT",
]
