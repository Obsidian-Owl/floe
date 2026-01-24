"""Unit tests for Fusion static analysis in DBTFusionPlugin.

Tests for the lint_project() method that uses Fusion's built-in
static analysis for SQL linting.

Requirements:
    FR-019: Built-in static analysis
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
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
    def test_lint_project_calls_fusion_cli(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() invokes Fusion CLI with lint command."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "violations": [],
            "files_analyzed": 5,
        })
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
                fix=False,
            )

            mock_run.assert_called()
            # Verify lint command was used
            call_args = mock_run.call_args[0][0]
            assert "lint" in call_args

    @pytest.mark.requirement("FR-019")
    def test_lint_project_returns_violations(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() returns violations from Fusion analysis."""
        from floe_dbt_fusion import DBTFusionPlugin

        violations = [
            {
                "file": "models/test.sql",
                "line": 10,
                "column": 5,
                "rule": "L001",
                "message": "Trailing whitespace",
                "severity": "warning",
            }
        ]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "violations": violations,
            "files_analyzed": 5,
        })
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
            assert len(result.issues) == 1
            assert result.issues[0]["rule"] == "L001"

    @pytest.mark.requirement("FR-019")
    def test_lint_project_success_no_violations(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() returns success when no violations."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "violations": [],
            "files_analyzed": 10,
        })
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
            assert len(result.issues) == 0
            assert result.files_checked == 10

    @pytest.mark.requirement("FR-019")
    def test_lint_project_fix_mode(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() passes --fix flag when fix=True."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "violations": [],
            "files_analyzed": 5,
            "files_fixed": 3,
        })
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
            assert result.files_fixed == 3

    @pytest.mark.requirement("FR-019")
    def test_lint_project_json_format(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() requests JSON output format."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "violations": [],
            "files_analyzed": 5,
        })
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
            assert "--format" in call_args
            assert "json" in call_args


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
    def test_lint_project_handles_invalid_json(
        self, temp_dbt_project: Path
    ) -> None:
        """lint_project() handles invalid JSON from Fusion gracefully."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json"
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
            assert len(result.issues) == 0

    @pytest.mark.requirement("FR-019")
    def test_lint_project_handles_cli_failure(
        self, temp_dbt_project: Path
    ) -> None:
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
    def test_lint_empty_project(
        self, temp_dbt_project: Path
    ) -> None:
        """Linting empty project returns success with 0 files."""
        from floe_dbt_fusion import DBTFusionPlugin

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "violations": [],
            "files_analyzed": 0,
        })
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
    def test_lint_multiple_violations(
        self, temp_dbt_project: Path
    ) -> None:
        """Linting returns multiple violations."""
        from floe_dbt_fusion import DBTFusionPlugin

        violations = [
            {
                "file": "models/a.sql",
                "line": 1,
                "column": 1,
                "rule": "L001",
                "message": "Issue 1",
                "severity": "warning",
            },
            {
                "file": "models/b.sql",
                "line": 2,
                "column": 3,
                "rule": "L002",
                "message": "Issue 2",
                "severity": "error",
            },
            {
                "file": "models/c.sql",
                "line": 5,
                "column": 10,
                "rule": "L003",
                "message": "Issue 3",
                "severity": "warning",
            },
        ]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "violations": violations,
            "files_analyzed": 3,
        })
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
            assert len(result.issues) == 3
            assert result.files_checked == 3
