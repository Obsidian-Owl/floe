"""Contract tests for QualityPlugin ABC compliance.

Tests:
    - T095: QualityPlugin ABC compliance (discovery, metadata, health_check)
    - T096: CompiledArtifacts v0.4.0 schema stability (partial)
    - T097: floe-core → plugin quality config passing
"""

from __future__ import annotations

import pytest
from floe_core.plugin_metadata import HealthStatus
from floe_core.plugins.quality import (
    GateResult,
    QualityPlugin,
    QualitySuiteResult,
    ValidationResult,
)
from floe_core.schemas.quality_config import QualityConfig, QualityGates


class TestQualityPluginABCCompliance:
    """Tests for T095: QualityPlugin ABC compliance."""

    @pytest.mark.requirement("FR-039")
    def test_gx_plugin_implements_abc(self) -> None:
        """GreatExpectationsPlugin implements QualityPlugin ABC."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()

        # Verify it's a QualityPlugin
        assert isinstance(plugin, QualityPlugin)

    @pytest.mark.requirement("FR-039")
    def test_dbt_plugin_implements_abc(self) -> None:
        """DBTExpectationsPlugin implements QualityPlugin ABC."""
        from floe_quality_dbt import DBTExpectationsPlugin

        plugin = DBTExpectationsPlugin()

        # Verify it's a QualityPlugin
        assert isinstance(plugin, QualityPlugin)

    @pytest.mark.requirement("FR-039")
    def test_gx_plugin_has_required_metadata(self) -> None:
        """GreatExpectationsPlugin provides required metadata properties."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()

        # Required metadata properties
        assert isinstance(plugin.name, str)
        assert len(plugin.name) > 0
        assert isinstance(plugin.version, str)
        assert isinstance(plugin.floe_api_version, str)
        assert isinstance(plugin.description, str)

    @pytest.mark.requirement("FR-039")
    def test_dbt_plugin_has_required_metadata(self) -> None:
        """DBTExpectationsPlugin provides required metadata properties."""
        from floe_quality_dbt import DBTExpectationsPlugin

        plugin = DBTExpectationsPlugin()

        # Required metadata properties
        assert isinstance(plugin.name, str)
        assert len(plugin.name) > 0
        assert isinstance(plugin.version, str)
        assert isinstance(plugin.floe_api_version, str)
        assert isinstance(plugin.description, str)

    @pytest.mark.requirement("FR-009")
    def test_gx_plugin_health_check_contract(self) -> None:
        """GreatExpectationsPlugin.health_check() returns HealthStatus."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()
        status = plugin.health_check()

        assert isinstance(status, HealthStatus)
        assert hasattr(status, "state")
        assert hasattr(status, "message")
        assert hasattr(status, "details")

    @pytest.mark.requirement("FR-009")
    def test_dbt_plugin_health_check_contract(self) -> None:
        """DBTExpectationsPlugin.health_check() returns HealthStatus."""
        from floe_quality_dbt import DBTExpectationsPlugin

        plugin = DBTExpectationsPlugin()
        status = plugin.health_check()

        assert isinstance(status, HealthStatus)
        assert hasattr(status, "state")
        assert hasattr(status, "message")
        assert hasattr(status, "details")

    @pytest.mark.requirement("FR-010")
    def test_gx_plugin_config_schema_contract(self) -> None:
        """GreatExpectationsPlugin.get_config_schema() returns Pydantic model."""
        from floe_quality_gx import GreatExpectationsPlugin
        from pydantic import BaseModel

        plugin = GreatExpectationsPlugin()
        schema = plugin.get_config_schema()

        assert schema is not None
        assert issubclass(schema, BaseModel)

    @pytest.mark.requirement("FR-010")
    def test_dbt_plugin_config_schema_contract(self) -> None:
        """DBTExpectationsPlugin.get_config_schema() returns Pydantic model."""
        from floe_quality_dbt import DBTExpectationsPlugin
        from pydantic import BaseModel

        plugin = DBTExpectationsPlugin()
        schema = plugin.get_config_schema()

        assert schema is not None
        assert issubclass(schema, BaseModel)


class TestQualityConfigContract:
    """Tests for T097: floe-core → plugin quality config passing."""

    @pytest.mark.requirement("FR-011", "FR-026")
    def test_quality_config_accepted_by_gx_plugin(self) -> None:
        """QualityConfig is accepted by GreatExpectationsPlugin.validate_config()."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()
        config = QualityConfig(provider="great_expectations")

        result = plugin.validate_config(config)

        assert isinstance(result, ValidationResult)
        assert result.success is True

    @pytest.mark.requirement("FR-011", "FR-026")
    def test_quality_config_accepted_by_dbt_plugin(self) -> None:
        """QualityConfig is accepted by DBTExpectationsPlugin.validate_config()."""
        from floe_quality_dbt import DBTExpectationsPlugin

        plugin = DBTExpectationsPlugin()
        config = QualityConfig(provider="dbt_expectations")

        result = plugin.validate_config(config)

        assert isinstance(result, ValidationResult)
        assert result.success is True

    @pytest.mark.requirement("FR-011")
    def test_quality_gates_accepted_by_gx_plugin(self) -> None:
        """QualityGates is accepted by GreatExpectationsPlugin.validate_quality_gates()."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()
        gates = QualityGates()

        # Pass empty models list
        result = plugin.validate_quality_gates(models=[], gates=gates)

        assert isinstance(result, GateResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "tier")
        assert hasattr(result, "coverage_actual")
        assert hasattr(result, "coverage_required")

    @pytest.mark.requirement("FR-011")
    def test_quality_gates_accepted_by_dbt_plugin(self) -> None:
        """QualityGates is accepted by DBTExpectationsPlugin.validate_quality_gates()."""
        from floe_quality_dbt import DBTExpectationsPlugin

        plugin = DBTExpectationsPlugin()
        gates = QualityGates()

        # Pass empty models list
        result = plugin.validate_quality_gates(models=[], gates=gates)

        assert isinstance(result, GateResult)


class TestPluginMethodContracts:
    """Tests for quality plugin method contracts."""

    @pytest.mark.requirement("FR-004")
    def test_run_checks_returns_suite_result(self) -> None:
        """run_checks() returns QualitySuiteResult."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()

        result = plugin.run_checks(
            suite_name="test_suite",
            data_source="test_data",
            options=None,
        )

        assert isinstance(result, QualitySuiteResult)
        assert result.suite_name == "test_suite"
        assert hasattr(result, "model_name")
        assert hasattr(result, "passed")
        assert hasattr(result, "checks")

    @pytest.mark.requirement("FR-007")
    def test_supports_dialect_contract(self) -> None:
        """supports_dialect() returns bool."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()

        # Should return bool for any dialect
        assert isinstance(plugin.supports_dialect("duckdb"), bool)
        assert isinstance(plugin.supports_dialect("unknown"), bool)

    @pytest.mark.requirement("FR-006")
    def test_get_lineage_emitter_contract(self) -> None:
        """get_lineage_emitter() returns emitter or None."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()

        # Should return None or an emitter (currently returns None)
        emitter = plugin.get_lineage_emitter()
        assert emitter is None or hasattr(emitter, "emit_fail_event")

    @pytest.mark.requirement("FR-007")
    def test_list_suites_contract(self) -> None:
        """list_suites() returns list of strings."""
        from floe_quality_gx import GreatExpectationsPlugin

        plugin = GreatExpectationsPlugin()

        suites = plugin.list_suites()

        assert isinstance(suites, list)
        for suite in suites:
            assert isinstance(suite, str)
