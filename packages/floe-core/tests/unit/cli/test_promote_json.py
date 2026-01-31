"""Unit tests for promote CLI JSON output (T085).

Task ID: T085
Phase: 9 - User Story 7 (CI/CD Automation)
User Story: US7 - CI/CD Automation Integration
Requirements: FR-031, FR-034

These tests validate JSON output for CI/CD automation:
- FR-031: JSON output includes success, promotion_id, artifact_digest, gate_results, trace_id
- FR-034: Error cases include structured error information

TDD: Tests written FIRST (T085), implementation follows if needed.
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
    """Create a mock PromotionRecord for JSON output tests."""
    return PromotionRecord(
        promotion_id=uuid4(),
        artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        artifact_tag="v1.0.0",
        source_environment="dev",
        target_environment="staging",
        gate_results=[
            GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=150,
            ),
            GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=500,
            ),
        ],
        signature_verified=True,
        operator="ci@github.com",
        promoted_at=datetime.now(timezone.utc),
        dry_run=False,
        trace_id="trace-abc123def456",
        authorization_passed=True,
    )


class TestPromoteJsonOutputFields:
    """Tests for JSON output field completeness (FR-031).

    FR-031: JSON output SHOULD include all fields needed for CI/CD automation.
    """

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_promotion_id(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """JSON output contains promotion_id field."""
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
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "promotion_id" in data
            assert data["promotion_id"] == str(mock_promotion_record.promotion_id)

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_artifact_digest(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """JSON output contains artifact_digest field."""
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
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "artifact_digest" in data
            assert data["artifact_digest"] == mock_promotion_record.artifact_digest

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_gate_results(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """JSON output contains gate_results array."""
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
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "gate_results" in data
            assert isinstance(data["gate_results"], list)
            assert len(data["gate_results"]) == 2
            # Verify gate structure
            gate = data["gate_results"][0]
            assert "gate" in gate
            assert "status" in gate
            assert "duration_ms" in gate

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_trace_id(self, mock_promotion_record: PromotionRecord) -> None:
        """JSON output contains trace_id for observability correlation."""
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
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "trace_id" in data
            assert data["trace_id"] == mock_promotion_record.trace_id

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_signature_verified(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """JSON output contains signature_verified status."""
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
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "signature_verified" in data
            assert data["signature_verified"] is True


class TestPromoteJsonErrorOutput:
    """Tests for JSON error output (FR-034).

    FR-034: Error cases SHOULD include structured error information.
    """

    @pytest.mark.requirement("FR-034")
    def test_invalid_transition_error_json_output(self) -> None:
        """Invalid transition error includes error field in JSON."""
        from floe_core.oci.errors import InvalidTransitionError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = InvalidTransitionError(
                from_env="dev",
                to_env="prod",
                reason="Cannot skip staging environment",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=prod",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code != 0
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "skip" in data["error"].lower() or "staging" in data["error"].lower()
            assert "exit_code" in data

    @pytest.mark.requirement("FR-034")
    def test_gate_validation_error_json_output(self) -> None:
        """Gate validation error includes gate name in JSON."""
        from floe_core.oci.errors import GateValidationError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = GateValidationError(
                gate="policy_compliance",
                details="Missing required owner tag",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code != 0
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "gate" in data
            assert data["gate"] == "policy_compliance"
            assert "exit_code" in data

    @pytest.mark.requirement("FR-034")
    def test_signature_verification_error_json_output(self) -> None:
        """Signature verification error includes error field in JSON."""
        from floe_core.oci.errors import SignatureVerificationError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = SignatureVerificationError(
                artifact_ref="oci://example.com/repo:v1.0.0",
                reason="Signature verification failed: invalid signature",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code != 0
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "signature" in data["error"].lower()
            assert "exit_code" in data

    @pytest.mark.requirement("FR-034")
    def test_registry_unavailable_error_json_output(self) -> None:
        """Registry unavailable error includes error field in JSON."""
        from floe_core.oci.errors import RegistryUnavailableError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = RegistryUnavailableError(
                registry="oci://example.com/repo",
                reason="Connection refused",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code != 0
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "exit_code" in data


class TestPromoteJsonExitCodes:
    """Tests for JSON output with exit codes (FR-034).

    FR-034: Exit codes SHOULD be consistent and machine-parseable.
    """

    @pytest.mark.requirement("FR-034")
    def test_success_returns_exit_code_0(self, mock_promotion_record: PromotionRecord) -> None:
        """Successful promotion returns exit code 0."""
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
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-034")
    def test_invalid_transition_returns_exit_code_9(self) -> None:
        """Invalid transition returns exit code 9."""
        from floe_core.oci.errors import InvalidTransitionError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = InvalidTransitionError(
                from_env="dev",
                to_env="prod",
                reason="Cannot skip staging",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=prod",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 9

    @pytest.mark.requirement("FR-034")
    def test_gate_validation_returns_exit_code_8(self) -> None:
        """Gate validation failure returns exit code 8."""
        from floe_core.oci.errors import GateValidationError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = GateValidationError(
                gate="tests",
                details="Test suite failed",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 8

    @pytest.mark.requirement("FR-034")
    def test_signature_verification_returns_exit_code_6(self) -> None:
        """Signature verification failure returns exit code 6."""
        from floe_core.oci.errors import SignatureVerificationError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = SignatureVerificationError(
                artifact_ref="oci://example.com/repo:v1.0.0",
                reason="Invalid signature",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 6

    @pytest.mark.requirement("FR-034")
    def test_registry_unavailable_returns_exit_code_5(self) -> None:
        """Registry unavailable returns exit code 5."""
        from floe_core.oci.errors import RegistryUnavailableError

        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.side_effect = RegistryUnavailableError(
                registry="oci://example.com/repo",
                reason="Connection refused",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "promote",
                    "v1.0.0",
                    "--from=dev",
                    "--to=staging",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 5


__all__: list[str] = [
    "TestPromoteJsonOutputFields",
    "TestPromoteJsonErrorOutput",
    "TestPromoteJsonExitCodes",
]
