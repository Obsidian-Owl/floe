"""Unit tests for network audit event models.

Task: T018
Epic: 7C - Network and Pod Security
Requirements: FR-071
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.network.audit import (
    NetworkPolicyAuditEvent,
    PolicyAuditResult,
    PolicyOperation,
)


class TestPolicyOperation:
    """Test PolicyOperation enum values."""

    @pytest.mark.requirement("FR-071")
    def test_all_values_are_strings(self) -> None:
        """Test that all PolicyOperation enum values are strings."""
        for operation in PolicyOperation:
            assert isinstance(operation.value, str)

    @pytest.mark.requirement("FR-071")
    def test_generate_value(self) -> None:
        """Test GENERATE operation has correct value."""
        assert PolicyOperation.GENERATE.value == "generate"

    @pytest.mark.requirement("FR-071")
    def test_apply_value(self) -> None:
        """Test APPLY operation has correct value."""
        assert PolicyOperation.APPLY.value == "apply"

    @pytest.mark.requirement("FR-071")
    def test_delete_value(self) -> None:
        """Test DELETE operation has correct value."""
        assert PolicyOperation.DELETE.value == "delete"

    @pytest.mark.requirement("FR-071")
    def test_validate_value(self) -> None:
        """Test VALIDATE operation has correct value."""
        assert PolicyOperation.VALIDATE.value == "validate"

    @pytest.mark.requirement("FR-071")
    def test_diff_value(self) -> None:
        """Test DIFF operation has correct value."""
        assert PolicyOperation.DIFF.value == "diff"


class TestPolicyAuditResult:
    """Test PolicyAuditResult enum values."""

    @pytest.mark.requirement("FR-071")
    def test_all_values_are_strings(self) -> None:
        """Test that all PolicyAuditResult enum values are strings."""
        for result in PolicyAuditResult:
            assert isinstance(result.value, str)

    @pytest.mark.requirement("FR-071")
    def test_success_value(self) -> None:
        """Test SUCCESS result has correct value."""
        assert PolicyAuditResult.SUCCESS.value == "success"

    @pytest.mark.requirement("FR-071")
    def test_failed_value(self) -> None:
        """Test FAILED result has correct value."""
        assert PolicyAuditResult.FAILED.value == "failed"

    @pytest.mark.requirement("FR-071")
    def test_skipped_value(self) -> None:
        """Test SKIPPED result has correct value."""
        assert PolicyAuditResult.SKIPPED.value == "skipped"

    @pytest.mark.requirement("FR-071")
    def test_dry_run_value(self) -> None:
        """Test DRY_RUN result has correct value."""
        assert PolicyAuditResult.DRY_RUN.value == "dry_run"


class TestNetworkPolicyAuditEvent:
    """Test NetworkPolicyAuditEvent model creation and validation."""

    @pytest.mark.requirement("FR-071")
    def test_create_with_required_fields(self) -> None:
        """Test creating audit event with only required fields."""
        timestamp = datetime.now(timezone.utc)
        event = NetworkPolicyAuditEvent(
            timestamp=timestamp,
            operation=PolicyOperation.GENERATE,
        )

        assert event.timestamp == timestamp
        assert event.operation == PolicyOperation.GENERATE
        assert event.result == PolicyAuditResult.SUCCESS  # default
        assert event.policy_name is None
        assert event.namespace is None
        assert event.policies_count == 0  # default
        assert event.trace_id is None
        assert event.user_id is None
        assert event.source is None
        assert event.metadata is None

    @pytest.mark.requirement("FR-071")
    def test_default_values(self) -> None:
        """Test default values are applied correctly."""
        event = NetworkPolicyAuditEvent(
            timestamp=datetime.now(timezone.utc),
            operation=PolicyOperation.APPLY,
        )

        assert event.result == PolicyAuditResult.SUCCESS
        assert event.policies_count == 0

    @pytest.mark.requirement("FR-071")
    def test_policies_count_minimum_validation(self) -> None:
        """Test policies_count must be >= 0."""
        timestamp = datetime.now(timezone.utc)

        # Valid: zero
        event = NetworkPolicyAuditEvent(
            timestamp=timestamp,
            operation=PolicyOperation.GENERATE,
            policies_count=0,
        )
        assert event.policies_count == 0

        # Valid: positive
        event = NetworkPolicyAuditEvent(
            timestamp=timestamp,
            operation=PolicyOperation.GENERATE,
            policies_count=5,
        )
        assert event.policies_count == 5

        # Invalid: negative
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            NetworkPolicyAuditEvent(
                timestamp=timestamp,
                operation=PolicyOperation.GENERATE,
                policies_count=-1,
            )

    @pytest.mark.requirement("FR-071")
    def test_frozen_model_rejects_mutation(self) -> None:
        """Test that frozen model prevents field mutation."""
        event = NetworkPolicyAuditEvent(
            timestamp=datetime.now(timezone.utc),
            operation=PolicyOperation.GENERATE,
        )

        with pytest.raises(ValidationError, match="Instance is frozen"):
            event.operation = PolicyOperation.APPLY  # type: ignore[misc]

    @pytest.mark.requirement("FR-071")
    def test_extra_fields_rejected(self) -> None:
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            NetworkPolicyAuditEvent(
                timestamp=datetime.now(timezone.utc),
                operation=PolicyOperation.GENERATE,
                unknown_field="value",  # type: ignore[call-arg]
            )


class TestEnsureTimezoneAware:
    """Test timestamp timezone validation and conversion."""

    @pytest.mark.requirement("FR-071")
    def test_naive_datetime_converted_to_utc(self) -> None:
        """Test naive datetime is converted to UTC."""
        naive_dt = datetime(2025, 1, 27, 12, 0, 0)
        event = NetworkPolicyAuditEvent(
            timestamp=naive_dt,
            operation=PolicyOperation.GENERATE,
        )

        assert event.timestamp.tzinfo == timezone.utc
        assert event.timestamp.year == 2025
        assert event.timestamp.month == 1
        assert event.timestamp.day == 27
        assert event.timestamp.hour == 12

    @pytest.mark.requirement("FR-071")
    def test_timezone_aware_datetime_preserved(self) -> None:
        """Test timezone-aware datetime is preserved."""
        aware_dt = datetime(2025, 1, 27, 12, 0, 0, tzinfo=timezone.utc)
        event = NetworkPolicyAuditEvent(
            timestamp=aware_dt,
            operation=PolicyOperation.GENERATE,
        )

        assert event.timestamp == aware_dt
        assert event.timestamp.tzinfo == timezone.utc

    @pytest.mark.requirement("FR-071")
    def test_iso_string_with_z_suffix_parsed(self) -> None:
        """Test ISO string with Z suffix is parsed correctly."""
        iso_string = "2025-01-27T12:00:00Z"
        event = NetworkPolicyAuditEvent(
            timestamp=iso_string,  # type: ignore[arg-type]
            operation=PolicyOperation.GENERATE,
        )

        assert event.timestamp.tzinfo == timezone.utc
        assert event.timestamp.year == 2025
        assert event.timestamp.month == 1
        assert event.timestamp.day == 27
        assert event.timestamp.hour == 12

    @pytest.mark.requirement("FR-071")
    def test_iso_string_with_offset_parsed(self) -> None:
        """Test ISO string with timezone offset is parsed correctly."""
        iso_string = "2025-01-27T12:00:00+05:00"
        event = NetworkPolicyAuditEvent(
            timestamp=iso_string,  # type: ignore[arg-type]
            operation=PolicyOperation.GENERATE,
        )

        assert event.timestamp.tzinfo is not None
        assert event.timestamp.year == 2025
        assert event.timestamp.month == 1
        assert event.timestamp.day == 27
        assert event.timestamp.hour == 12

    @pytest.mark.requirement("FR-071")
    def test_naive_iso_string_gets_utc(self) -> None:
        """Test naive ISO string gets UTC timezone."""
        iso_string = "2025-01-27T12:00:00"
        event = NetworkPolicyAuditEvent(
            timestamp=iso_string,  # type: ignore[arg-type]
            operation=PolicyOperation.GENERATE,
        )

        assert event.timestamp.tzinfo == timezone.utc
        assert event.timestamp.year == 2025
        assert event.timestamp.month == 1
        assert event.timestamp.day == 27
        assert event.timestamp.hour == 12


class TestToLogDict:
    """Test conversion to log dictionary."""

    @pytest.mark.requirement("FR-071")
    def test_includes_required_fields(self) -> None:
        """Test log dict includes all required fields."""
        timestamp = datetime(2025, 1, 27, 12, 0, 0, tzinfo=timezone.utc)
        event = NetworkPolicyAuditEvent(
            timestamp=timestamp,
            operation=PolicyOperation.GENERATE,
        )

        log_dict = event.to_log_dict()

        assert "timestamp" in log_dict
        assert "operation" in log_dict
        assert "result" in log_dict
        assert "policies_count" in log_dict

    @pytest.mark.requirement("FR-071")
    def test_excludes_none_values(self) -> None:
        """Test log dict excludes None optional fields."""
        event = NetworkPolicyAuditEvent(
            timestamp=datetime.now(timezone.utc),
            operation=PolicyOperation.GENERATE,
        )

        log_dict = event.to_log_dict()

        assert "policy_name" not in log_dict
        assert "namespace" not in log_dict
        assert "trace_id" not in log_dict
        assert "user_id" not in log_dict
        assert "source" not in log_dict
        assert "metadata" not in log_dict

    @pytest.mark.requirement("FR-071")
    def test_timestamp_as_isoformat(self) -> None:
        """Test timestamp is converted to ISO format string."""
        timestamp = datetime(2025, 1, 27, 12, 0, 0, tzinfo=timezone.utc)
        event = NetworkPolicyAuditEvent(
            timestamp=timestamp,
            operation=PolicyOperation.GENERATE,
        )

        log_dict = event.to_log_dict()

        assert isinstance(log_dict["timestamp"], str)
        assert log_dict["timestamp"] == "2025-01-27T12:00:00+00:00"

    @pytest.mark.requirement("FR-071")
    def test_enum_values_as_strings(self) -> None:
        """Test enum values are converted to strings."""
        event = NetworkPolicyAuditEvent(
            timestamp=datetime.now(timezone.utc),
            operation=PolicyOperation.GENERATE,
            result=PolicyAuditResult.SUCCESS,
        )

        log_dict = event.to_log_dict()

        assert log_dict["operation"] == "generate"
        assert log_dict["result"] == "success"

    @pytest.mark.requirement("FR-071")
    def test_includes_optional_fields_when_set(self) -> None:
        """Test log dict includes optional fields when set."""
        event = NetworkPolicyAuditEvent(
            timestamp=datetime.now(timezone.utc),
            operation=PolicyOperation.APPLY,
            policy_name="default-deny-egress",
            namespace="floe-jobs",
            trace_id="abc123",
            user_id="user@example.com",
            source="cli",
        )

        log_dict = event.to_log_dict()

        assert log_dict["policy_name"] == "default-deny-egress"
        assert log_dict["namespace"] == "floe-jobs"
        assert log_dict["trace_id"] == "abc123"
        assert log_dict["user_id"] == "user@example.com"
        assert log_dict["source"] == "cli"

    @pytest.mark.requirement("FR-071")
    def test_includes_metadata_when_set(self) -> None:
        """Test log dict includes metadata when set."""
        metadata: dict[str, Any] = {
            "reason": "security_policy",
            "affected_pods": 5,
        }
        event = NetworkPolicyAuditEvent(
            timestamp=datetime.now(timezone.utc),
            operation=PolicyOperation.DELETE,
            metadata=metadata,
        )

        log_dict = event.to_log_dict()

        assert log_dict["metadata"] == metadata


class TestCreateGenerateEvent:
    """Test create_generate_event factory method."""

    @pytest.mark.requirement("FR-071")
    def test_sets_operation_to_generate(self) -> None:
        """Test factory method sets operation to GENERATE."""
        event = NetworkPolicyAuditEvent.create_generate_event(
            namespace="test-namespace",
            policies_count=3,
        )

        assert event.operation == PolicyOperation.GENERATE

    @pytest.mark.requirement("FR-071")
    def test_sets_timestamp_to_now(self) -> None:
        """Test factory method sets timestamp to current time."""
        before = datetime.now(timezone.utc)
        event = NetworkPolicyAuditEvent.create_generate_event(
            namespace="test-namespace",
            policies_count=3,
        )
        after = datetime.now(timezone.utc)

        assert before <= event.timestamp <= after
        assert event.timestamp.tzinfo == timezone.utc

    @pytest.mark.requirement("FR-071")
    def test_accepts_namespace_and_count(self) -> None:
        """Test factory method accepts namespace and policies_count."""
        event = NetworkPolicyAuditEvent.create_generate_event(
            namespace="floe-jobs",
            policies_count=5,
        )

        assert event.namespace == "floe-jobs"
        assert event.policies_count == 5

    @pytest.mark.requirement("FR-071")
    def test_accepts_optional_parameters(self) -> None:
        """Test factory method accepts optional parameters."""
        metadata: dict[str, Any] = {"reason": "test"}
        event = NetworkPolicyAuditEvent.create_generate_event(
            namespace="test-namespace",
            policies_count=2,
            result=PolicyAuditResult.DRY_RUN,
            trace_id="trace123",
            user_id="user@example.com",
            source="api",
            metadata=metadata,
        )

        assert event.result == PolicyAuditResult.DRY_RUN
        assert event.trace_id == "trace123"
        assert event.user_id == "user@example.com"
        assert event.source == "api"
        assert event.metadata == metadata

    @pytest.mark.requirement("FR-071")
    def test_default_result_is_success(self) -> None:
        """Test factory method defaults result to SUCCESS."""
        event = NetworkPolicyAuditEvent.create_generate_event(
            namespace="test-namespace",
            policies_count=1,
        )

        assert event.result == PolicyAuditResult.SUCCESS
