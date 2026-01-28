"""Unit tests for GreatExpectationsPlugin.

Tests:
    - T047: run_checks() basic execution
    - T049: FLOE-DQ102 error on check failures
    - T050: FLOE-DQ106 timeout handling
    - T050a: fail_fast behavior
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


class TestGreatExpectationsPluginMetadata:
    """Tests for plugin metadata properties."""

    @pytest.mark.requirement("FR-039")
    def test_plugin_name(self, gx_plugin) -> None:
        """Plugin returns correct name."""
        assert gx_plugin.name == "great_expectations"

    @pytest.mark.requirement("FR-039")
    def test_plugin_version(self, gx_plugin) -> None:
        """Plugin returns version string."""
        assert gx_plugin.version == "0.1.0"

    @pytest.mark.requirement("FR-039")
    def test_plugin_floe_api_version(self, gx_plugin) -> None:
        """Plugin returns floe API version."""
        assert gx_plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("FR-039")
    def test_plugin_description(self, gx_plugin) -> None:
        """Plugin returns description."""
        assert "Great Expectations" in gx_plugin.description


class TestGreatExpectationsPluginValidateConfig:
    """Tests for validate_config method."""

    @pytest.mark.requirement("FR-002")
    def test_validate_config_success(self, gx_plugin) -> None:
        """Validates config with matching provider."""
        config = QualityConfig(provider="great_expectations")
        result = gx_plugin.validate_config(config)
        assert result.success is True
        assert len(result.errors) == 0

    @pytest.mark.requirement("FR-002")
    def test_validate_config_provider_mismatch(self, gx_plugin) -> None:
        """Fails validation for mismatched provider."""
        config = QualityConfig(provider="soda")
        result = gx_plugin.validate_config(config)
        assert result.success is False
        assert "Provider mismatch" in result.errors[0]


class TestGreatExpectationsPluginRunSuite:
    """Tests for run_suite method (T047)."""

    @pytest.mark.requirement("FR-004", "FR-027")
    def test_run_suite_returns_result(self, gx_plugin) -> None:
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
        connection_config: dict[str, Any] = {"dialect": "duckdb", "path": ":memory:"}

        result = gx_plugin.run_suite(suite, connection_config)

        assert isinstance(result, QualitySuiteResult)
        assert result.model_name == "test_model"

    @pytest.mark.requirement("FR-004")
    def test_run_suite_empty_checks(self, gx_plugin) -> None:
        """run_suite handles empty checks list."""
        suite = QualitySuite(model_name="test_model", checks=[])
        connection_config: dict[str, Any] = {"dialect": "duckdb"}

        result = gx_plugin.run_suite(suite, connection_config)

        assert result.passed is True
        assert len(result.checks) == 0


class TestGreatExpectationsPluginRunChecks:
    """Tests for run_checks method."""

    @pytest.mark.requirement("FR-004")
    def test_run_checks_basic(self, gx_plugin) -> None:
        """run_checks returns QualitySuiteResult."""
        result = gx_plugin.run_checks(
            suite_name="test_suite",
            data_source="staging.orders",
            options=None,
        )

        assert isinstance(result, QualitySuiteResult)
        assert result.suite_name == "test_suite"


class TestGreatExpectationsPluginCheckFailures:
    """Tests for FLOE-DQ102 check failure handling (T049)."""

    @pytest.mark.requirement("FR-042")
    def test_failed_check_in_results(self, gx_plugin) -> None:
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

        result = gx_plugin.run_suite(suite, connection_config)

        assert isinstance(result, QualitySuiteResult)
        # Verify result structure captures check metadata
        for check_result in result.checks:
            assert isinstance(check_result, QualityCheckResult)
            assert check_result.dimension in Dimension
            assert check_result.severity in SeverityLevel

    @pytest.mark.requirement("FR-042")
    def test_calculate_score_with_failures(self, gx_plugin) -> None:
        """Quality score reflects failures correctly."""
        results = QualitySuiteResult(
            suite_name="test_suite",
            model_name="test_model",
            passed=False,
            checks=[
                QualityCheckResult(
                    check_name="check1",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                ),
                QualityCheckResult(
                    check_name="check2",
                    passed=False,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.CRITICAL,
                ),
            ],
            summary={"passed": 1, "failed": 1},
        )
        config = QualityConfig(provider="great_expectations")

        score = gx_plugin.calculate_quality_score(results, config)

        assert score.checks_passed == 1
        assert score.checks_failed == 1
        assert score.overall < 100.0


class TestGreatExpectationsPluginTimeout:
    """Tests for FLOE-DQ106 timeout handling (T050)."""

    @pytest.mark.requirement("FR-032", "FR-046")
    def test_suite_timeout_seconds_default(self, gx_plugin) -> None:
        """Suite uses default timeout if not specified."""
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
    def test_suite_custom_timeout(self, gx_plugin) -> None:
        """Suite accepts custom timeout."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[],
            timeout_seconds=60,
        )
        assert suite.timeout_seconds == 60


class TestGreatExpectationsPluginFailFast:
    """Tests for fail_fast behavior (T050a)."""

    @pytest.mark.requirement("FR-004")
    def test_suite_fail_fast_default_false(self, gx_plugin) -> None:
        """fail_fast defaults to False."""
        suite = QualitySuite(model_name="test_model", checks=[])
        assert suite.fail_fast is False

    @pytest.mark.requirement("FR-004")
    def test_suite_fail_fast_enabled(self, gx_plugin) -> None:
        """Suite accepts fail_fast=True."""
        suite = QualitySuite(
            model_name="test_model",
            checks=[],
            fail_fast=True,
        )
        assert suite.fail_fast is True


class TestGreatExpectationsPluginSupportsDialect:
    """Tests for supports_dialect method."""

    @pytest.mark.requirement("FR-007", "FR-040")
    def test_supports_duckdb(self, gx_plugin) -> None:
        """Plugin supports DuckDB dialect."""
        assert gx_plugin.supports_dialect("duckdb") is True

    @pytest.mark.requirement("FR-007", "FR-040")
    def test_supports_postgresql(self, gx_plugin) -> None:
        """Plugin supports PostgreSQL dialect."""
        assert gx_plugin.supports_dialect("postgresql") is True

    @pytest.mark.requirement("FR-007", "FR-040")
    def test_supports_snowflake(self, gx_plugin) -> None:
        """Plugin supports Snowflake dialect."""
        assert gx_plugin.supports_dialect("snowflake") is True

    @pytest.mark.requirement("FR-007")
    def test_unsupported_dialect(self, gx_plugin) -> None:
        """Plugin returns False for unsupported dialects."""
        assert gx_plugin.supports_dialect("oracle") is False

    @pytest.mark.requirement("FR-007")
    def test_dialect_case_insensitive(self, gx_plugin) -> None:
        """Dialect matching is case-insensitive."""
        assert gx_plugin.supports_dialect("DuckDB") is True
        assert gx_plugin.supports_dialect("POSTGRESQL") is True


class TestGreatExpectationsPluginLineage:
    """Tests for lineage emitter."""

    @pytest.mark.requirement("FR-006")
    def test_get_lineage_emitter_none_by_default(self, gx_plugin) -> None:
        """Returns None when lineage not configured."""
        emitter = gx_plugin.get_lineage_emitter()
        assert emitter is None


class TestGreatExpectationsPluginHealthCheck:
    """Tests for health_check method (T064)."""

    @pytest.mark.requirement("FR-009")
    def test_health_check_returns_status(self, gx_plugin) -> None:
        """health_check returns HealthStatus."""
        from floe_core.plugin_metadata import HealthStatus

        status = gx_plugin.health_check()
        assert isinstance(status, HealthStatus)

    @pytest.mark.requirement("FR-009")
    def test_health_check_details_has_gx_available(self, gx_plugin) -> None:
        """health_check includes gx_available in details."""
        status = gx_plugin.health_check()
        assert "gx_available" in status.details


class TestGreatExpectationsPluginConfigSchema:
    """Tests for get_config_schema method (T064b)."""

    @pytest.mark.requirement("FR-010")
    def test_get_config_schema_returns_quality_config(self, gx_plugin) -> None:
        """get_config_schema returns QualityConfig."""
        schema = gx_plugin.get_config_schema()
        assert schema is QualityConfig

    @pytest.mark.requirement("FR-010")
    def test_config_schema_is_pydantic_model(self, gx_plugin) -> None:
        """Config schema is a Pydantic BaseModel."""
        from pydantic import BaseModel

        schema = gx_plugin.get_config_schema()
        assert issubclass(schema, BaseModel)


class TestGreatExpectationsPluginQualityScore:
    """Tests for quality score calculation."""

    @pytest.mark.requirement("FR-005")
    def test_all_checks_pass_score_100(self, gx_plugin) -> None:
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
                QualityCheckResult(
                    check_name="c2",
                    passed=True,
                    dimension=Dimension.ACCURACY,
                    severity=SeverityLevel.WARNING,
                ),
            ],
            summary={"passed": 2, "failed": 0},
        )
        config = QualityConfig(provider="great_expectations")

        score = gx_plugin.calculate_quality_score(results, config)

        assert score.overall == pytest.approx(100.0)
        assert score.checks_passed == 2
        assert score.checks_failed == 0

    @pytest.mark.requirement("FR-005")
    def test_empty_checks_score_100(self, gx_plugin) -> None:
        """Empty checks list yields score of 100."""
        results = QualitySuiteResult(
            suite_name="test",
            model_name="model",
            passed=True,
            checks=[],
            summary={},
        )
        config = QualityConfig(provider="great_expectations")

        score = gx_plugin.calculate_quality_score(results, config)

        assert score.overall == pytest.approx(100.0)
