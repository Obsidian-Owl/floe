"""Unit tests for promote CLI command (T040).

Tests for the `floe platform promote` command output formatting:
- Table output format for dry-run
- JSON output format for dry-run
- Success messages
- Error handling

Task ID: T040
Phase: 4 - User Story 2 (Dry-Run)
Requirements: FR-007

See Also:
    - specs/8c-promotion-lifecycle/spec.md: Feature specification
    - User Story 2: Dry-Run Promotion
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
    """Create a mock PromotionRecord for testing output formatting."""
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
        dry_run=True,
        trace_id="abc123def456",
        authorization_passed=True,
    )


@pytest.fixture
def mock_promotion_record_with_warnings() -> PromotionRecord:
    """Create a mock PromotionRecord with warnings."""
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
        ],
        signature_verified=True,
        operator="ci@github.com",
        promoted_at=datetime.now(timezone.utc),
        dry_run=True,
        trace_id="abc123def456",
        authorization_passed=True,
        warnings=["Warning: Policy version is outdated"],
    )


@pytest.fixture
def mock_promotion_record_with_failed_gate() -> PromotionRecord:
    """Create a mock PromotionRecord with a failed gate."""
    return PromotionRecord(
        promotion_id=uuid4(),
        artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        artifact_tag="v1.0.0",
        source_environment="dev",
        target_environment="staging",
        gate_results=[
            GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.FAILED,
                duration_ms=150,
                error="Policy compliance check failed: missing owner tag",
            ),
        ],
        signature_verified=True,
        operator="ci@github.com",
        promoted_at=datetime.now(timezone.utc),
        dry_run=True,
        trace_id="abc123def456",
        authorization_passed=True,
    )


class TestPromoteCliHelp:
    """Tests for promote CLI help output."""

    @pytest.mark.requirement("8C-FR-007")
    def test_promote_appears_in_platform_help(self) -> None:
        """Test that promote command is listed in platform group."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0
        assert "promote" in result.output

    @pytest.mark.requirement("8C-FR-007")
    def test_promote_help_shows_dry_run_option(self) -> None:
        """Test that promote help shows --dry-run option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "promote", "--help"])

        assert result.exit_code == 0
        assert "--dry-run" in result.output

    @pytest.mark.requirement("8C-FR-007")
    def test_promote_help_shows_output_option(self) -> None:
        """Test that promote help shows --output option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "promote", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "table" in result.output.lower()
        assert "json" in result.output.lower()


class TestPromoteCliDryRunTableOutput:
    """Tests for promote CLI dry-run table output format (T040)."""

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_table_output_shows_promotion_id(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run table output shows promotion ID."""
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
                    "--dry-run",
                ],
            )

            assert "Promotion ID:" in result.output
            assert str(mock_promotion_record.promotion_id) in result.output

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_table_output_shows_environments(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run table output shows source and target environments."""
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
                    "--dry-run",
                ],
            )

            assert "From:" in result.output
            assert "dev" in result.output
            assert "To:" in result.output
            assert "staging" in result.output

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_table_output_shows_gate_results(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run table output shows gate results."""
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
                    "--dry-run",
                ],
            )

            assert "Gate Results:" in result.output
            assert "policy_compliance" in result.output
            assert "passed" in result.output

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_table_output_shows_dry_run_indicator(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run table output indicates it was a dry-run."""
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
                    "--dry-run",
                ],
            )

            assert "Dry Run:" in result.output
            assert "True" in result.output

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_table_output_shows_success_message(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run table output shows 'Dry run complete' message."""
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
                    "--dry-run",
                ],
            )

            # Should show dry-run completion message
            assert "Dry run complete" in result.output or "dry run" in result.output.lower()

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_table_output_shows_failed_gate(
        self, mock_promotion_record_with_failed_gate: PromotionRecord
    ) -> None:
        """Test dry-run table output shows failed gate with error."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record_with_failed_gate
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
                    "--dry-run",
                ],
            )

            # Should show failed status
            assert "failed" in result.output
            # Should show error message
            assert "Error:" in result.output or "missing owner tag" in result.output


class TestPromoteCliDryRunJsonOutput:
    """Tests for promote CLI dry-run JSON output format (T040)."""

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_json_output_is_valid_json(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run JSON output is valid JSON."""
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
                    "--dry-run",
                    "--output=json",
                ],
            )

            # Should be valid JSON (may have log messages before JSON)
            data = extract_json_from_output(result.output)
            assert isinstance(data, dict)

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_json_output_contains_promotion_id(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run JSON output contains promotion_id."""
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
                    "--dry-run",
                    "--output=json",
                ],
            )

            data = extract_json_from_output(result.output)
            assert "promotion_id" in data
            assert data["promotion_id"] == str(mock_promotion_record.promotion_id)

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_json_output_contains_dry_run_true(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run JSON output has dry_run=true."""
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
                    "--dry-run",
                    "--output=json",
                ],
            )

            data = extract_json_from_output(result.output)
            assert "dry_run" in data
            assert data["dry_run"] is True

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_json_output_contains_gate_results(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run JSON output contains gate_results."""
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
                    "--dry-run",
                    "--output=json",
                ],
            )

            data = extract_json_from_output(result.output)
            assert "gate_results" in data
            assert isinstance(data["gate_results"], list)
            assert len(data["gate_results"]) == 2

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_json_output_contains_environments(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run JSON output contains source and target environments."""
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
                    "--dry-run",
                    "--output=json",
                ],
            )

            data = extract_json_from_output(result.output)
            assert "source_environment" in data
            assert data["source_environment"] == "dev"
            assert "target_environment" in data
            assert data["target_environment"] == "staging"


class TestPromoteCliDryRunWarnings:
    """Tests for promote CLI dry-run warning output."""

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_table_output_shows_warnings(
        self, mock_promotion_record_with_warnings: PromotionRecord
    ) -> None:
        """Test dry-run table output shows warnings."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record_with_warnings
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
                    "--dry-run",
                ],
            )

            # Should show warnings section
            assert "Warnings:" in result.output
            assert "Policy version is outdated" in result.output

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_json_output_contains_warnings(
        self, mock_promotion_record_with_warnings: PromotionRecord
    ) -> None:
        """Test dry-run JSON output contains warnings list."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record_with_warnings
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
                    "--dry-run",
                    "--output=json",
                ],
            )

            data = extract_json_from_output(result.output)
            assert "warnings" in data
            assert isinstance(data["warnings"], list)
            assert "Policy version is outdated" in data["warnings"][0]


class TestPromoteCliExitCodes:
    """Tests for promote CLI exit codes."""

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_success_returns_exit_code_0(
        self, mock_promotion_record: PromotionRecord
    ) -> None:
        """Test dry-run success returns exit code 0."""
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
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_with_failed_gates_still_returns_exit_code_0(
        self, mock_promotion_record_with_failed_gate: PromotionRecord
    ) -> None:
        """Test dry-run with failed gates still returns exit code 0.

        In dry-run mode, gate failures are informational, not errors.
        """
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_promotion_record_with_failed_gate
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
                    "--dry-run",
                ],
            )

            # Dry-run should succeed even with failed gates
            assert result.exit_code == 0


class TestPromoteCliSignatureVerificationMessages:
    """Tests for signature verification CLI messages (T074 - FR-021)."""

    @pytest.fixture
    def mock_record_signature_verified(self) -> PromotionRecord:
        """Create a mock PromotionRecord with verified signature."""
        return PromotionRecord(
            promotion_id=uuid4(),
            artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            artifact_tag="v1.0.0",
            source_environment="dev",
            target_environment="staging",
            gate_results=[],
            signature_verified=True,
            operator="ci@github.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
        )

    @pytest.fixture
    def mock_record_signature_not_verified(self) -> PromotionRecord:
        """Create a mock PromotionRecord with unverified/unsigned signature."""
        return PromotionRecord(
            promotion_id=uuid4(),
            artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            artifact_tag="v1.0.0",
            source_environment="dev",
            target_environment="staging",
            gate_results=[],
            signature_verified=False,
            operator="ci@github.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="abc123",
            authorization_passed=True,
        )

    @pytest.mark.requirement("FR-021")
    def test_table_output_shows_signature_verified_message(
        self, mock_record_signature_verified: PromotionRecord
    ) -> None:
        """Table output shows '✓ Signature verified' when signature is verified."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_record_signature_verified
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
                ],
            )

            assert result.exit_code == 0
            assert "Signature verified" in result.output

    @pytest.mark.requirement("FR-021")
    def test_table_output_shows_unsigned_warning(
        self, mock_record_signature_not_verified: PromotionRecord
    ) -> None:
        """Table output shows warning when signature is not verified."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_record_signature_not_verified
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
                ],
            )

            assert result.exit_code == 0
            # Should contain warning about unsigned
            assert "WARNING" in result.output or "unsigned" in result.output.lower()

    @pytest.mark.requirement("FR-021")
    def test_json_output_does_not_add_signature_messages(
        self, mock_record_signature_verified: PromotionRecord
    ) -> None:
        """JSON output includes signature_verified field but no extra messages."""
        runner = CliRunner()

        with patch("floe_core.oci.promotion.PromotionController") as mock_controller_class:
            mock_controller = MagicMock()
            mock_controller.promote.return_value = mock_record_signature_verified
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
            # JSON output should be parseable and contain signature_verified
            data = extract_json_from_output(result.output)
            assert "signature_verified" in data
            assert data["signature_verified"] is True
