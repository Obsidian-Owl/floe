"""Unit tests for status CLI JSON output (T087).

Task ID: T087
Phase: 9 - User Story 7 (CI/CD Automation)
User Story: US7 - CI/CD Automation Integration
Requirements: FR-031

These tests validate JSON output for CI/CD automation:
- FR-031: JSON output includes environment statuses for machine parsing.

TDD: Tests written FIRST (T087), implementation follows if needed.
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
    EnvironmentStatus,
    PromotionHistoryEntry,
    PromotionStatusResponse,
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
def mock_status_response() -> PromotionStatusResponse:
    """Create a mock PromotionStatusResponse for JSON output tests."""
    return PromotionStatusResponse(
        tag="v1.0.0",
        digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        environments={
            "dev": EnvironmentStatus(
                promoted=True,
                promoted_at=datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc),
                is_latest=False,
                operator="ci@example.com",
            ),
            "staging": EnvironmentStatus(
                promoted=True,
                promoted_at=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
                is_latest=True,
                operator="release@example.com",
            ),
            "prod": EnvironmentStatus(
                promoted=False,
                promoted_at=None,
                is_latest=False,
                operator=None,
            ),
        },
        history=[
            PromotionHistoryEntry(
                promotion_id=str(uuid4()),
                artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                source_environment="dev",
                target_environment="staging",
                operator="release@example.com",
                promoted_at=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ],
        queried_at=datetime.now(timezone.utc),
    )


class TestStatusJsonOutputFields:
    """Tests for status JSON output field completeness (FR-031).

    FR-031: JSON output SHOULD include all fields needed for CI/CD automation.
    """

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_tag(self, mock_status_response: PromotionStatusResponse) -> None:
        """JSON output contains tag field."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "tag" in data
            assert data["tag"] == "v1.0.0"

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_digest(
        self, mock_status_response: PromotionStatusResponse
    ) -> None:
        """JSON output contains artifact digest field."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "digest" in data
            assert data["digest"].startswith("sha256:")

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_environments(
        self, mock_status_response: PromotionStatusResponse
    ) -> None:
        """JSON output contains environments object with status per environment."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "environments" in data
            assert isinstance(data["environments"], dict)
            assert "dev" in data["environments"]
            assert "staging" in data["environments"]
            assert "prod" in data["environments"]

    @pytest.mark.requirement("FR-031")
    def test_json_output_environment_has_promoted_status(
        self, mock_status_response: PromotionStatusResponse
    ) -> None:
        """JSON output contains promoted status for each environment."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)

            # Verify each environment has promoted field
            for env_name in ["dev", "staging", "prod"]:
                assert "promoted" in data["environments"][env_name]

            # Verify specific values
            assert data["environments"]["dev"]["promoted"] is True
            assert data["environments"]["staging"]["promoted"] is True
            assert data["environments"]["prod"]["promoted"] is False

    @pytest.mark.requirement("FR-031")
    def test_json_output_contains_queried_at(
        self, mock_status_response: PromotionStatusResponse
    ) -> None:
        """JSON output contains queried_at timestamp for CI/CD audit."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert "queried_at" in data


class TestStatusJsonErrorOutput:
    """Tests for status JSON error output (FR-031).

    FR-031: Error cases SHOULD include structured error information.
    """

    @pytest.mark.requirement("FR-031")
    def test_artifact_not_found_error_json_output(self) -> None:
        """ArtifactNotFoundError includes error and context in JSON."""
        from floe_core.oci.errors import ArtifactNotFoundError

        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.side_effect = ArtifactNotFoundError(
                tag="v1.0.0",
                registry="oci://example.com/repo",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 3
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "tag" in data
            assert data["tag"] == "v1.0.0"
            assert "exit_code" in data
            assert data["exit_code"] == 3

    @pytest.mark.requirement("FR-031")
    def test_registry_unavailable_error_json_output(self) -> None:
        """RegistryUnavailableError includes error field in JSON."""
        from floe_core.oci.errors import RegistryUnavailableError

        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.side_effect = RegistryUnavailableError(
                registry="oci://example.com/repo",
                reason="Connection refused",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 5
            data = extract_json_from_output(result.output)
            assert "error" in data
            assert "exit_code" in data


class TestStatusJsonExitCodes:
    """Tests for status JSON output with exit codes (FR-031).

    Exit codes are important for CI/CD pipeline integration.
    """

    @pytest.mark.requirement("FR-031")
    def test_success_returns_exit_code_0(
        self, mock_status_response: PromotionStatusResponse
    ) -> None:
        """Successful status query returns exit code 0."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-031")
    def test_artifact_not_found_returns_exit_code_3(self) -> None:
        """ArtifactNotFoundError returns exit code 3."""
        from floe_core.oci.errors import ArtifactNotFoundError

        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.side_effect = ArtifactNotFoundError(
                tag="v1.0.0",
                registry="oci://example.com/repo",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 3

    @pytest.mark.requirement("FR-031")
    def test_registry_unavailable_returns_exit_code_5(self) -> None:
        """RegistryUnavailableError returns exit code 5."""
        from floe_core.oci.errors import RegistryUnavailableError

        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.side_effect = RegistryUnavailableError(
                registry="oci://example.com/repo",
                reason="Connection refused",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 5


__all__: list[str] = [
    "TestStatusJsonOutputFields",
    "TestStatusJsonErrorOutput",
    "TestStatusJsonExitCodes",
]
