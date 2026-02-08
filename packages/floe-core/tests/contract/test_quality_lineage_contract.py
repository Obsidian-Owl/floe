"""Contract tests for quality lineage unification and backward compatibility.

These tests ensure the quality lineage contract remains stable across versions:
- Backward compatibility: deprecated get_lineage_emitter() still works
- New path: get_quality_facets() returns valid OpenLineage facets
- Facet structure: Output matches DataQualityAssertionsDatasetFacet schema
- Cross-package: QualityPlugin can be subclassed without implementing deprecated methods
- Protocol importability: OpenLineageEmitter still importable for backward compat

Contract Version: 0.5.0

Requirements Covered:
- REQ-524: Deprecate OpenLineageEmitter and add get_quality_facets
- SC-002: Quality lineage contract stability
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


class MinimalQualityPlugin(QualityPlugin):
    """Minimal concrete QualityPlugin for contract testing.

    Implements only required abstract methods with minimal implementations.
    Tests that subclasses don't need to implement deprecated methods.
    """

    @property
    def name(self) -> str:
        return "minimal-quality"

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
        return []

    def supports_dialect(self, dialect: str) -> bool:
        return False


class TestBackwardCompatibilityGetLineageEmitter:
    """Contract tests for backward compatibility of get_lineage_emitter()."""

    @pytest.mark.requirement("REQ-524")
    def test_get_lineage_emitter_returns_none(self) -> None:
        """Verify get_lineage_emitter() returns None (deprecated path).

        The method should return None to indicate lineage is now handled
        by the unified LineageEmitter, not plugin-specific emitters.
        """
        plugin = MinimalQualityPlugin()

        with pytest.warns(DeprecationWarning):
            result = plugin.get_lineage_emitter()

        assert result is None

    @pytest.mark.requirement("REQ-524")
    def test_get_lineage_emitter_deprecation_warning_issued(self) -> None:
        """Verify get_lineage_emitter() issues DeprecationWarning.

        Plugins calling this method should see a clear deprecation warning
        directing them to use get_quality_facets() instead.
        """
        plugin = MinimalQualityPlugin()

        with pytest.warns(DeprecationWarning, match="get_lineage_emitter.*deprecated"):
            plugin.get_lineage_emitter()

    @pytest.mark.requirement("REQ-524")
    def test_deprecation_message_mentions_unified_lineage_emitter(self) -> None:
        """Verify deprecation message mentions unified LineageEmitter.

        The warning should explain that quality lineage now flows through
        the unified LineageEmitter from floe_core.lineage.
        """
        plugin = MinimalQualityPlugin()

        with pytest.warns(DeprecationWarning, match="unified LineageEmitter"):
            plugin.get_lineage_emitter()

    @pytest.mark.requirement("REQ-524")
    def test_deprecation_message_mentions_get_quality_facets(self) -> None:
        """Verify deprecation message mentions get_quality_facets() replacement.

        The warning should direct users to use get_quality_facets() for
        building quality facets for the unified LineageEmitter.
        """
        plugin = MinimalQualityPlugin()

        with pytest.warns(DeprecationWarning, match="get_quality_facets"):
            plugin.get_lineage_emitter()


class TestOpenLineageEmitterProtocolBackwardCompat:
    """Contract tests for OpenLineageEmitter Protocol backward compatibility."""

    @pytest.mark.requirement("REQ-524")
    def test_openlineage_emitter_protocol_importable(self) -> None:
        """Verify OpenLineageEmitter Protocol can still be imported.

        Existing code that imports OpenLineageEmitter should continue to work
        for backward compatibility, even though it's deprecated.
        """
        # This import should not raise
        from floe_core.plugins.quality import OpenLineageEmitter as OLE

        assert OLE is not None

    @pytest.mark.requirement("REQ-524")
    def test_openlineage_emitter_is_runtime_checkable_protocol(self) -> None:
        """Verify OpenLineageEmitter is a runtime_checkable Protocol.

        The Protocol should support isinstance() checks for backward compat.
        """
        # Check it's a Protocol by verifying it has protocol markers
        assert hasattr(OpenLineageEmitter, "_is_protocol")
        assert hasattr(OpenLineageEmitter, "_is_runtime_protocol")

    @pytest.mark.requirement("REQ-524")
    def test_openlineage_emitter_has_emit_fail_event_method(self) -> None:
        """Verify OpenLineageEmitter Protocol defines emit_fail_event method.

        The Protocol should still define the emit_fail_event method signature
        for backward compatibility with existing implementations.
        """
        assert hasattr(OpenLineageEmitter, "emit_fail_event")


class TestGetQualityFacetsNewPath:
    """Contract tests for new get_quality_facets() method."""

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_returns_dict(self) -> None:
        """Verify get_quality_facets() returns a dict.

        The method should return a dict compatible with OpenLineage
        DataQualityAssertionsDatasetFacet schema.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="test_check",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert isinstance(facet, dict)

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_has_producer_field(self) -> None:
        """Verify get_quality_facets() output has _producer field.

        OpenLineage facets MUST have _producer field set to 'floe'.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="test_check",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert "_producer" in facet
        assert facet["_producer"] == "floe"

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_has_schema_url_field(self) -> None:
        """Verify get_quality_facets() output has _schemaURL field.

        OpenLineage facets MUST have _schemaURL pointing to the spec version.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="test_check",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert "_schemaURL" in facet
        assert "DataQualityAssertionsDatasetFacet" in facet["_schemaURL"]
        assert "openlineage.io" in facet["_schemaURL"]

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_schema_url_is_correct_version(self) -> None:
        """Verify _schemaURL points to correct OpenLineage spec version.

        The schema URL should point to version 1-0-0 of the spec.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="test_check",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        expected_url = "https://openlineage.io/spec/facets/1-0-0/DataQualityAssertionsDatasetFacet.json"
        assert facet["_schemaURL"] == expected_url

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_has_assertions_field(self) -> None:
        """Verify get_quality_facets() output has assertions field.

        The assertions field should contain the quality check results.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="test_check",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert "assertions" in facet
        assert isinstance(facet["assertions"], list)

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_assertions_have_correct_structure(self) -> None:
        """Verify assertions in facet have correct structure.

        Each assertion should have 'assertion' (name) and 'success' (passed) fields.
        """
        plugin = MinimalQualityPlugin()
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

        assert len(facet["assertions"]) == 2

        # First assertion
        assert facet["assertions"][0]["assertion"] == "not_null_id"
        assert facet["assertions"][0]["success"] is True

        # Second assertion
        assert facet["assertions"][1]["assertion"] == "unique_email"
        assert facet["assertions"][1]["success"] is False

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_maps_check_name_to_assertion(self) -> None:
        """Verify check_name is mapped to 'assertion' field in facet.

        The OpenLineage spec uses 'assertion' field for check names.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="my_quality_check",
                passed=True,
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert facet["assertions"][0]["assertion"] == "my_quality_check"

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_maps_passed_to_success(self) -> None:
        """Verify passed field is mapped to 'success' in facet.

        The OpenLineage spec uses 'success' field for pass/fail status.
        """
        plugin = MinimalQualityPlugin()

        # Test passed=True
        results_pass = [
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]
        facet_pass = plugin.get_quality_facets(results_pass)
        assert facet_pass["assertions"][0]["success"] is True

        # Test passed=False
        results_fail = [
            QualityCheckResult(
                check_name="test",
                passed=False,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]
        facet_fail = plugin.get_quality_facets(results_fail)
        assert facet_fail["assertions"][0]["success"] is False


class TestGetQualityFacetsEdgeCases:
    """Contract tests for edge cases in get_quality_facets()."""

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_empty_list_returns_empty_dict(self) -> None:
        """Verify get_quality_facets([]) returns empty dict.

        When no results are provided, the method should return an empty dict
        rather than a facet with empty assertions.
        """
        plugin = MinimalQualityPlugin()

        facet = plugin.get_quality_facets([])

        assert facet == {}

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_single_result(self) -> None:
        """Verify get_quality_facets() works with single result.

        The method should handle a list with a single QualityCheckResult.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="single_check",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert len(facet["assertions"]) == 1
        assert facet["assertions"][0]["assertion"] == "single_check"

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_multiple_results(self) -> None:
        """Verify get_quality_facets() handles multiple results.

        The method should preserve order and include all results.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="check_1",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
            QualityCheckResult(
                check_name="check_2",
                passed=False,
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.WARNING,
            ),
            QualityCheckResult(
                check_name="check_3",
                passed=True,
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.CRITICAL,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert len(facet["assertions"]) == 3
        assert facet["assertions"][0]["assertion"] == "check_1"
        assert facet["assertions"][1]["assertion"] == "check_2"
        assert facet["assertions"][2]["assertion"] == "check_3"

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_all_dimensions(self) -> None:
        """Verify get_quality_facets() handles all quality dimensions.

        The method should work with all Dimension enum values.
        """
        plugin = MinimalQualityPlugin()

        # Test all dimensions
        dimensions = [
            Dimension.COMPLETENESS,
            Dimension.ACCURACY,
            Dimension.VALIDITY,
            Dimension.CONSISTENCY,
            Dimension.TIMELINESS,
        ]

        for _i, dimension in enumerate(dimensions):
            results = [
                QualityCheckResult(
                    check_name=f"check_{dimension.value}",
                    passed=True,
                    dimension=dimension,
                    severity=SeverityLevel.INFO,
                ),
            ]

            facet = plugin.get_quality_facets(results)

            assert len(facet["assertions"]) == 1
            assert facet["assertions"][0]["assertion"] == f"check_{dimension.value}"

    @pytest.mark.requirement("REQ-524")
    def test_get_quality_facets_all_severity_levels(self) -> None:
        """Verify get_quality_facets() handles all severity levels.

        The method should work with all SeverityLevel enum values.
        """
        plugin = MinimalQualityPlugin()

        severities = [
            SeverityLevel.CRITICAL,
            SeverityLevel.WARNING,
            SeverityLevel.INFO,
        ]

        for severity in severities:
            results = [
                QualityCheckResult(
                    check_name=f"check_{severity.value}",
                    passed=True,
                    dimension=Dimension.COMPLETENESS,
                    severity=severity,
                ),
            ]

            facet = plugin.get_quality_facets(results)

            assert len(facet["assertions"]) == 1


class TestQualityPluginSubclassingContract:
    """Contract tests for QualityPlugin subclassing without deprecated methods."""

    @pytest.mark.requirement("REQ-524")
    def test_minimal_plugin_can_be_instantiated(self) -> None:
        """Verify minimal QualityPlugin subclass can be instantiated.

        Subclasses should not need to implement deprecated methods.
        They should inherit default implementations.
        """
        plugin = MinimalQualityPlugin()

        assert plugin is not None
        assert plugin.name == "minimal-quality"

    @pytest.mark.requirement("REQ-524")
    def test_minimal_plugin_has_get_lineage_emitter(self) -> None:
        """Verify minimal plugin inherits get_lineage_emitter() method.

        Even though it's deprecated, the method should be available
        for backward compatibility.
        """
        plugin = MinimalQualityPlugin()

        assert hasattr(plugin, "get_lineage_emitter")
        assert callable(plugin.get_lineage_emitter)

    @pytest.mark.requirement("REQ-524")
    def test_minimal_plugin_has_get_quality_facets(self) -> None:
        """Verify minimal plugin inherits get_quality_facets() method.

        The new method should be available on all QualityPlugin subclasses.
        """
        plugin = MinimalQualityPlugin()

        assert hasattr(plugin, "get_quality_facets")
        assert callable(plugin.get_quality_facets)

    @pytest.mark.requirement("REQ-524")
    def test_minimal_plugin_get_quality_facets_works(self) -> None:
        """Verify get_quality_facets() works on minimal plugin.

        The inherited implementation should work without subclass override.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        facet = plugin.get_quality_facets(results)

        assert isinstance(facet, dict)
        assert "_producer" in facet
        assert "assertions" in facet


class TestQualityLineageContractStability:
    """Contract tests for overall quality lineage contract stability."""

    @pytest.mark.requirement("REQ-524")
    def test_quality_plugin_exports_openlineage_emitter(self) -> None:
        """Verify OpenLineageEmitter is exported from quality module.

        The module's __all__ should include OpenLineageEmitter for backward compat.
        """
        from floe_core.plugins import quality

        assert hasattr(quality, "OpenLineageEmitter")
        assert "OpenLineageEmitter" in quality.__all__

    @pytest.mark.requirement("REQ-524")
    def test_quality_plugin_exports_quality_plugin(self) -> None:
        """Verify QualityPlugin is exported from quality module.

        The module's __all__ should include QualityPlugin.
        """
        from floe_core.plugins import quality

        assert hasattr(quality, "QualityPlugin")
        assert "QualityPlugin" in quality.__all__

    @pytest.mark.requirement("REQ-524")
    def test_backward_compat_and_new_path_coexist(self) -> None:
        """Verify both deprecated and new paths work together.

        A plugin can use both get_lineage_emitter() (deprecated) and
        get_quality_facets() (new) without conflicts.
        """
        plugin = MinimalQualityPlugin()
        results = [
            QualityCheckResult(
                check_name="test",
                passed=True,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            ),
        ]

        # Old path (deprecated)
        with pytest.warns(DeprecationWarning):
            emitter = plugin.get_lineage_emitter()
        assert emitter is None

        # New path (current)
        facet = plugin.get_quality_facets(results)
        assert isinstance(facet, dict)
        assert "_producer" in facet


__all__ = [
    "MinimalQualityPlugin",
    "TestBackwardCompatibilityGetLineageEmitter",
    "TestOpenLineageEmitterProtocolBackwardCompat",
    "TestGetQualityFacetsNewPath",
    "TestGetQualityFacetsEdgeCases",
    "TestQualityPluginSubclassingContract",
    "TestQualityLineageContractStability",
]
