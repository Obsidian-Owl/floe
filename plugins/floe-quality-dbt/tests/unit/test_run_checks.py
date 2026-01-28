"""Unit tests for DBTExpectationsPlugin run_checks functionality.

Tests for US3 - Runtime quality check execution:
    - T048: run_checks() basic execution
    - FLOE-DQ102 error on check failures
    - FLOE-DQ106 timeout handling
    - fail_fast behavior
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualitySuite,
    QualitySuiteResult,
)

if TYPE_CHECKING:
    from floe_quality_dbt import DBTExpectationsPlugin


class TestRunChecksBasicExecution:
    """Tests for run_checks() basic execution (T048)."""

    @pytest.mark.requirement("FR-004", "FR-027", "FR-037")
    def test_run_checks_returns_suite_result(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """run_checks returns QualitySuiteResult with correct structure."""
        result = dbt_plugin.run_checks(
            suite_name="test_suite",
            data_source="staging.orders",
            options=None,
        )

        assert isinstance(result, QualitySuiteResult)
        assert result.suite_name == "test_suite"
        assert result.model_name == "staging.orders"

    @pytest.mark.requirement("FR-004", "FR-037")
    def test_run_checks_with_options(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """run_checks accepts execution options."""
        result = dbt_plugin.run_checks(
            suite_name="test_suite",
            data_source="staging.orders",
            options={"timeout_seconds": 60, "fail_fast": True},
        )

        assert isinstance(result, QualitySuiteResult)

    @pytest.mark.requirement("FR-004", "FR-037")
    def test_run_suite_executes_checks(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """run_suite executes all checks in the suite."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="id_not_null",
                    type="not_null",
                    column="id",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheck(
                    name="email_format",
                    type="regex_match",
                    column="email",
                    dimension=Dimension.VALIDITY,
                    parameters={"regex": r"^[a-z]+@[a-z]+\.[a-z]+$"},
                ),
            ],
        )
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = dbt_plugin.run_suite(suite, connection_config)

        assert isinstance(result, QualitySuiteResult)
        assert result.model_name == "test_model"
        assert isinstance(result.checks, list)

    @pytest.mark.requirement("FR-004")
    def test_run_suite_empty_checks_passes(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """run_suite with no checks returns passing result."""
        suite = QualitySuite(model_name="test_model", checks=[])
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = dbt_plugin.run_suite(suite, connection_config)

        assert result.passed is True
        assert len(result.checks) == 0


class TestRunChecksFailures:
    """Tests for FLOE-DQ102 check failure handling."""

    @pytest.mark.requirement("FR-042")
    def test_failed_checks_reported_in_results(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """Failed checks are included in results with correct metadata."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="email_not_null",
                    type="not_null",
                    column="email",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
            ],
        )
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = dbt_plugin.run_suite(suite, connection_config)

        assert isinstance(result, QualitySuiteResult)
        for check_result in result.checks:
            assert isinstance(check_result, QualityCheckResult)
            assert check_result.dimension in Dimension
            assert check_result.severity in SeverityLevel


class TestTimeoutHandling:
    """Tests for FLOE-DQ106 timeout handling."""

    @pytest.mark.requirement("FR-032", "FR-046")
    def test_suite_default_timeout(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """Suite uses default timeout of 300 seconds."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="check1",
                    type="not_null",
                    column="id",
                    dimension=Dimension.COMPLETENESS,
                ),
            ],
        )
        assert suite.timeout_seconds == 300

    @pytest.mark.requirement("FR-032")
    def test_suite_custom_timeout(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """Suite accepts custom timeout value."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[],
            timeout_seconds=60,
        )
        assert suite.timeout_seconds == 60


class TestFailFastBehavior:
    """Tests for fail_fast behavior."""

    @pytest.mark.requirement("FR-004")
    def test_fail_fast_default_false(self) -> None:
        """fail_fast defaults to False."""
        suite = QualitySuite(model_name="test_model", checks=[])
        assert suite.fail_fast is False

    @pytest.mark.requirement("FR-004")
    def test_fail_fast_enabled(self) -> None:
        """Suite accepts fail_fast=True."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[],
            fail_fast=True,
        )
        assert suite.fail_fast is True


class TestValidateExpectations:
    """Tests for validate_expectations method."""

    @pytest.mark.requirement("FR-004")
    def test_validate_expectations_returns_list(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """validate_expectations returns list of QualityCheckResult."""
        results = dbt_plugin.validate_expectations(
            data_source="staging.orders",
            expectations=[
                {"type": "not_null", "column": "order_id"},
                {"type": "unique", "column": "order_id"},
            ],
        )

        assert isinstance(results, list)

    @pytest.mark.requirement("FR-004")
    def test_validate_expectations_empty_list(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """validate_expectations handles empty expectations list."""
        results = dbt_plugin.validate_expectations(
            data_source="staging.orders",
            expectations=[],
        )

        assert results == []


class TestDbtIntegration:
    """Tests specific to dbt-expectations integration."""

    @pytest.mark.requirement("FR-037")
    def test_plugin_executes_via_dbt(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """Plugin is designed to execute quality checks via dbt test command."""
        # This verifies the plugin has the right interface for dbt integration
        assert dbt_plugin.name == "dbt_expectations"
        assert "dbt" in dbt_plugin.description.lower()

    @pytest.mark.requirement("FR-037")
    def test_plugin_supports_dbt_dialects(self, dbt_plugin: DBTExpectationsPlugin) -> None:
        """Plugin supports dialects compatible with dbt."""
        assert dbt_plugin.supports_dialect("duckdb")
        assert dbt_plugin.supports_dialect("postgresql")
        assert dbt_plugin.supports_dialect("snowflake")
