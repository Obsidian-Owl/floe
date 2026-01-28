"""Unit tests for DBTExpectationsPlugin.

Tests:
    - T048: run_checks() basic execution
"""

from __future__ import annotations

from typing import Any

import pytest
from floe_core.schemas.quality_config import (
    Dimension,
    QualityConfig,
    SeverityLevel,
)
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualitySuite,
    QualitySuiteResult,
)


class TestDBTExpectationsPluginMetadata:
    """Tests for plugin metadata properties."""

    @pytest.mark.requirement("FR-039")
    def test_plugin_name(self, dbt_plugin) -> None:
        """Plugin returns correct name."""
        assert dbt_plugin.name == "dbt_expectations"

    @pytest.mark.requirement("FR-039")
    def test_plugin_version(self, dbt_plugin) -> None:
        """Plugin returns version string."""
        assert dbt_plugin.version == "0.1.0"

    @pytest.mark.requirement("FR-039")
    def test_plugin_floe_api_version(self, dbt_plugin) -> None:
        """Plugin returns floe API version."""
        assert dbt_plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("FR-039")
    def test_plugin_description(self, dbt_plugin) -> None:
        """Plugin returns description."""
        assert "dbt-expectations" in dbt_plugin.description


class TestDBTExpectationsPluginValidateConfig:
    """Tests for validate_config method."""

    @pytest.mark.requirement("FR-002")
    def test_validate_config_success(self, dbt_plugin) -> None:
        """Validates config with matching provider."""
        config = QualityConfig(provider="dbt_expectations")
        result = dbt_plugin.validate_config(config)
        assert result.success is True
        assert len(result.errors) == 0

    @pytest.mark.requirement("FR-002")
    def test_validate_config_provider_mismatch(self, dbt_plugin) -> None:
        """Fails validation for mismatched provider."""
        config = QualityConfig(provider="great_expectations")
        result = dbt_plugin.validate_config(config)
        assert result.success is False
        assert "Provider mismatch" in result.errors[0]


class TestDBTExpectationsPluginRunSuite:
    """Tests for run_suite method (T048)."""

    @pytest.mark.requirement("FR-004", "FR-027", "FR-037")
    def test_run_suite_returns_result(self, dbt_plugin) -> None:
        """run_suite returns QualitySuiteResult."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[
                QualityCheck(
                    name="id_not_null",
                    type="not_null",
                    column="id",
                    dimension=Dimension.COMPLETENESS,
                ),
            ],
        )
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = dbt_plugin.run_suite(suite, connection_config)

        assert isinstance(result, QualitySuiteResult)
        assert result.model_name == "test_model"

    @pytest.mark.requirement("FR-004")
    def test_run_suite_empty_checks(self, dbt_plugin) -> None:
        """run_suite handles empty checks list."""
        suite = QualitySuite(model_name="test_model", checks=[])
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = dbt_plugin.run_suite(suite, connection_config)

        assert result.passed is True
        assert len(result.checks) == 0


class TestDBTExpectationsPluginRunChecks:
    """Tests for run_checks method."""

    @pytest.mark.requirement("FR-004", "FR-037")
    def test_run_checks_basic(self, dbt_plugin) -> None:
        """run_checks returns QualitySuiteResult."""
        result = dbt_plugin.run_checks(
            suite_name="test_suite",
            data_source="staging.orders",
            options=None,
        )

        assert isinstance(result, QualitySuiteResult)
        assert result.suite_name == "test_suite"


class TestDBTExpectationsPluginSupportsDialect:
    """Tests for supports_dialect method."""

    @pytest.mark.requirement("FR-007", "FR-040")
    def test_supports_duckdb(self, dbt_plugin) -> None:
        """Plugin supports DuckDB dialect."""
        assert dbt_plugin.supports_dialect("duckdb") is True

    @pytest.mark.requirement("FR-007", "FR-040")
    def test_supports_postgresql(self, dbt_plugin) -> None:
        """Plugin supports PostgreSQL dialect."""
        assert dbt_plugin.supports_dialect("postgresql") is True

    @pytest.mark.requirement("FR-007", "FR-040")
    def test_supports_snowflake(self, dbt_plugin) -> None:
        """Plugin supports Snowflake dialect."""
        assert dbt_plugin.supports_dialect("snowflake") is True

    @pytest.mark.requirement("FR-007")
    def test_unsupported_dialect(self, dbt_plugin) -> None:
        """Plugin returns False for unsupported dialects."""
        assert dbt_plugin.supports_dialect("oracle") is False


class TestDBTExpectationsPluginHealthCheck:
    """Tests for health_check method (T064a)."""

    @pytest.mark.requirement("FR-009")
    def test_health_check_returns_status(self, dbt_plugin) -> None:
        """health_check returns HealthStatus."""
        from floe_core.plugin_metadata import HealthStatus

        status = dbt_plugin.health_check()
        assert isinstance(status, HealthStatus)

    @pytest.mark.requirement("FR-009")
    def test_health_check_details_has_dbt_available(self, dbt_plugin) -> None:
        """health_check includes dbt_available in details."""
        status = dbt_plugin.health_check()
        assert "dbt_available" in status.details


class TestDBTExpectationsPluginConfigSchema:
    """Tests for get_config_schema method (T064c)."""

    @pytest.mark.requirement("FR-010")
    def test_get_config_schema_returns_quality_config(self, dbt_plugin) -> None:
        """get_config_schema returns QualityConfig."""
        schema = dbt_plugin.get_config_schema()
        assert schema is QualityConfig

    @pytest.mark.requirement("FR-010")
    def test_config_schema_is_pydantic_model(self, dbt_plugin) -> None:
        """Config schema is a Pydantic BaseModel."""
        from pydantic import BaseModel

        schema = dbt_plugin.get_config_schema()
        assert issubclass(schema, BaseModel)


class TestDBTExpectationsPluginQualityScore:
    """Tests for quality score calculation."""

    @pytest.mark.requirement("FR-005")
    def test_all_checks_pass_score_100(self, dbt_plugin) -> None:
        """All passing checks yield score of 100."""
        results = QualitySuiteResult(
            suite_name="test",
            model_name="model",
            passed=True,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                ),
            ],
            summary={"passed": 1, "failed": 0},
        )
        config = QualityConfig(provider="dbt_expectations")

        score = dbt_plugin.calculate_quality_score(results, config)

        assert score.overall == pytest.approx(100.0)
        assert score.checks_passed == 1
        assert score.checks_failed == 0

    @pytest.mark.requirement("FR-005")
    def test_calculate_score_with_failures(self, dbt_plugin) -> None:
        """Quality score reflects failures correctly."""
        results = QualitySuiteResult(
            suite_name="test",
            model_name="model",
            passed=False,
            checks=[
                QualityCheckResult(
                    check_name="c1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                ),
                QualityCheckResult(
                    check_name="c2",
                    passed=False,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.CRITICAL,
                ),
            ],
            summary={"passed": 1, "failed": 1},
        )
        config = QualityConfig(provider="dbt_expectations")

        score = dbt_plugin.calculate_quality_score(results, config)

        assert score.checks_passed == 1
        assert score.checks_failed == 1
        assert score.overall < 100.0


class TestDBTExpectationsPluginLineage:
    """Tests for lineage emitter."""

    @pytest.mark.requirement("FR-006")
    def test_get_lineage_emitter_none_by_default(self, dbt_plugin) -> None:
        """Returns None when lineage not configured."""
        emitter = dbt_plugin.get_lineage_emitter()
        assert emitter is None
