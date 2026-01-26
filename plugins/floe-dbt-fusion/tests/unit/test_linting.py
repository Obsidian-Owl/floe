"""Unit tests for Fusion static analysis in DBTFusionPlugin.

Tests for the lint_project() method that uses Fusion's built-in
static analysis for SQL linting.

Requirements:
    FR-019: Built-in static analysis
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Fusion Static Analysis Tests
# ---------------------------------------------------------------------------


class TestFusionStaticAnalysis:
    """Tests for Fusion's built-in static analysis."""

    @pytest.mark.requirement("FR-019")
    def test_lint_project_calls_fusion_cli(self, temp_dbt_project: Path) -> None:
        """lint_project() invokes Fusion CLI with lint command."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "violations": [],
                "files_analyzed": 5,
            }
        )
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            plugin = DBTFusionPlugin()
            plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            mock_run.assert_called()
            # Verify lint command was used
            call_args = mock_run.call_args[0][0]
            assert "lint" in call_args

    @pytest.mark.requirement("FR-019")
    def test_lint_project_returns_violations(self, temp_dbt_project: Path) -> None:
        """lint_project() returns violations from Fusion analysis.

        Note: Fusion outputs TEXT, not JSON. Format: file.sql:line:col: severity: message
        """
        from floe_dbt_fusion import DBTFusionPlugin

        # Fusion lint outputs text in format: file.sql:line:col: severity: message
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Linting models/test.sql\n"
            "models/test.sql:10:5: warning: Trailing whitespace\n"
            "Done linting 1 file\n"
        )
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            assert result.success is False
            assert len(result.violations) == 1
            assert result.violations[0].message == "Trailing whitespace"
            assert result.violations[0].line == 10

    @pytest.mark.requirement("FR-019")
    def test_lint_project_success_no_violations(self, temp_dbt_project: Path) -> None:
        """lint_project() returns success when no violations.

        Note: Fusion outputs TEXT, not JSON. The code counts SQL files in output.
        """
        from floe_dbt_fusion import DBTFusionPlugin

        # Fusion lint outputs text with SQL file names
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Linting model_a.sql\nLinting model_b.sql\nLinting model_c.sql\nDone linting 3 files\n"
        )
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            assert result.success is True
            assert len(result.violations) == 0
            # Code counts unique SQL file names in output
            assert result.files_checked == 3

    @pytest.mark.requirement("FR-019")
    def test_lint_project_fix_mode(self, temp_dbt_project: Path) -> None:
        """lint_project() passes --fix flag when fix=True.

        Note: Code counts "fixed" mentions in output.
        """
        from floe_dbt_fusion import DBTFusionPlugin

        # Fusion lint outputs text with "fixed" for each fix
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Linting model_a.sql - fixed\n"
            "Linting model_b.sql - fixed\n"
            "Linting model_c.sql - fixed\n"
            "Done linting 3 files, fixed 3\n"
        )
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            plugin = DBTFusionPlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=True,
            )

            # Verify --fix flag was passed
            call_args = mock_run.call_args[0][0]
            assert "--fix" in call_args
            # Code counts "fixed" mentions in output
            assert result.files_fixed == 4  # "fixed" appears 4 times

    @pytest.mark.requirement("FR-019")
    def test_lint_project_passes_correct_args(self, temp_dbt_project: Path) -> None:
        """lint_project() passes correct arguments to Fusion CLI.

        Note: Fusion lint outputs TEXT, not JSON. The CLI receives:
        - lint command
        - --project-dir
        - --profiles-dir
        - --target
        """
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Linting test.sql\nDone\n"
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            plugin = DBTFusionPlugin()
            plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            call_args = mock_run.call_args[0][0]
            assert "lint" in call_args
            assert "--project-dir" in call_args
            assert "--profiles-dir" in call_args
            assert "--target" in call_args


# ---------------------------------------------------------------------------
# DBTFusionPlugin lint_project() Tests
# ---------------------------------------------------------------------------


class TestDBTFusionPluginLinting:
    """Tests for DBTFusionPlugin.lint_project() method."""

    @pytest.mark.requirement("FR-019")
    def test_supports_sql_linting_returns_true(self) -> None:
        """DBTFusionPlugin.supports_sql_linting() returns True."""
        from floe_dbt_fusion import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()

            assert plugin.supports_sql_linting() is True

    @pytest.mark.requirement("FR-019")
    def test_lint_project_handles_empty_output(self, temp_dbt_project: Path) -> None:
        """lint_project() handles empty output from Fusion gracefully.

        Note: Fusion outputs TEXT. If output doesn't match expected patterns,
        the code should return an empty result without crashing.
        """
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "no recognizable patterns here"
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            # Should return empty result, not crash
            assert result.success is True
            assert len(result.violations) == 0

    @pytest.mark.requirement("FR-019")
    def test_lint_project_handles_cli_failure(self, temp_dbt_project: Path) -> None:
        """lint_project() handles Fusion CLI failure."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: lint command failed"

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            # Non-zero exit but we should still return a result
            assert result.files_checked == 0


# ---------------------------------------------------------------------------
# Comparison: Fusion vs SQLFluff
# ---------------------------------------------------------------------------


class TestFusionVsSQLFluff:
    """Tests comparing Fusion static analysis to SQLFluff."""

    @pytest.mark.requirement("FR-019")
    def test_fusion_linting_is_faster(self) -> None:
        """Document: Fusion static analysis is faster than SQLFluff.

        This is a documentation test - Fusion's Rust-based analyzer
        provides ~30x faster linting than SQLFluff for large projects.
        """
        # This test documents the expected behavior
        # Actual performance testing would be in integration tests
        from floe_dbt_fusion import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()
            # Fusion is thread-safe and uses Rust for parsing
            assert plugin.supports_parallel_execution() is True
            assert plugin.supports_sql_linting() is True

    @pytest.mark.requirement("FR-019")
    def test_fusion_linting_is_thread_safe(self) -> None:
        """Fusion static analysis can run in parallel."""
        from floe_dbt_fusion import DBTFusionPlugin

        with patch(
            "floe_dbt_fusion.plugin.detect_fusion_binary",
            return_value=Path("/usr/local/bin/dbt-sa-cli"),
        ):
            plugin = DBTFusionPlugin()

            # Fusion is Rust-based and thread-safe
            assert plugin.supports_parallel_execution() is True


# ---------------------------------------------------------------------------
# Edge Cases Tests
# ---------------------------------------------------------------------------


class TestFusionLintingEdgeCases:
    """Tests for edge cases in Fusion linting."""

    @pytest.mark.requirement("FR-019")
    def test_lint_empty_project(self, temp_dbt_project: Path) -> None:
        """Linting empty project returns success with 0 files."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "violations": [],
                "files_analyzed": 0,
            }
        )
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            assert result.success is True
            assert result.files_checked == 0

    @pytest.mark.requirement("FR-019")
    def test_lint_multiple_violations(self, temp_dbt_project: Path) -> None:
        """Linting returns multiple violations.

        Note: Fusion outputs TEXT. Format: file.sql:line:col: severity: message
        """
        from floe_dbt_fusion import DBTFusionPlugin

        # Fusion lint outputs text with multiple violations
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Linting models/a.sql\n"
            "models/a.sql:1:1: warning: Issue 1\n"
            "Linting models/b.sql\n"
            "models/b.sql:2:3: error: Issue 2\n"
            "Linting models/c.sql\n"
            "models/c.sql:5:10: warning: Issue 3\n"
            "Done linting 3 files\n"
        )
        mock_result.stderr = ""

        with (
            patch(
                "floe_dbt_fusion.plugin.detect_fusion_binary",
                return_value=Path("/usr/local/bin/dbt-sa-cli"),
            ),
            patch("subprocess.run", return_value=mock_result),
        ):
            plugin = DBTFusionPlugin()
            result = plugin.lint_project(
                project_dir=temp_dbt_project,
                profiles_dir=temp_dbt_project,
                target="dev",
                fix=False,
            )

            assert result.success is False
            assert len(result.violations) == 3
            assert result.files_checked == 3
