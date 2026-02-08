"""Unit tests for rollback CLI JSON output (T086).

Task ID: T086
Phase: 9 - User Story 7 (CI/CD Automation)
User Story: US7 - CI/CD Automation Integration
Requirements: FR-031

These tests validate JSON output for CI/CD automation:
- FR-031: JSON output includes rollback_id, artifact_digest, trace_id, etc.

TDD: Tests written FIRST (T086), implementation follows if needed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli
from floe_core.schemas.promotion import RollbackRecord


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
def mock_rollback_record() -> RollbackRecord:
    """Create a mock RollbackRecord for JSON output tests."""
    return RollbackRecord(
        rollback_id=uuid4(),
        artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        environment="prod",
        previous_digest="sha256:f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5",
        reason="Performance regression in v2.0.0",
        operator="sre@example.com",
        rolled_back_at=datetime.now(timezone.utc),
        trace_id="trace-rollback-123abc",
    )


class TestRollbackJsonOutputFields:
    """Tests for rollback JSON output field completeness (FR-031).

    FR-031: JSON output SHOULD include all fields needed for CI/CD automation.
    """

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_rollback_id(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """JSON output contains rollback_id field."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
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
            assert "rollback_id" in data
            assert data["rollback_id"] == str(mock_rollback_record.rollback_id)

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_artifact_digest(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """JSON output contains artifact_digest field."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
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
            assert "artifact_digest" in data
            assert data["artifact_digest"] == mock_rollback_record.artifact_digest

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_trace_id(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """JSON output contains trace_id for observability correlation."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
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

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_environment(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """JSON output contains environment field."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
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
            assert "environment" in data
            assert data["environment"] == "prod"

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_previous_digest(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """JSON output contains previous_digest for audit trail."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
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
            assert "previous_digest" in data
            assert data["previous_digest"] == mock_rollback_record.previous_digest


class TestRollbackJsonErrorOutput:
    """Tests for rollback JSON error output (FR-031).

    FR-031: Error cases SHOULD include structured error information.
    """

    @pytest.mark.requirement("FR-031")
    def test_version_not_promoted_error_json_output(self) -> None:
        """VersionNotPromotedError includes error and context in JSON."""
        from floe_core.oci.errors import VersionNotPromotedError

        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = VersionNotPromotedError(
                tag="v1.0.0",
                environment="prod",
                available_versions=["v0.9.0", "v0.8.0"],
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Bug fix",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 11
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "tag" in data
            assert data["tag"] == "v1.0.0"
            assert "environment" in data
            assert data["environment"] == "prod"
            assert "exit_code" in data
            assert data["exit_code"] == 11

    @pytest.mark.requirement("FR-031")
    def test_registry_unavailable_error_json_output(self) -> None:
        """RegistryUnavailableError includes error field in JSON."""
        from floe_core.oci.errors import RegistryUnavailableError

        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = RegistryUnavailableError(
                registry="oci://example.com/repo",
                reason="Connection refused",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Bug fix",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 5
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "exit_code" in data


class TestRollbackJsonExitCodes:
    """Tests for rollback JSON output with exit codes (FR-031).

    Exit codes are important for CI/CD pipeline integration.
    """

    @pytest.mark.requirement("FR-031")
    def test_success_returns_exit_code_0(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """Successful rollback returns exit code 0."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
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

    @pytest.mark.requirement("FR-031")
    def test_version_not_promoted_returns_exit_code_11(self) -> None:
        """VersionNotPromotedError returns exit code 11."""
        from floe_core.oci.errors import VersionNotPromotedError

        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = VersionNotPromotedError(
                tag="v1.0.0",
                environment="prod",
                available_versions=[],
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Bug fix",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 11

    @pytest.mark.requirement("FR-031")
    def test_registry_unavailable_returns_exit_code_5(self) -> None:
        """RegistryUnavailableError returns exit code 5."""
        from floe_core.oci.errors import RegistryUnavailableError

        runner = CliRunner()

        with patch(
            "floe_core.oci.promotion.PromotionController"
        ) as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = RegistryUnavailableError(
                registry="oci://example.com/repo",
                reason="Connection refused",
            )
            mock_controller_class.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Bug fix",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 5


__all__: list[str] = [
    "TestRollbackJsonOutputFields",
    "TestRollbackJsonErrorOutput",
    "TestRollbackJsonExitCodes",
]
