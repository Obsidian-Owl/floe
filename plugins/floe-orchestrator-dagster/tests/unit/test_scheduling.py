"""Unit tests for scheduling in DagsterOrchestratorPlugin.

These tests verify the schedule_job() method creates valid Dagster
ScheduleDefinition objects with proper cron and timezone validation.

Note: @pytest.mark.requirement markers are used for traceability to spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestScheduleJobBasics:
    """Test basic schedule_job functionality.

    Validates FR-013: System MUST support cron-based scheduling with timezone.
    """

    def test_schedule_job_creates_schedule_definition(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test schedule_job creates a ScheduleDefinition."""
        from dagster import ScheduleDefinition

        dagster_plugin.schedule_job("daily_refresh", "0 8 * * *", "UTC")

        assert hasattr(dagster_plugin, "_schedules")
        assert len(dagster_plugin._schedules) == 1
        assert isinstance(dagster_plugin._schedules[0], ScheduleDefinition)

    def test_schedule_job_uses_correct_job_name(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test schedule references correct job name."""
        dagster_plugin.schedule_job("my_job", "0 8 * * *", "UTC")

        schedule = dagster_plugin._schedules[0]
        assert schedule.job_name == "my_job"

    def test_schedule_job_creates_schedule_name(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test schedule name is derived from job name."""
        dagster_plugin.schedule_job("daily_refresh", "0 8 * * *", "UTC")

        schedule = dagster_plugin._schedules[0]
        assert schedule.name == "daily_refresh_schedule"

    def test_schedule_job_uses_correct_cron(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test schedule uses correct cron expression."""
        dagster_plugin.schedule_job("daily_refresh", "0 8 * * *", "UTC")

        schedule = dagster_plugin._schedules[0]
        assert schedule.cron_schedule == "0 8 * * *"

    def test_schedule_job_uses_correct_timezone(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test schedule uses correct timezone."""
        dagster_plugin.schedule_job("daily_refresh", "0 8 * * *", "America/New_York")

        schedule = dagster_plugin._schedules[0]
        assert schedule.execution_timezone == "America/New_York"

    def test_schedule_job_multiple_schedules(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test creating multiple schedules."""
        dagster_plugin.schedule_job("job_1", "0 8 * * *", "UTC")
        dagster_plugin.schedule_job("job_2", "0 12 * * *", "UTC")
        dagster_plugin.schedule_job("job_3", "0 18 * * *", "UTC")

        assert len(dagster_plugin._schedules) == 3
        assert dagster_plugin._schedules[0].name == "job_1_schedule"
        assert dagster_plugin._schedules[1].name == "job_2_schedule"
        assert dagster_plugin._schedules[2].name == "job_3_schedule"


class TestCronExpressionValidation:
    """Test cron expression validation.

    Validates FR-014: System MUST validate cron expressions.
    """

    def test_valid_cron_daily(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test valid daily cron expression."""
        # Should not raise
        dagster_plugin.schedule_job("job", "0 8 * * *", "UTC")

    def test_valid_cron_hourly(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test valid hourly cron expression."""
        dagster_plugin.schedule_job("job", "0 * * * *", "UTC")

    def test_valid_cron_weekly(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test valid weekly cron expression."""
        dagster_plugin.schedule_job("job", "0 8 * * 1", "UTC")

    def test_valid_cron_monthly(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test valid monthly cron expression."""
        dagster_plugin.schedule_job("job", "0 8 1 * *", "UTC")

    def test_valid_cron_complex(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test valid complex cron expression with ranges."""
        dagster_plugin.schedule_job("job", "*/15 8-17 * * 1-5", "UTC")

    def test_invalid_cron_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test invalid cron expression raises ValueError."""
        with pytest.raises(ValueError):
            dagster_plugin.schedule_job("job", "invalid", "UTC")

    def test_invalid_cron_error_includes_expression(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test error message includes the invalid expression."""
        with pytest.raises(ValueError, match="invalid_cron"):
            dagster_plugin.schedule_job("job", "invalid_cron", "UTC")

    def test_invalid_cron_error_includes_guidance(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test error message includes format guidance."""
        with pytest.raises(ValueError, match="minute hour day month weekday"):
            dagster_plugin.schedule_job("job", "invalid", "UTC")

    def test_empty_cron_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test empty cron expression raises ValueError."""
        with pytest.raises(ValueError, match="empty string"):
            dagster_plugin.schedule_job("job", "", "UTC")

    def test_whitespace_cron_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test whitespace-only cron expression raises ValueError."""
        with pytest.raises(ValueError, match="empty string"):
            dagster_plugin.schedule_job("job", "   ", "UTC")

    def test_invalid_minute_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test invalid minute value raises ValueError."""
        with pytest.raises(ValueError):
            dagster_plugin.schedule_job("job", "60 8 * * *", "UTC")

    def test_invalid_hour_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test invalid hour value raises ValueError."""
        with pytest.raises(ValueError):
            dagster_plugin.schedule_job("job", "0 25 * * *", "UTC")


class TestTimezoneValidation:
    """Test timezone validation.

    Validates FR-015: System MUST validate IANA timezones.
    """

    def test_valid_timezone_utc(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test valid UTC timezone."""
        dagster_plugin.schedule_job("job", "0 8 * * *", "UTC")

    def test_valid_timezone_us_eastern(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test valid US Eastern timezone."""
        dagster_plugin.schedule_job("job", "0 8 * * *", "America/New_York")

    def test_valid_timezone_us_pacific(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test valid US Pacific timezone."""
        dagster_plugin.schedule_job("job", "0 8 * * *", "America/Los_Angeles")

    def test_valid_timezone_europe(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test valid European timezone."""
        dagster_plugin.schedule_job("job", "0 8 * * *", "Europe/London")

    def test_valid_timezone_asia(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test valid Asian timezone."""
        dagster_plugin.schedule_job("job", "0 8 * * *", "Asia/Tokyo")

    def test_invalid_timezone_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test invalid timezone raises ValueError."""
        with pytest.raises(ValueError):
            dagster_plugin.schedule_job("job", "0 8 * * *", "Invalid/Timezone")

    def test_invalid_timezone_error_includes_timezone(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test error message includes the invalid timezone."""
        with pytest.raises(ValueError, match="NotATimezone"):
            dagster_plugin.schedule_job("job", "0 8 * * *", "NotATimezone")

    def test_invalid_timezone_error_includes_examples(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test error message includes valid timezone examples."""
        with pytest.raises(ValueError, match="UTC") as exc_info:
            dagster_plugin.schedule_job("job", "0 8 * * *", "Invalid")

        error_message = str(exc_info.value)
        assert "America/New_York" in error_message
        assert "Europe/London" in error_message

    def test_empty_timezone_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test empty timezone raises ValueError."""
        with pytest.raises(ValueError, match="empty string"):
            dagster_plugin.schedule_job("job", "0 8 * * *", "")

    def test_whitespace_timezone_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test whitespace-only timezone raises ValueError."""
        with pytest.raises(ValueError, match="empty string"):
            dagster_plugin.schedule_job("job", "0 8 * * *", "   ")

    def test_timezone_case_variants(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test timezone case handling.

        Note: Python's zoneinfo module behavior varies by platform.
        On macOS, zoneinfo may be case-insensitive due to underlying tzdata.
        On Linux, zoneinfo is case-sensitive (IANA names are case-sensitive).
        We test the documented IANA behavior: uppercase "UTC" is the canonical form.
        """
        # UTC (uppercase) is always valid - this is the canonical IANA form
        dagster_plugin.schedule_job("job_utc", "0 8 * * *", "UTC")

        # Proper case IANA timezones work
        dagster_plugin.schedule_job("job_proper", "0 8 * * *", "America/New_York")

        # Invalid timezones are rejected
        with pytest.raises(ValueError):
            dagster_plugin.schedule_job("job", "0 8 * * *", "Invalid_Zone")

        # Note: lowercase 'utc' may work on some platforms (macOS) but fails on
        # others (Linux). We don't test it because IANA timezone names are
        # case-sensitive per the spec. Users should always use "UTC".


class TestScheduleJobEdgeCases:
    """Test edge cases for schedule_job."""

    def test_job_name_with_underscores(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test job name with underscores."""
        dagster_plugin.schedule_job("my_daily_job_v2", "0 8 * * *", "UTC")

        assert dagster_plugin._schedules[0].name == "my_daily_job_v2_schedule"

    def test_job_name_with_hyphens_raises_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test job name with hyphens raises error.

        Note: Dagster requires names to match ^[A-Za-z0-9_]+$ pattern.
        Hyphens are not allowed in schedule names.
        """
        from dagster._core.errors import DagsterInvalidDefinitionError

        with pytest.raises(DagsterInvalidDefinitionError, match="not a valid name"):
            dagster_plugin.schedule_job("my-daily-job", "0 8 * * *", "UTC")

    def test_cron_with_leading_zeros(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test cron expression with leading zeros."""
        dagster_plugin.schedule_job("job", "00 08 01 01 *", "UTC")

    def test_cron_at_midnight(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test cron at midnight."""
        dagster_plugin.schedule_job("job", "0 0 * * *", "UTC")

    def test_cron_every_minute(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test cron every minute."""
        dagster_plugin.schedule_job("job", "* * * * *", "UTC")

    def test_different_timezones_same_job(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test same job can be scheduled in different timezones."""
        dagster_plugin.schedule_job("job_east", "0 8 * * *", "America/New_York")
        dagster_plugin.schedule_job("job_west", "0 8 * * *", "America/Los_Angeles")

        assert dagster_plugin._schedules[0].execution_timezone == "America/New_York"
        assert dagster_plugin._schedules[1].execution_timezone == "America/Los_Angeles"
