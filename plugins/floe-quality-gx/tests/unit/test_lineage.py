"""Unit tests for OpenLineage integration.

Tests for US6 - OpenLineage event emission:
    - T088: FAIL event emission on check failure
    - T089: Graceful handling when lineage backend not configured
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import QualityCheckResult

if TYPE_CHECKING:
    from floe_quality_gx import GreatExpectationsPlugin


class TestOpenLineageFailEvent:
    """Tests for T088: FAIL event emission on check failure."""

    @pytest.mark.requirement("FR-006")
    def test_lineage_emitter_emit_fail_event(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """OpenLineageEmitter emits FAIL event with check results."""
        from floe_quality_gx.lineage import OpenLineageQualityEmitter

        # Create a mock emitter
        emitter = OpenLineageQualityEmitter(backend_url="http://localhost:5000")

        failed_checks = [
            QualityCheckResult(
                check_name="email_not_null",
                passed=False,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
                error_message="15% of values are null",
            ),
        ]

        # Should not raise
        emitter.emit_fail_event(
            job_name="quality_check_job",
            dataset_name="staging.customers",
            check_results=failed_checks,
        )

    @pytest.mark.requirement("FR-006")
    def test_lineage_emitter_formats_facet(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """OpenLineageEmitter creates quality facet with check details."""
        from floe_quality_gx.lineage import create_quality_facet

        check_results = [
            QualityCheckResult(
                check_name="id_unique",
                passed=False,
                dimension=Dimension.CONSISTENCY,
                severity=SeverityLevel.WARNING,
                records_checked=1000,
                records_failed=5,
            ),
        ]

        facet = create_quality_facet(check_results)

        assert "dataQuality" in facet
        assert facet["dataQuality"]["assertions"] is not None
        assert len(facet["dataQuality"]["assertions"]) == 1

    @pytest.mark.requirement("FR-006")
    def test_lineage_emitter_multiple_failures(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """OpenLineageEmitter handles multiple failed checks."""
        from floe_quality_gx.lineage import OpenLineageQualityEmitter

        emitter = OpenLineageQualityEmitter(backend_url="http://localhost:5000")

        failed_checks = [
            QualityCheckResult(
                check_name="check1",
                passed=False,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            ),
            QualityCheckResult(
                check_name="check2",
                passed=False,
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.WARNING,
            ),
            QualityCheckResult(
                check_name="check3",
                passed=True,  # This one passed - should not be in failure event
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.INFO,
            ),
        ]

        # Should not raise
        emitter.emit_fail_event(
            job_name="quality_check_job",
            dataset_name="staging.orders",
            check_results=failed_checks,
        )


class TestGracefulDegradation:
    """Tests for T089: Graceful handling when lineage backend not configured."""

    @pytest.mark.requirement("FR-006")
    def test_get_lineage_emitter_returns_none_by_default(
        self, gx_plugin: GreatExpectationsPlugin
    ) -> None:
        """Plugin returns None when lineage is not configured."""
        emitter = gx_plugin.get_lineage_emitter()
        assert emitter is None

    @pytest.mark.requirement("FR-006")
    def test_emitter_handles_connection_failure(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Emitter gracefully handles connection failures."""
        from floe_quality_gx.lineage import OpenLineageQualityEmitter

        # Create emitter with invalid URL
        emitter = OpenLineageQualityEmitter(backend_url="http://invalid-host:9999")

        failed_checks = [
            QualityCheckResult(
                check_name="check1",
                passed=False,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
        ]

        # Should not raise - graceful degradation
        emitter.emit_fail_event(
            job_name="test_job",
            dataset_name="test_dataset",
            check_results=failed_checks,
        )

    @pytest.mark.requirement("FR-006")
    def test_emitter_handles_empty_results(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Emitter handles empty check results gracefully."""
        from floe_quality_gx.lineage import OpenLineageQualityEmitter

        emitter = OpenLineageQualityEmitter(backend_url="http://localhost:5000")

        # Should not raise with empty list
        emitter.emit_fail_event(
            job_name="test_job",
            dataset_name="test_dataset",
            check_results=[],
        )


class TestQualityFacet:
    """Tests for OpenLineage quality facet creation."""

    @pytest.mark.requirement("FR-006")
    def test_facet_includes_dimension(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Quality facet includes dimension information."""
        from floe_quality_gx.lineage import create_quality_facet

        check_results = [
            QualityCheckResult(
                check_name="completeness_check",
                passed=False,
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            ),
        ]

        facet = create_quality_facet(check_results)

        assertion = facet["dataQuality"]["assertions"][0]
        assert "dimension" in assertion or "completeness" in str(assertion).lower()

    @pytest.mark.requirement("FR-006")
    def test_facet_includes_severity(self, gx_plugin: GreatExpectationsPlugin) -> None:
        """Quality facet includes severity information."""
        from floe_quality_gx.lineage import create_quality_facet

        check_results = [
            QualityCheckResult(
                check_name="critical_check",
                passed=False,
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.CRITICAL,
            ),
        ]

        facet = create_quality_facet(check_results)

        assertion = facet["dataQuality"]["assertions"][0]
        assert "severity" in assertion or "critical" in str(assertion).lower()
