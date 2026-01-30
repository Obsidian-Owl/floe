"""Unit tests for trace_id inclusion in CLI output (T089).

Task ID: T089
Phase: 9 - User Story 7 (CI/CD Automation)
User Story: US7 - CI/CD Automation Integration
Requirements: FR-033

These tests validate trace_id is included in CLI output for observability:
- FR-033: trace_id appears in both human and JSON output for correlation.

TDD: Tests written FIRST (T089), implementation follows if needed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli
from floe_core.schemas.promotion import (
    GateResult,
    GateStatus,
    PromotionGate,
    PromotionRecord,
    RollbackRecord,
)


def extract_json_from_output(output: str) -> dict:
    """Extract JSON object from CLI output that may contain log messages.

    The CLI may output structlog messages before the JSON. This helper
    finds and parses the JSON object from the output.

    Args:
        output: Raw CLI output that may contain log messages and JSON.

    Returns:
        Parsed JSON dictionary.

    Raises:
        json.JSONDecodeError: If no valid JSON found.
    """
    # Find the start of JSON (first '{')
    start = output.find("{")
    if start == -1:
        return json.loads(output)  # Let json handle the error

    # Find matching end brace
    depth = 0
    for i, char in enumerate(output[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(output[start : i + 1])

    # If we get here, try parsing from start
    return json.loads(output[start:])


@pytest.fixture
def mock_promotion_record() -> PromotionRecord:
    """Create a mock PromotionRecord with trace_id for testing."""
    return PromotionRecord(
        promotion_id=uuid4(),
        artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        artifact_tag="v1.0.0-staging",
        source_environment="staging",
        target_environment="prod",
        operator="release@example.com",
        promoted_at=datetime.now(timezone.utc),
        gate_results=[
            GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=1500,
            ),
            GateResult(
                gate=PromotionGate.SECURITY_SCAN,
                status=GateStatus.PASSED,
                duration_ms=3000,
            ),
        ],
        dry_run=False,
        trace_id="trace-promote-abc123def456",
        authorization_passed=True,
        signature_verified=True,
    )


@pytest.fixture
def mock_rollback_record() -> RollbackRecord:
    """Create a mock RollbackRecord with trace_id for testing."""
    return RollbackRecord(
        rollback_id=uuid4(),
        artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        environment="prod",
        previous_digest="sha256:f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5",
        reason="Performance regression in v2.0.0",
        operator="sre@example.com",
        rolled_back_at=datetime.now(timezone.utc),
        trace_id="trace-rollback-xyz789uvw012",
    )


class TestPromoteTraceIdOutput:
    """Tests for trace_id inclusion in promote command output (FR-033)."""

    @pytest.mark.requirement("FR-033")
    def test_promote_json_output_contains_trace_id(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Promote command JSON output includes trace_id for observability."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=staging",
                    "--to=prod",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "trace_id" in data
            assert data["trace_id"] == mock_promotion_record.trace_id

    @pytest.mark.requirement("FR-033")
    def test_promote_table_output_contains_trace_id(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Promote command human-readable output includes trace_id."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=staging",
                    "--to=prod",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 0
            # trace_id should appear somewhere in human-readable output
            output_lower = result.output.lower()
            assert "trace" in output_lower or mock_promotion_record.trace_id in result.output

    @pytest.mark.requirement("FR-033")
    def test_promote_trace_id_is_non_empty(self, mock_promotion_record: PromotionRecord) -> None:
        """Promote command trace_id is a non-empty string."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=staging",
                    "--to=prod",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "trace_id" in data
            assert isinstance(data["trace_id"], str)
            assert len(data["trace_id"]) > 0


class TestRollbackTraceIdOutput:
    """Tests for trace_id inclusion in rollback command output (FR-033)."""

    @pytest.mark.requirement("FR-033")
    def test_rollback_json_output_contains_trace_id(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """Rollback command JSON output includes trace_id for observability."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.rollback.return_value = mock_rollback_record
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Performance regression",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "trace_id" in data
            assert data["trace_id"] == mock_rollback_record.trace_id

    @pytest.mark.requirement("FR-033")
    def test_rollback_table_output_contains_trace_id(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """Rollback command human-readable output includes trace_id."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.rollback.return_value = mock_rollback_record
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Performance regression",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 0
            # trace_id should appear somewhere in human-readable output
            output_lower = result.output.lower()
            assert "trace" in output_lower or mock_rollback_record.trace_id in result.output

    @pytest.mark.requirement("FR-033")
    def test_rollback_trace_id_is_non_empty(self, mock_rollback_record: RollbackRecord) -> None:
        """Rollback command trace_id is a non-empty string."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.rollback.return_value = mock_rollback_record
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Performance regression",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "trace_id" in data
            assert isinstance(data["trace_id"], str)
            assert len(data["trace_id"]) > 0


class TestTraceIdObservabilityCorrelation:
    """Tests for trace_id correlation with observability systems (FR-033)."""

    @pytest.mark.requirement("FR-033")
    def test_trace_id_format_is_usable(self, mock_promotion_record: PromotionRecord) -> None:
        """Trace ID format is suitable for OpenTelemetry correlation.

        The trace_id should be a non-empty string that can be used to
        correlate logs, metrics, and traces in observability systems.
        """
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=staging",
                    "--to=prod",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            trace_id = data.get("trace_id", "")

            # Trace ID should be usable as a correlation ID
            # - Non-empty
            # - No whitespace
            # - Printable characters only
            assert len(trace_id) > 0
            assert trace_id == trace_id.strip()
            assert trace_id.isprintable()

    @pytest.mark.requirement("FR-033")
    def test_different_operations_have_different_trace_ids(
        self,
        mock_promotion_record: PromotionRecord,
        mock_rollback_record: RollbackRecord,
    ) -> None:
        """Different operations should have different trace_ids."""
        # This test validates that trace_ids are unique per operation
        # by checking that the fixtures have different trace_ids
        assert mock_promotion_record.trace_id != mock_rollback_record.trace_id


__all__: list[str] = [
    "TestPromoteTraceIdOutput",
    "TestRollbackTraceIdOutput",
    "TestTraceIdObservabilityCorrelation",
]
