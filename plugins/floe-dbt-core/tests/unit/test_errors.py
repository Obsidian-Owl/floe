"""Unit tests for DBTCorePlugin error handling.

Tests error preservation and file/line information.

Requirements:
    - FR-036: Errors preserve file/line information when available
"""

from __future__ import annotations

import pytest

from floe_dbt_core.errors import (
    DBTCompilationError,
    DBTConfigurationError,
    DBTError,
    DBTExecutionError,
    DBTLintError,
    parse_dbt_error_location,
)


class TestDBTError:
    """Test base DBTError class."""

    @pytest.mark.requirement("FR-036")
    def test_dbt_error_preserves_message(self) -> None:
        """DBTError should preserve the error message."""
        error = DBTError("Something went wrong")
        assert error.message == "Something went wrong"
        assert "Something went wrong" in str(error)

    @pytest.mark.requirement("FR-036")
    def test_dbt_error_preserves_file_path(self) -> None:
        """DBTError should preserve file path when provided."""
        error = DBTError(
            "Error occurred",
            file_path="models/staging/stg_orders.sql",
        )
        assert error.file_path == "models/staging/stg_orders.sql"
        assert "stg_orders.sql" in str(error)

    @pytest.mark.requirement("FR-036")
    def test_dbt_error_preserves_line_number(self) -> None:
        """DBTError should preserve line number when provided."""
        error = DBTError(
            "Error occurred",
            file_path="models/staging/stg_orders.sql",
            line_number=42,
        )
        assert error.line_number == 42
        assert ":42" in str(error)

    @pytest.mark.requirement("FR-036")
    def test_dbt_error_preserves_original_message(self) -> None:
        """DBTError should preserve original dbt error message."""
        original = "dbt.exceptions.CompilationException: undefined variable"
        error = DBTError(
            "Compilation failed",
            original_message=original,
        )
        assert error.original_message == original


class TestDBTCompilationError:
    """Test DBTCompilationError class."""

    @pytest.mark.requirement("FR-033")
    def test_compilation_error_prefixes_message(self) -> None:
        """DBTCompilationError should prefix with 'Compilation failed:'."""
        error = DBTCompilationError("undefined variable 'foo'")
        assert "Compilation failed:" in str(error)
        assert "undefined variable 'foo'" in str(error)

    @pytest.mark.requirement("FR-033")
    def test_compilation_error_with_location(self) -> None:
        """DBTCompilationError should include file location."""
        error = DBTCompilationError(
            "undefined variable 'foo'",
            file_path="models/dim_customers.sql",
            line_number=15,
        )
        assert "dim_customers.sql:15" in str(error)

    @pytest.mark.requirement("FR-033")
    def test_compilation_error_is_dbt_error(self) -> None:
        """DBTCompilationError should inherit from DBTError."""
        error = DBTCompilationError("test error")
        assert isinstance(error, DBTError)


class TestDBTExecutionError:
    """Test DBTExecutionError class."""

    @pytest.mark.requirement("FR-034")
    def test_execution_error_prefixes_message(self) -> None:
        """DBTExecutionError should prefix with 'Execution failed:'."""
        error = DBTExecutionError("Column 'id' not found")
        assert "Execution failed:" in str(error)
        assert "Column 'id' not found" in str(error)

    @pytest.mark.requirement("FR-034")
    def test_execution_error_includes_model_name(self) -> None:
        """DBTExecutionError should include model name when provided."""
        error = DBTExecutionError(
            "Column 'id' not found",
            model_name="model.my_project.dim_customers",
        )
        assert "model.my_project.dim_customers" in str(error)

    @pytest.mark.requirement("FR-034")
    def test_execution_error_includes_adapter(self) -> None:
        """DBTExecutionError should include adapter info when provided."""
        error = DBTExecutionError(
            "Column 'id' not found",
            model_name="model.my_project.dim_customers",
            adapter="snowflake",
        )
        assert "snowflake" in str(error)

    @pytest.mark.requirement("FR-034")
    def test_execution_error_is_dbt_error(self) -> None:
        """DBTExecutionError should inherit from DBTError."""
        error = DBTExecutionError("test error")
        assert isinstance(error, DBTError)


class TestDBTConfigurationError:
    """Test DBTConfigurationError class."""

    @pytest.mark.requirement("FR-035")
    def test_configuration_error_prefixes_message(self) -> None:
        """DBTConfigurationError should prefix with 'Configuration error:'."""
        error = DBTConfigurationError("Missing profiles.yml")
        assert "Configuration error:" in str(error)
        assert "Missing profiles.yml" in str(error)

    @pytest.mark.requirement("FR-035")
    def test_configuration_error_includes_config_file(self) -> None:
        """DBTConfigurationError should include config file path."""
        error = DBTConfigurationError(
            "Invalid target",
            config_file="~/.dbt/profiles.yml",
        )
        assert "profiles.yml" in str(error)

    @pytest.mark.requirement("FR-035")
    def test_configuration_error_includes_missing_keys(self) -> None:
        """DBTConfigurationError should list missing required keys."""
        error = DBTConfigurationError(
            "Missing required keys",
            missing_keys=["host", "user", "password"],
        )
        assert "host" in str(error)
        assert "user" in str(error)
        assert "password" in str(error)

    @pytest.mark.requirement("FR-035")
    def test_configuration_error_includes_available_targets(self) -> None:
        """DBTConfigurationError should list available targets for target errors."""
        error = DBTConfigurationError(
            "Target 'production' not found",
            available_targets=["dev", "staging"],
        )
        assert "dev" in str(error)
        assert "staging" in str(error)

    @pytest.mark.requirement("FR-035")
    def test_configuration_error_is_dbt_error(self) -> None:
        """DBTConfigurationError should inherit from DBTError."""
        error = DBTConfigurationError("test error")
        assert isinstance(error, DBTError)


class TestDBTLintError:
    """Test DBTLintError class."""

    @pytest.mark.requirement("FR-041")
    def test_lint_error_prefixes_message(self) -> None:
        """DBTLintError should prefix with 'Lint error:'."""
        error = DBTLintError("SQLFluff failed to parse config")
        assert "Lint error:" in str(error)
        assert "SQLFluff failed to parse config" in str(error)

    @pytest.mark.requirement("FR-041")
    def test_lint_error_includes_linter_name(self) -> None:
        """DBTLintError should include linter name."""
        error = DBTLintError("Config parse failed", linter="sqlfluff")
        assert "sqlfluff" in str(error)

    @pytest.mark.requirement("FR-041")
    def test_lint_error_includes_dialect(self) -> None:
        """DBTLintError should include SQL dialect when provided."""
        error = DBTLintError(
            "Unsupported syntax",
            linter="sqlfluff",
            dialect="snowflake",
        )
        assert "snowflake" in str(error)

    @pytest.mark.requirement("FR-041")
    def test_lint_error_is_dbt_error(self) -> None:
        """DBTLintError should inherit from DBTError."""
        error = DBTLintError("test error")
        assert isinstance(error, DBTError)


class TestParseDbtErrorLocation:
    """Test parse_dbt_error_location utility function."""

    @pytest.mark.requirement("FR-036")
    def test_parse_location_from_at_format(self) -> None:
        """parse_dbt_error_location should parse 'at file:line' format."""
        file_path, line = parse_dbt_error_location(
            "Error at models/dim_customers.sql:15"
        )
        assert file_path == "models/dim_customers.sql"
        assert line == 15

    @pytest.mark.requirement("FR-036")
    def test_parse_location_from_in_file_format(self) -> None:
        """parse_dbt_error_location should parse 'in file X at line Y' format."""
        file_path, line = parse_dbt_error_location(
            "Error in file 'models/stg_orders.sql' at line 42"
        )
        assert file_path == "models/stg_orders.sql"
        assert line == 42

    @pytest.mark.requirement("FR-036")
    def test_parse_location_returns_none_when_not_found(self) -> None:
        """parse_dbt_error_location should return (None, None) when no location."""
        file_path, line = parse_dbt_error_location("Some error without location info")
        assert file_path is None
        assert line is None

    @pytest.mark.requirement("FR-036")
    def test_parse_location_from_path_line_col_format(self) -> None:
        """parse_dbt_error_location should parse 'path:line:col' format."""
        file_path, line = parse_dbt_error_location(
            "models/marts/fact_orders.sql:100:5: ERROR"
        )
        assert file_path == "models/marts/fact_orders.sql"
        assert line == 100
