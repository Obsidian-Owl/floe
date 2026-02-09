"""Unit tests for SLA status tracking and compliance reporting models.

Tasks: T017 (Epic 3D)
Requirements: FR-036, FR-037
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from floe_core.contracts.monitoring.sla import (
    CheckTypeSummary,
    SLAComplianceReport,
    SLAStatus,
    TrendDirection,
    aggregate_daily,
    calculate_compliance,
    compute_trend,
)
from floe_core.contracts.monitoring.violations import ViolationType


class TestSLAStatus:
    """Test suite for SLAStatus model."""

    @pytest.mark.requirement("3D-FR-036")
    def test_valid_construction_with_required_fields(self) -> None:
        """Test SLAStatus construction with all required fields."""
        now = datetime.now(tz=timezone.utc)
        status = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=99.5,
            window_start=now,
        )

        assert status.contract_name == "orders_v1"
        assert status.check_type == ViolationType.FRESHNESS
        assert status.current_value == pytest.approx(3600.0)
        assert status.threshold == pytest.approx(7200.0)
        assert status.compliance_pct == pytest.approx(99.5)
        assert status.window_start == now

    @pytest.mark.requirement("3D-FR-036")
    def test_default_values(self) -> None:
        """Test SLAStatus has correct default values."""
        now = datetime.now(tz=timezone.utc)
        status = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=99.5,
            window_start=now,
        )

        assert status.last_check_time is None
        assert status.consecutive_failures == 0
        assert status.violation_count_24h == 0

    @pytest.mark.requirement("3D-FR-036")
    def test_mutable_model(self) -> None:
        """Test SLAStatus is NOT frozen and can be updated."""
        now = datetime.now(tz=timezone.utc)
        status = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=99.5,
            window_start=now,
        )

        # Should be able to update fields
        status.current_value = 7300.0
        assert status.current_value == pytest.approx(7300.0)

        status.compliance_pct = 95.0
        assert status.compliance_pct == pytest.approx(95.0)

        status.consecutive_failures = 2
        assert status.consecutive_failures == 2

    @pytest.mark.requirement("3D-FR-036")
    def test_extra_fields_forbidden(self) -> None:
        """Test SLAStatus rejects extra fields (extra='forbid')."""
        now = datetime.now(tz=timezone.utc)

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            SLAStatus(
                contract_name="orders_v1",
                check_type=ViolationType.FRESHNESS,
                current_value=3600.0,
                threshold=7200.0,
                compliance_pct=99.5,
                window_start=now,
                unexpected_field="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("3D-FR-036")
    def test_compliance_pct_validation_valid_range(self) -> None:
        """Test SLAStatus compliance_pct accepts valid range 0-100."""
        now = datetime.now(tz=timezone.utc)

        # Test lower bound
        status_0 = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=0.0,
            window_start=now,
        )
        assert status_0.compliance_pct == pytest.approx(0.0)

        # Test upper bound
        status_100 = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=100.0,
            window_start=now,
        )
        assert status_100.compliance_pct == pytest.approx(100.0)

        # Test mid range
        status_mid = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=50.5,
            window_start=now,
        )
        assert status_mid.compliance_pct == pytest.approx(50.5)

    @pytest.mark.requirement("3D-FR-036")
    def test_compliance_pct_validation_out_of_range(self) -> None:
        """Test SLAStatus compliance_pct rejects values outside 0-100."""
        now = datetime.now(tz=timezone.utc)

        # Below 0
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            SLAStatus(
                contract_name="orders_v1",
                check_type=ViolationType.FRESHNESS,
                current_value=3600.0,
                threshold=7200.0,
                compliance_pct=-1.0,
                window_start=now,
            )

        # Above 100
        with pytest.raises(ValidationError, match="Input should be less than or equal to 100"):
            SLAStatus(
                contract_name="orders_v1",
                check_type=ViolationType.FRESHNESS,
                current_value=3600.0,
                threshold=7200.0,
                compliance_pct=101.0,
                window_start=now,
            )

    @pytest.mark.requirement("3D-FR-036")
    def test_consecutive_failures_validation(self) -> None:
        """Test SLAStatus consecutive_failures must be >= 0."""
        now = datetime.now(tz=timezone.utc)

        # Valid: 0
        status = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=99.5,
            window_start=now,
            consecutive_failures=0,
        )
        assert status.consecutive_failures == 0

        # Valid: positive
        status.consecutive_failures = 5
        assert status.consecutive_failures == 5

        # Invalid: negative
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            SLAStatus(
                contract_name="orders_v1",
                check_type=ViolationType.FRESHNESS,
                current_value=3600.0,
                threshold=7200.0,
                compliance_pct=99.5,
                window_start=now,
                consecutive_failures=-1,
            )

    @pytest.mark.requirement("3D-FR-036")
    def test_violation_count_24h_validation(self) -> None:
        """Test SLAStatus violation_count_24h must be >= 0."""
        now = datetime.now(tz=timezone.utc)

        # Valid: 0
        status = SLAStatus(
            contract_name="orders_v1",
            check_type=ViolationType.FRESHNESS,
            current_value=3600.0,
            threshold=7200.0,
            compliance_pct=99.5,
            window_start=now,
            violation_count_24h=0,
        )
        assert status.violation_count_24h == 0

        # Valid: positive
        status.violation_count_24h = 10
        assert status.violation_count_24h == 10

        # Invalid: negative
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            SLAStatus(
                contract_name="orders_v1",
                check_type=ViolationType.FRESHNESS,
                current_value=3600.0,
                threshold=7200.0,
                compliance_pct=99.5,
                window_start=now,
                violation_count_24h=-1,
            )

    @pytest.mark.requirement("3D-FR-036")
    def test_all_check_types_supported(self) -> None:
        """Test SLAStatus accepts all ViolationType values."""
        now = datetime.now(tz=timezone.utc)

        for check_type in ViolationType:
            status = SLAStatus(
                contract_name="orders_v1",
                check_type=check_type,
                current_value=3600.0,
                threshold=7200.0,
                compliance_pct=99.5,
                window_start=now,
            )
            assert status.check_type == check_type


class TestTrendDirection:
    """Test suite for TrendDirection enum."""

    @pytest.mark.requirement("3D-FR-037")
    def test_all_trend_values(self) -> None:
        """Test TrendDirection has all expected values."""
        assert TrendDirection.IMPROVING.value == "improving"
        assert TrendDirection.DEGRADING.value == "degrading"
        assert TrendDirection.STABLE.value == "stable"

    @pytest.mark.requirement("3D-FR-037")
    def test_string_values_lowercase(self) -> None:
        """Test TrendDirection values are lowercase strings."""
        for trend in TrendDirection:
            assert isinstance(trend.value, str)
            assert trend.value.islower()


class TestCheckTypeSummary:
    """Test suite for CheckTypeSummary model."""

    @pytest.mark.requirement("3D-FR-037")
    def test_valid_construction_with_all_fields(self) -> None:
        """Test CheckTypeSummary construction with all required fields."""
        summary = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=100,
            passed_checks=95,
            failed_checks=4,
            error_checks=1,
            compliance_pct=95.0,
            avg_duration_seconds=1.5,
            violation_count=4,
            trend=TrendDirection.IMPROVING,
        )

        assert summary.check_type == ViolationType.FRESHNESS
        assert summary.total_checks == 100
        assert summary.passed_checks == 95
        assert summary.failed_checks == 4
        assert summary.error_checks == 1
        assert summary.compliance_pct == pytest.approx(95.0)
        assert summary.avg_duration_seconds == pytest.approx(1.5)
        assert summary.violation_count == 4
        assert summary.trend == TrendDirection.IMPROVING

    @pytest.mark.requirement("3D-FR-037")
    def test_frozen_immutability(self) -> None:
        """Test CheckTypeSummary is frozen and immutable."""
        summary = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=100,
            passed_checks=95,
            failed_checks=4,
            error_checks=1,
            compliance_pct=95.0,
            avg_duration_seconds=1.5,
            violation_count=4,
        )

        with pytest.raises(ValidationError, match="Instance is frozen"):
            summary.compliance_pct = 90.0

    @pytest.mark.requirement("3D-FR-037")
    def test_extra_fields_forbidden(self) -> None:
        """Test CheckTypeSummary rejects extra fields (extra='forbid')."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=95,
                failed_checks=4,
                error_checks=1,
                compliance_pct=95.0,
                avg_duration_seconds=1.5,
                violation_count=4,
                unexpected_field="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("3D-FR-037")
    def test_default_trend_stable(self) -> None:
        """Test CheckTypeSummary defaults trend to STABLE."""
        summary = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=100,
            passed_checks=95,
            failed_checks=4,
            error_checks=1,
            compliance_pct=95.0,
            avg_duration_seconds=1.5,
            violation_count=4,
        )

        assert summary.trend == TrendDirection.STABLE

    @pytest.mark.requirement("3D-FR-037")
    def test_total_checks_validation(self) -> None:
        """Test CheckTypeSummary total_checks must be >= 0."""
        # Valid: 0
        summary = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=0,
            passed_checks=0,
            failed_checks=0,
            error_checks=0,
            compliance_pct=0.0,
            avg_duration_seconds=0.0,
            violation_count=0,
        )
        assert summary.total_checks == 0

        # Invalid: negative
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=-1,
                passed_checks=0,
                failed_checks=0,
                error_checks=0,
                compliance_pct=0.0,
                avg_duration_seconds=0.0,
                violation_count=0,
            )

    @pytest.mark.requirement("3D-FR-037")
    def test_count_fields_validation(self) -> None:
        """Test CheckTypeSummary count fields must be >= 0."""
        # Test passed_checks
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=-1,
                failed_checks=0,
                error_checks=0,
                compliance_pct=95.0,
                avg_duration_seconds=1.5,
                violation_count=0,
            )

        # Test failed_checks
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=100,
                failed_checks=-1,
                error_checks=0,
                compliance_pct=95.0,
                avg_duration_seconds=1.5,
                violation_count=0,
            )

        # Test error_checks
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=100,
                failed_checks=0,
                error_checks=-1,
                compliance_pct=95.0,
                avg_duration_seconds=1.5,
                violation_count=0,
            )

        # Test violation_count
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=100,
                failed_checks=0,
                error_checks=0,
                compliance_pct=95.0,
                avg_duration_seconds=1.5,
                violation_count=-1,
            )

    @pytest.mark.requirement("3D-FR-037")
    def test_compliance_pct_validation(self) -> None:
        """Test CheckTypeSummary compliance_pct must be 0-100."""
        # Valid: 0
        summary_0 = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=100,
            passed_checks=0,
            failed_checks=100,
            error_checks=0,
            compliance_pct=0.0,
            avg_duration_seconds=1.5,
            violation_count=100,
        )
        assert summary_0.compliance_pct == pytest.approx(0.0)

        # Valid: 100
        summary_100 = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=100,
            passed_checks=100,
            failed_checks=0,
            error_checks=0,
            compliance_pct=100.0,
            avg_duration_seconds=1.5,
            violation_count=0,
        )
        assert summary_100.compliance_pct == pytest.approx(100.0)

        # Invalid: below 0
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=95,
                failed_checks=5,
                error_checks=0,
                compliance_pct=-1.0,
                avg_duration_seconds=1.5,
                violation_count=5,
            )

        # Invalid: above 100
        with pytest.raises(ValidationError, match="Input should be less than or equal to 100"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=95,
                failed_checks=5,
                error_checks=0,
                compliance_pct=101.0,
                avg_duration_seconds=1.5,
                violation_count=5,
            )

    @pytest.mark.requirement("3D-FR-037")
    def test_avg_duration_seconds_validation(self) -> None:
        """Test CheckTypeSummary avg_duration_seconds must be >= 0."""
        # Valid: 0
        summary = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=100,
            passed_checks=95,
            failed_checks=5,
            error_checks=0,
            compliance_pct=95.0,
            avg_duration_seconds=0.0,
            violation_count=5,
        )
        assert summary.avg_duration_seconds == pytest.approx(0.0)

        # Invalid: negative
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=95,
                failed_checks=5,
                error_checks=0,
                compliance_pct=95.0,
                avg_duration_seconds=-1.0,
                violation_count=5,
            )


class TestSLAComplianceReport:
    """Test suite for SLAComplianceReport model."""

    @pytest.mark.requirement("3D-FR-037")
    def test_valid_construction_with_all_fields(self) -> None:
        """Test SLAComplianceReport construction with all fields."""
        period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 31, tzinfo=timezone.utc)
        generated_at = datetime.now(tz=timezone.utc)

        summary = CheckTypeSummary(
            check_type=ViolationType.FRESHNESS,
            total_checks=100,
            passed_checks=95,
            failed_checks=4,
            error_checks=1,
            compliance_pct=95.0,
            avg_duration_seconds=1.5,
            violation_count=4,
            trend=TrendDirection.IMPROVING,
        )

        report = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=period_start,
            period_end=period_end,
            overall_compliance_pct=99.5,
            check_summaries=[summary],
            total_violations=3,
            total_checks_executed=2880,
            monitoring_coverage_pct=100.0,
            generated_at=generated_at,
        )

        assert report.contract_name == "orders_v1"
        assert report.period_start == period_start
        assert report.period_end == period_end
        assert report.overall_compliance_pct == pytest.approx(99.5)
        assert len(report.check_summaries) == 1
        assert report.check_summaries[0].check_type == ViolationType.FRESHNESS
        assert report.total_violations == 3
        assert report.total_checks_executed == 2880
        assert report.monitoring_coverage_pct == pytest.approx(100.0)
        assert report.generated_at == generated_at

    @pytest.mark.requirement("3D-FR-037")
    def test_frozen_immutability(self) -> None:
        """Test SLAComplianceReport is frozen and immutable."""
        report = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            overall_compliance_pct=99.5,
            check_summaries=[],
            total_violations=3,
            total_checks_executed=2880,
            monitoring_coverage_pct=100.0,
            generated_at=datetime.now(tz=timezone.utc),
        )

        with pytest.raises(ValidationError, match="Instance is frozen"):
            report.overall_compliance_pct = 95.0

    @pytest.mark.requirement("3D-FR-037")
    def test_extra_fields_forbidden(self) -> None:
        """Test SLAComplianceReport rejects extra fields (extra='forbid')."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            SLAComplianceReport(
                contract_name="orders_v1",
                period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
                overall_compliance_pct=99.5,
                check_summaries=[],
                total_violations=3,
                total_checks_executed=2880,
                monitoring_coverage_pct=100.0,
                generated_at=datetime.now(tz=timezone.utc),
                unexpected_field="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("3D-FR-037")
    def test_nested_check_summaries_accepted(self) -> None:
        """Test SLAComplianceReport accepts nested CheckTypeSummary list."""
        summaries = [
            CheckTypeSummary(
                check_type=ViolationType.FRESHNESS,
                total_checks=100,
                passed_checks=95,
                failed_checks=4,
                error_checks=1,
                compliance_pct=95.0,
                avg_duration_seconds=1.5,
                violation_count=4,
            ),
            CheckTypeSummary(
                check_type=ViolationType.SCHEMA_DRIFT,
                total_checks=100,
                passed_checks=98,
                failed_checks=2,
                error_checks=0,
                compliance_pct=98.0,
                avg_duration_seconds=2.0,
                violation_count=2,
            ),
        ]

        report = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            overall_compliance_pct=96.5,
            check_summaries=summaries,
            total_violations=6,
            total_checks_executed=200,
            monitoring_coverage_pct=100.0,
            generated_at=datetime.now(tz=timezone.utc),
        )

        assert len(report.check_summaries) == 2
        assert report.check_summaries[0].check_type == ViolationType.FRESHNESS
        assert report.check_summaries[1].check_type == ViolationType.SCHEMA_DRIFT

    @pytest.mark.requirement("3D-FR-037")
    def test_empty_check_summaries_accepted(self) -> None:
        """Test SLAComplianceReport accepts empty check_summaries list."""
        report = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            overall_compliance_pct=100.0,
            check_summaries=[],
            total_violations=0,
            total_checks_executed=0,
            monitoring_coverage_pct=0.0,
            generated_at=datetime.now(tz=timezone.utc),
        )

        assert len(report.check_summaries) == 0

    @pytest.mark.requirement("3D-FR-037")
    def test_overall_compliance_pct_validation(self) -> None:
        """Test SLAComplianceReport overall_compliance_pct must be 0-100."""
        # Valid: 0
        report_0 = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            overall_compliance_pct=0.0,
            check_summaries=[],
            total_violations=0,
            total_checks_executed=0,
            monitoring_coverage_pct=0.0,
            generated_at=datetime.now(tz=timezone.utc),
        )
        assert report_0.overall_compliance_pct == pytest.approx(0.0)

        # Valid: 100
        report_100 = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            overall_compliance_pct=100.0,
            check_summaries=[],
            total_violations=0,
            total_checks_executed=100,
            monitoring_coverage_pct=100.0,
            generated_at=datetime.now(tz=timezone.utc),
        )
        assert report_100.overall_compliance_pct == pytest.approx(100.0)

        # Invalid: below 0
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            SLAComplianceReport(
                contract_name="orders_v1",
                period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
                overall_compliance_pct=-1.0,
                check_summaries=[],
                total_violations=0,
                total_checks_executed=0,
                monitoring_coverage_pct=0.0,
                generated_at=datetime.now(tz=timezone.utc),
            )

        # Invalid: above 100
        with pytest.raises(ValidationError, match="Input should be less than or equal to 100"):
            SLAComplianceReport(
                contract_name="orders_v1",
                period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
                overall_compliance_pct=101.0,
                check_summaries=[],
                total_violations=0,
                total_checks_executed=0,
                monitoring_coverage_pct=100.0,
                generated_at=datetime.now(tz=timezone.utc),
            )

    @pytest.mark.requirement("3D-FR-037")
    def test_monitoring_coverage_pct_validation(self) -> None:
        """Test SLAComplianceReport monitoring_coverage_pct must be 0-100."""
        # Valid: 0
        report_0 = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            overall_compliance_pct=0.0,
            check_summaries=[],
            total_violations=0,
            total_checks_executed=0,
            monitoring_coverage_pct=0.0,
            generated_at=datetime.now(tz=timezone.utc),
        )
        assert report_0.monitoring_coverage_pct == pytest.approx(0.0)

        # Valid: 100
        report_100 = SLAComplianceReport(
            contract_name="orders_v1",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            overall_compliance_pct=100.0,
            check_summaries=[],
            total_violations=0,
            total_checks_executed=100,
            monitoring_coverage_pct=100.0,
            generated_at=datetime.now(tz=timezone.utc),
        )
        assert report_100.monitoring_coverage_pct == pytest.approx(100.0)

        # Invalid: below 0
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            SLAComplianceReport(
                contract_name="orders_v1",
                period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
                overall_compliance_pct=95.0,
                check_summaries=[],
                total_violations=0,
                total_checks_executed=100,
                monitoring_coverage_pct=-1.0,
                generated_at=datetime.now(tz=timezone.utc),
            )

        # Invalid: above 100
        with pytest.raises(ValidationError, match="Input should be less than or equal to 100"):
            SLAComplianceReport(
                contract_name="orders_v1",
                period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
                overall_compliance_pct=95.0,
                check_summaries=[],
                total_violations=0,
                total_checks_executed=100,
                monitoring_coverage_pct=101.0,
                generated_at=datetime.now(tz=timezone.utc),
            )

    @pytest.mark.requirement("3D-FR-037")
    def test_count_fields_validation(self) -> None:
        """Test SLAComplianceReport count fields must be >= 0."""
        # Test total_violations
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            SLAComplianceReport(
                contract_name="orders_v1",
                period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
                overall_compliance_pct=95.0,
                check_summaries=[],
                total_violations=-1,
                total_checks_executed=100,
                monitoring_coverage_pct=100.0,
                generated_at=datetime.now(tz=timezone.utc),
            )

        # Test total_checks_executed
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            SLAComplianceReport(
                contract_name="orders_v1",
                period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
                overall_compliance_pct=95.0,
                check_summaries=[],
                total_violations=5,
                total_checks_executed=-1,
                monitoring_coverage_pct=100.0,
                generated_at=datetime.now(tz=timezone.utc),
            )


class TestCalculateCompliance:
    """Test suite for calculate_compliance function."""

    @pytest.mark.requirement("3D-FR-036")
    def test_calculate_compliance_100_percent(self) -> None:
        """Test calculate_compliance returns 100% when all checks pass."""
        period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 2, tzinfo=timezone.utc)

        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
            },
        ]

        report = calculate_compliance(
            check_results=check_results,
            period_start=period_start,
            period_end=period_end,
            contract_name="orders_v1",
        )

        assert report.overall_compliance_pct == pytest.approx(100.0)
        assert report.total_checks_executed == 2
        assert report.total_violations == 0
        assert len(report.check_summaries) == 1
        assert report.check_summaries[0].compliance_pct == pytest.approx(100.0)

    @pytest.mark.requirement("3D-FR-036")
    def test_calculate_compliance_partial(self) -> None:
        """Test calculate_compliance with partial compliance (some violations)."""
        period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 2, tzinfo=timezone.utc)

        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "fail",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "schema_drift",
                "status": "pass",
                "duration_seconds": 0.4,
                "timestamp": datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc),
            },
        ]

        report = calculate_compliance(
            check_results=check_results,
            period_start=period_start,
            period_end=period_end,
            contract_name="orders_v1",
        )

        # Overall: 2/3 = 66.67%
        assert report.overall_compliance_pct == pytest.approx(66.67, abs=0.01)
        assert report.total_checks_executed == 3
        assert report.total_violations == 1

        # Freshness: 1/2 = 50%
        freshness_summary = next(
            s for s in report.check_summaries if s.check_type == ViolationType.FRESHNESS
        )
        assert freshness_summary.compliance_pct == pytest.approx(50.0)
        assert freshness_summary.passed_checks == 1
        assert freshness_summary.failed_checks == 1

        # Schema drift: 1/1 = 100%
        schema_summary = next(
            s for s in report.check_summaries if s.check_type == ViolationType.SCHEMA_DRIFT
        )
        assert schema_summary.compliance_pct == pytest.approx(100.0)

    @pytest.mark.requirement("3D-FR-036")
    def test_calculate_compliance_zero_percent(self) -> None:
        """Test calculate_compliance returns 0% when all checks fail."""
        period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 2, tzinfo=timezone.utc)

        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "fail",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "fail",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
            },
        ]

        report = calculate_compliance(
            check_results=check_results,
            period_start=period_start,
            period_end=period_end,
            contract_name="orders_v1",
        )

        assert report.overall_compliance_pct == pytest.approx(0.0)
        assert report.total_checks_executed == 2
        assert report.total_violations == 2
        assert report.check_summaries[0].compliance_pct == pytest.approx(0.0)

    @pytest.mark.requirement("3D-FR-037")
    def test_calculate_compliance_filters_by_contract_name(self) -> None:
        """Test calculate_compliance filters results by contract_name."""
        period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 2, tzinfo=timezone.utc)

        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "customers_v1",
                "check_type": "freshness",
                "status": "fail",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc),
            },
        ]

        report = calculate_compliance(
            check_results=check_results,
            period_start=period_start,
            period_end=period_end,
            contract_name="orders_v1",
        )

        # Should only include orders_v1 check
        assert report.contract_name == "orders_v1"
        assert report.total_checks_executed == 1
        assert report.overall_compliance_pct == pytest.approx(100.0)

    @pytest.mark.requirement("3D-FR-037")
    def test_calculate_compliance_filters_by_time_window(self) -> None:
        """Test calculate_compliance filters results by time window."""
        period_start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)

        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),  # Before
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "fail",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc),  # During
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.7,
                "timestamp": datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc),  # After
            },
        ]

        report = calculate_compliance(
            check_results=check_results,
            period_start=period_start,
            period_end=period_end,
            contract_name="orders_v1",
        )

        # Should only include the check at 14:00
        assert report.total_checks_executed == 1
        assert report.overall_compliance_pct == pytest.approx(0.0)

    @pytest.mark.requirement("3D-FR-037")
    def test_calculate_compliance_includes_error_checks(self) -> None:
        """Test calculate_compliance counts error status as failed."""
        period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 2, tzinfo=timezone.utc)

        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "error",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
            },
        ]

        report = calculate_compliance(
            check_results=check_results,
            period_start=period_start,
            period_end=period_end,
            contract_name="orders_v1",
        )

        assert report.total_checks_executed == 2
        assert report.check_summaries[0].error_checks == 1
        assert report.check_summaries[0].compliance_pct == pytest.approx(50.0)

    @pytest.mark.requirement("3D-FR-038")
    def test_calculate_compliance_computes_avg_duration(self) -> None:
        """Test calculate_compliance computes average check duration."""
        period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 2, tzinfo=timezone.utc)

        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 1.0,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 3.0,
                "timestamp": datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
            },
        ]

        report = calculate_compliance(
            check_results=check_results,
            period_start=period_start,
            period_end=period_end,
            contract_name="orders_v1",
        )

        # Average: (1.0 + 3.0) / 2 = 2.0
        assert report.check_summaries[0].avg_duration_seconds == pytest.approx(2.0)


class TestComputeTrend:
    """Test suite for compute_trend function."""

    @pytest.mark.requirement("3D-FR-038")
    def test_compute_trend_improving(self) -> None:
        """Test compute_trend returns IMPROVING for increasing compliance."""
        # Compliance increasing from 90% to 98%
        daily_compliance = [90.0, 92.0, 94.0, 96.0, 98.0]

        trend = compute_trend(daily_compliance=daily_compliance, threshold=2.0)

        assert trend == TrendDirection.IMPROVING

    @pytest.mark.requirement("3D-FR-038")
    def test_compute_trend_degrading(self) -> None:
        """Test compute_trend returns DEGRADING for decreasing compliance."""
        # Compliance decreasing from 98% to 90%
        daily_compliance = [98.0, 96.0, 94.0, 92.0, 90.0]

        trend = compute_trend(daily_compliance=daily_compliance, threshold=2.0)

        assert trend == TrendDirection.DEGRADING

    @pytest.mark.requirement("3D-FR-038")
    def test_compute_trend_stable(self) -> None:
        """Test compute_trend returns STABLE for flat compliance."""
        # Compliance stable around 95%
        daily_compliance = [95.0, 95.5, 94.8, 95.2, 95.0]

        trend = compute_trend(daily_compliance=daily_compliance, threshold=2.0)

        assert trend == TrendDirection.STABLE

    @pytest.mark.requirement("3D-FR-038")
    def test_compute_trend_slight_increase_is_stable(self) -> None:
        """Test compute_trend returns STABLE when increase is below threshold."""
        # Compliance increasing but slope < 2.0
        daily_compliance = [95.0, 95.5, 96.0]

        trend = compute_trend(daily_compliance=daily_compliance, threshold=2.0)

        assert trend == TrendDirection.STABLE

    @pytest.mark.requirement("3D-FR-038")
    def test_compute_trend_single_value(self) -> None:
        """Test compute_trend returns STABLE for single value."""
        daily_compliance = [95.0]

        trend = compute_trend(daily_compliance=daily_compliance, threshold=2.0)

        assert trend == TrendDirection.STABLE

    @pytest.mark.requirement("3D-FR-038")
    def test_compute_trend_empty_list(self) -> None:
        """Test compute_trend returns STABLE for empty list."""
        daily_compliance: list[float] = []

        trend = compute_trend(daily_compliance=daily_compliance, threshold=2.0)

        assert trend == TrendDirection.STABLE


class TestAggregateDaily:
    """Test suite for aggregate_daily function."""

    @pytest.mark.requirement("3D-FR-037")
    def test_aggregate_daily_single_day_single_check_type(self) -> None:
        """Test aggregate_daily aggregates checks by day and check_type."""
        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "fail",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
            },
        ]

        daily_agg = aggregate_daily(check_results)

        assert "2026-01-01" in daily_agg
        assert "freshness" in daily_agg["2026-01-01"]
        assert daily_agg["2026-01-01"]["freshness"]["total"] == 2
        assert daily_agg["2026-01-01"]["freshness"]["passed"] == 1
        assert daily_agg["2026-01-01"]["freshness"]["failed"] == 1
        assert daily_agg["2026-01-01"]["freshness"]["error"] == 0

    @pytest.mark.requirement("3D-FR-037")
    def test_aggregate_daily_multiple_days(self) -> None:
        """Test aggregate_daily separates results by day."""
        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc),
            },
        ]

        daily_agg = aggregate_daily(check_results)

        assert "2026-01-01" in daily_agg
        assert "2026-01-02" in daily_agg
        assert daily_agg["2026-01-01"]["freshness"]["total"] == 1
        assert daily_agg["2026-01-02"]["freshness"]["total"] == 1

    @pytest.mark.requirement("3D-FR-037")
    def test_aggregate_daily_multiple_check_types(self) -> None:
        """Test aggregate_daily separates results by check_type."""
        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "pass",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
            {
                "contract_name": "orders_v1",
                "check_type": "schema_drift",
                "status": "fail",
                "duration_seconds": 0.6,
                "timestamp": datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc),
            },
        ]

        daily_agg = aggregate_daily(check_results)

        assert "freshness" in daily_agg["2026-01-01"]
        assert "schema_drift" in daily_agg["2026-01-01"]
        assert daily_agg["2026-01-01"]["freshness"]["total"] == 1
        assert daily_agg["2026-01-01"]["schema_drift"]["total"] == 1

    @pytest.mark.requirement("3D-FR-037")
    def test_aggregate_daily_error_status(self) -> None:
        """Test aggregate_daily counts error status."""
        check_results = [
            {
                "contract_name": "orders_v1",
                "check_type": "freshness",
                "status": "error",
                "duration_seconds": 0.5,
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            },
        ]

        daily_agg = aggregate_daily(check_results)

        assert daily_agg["2026-01-01"]["freshness"]["error"] == 1
        assert daily_agg["2026-01-01"]["freshness"]["total"] == 1

    @pytest.mark.requirement("3D-FR-037")
    def test_aggregate_daily_empty_list(self) -> None:
        """Test aggregate_daily handles empty check results list."""
        check_results: list[dict[str, object]] = []

        daily_agg = aggregate_daily(check_results)

        assert daily_agg == {}
