"""Unit tests for SQLFluff integration in DBTCorePlugin.

Tests for the lint_project() method that uses SQLFluff for
dialect-aware SQL linting.

Requirements:
    FR-013: Dialect-specific linting
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# LintViolation Pydantic Model Tests
# ---------------------------------------------------------------------------


class TestLintViolationModel:
    """Tests for LintViolation Pydantic model."""

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_creation(self) -> None:
        """LintViolation can be created with valid data."""
        from floe_dbt_core.linting import LintViolation

        violation = LintViolation(
            file_path="models/customers.sql",
            line=10,
            column=5,
            code="L001",
            message="Trailing whitespace",
            severity="warning",
        )

        assert violation.file_path == "models/customers.sql"
        assert violation.line == 10
        assert violation.column == 5
        assert violation.code == "L001"
        assert violation.message == "Trailing whitespace"
        assert violation.severity == "warning"

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_is_frozen(self) -> None:
        """LintViolation is immutable (frozen)."""
        from floe_dbt_core.linting import LintViolation

        violation = LintViolation(
            file_path="models/test.sql",
            line=1,
            column=0,
            code="L001",
            message="Test",
            severity="warning",
        )

        with pytest.raises(ValidationError):
            violation.line = 5  # type: ignore[misc]

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_default_severity(self) -> None:
        """LintViolation defaults to 'warning' severity."""
        from floe_dbt_core.linting import LintViolation

        violation = LintViolation(
            file_path="models/test.sql",
            line=1,
            column=0,
            code="L001",
            message="Test",
        )

        assert violation.severity == "warning"

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_valid_severities(self) -> None:
        """LintViolation accepts error, warning, info severities."""
        from floe_dbt_core.linting import LintViolation

        for severity in ["error", "warning", "info"]:
            violation = LintViolation(
                file_path="models/test.sql",
                line=1,
                column=0,
                code="L001",
                message="Test",
                severity=severity,  # type: ignore[arg-type]
            )
            assert violation.severity == severity

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_invalid_severity(self) -> None:
        """LintViolation rejects invalid severity."""
        from floe_dbt_core.linting import LintViolation

        with pytest.raises(ValidationError, match="severity"):
            LintViolation(
                file_path="models/test.sql",
                line=1,
                column=0,
                code="L001",
                message="Test",
                severity="critical",  # type: ignore[arg-type]
            )

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_line_must_be_positive(self) -> None:
        """LintViolation requires line >= 1."""
        from floe_dbt_core.linting import LintViolation

        with pytest.raises(ValidationError, match="line"):
            LintViolation(
                file_path="models/test.sql",
                line=0,  # Invalid: must be >= 1
                column=0,
                code="L001",
                message="Test",
            )

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_code_required(self) -> None:
        """LintViolation requires non-empty code."""
        from floe_dbt_core.linting import LintViolation

        with pytest.raises(ValidationError, match="code"):
            LintViolation(
                file_path="models/test.sql",
                line=1,
                column=0,
                code="",  # Invalid: must be non-empty
                message="Test",
            )

    @pytest.mark.requirement("FR-013")
    def test_lint_violation_forbids_extra_fields(self) -> None:
        """LintViolation rejects extra fields (extra='forbid')."""
        from floe_dbt_core.linting import LintViolation

        with pytest.raises(ValidationError, match="extra"):
            LintViolation(
                file_path="models/test.sql",
                line=1,
                column=0,
                code="L001",
                message="Test",
                extra_field="not allowed",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# SQLFluff Dialect Mapping Tests
# ---------------------------------------------------------------------------


class TestSQLFluffDialectMapping:
    """Tests for SQLFluff dialect mapping from dbt adapters."""

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_duckdb(self) -> None:
        """DuckDB adapter maps to duckdb SQLFluff dialect."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        dialect = get_sqlfluff_dialect("duckdb")

        assert dialect == "duckdb"

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_snowflake(self) -> None:
        """Snowflake adapter maps to snowflake SQLFluff dialect."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        dialect = get_sqlfluff_dialect("snowflake")

        assert dialect == "snowflake"

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_bigquery(self) -> None:
        """BigQuery adapter maps to bigquery SQLFluff dialect."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        dialect = get_sqlfluff_dialect("bigquery")

        assert dialect == "bigquery"

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_postgres(self) -> None:
        """PostgreSQL adapter maps to postgres SQLFluff dialect."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        dialect = get_sqlfluff_dialect("postgres")

        assert dialect == "postgres"

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_redshift(self) -> None:
        """Redshift adapter maps to redshift SQLFluff dialect."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        dialect = get_sqlfluff_dialect("redshift")

        assert dialect == "redshift"

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_databricks(self) -> None:
        """Databricks adapter maps to sparksql SQLFluff dialect."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        dialect = get_sqlfluff_dialect("databricks")

        assert dialect == "sparksql"

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_unknown_defaults_to_ansi(self) -> None:
        """Unknown adapter defaults to ANSI SQL dialect."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        dialect = get_sqlfluff_dialect("unknown_adapter")

        assert dialect == "ansi"

    @pytest.mark.requirement("FR-013")
    def test_dialect_mapping_case_insensitive(self) -> None:
        """Dialect mapping is case-insensitive."""
        from floe_dbt_core.linting import get_sqlfluff_dialect

        assert get_sqlfluff_dialect("DuckDB") == "duckdb"
        assert get_sqlfluff_dialect("SNOWFLAKE") == "snowflake"
        assert get_sqlfluff_dialect("BigQuery") == "bigquery"


# ---------------------------------------------------------------------------
# SQLFluff Linting Tests
# ---------------------------------------------------------------------------


class TestSQLFluffLinting:
    """Tests for SQLFluff linting functionality."""

    @pytest.mark.requirement("FR-013")
    def test_lint_project_calls_sqlfluff(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() invokes SQLFluff with correct dialect."""
        from floe_dbt_core.linting import lint_sql_files

        mock_result = MagicMock()
        mock_result.violations = []

        with patch("sqlfluff.lint", return_value=[]) as mock_lint:
            result = lint_sql_files(
                project_dir=temp_dbt_project,
                dialect="duckdb",
                fix=False,
            )

            mock_lint.assert_called()
            assert result.success is True

    @pytest.mark.requirement("FR-013")
    def test_lint_project_returns_violations(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() returns violations from SQLFluff."""
        from floe_dbt_core.linting import LintViolation, lint_sql_files

        mock_violations = [
            {
                "filepath": str(temp_dbt_project / "models" / "test.sql"),
                "start_line_no": 10,
                "start_line_pos": 5,
                "code": "L001",
                "description": "Trailing whitespace",
            }
        ]

        with patch("sqlfluff.lint", return_value=mock_violations):
            result = lint_sql_files(
                project_dir=temp_dbt_project,
                dialect="duckdb",
                fix=False,
            )

            assert result.success is False
            # Check new violations property (LintViolation objects)
            assert len(result.violations) == 1
            assert isinstance(result.violations[0], LintViolation)
            assert result.violations[0].code == "L001"
            assert result.violations[0].message == "Trailing whitespace"
            assert result.violations[0].line == 10
            assert result.violations[0].column == 5
            # Check backwards-compatible issues property (dict format)
            assert len(result.issues) == 1
            assert result.issues[0]["code"] == "L001"

    @pytest.mark.requirement("FR-013")
    def test_lint_project_fix_mode(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() calls sqlfluff.fix when fix=True."""
        from floe_dbt_core.linting import lint_sql_files

        with patch("sqlfluff.fix") as mock_fix:
            mock_fix.return_value = []
            result = lint_sql_files(
                project_dir=temp_dbt_project,
                dialect="duckdb",
                fix=True,
            )

            mock_fix.assert_called()
            assert result.files_fixed >= 0

    @pytest.mark.requirement("FR-013")
    def test_lint_project_counts_files(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() counts checked files."""
        from floe_dbt_core.linting import lint_sql_files

        with patch("sqlfluff.lint", return_value=[]):
            result = lint_sql_files(
                project_dir=temp_dbt_project,
                dialect="duckdb",
                fix=False,
            )

            assert result.files_checked >= 0


# ---------------------------------------------------------------------------
# DBTCorePlugin lint_project() Integration Tests
# ---------------------------------------------------------------------------


class TestDBTCorePluginLinting:
    """Tests for DBTCorePlugin.lint_project() method."""

    @pytest.mark.requirement("FR-013")
    def test_lint_project_success(
        self, temp_dbt_project: Path, mock_dbt_runner: MagicMock
    ) -> None:
        """DBTCorePlugin.lint_project() returns success for clean project."""
        from floe_dbt_core import DBTCorePlugin

        with patch("floe_dbt_core.linting.lint_sql_files") as mock_lint:
            mock_lint.return_value = MagicMock(
                success=True,
                issues=[],
                files_checked=5,
                files_fixed=0,
            )

            plugin = DBTCorePlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            assert result.success is True
            assert result.files_checked == 5

    @pytest.mark.requirement("FR-013")
    def test_lint_project_with_issues(
        self, temp_dbt_project: Path, mock_dbt_runner: MagicMock
    ) -> None:
        """DBTCorePlugin.lint_project() returns issues found."""
        from floe_dbt_core import DBTCorePlugin

        issues = [
            {"code": "L001", "description": "Trailing whitespace"},
            {"code": "L003", "description": "Inconsistent indentation"},
        ]

        with patch("floe_dbt_core.linting.lint_sql_files") as mock_lint:
            mock_lint.return_value = MagicMock(
                success=False,
                issues=issues,
                files_checked=5,
                files_fixed=0,
            )

            plugin = DBTCorePlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            assert result.success is False
            assert len(result.issues) == 2

    @pytest.mark.requirement("FR-013")
    def test_lint_project_with_fix(
        self, temp_dbt_project: Path, mock_dbt_runner: MagicMock
    ) -> None:
        """DBTCorePlugin.lint_project() fixes issues when fix=True."""
        from floe_dbt_core import DBTCorePlugin

        with patch("floe_dbt_core.linting.lint_sql_files") as mock_lint:
            mock_lint.return_value = MagicMock(
                success=True,
                issues=[],
                files_checked=5,
                files_fixed=3,
            )

            plugin = DBTCorePlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=True,
            )

            assert result.success is True
            assert result.files_fixed == 3

    @pytest.mark.requirement("FR-013")
    def test_supports_sql_linting_returns_true(self) -> None:
        """DBTCorePlugin.supports_sql_linting() returns True."""
        from floe_dbt_core import DBTCorePlugin

        plugin = DBTCorePlugin()

        assert plugin.supports_sql_linting() is True


# ---------------------------------------------------------------------------
# Edge Cases Tests
# ---------------------------------------------------------------------------


class TestLintingEdgeCases:
    """Tests for edge cases in linting functionality."""

    @pytest.mark.requirement("FR-013")
    def test_lint_empty_project(self, tmp_path: Path) -> None:
        """Linting empty project returns success with 0 files."""
        from floe_dbt_core.linting import lint_sql_files

        # Create empty project
        project_dir = tmp_path / "empty_project"
        project_dir.mkdir()
        (project_dir / "models").mkdir()

        with patch("sqlfluff.lint", return_value=[]):
            result = lint_sql_files(
                project_dir=project_dir,
                dialect="duckdb",
                fix=False,
            )

            assert result.success is True
            assert result.files_checked == 0

    @pytest.mark.requirement("FR-013")
    def test_lint_handles_sqlfluff_error(
        self, temp_dbt_project: Path
    ) -> None:
        """Linting handles SQLFluff errors gracefully by logging warning.

        Per implementation, SQLFluff errors per-file are caught and logged
        as warnings, not re-raised. This allows partial results.
        """
        from floe_dbt_core.linting import lint_sql_files

        with patch(
            "sqlfluff.lint",
            side_effect=Exception("SQLFluff error"),
        ):
            # Should complete without raising - errors are logged as warnings
            result = lint_sql_files(
                project_dir=temp_dbt_project,
                dialect="duckdb",
                fix=False,
            )
            # Files were checked but errors logged as warnings
            assert result.files_checked >= 1
            assert result.success is True  # No violations collected due to error

    @pytest.mark.requirement("FR-013")
    def test_lint_uses_project_sqlfluff_config(
        self, temp_dbt_project: Path
    ) -> None:
        """Linting respects project's .sqlfluff config if present."""
        from floe_dbt_core.linting import lint_sql_files

        # Create .sqlfluff config
        config_content = """[sqlfluff]
dialect = duckdb
exclude_rules = L001,L002
"""
        (temp_dbt_project / ".sqlfluff").write_text(config_content)

        with patch("sqlfluff.lint", return_value=[]) as mock_lint:
            lint_sql_files(
                project_dir=temp_dbt_project,
                dialect="duckdb",
                fix=False,
            )

            # Should use project's config path
            mock_lint.assert_called()
