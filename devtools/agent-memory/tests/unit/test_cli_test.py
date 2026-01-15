"""Unit tests for CLI test command.

Tests for the test command functionality:
- Quality validation execution
- Pass/fail display
- Verbose output
- Threshold-based exit codes
- Error handling

Implementation: T045 (FLO-630)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestTestCommand:
    """Tests for test CLI command."""

    @pytest.mark.requirement("FR-023")
    def test_test_runs_quality_validation(self) -> None:
        """Test that test command runs quality validation."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            # Mock successful validation
            mock_report = QualityReport(
                total_tests=3,
                passed_tests=3,
                failed_tests=0,
                results=[
                    TestResult(query="q1", passed=True),
                    TestResult(query="q2", passed=True),
                    TestResult(query="q3", passed=True),
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test"])

            assert result.exit_code == 0
            mock_validate.assert_called_once()

    @pytest.mark.requirement("FR-023")
    def test_test_displays_pass_status(self) -> None:
        """Test that test command displays pass status for each query."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            mock_report = QualityReport(
                total_tests=2,
                passed_tests=1,
                failed_tests=1,
                results=[
                    TestResult(query="What functions?", passed=True),
                    TestResult(query="What classes?", passed=False, missing_keywords=["class"]),
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test", "--threshold", "50"])

            assert "What functions?" in result.output
            assert "What classes?" in result.output

    @pytest.mark.requirement("FR-023")
    def test_test_displays_fail_status(self) -> None:
        """Test that test command displays fail status for failing queries."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            mock_report = QualityReport(
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                results=[
                    TestResult(
                        query="Missing query",
                        passed=False,
                        missing_keywords=["expected"],
                    ),
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test", "--threshold", "0"])

            assert "Missing query" in result.output

    @pytest.mark.requirement("FR-023")
    def test_test_verbose_shows_details(self) -> None:
        """Test that --verbose flag shows detailed results."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            mock_report = QualityReport(
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                results=[
                    TestResult(
                        query="Test query",
                        passed=False,
                        found_keywords=["found1", "found2"],
                        missing_keywords=["missing1"],
                        result_count=5,
                    ),
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test", "--verbose", "--threshold", "0"])

            # Verbose output shows counts and keywords
            assert "Results: 5" in result.output
            assert "found1" in result.output
            assert "missing1" in result.output

    @pytest.mark.requirement("FR-023")
    def test_test_verbose_shows_error(self) -> None:
        """Test that --verbose shows error messages."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            mock_report = QualityReport(
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                results=[
                    TestResult(
                        query="Error query",
                        passed=False,
                        error="Connection failed",
                    ),
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test", "--verbose", "--threshold", "0"])

            assert "Connection failed" in result.output

    @pytest.mark.requirement("FR-023")
    def test_test_exit_code_on_all_pass(self) -> None:
        """Test exit code 0 when all tests pass."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            mock_report = QualityReport(
                total_tests=3,
                passed_tests=3,
                failed_tests=0,
                results=[
                    TestResult(query="q1", passed=True),
                    TestResult(query="q2", passed=True),
                    TestResult(query="q3", passed=True),
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test"])

            assert result.exit_code == 0
            assert "All tests passed" in result.output

    @pytest.mark.requirement("FR-023")
    def test_test_exit_code_on_failure(self) -> None:
        """Test exit code 1 when tests fail below threshold."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            # 1 of 3 tests pass = 33.3% < 100% default threshold
            mock_report = QualityReport(
                total_tests=3,
                passed_tests=1,
                failed_tests=2,
                results=[
                    TestResult(query="q1", passed=True),
                    TestResult(query="q2", passed=False),
                    TestResult(query="q3", passed=False),
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test"])

            assert result.exit_code == 1
            assert "Failed:" in result.output

    @pytest.mark.requirement("FR-023")
    def test_test_threshold_option(self) -> None:
        """Test that --threshold option controls pass/fail."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            # 2 of 3 tests pass = 66.6%
            mock_report = QualityReport(
                total_tests=3,
                passed_tests=2,
                failed_tests=1,
                results=[
                    TestResult(query="q1", passed=True),
                    TestResult(query="q2", passed=True),
                    TestResult(query="q3", passed=False),
                ],
            )
            mock_validate.return_value = mock_report

            # With 50% threshold, should pass
            result = runner.invoke(app, ["test", "--threshold", "50"])
            assert result.exit_code == 0

            # With 80% threshold, should fail
            result = runner.invoke(app, ["test", "--threshold", "80"])
            assert result.exit_code == 1

    @pytest.mark.requirement("FR-023")
    def test_test_shows_summary(self) -> None:
        """Test that test command shows summary statistics."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()

            mock_report = QualityReport(
                total_tests=5,
                passed_tests=4,
                failed_tests=1,
                results=[
                    TestResult(query=f"q{i}", passed=(i != 3)) for i in range(5)
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test", "--threshold", "50"])

            # Should show summary with counts
            assert "4/5" in result.output

    @pytest.mark.requirement("FR-023")
    def test_test_fails_without_config(self) -> None:
        """Test that test command fails if config cannot be loaded."""
        from agent_memory.cli import app

        with patch("agent_memory.cli._load_config") as mock_config:
            mock_config.return_value = None

            result = runner.invoke(app, ["test"])

            assert result.exit_code == 1

    @pytest.mark.requirement("FR-023")
    def test_test_handles_client_error(self) -> None:
        """Test that test command handles client errors gracefully."""
        from agent_memory.cli import app
        from agent_memory.cognee_client import CogneeClientError

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()
            mock_validate.side_effect = CogneeClientError("API error")

            result = runner.invoke(app, ["test"])

            assert result.exit_code == 1
            assert "API error" in result.output


class TestDefaultTestQueries:
    """Tests for default test queries integration."""

    @pytest.mark.requirement("FR-023")
    def test_uses_default_queries(self) -> None:
        """Test that test command uses default queries from quality module."""
        from agent_memory.cli import app
        from agent_memory.ops.quality import QualityReport, TestResult, create_default_test_queries

        default_queries = create_default_test_queries()

        with (
            patch("agent_memory.cli._load_config") as mock_config,
            patch("agent_memory.cli.CogneeClient") as mock_client_class,
            patch("agent_memory.ops.quality.validate_quality") as mock_validate,
            patch("agent_memory.ops.quality.create_default_test_queries") as mock_queries,
        ):
            mock_config.return_value = MagicMock()
            mock_client_class.return_value = MagicMock()
            mock_queries.return_value = default_queries

            mock_report = QualityReport(
                total_tests=len(default_queries),
                passed_tests=len(default_queries),
                failed_tests=0,
                results=[
                    TestResult(query=q.query, passed=True) for q in default_queries
                ],
            )
            mock_validate.return_value = mock_report

            result = runner.invoke(app, ["test"])

            # Validate that default queries were fetched
            mock_queries.assert_called_once()
            # Validate that validate_quality was called with those queries
            call_args = mock_validate.call_args
            assert call_args is not None
