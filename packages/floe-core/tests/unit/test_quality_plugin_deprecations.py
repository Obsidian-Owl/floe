"""Tests for QualityPlugin deprecations and new get_quality_facets method.

This module tests:
- OpenLineageEmitter Protocol deprecation warning
- get_lineage_emitter() deprecation warning
- get_quality_facets() functionality

Requirements Covered:
- REQ-524: Deprecate OpenLineageEmitter and add get_quality_facets
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.plugins.quality import OpenLineageEmitter, QualityPlugin
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import (
    QualityCheckResult,
    QualitySuite,
    QualitySuiteResult,
)


class MockQualityPlugin(QualityPlugin):
    """Minimal concrete QualityPlugin for testing."""

    @property
    def name(self) -> str:
        return "mock-quality"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def run_checks(
        self,
        suite_name: str,
        data_source: str,
        options: dict[str, Any] | None = None,
    ) -> QualitySuiteResult:
        return QualitySuiteResult(
            suite_name=suite_name,
            model_name="test_model",
            passed=True,
            checks=[],
        )

    def run_suite(
        self,
        suite: QualitySuite,
        connection_config: dict[str, Any],
    ) -> QualitySuiteResult:
        return QualitySuiteResult(
            suite_name=suite.model_name,
            model_name=suite.model_name,
            passed=True,
            checks=[],
        )

    def validate_expectations(
        self,
        data_source: str,
        expectations: list[dict[str, Any]],
    ) -> list[QualityCheckResult]:
        return []

    def list_suites(self) -> list[str]:
        return ["test_suite"]

    def supports_dialect(self, dialect: str) -> bool:
        return dialect == "duckdb"


class TestGetLineageEmitterDeprecation:
    """Test get_lineage_emitter() deprecation warning."""

    @pytest.mark.requirement("REQ-524")
    def test_get_lineage_emitter_issues_deprecation_warning(self) -> None:
        """Verify get_lineage_emitter() issues DeprecationWarning."""
        plugin = MockQualityPlugin()

        with pytest.warns(DeprecationWarning, match="get_lineage_emitter.*deprecated"):
            result = plugin.get_lineage_emitter()

        assert result is None

    @pytest.mark.requirement("REQ-524")
    def test_deprecation_warning_mentions_get_quality_facets(self) -> None:
        """Verify deprecation warning mentions get_quality_facets() as replacement."""
        plugin = MockQualityPlugin()

        with pytest.warns(
            DeprecationWarning, match="Use get_quality_facets\\(\\) instead"
        ):
            plugin.get_lineage_emitter()

    @pytest.mark.requirement("REQ-524")
    def test_deprecation_warning_mentions_unified_lineage_emitter(self) -> None:
        """Verify deprecation warning mentions unified LineageEmitter."""
        plugin = MockQualityPlugin()

        with pytest.warns(DeprecationWarning, match="unified LineageEmitter"):
            plugin.get_lineage_emitter()


class TestOpenLineageEmitterProtocolImportable:
    """Test OpenLineageEmitter Protocol is still importable."""

    @pytest.mark.requirement("REQ-524")
    def test_openlineage_emitter_protocol_importable(self) -> None:
        """Verify OpenLineageEmitter Protocol can still be imported."""
        from floe_core.plugins.quality import OpenLineageEmitter

        assert OpenLineageEmitter is not None

    @pytest.mark.requirement("REQ-524")
    def test_openlineage_emitter_is_protocol(self) -> None:
        """Verify OpenLineageEmitter is a Protocol."""
        import inspect

        assert hasattr(OpenLineageEmitter, "__protocol_attrs__") or inspect.isclass(
            OpenLineageEmitter
        )


class TestGetQualityFacets:
    """Test get_quality_facets() method."""

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_returns_valid_facet_dict(self) -> None:
        """Verify get_quality_facets() returns valid facet dict from QualityCheckResult list."""
        plugin = MockQualityPlugin()

        results = [
            QualityCheckResult(
                check_name="not_null_id",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            ),
            QualityCheckResult(
                check_name="unique_email",
                passed=False,
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.WARNING,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert isinstance(facet, dict)
        assert "_producer" in facet
        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "assertions" in facet
        assert len(facet["assertions"]) == 2

        assert facet["assertions"][0]["assertion"] == "not_null_id"
        assert facet["assertions"][0]["success"] is True

        assert facet["assertions"][1]["assertion"] == "unique_email"
        assert facet["assertions"][1]["success"] is False

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_returns_empty_dict_for_empty_list(self) -> None:
        """Verify get_quality_facets() returns empty dict for empty list."""
        plugin = MockQualityPlugin()

        facet = plugin.get_quality_facets([])

        assert facet == {}

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_handles_dimension_enum(self) -> None:
        """Verify get_quality_facets() correctly handles Dimension enum values."""
        plugin = MockQualityPlugin()

        results = [
            QualityCheckResult(
                check_name="test_check",
                passed=True,
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert "assertions" in facet
        assert len(facet["assertions"]) == 1

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_with_multiple_dimensions(self) -> None:
        """Verify get_quality_facets() handles multiple quality dimensions."""
        plugin = MockQualityPlugin()

        results = [
            QualityCheckResult(
                check_name="completeness_check",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            ),
            QualityCheckResult(
                check_name="accuracy_check",
                passed=True,
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.WARNING,
            ),
            QualityCheckResult(
                check_name="validity_check",
                passed=False,
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert len(facet["assertions"]) == 3
        assert all("assertion" in a for a in facet["assertions"])
        assert all("success" in a for a in facet["assertions"])

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_schema_url_is_correct(self) -> None:
        """Verify get_quality_facets() returns correct OpenLineage schema URL."""
        plugin = MockQualityPlugin()

        results = [
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert (
            facet["_schemaURL"]
            == "https://openlineage.io/spec/facets/1-0-0/DataQualityAssertionsDatasetFacet.json"
        )
