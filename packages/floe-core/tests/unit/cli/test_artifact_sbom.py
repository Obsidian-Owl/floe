"""Unit tests for artifact sbom CLI command.

Task ID: T051
Phase: 5 - User Story 3 (SBOM Generation and Attestation)
Requirements: FR-014, FR-016, FR-017
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli


class TestArtifactSbomHelp:
    """Tests for artifact sbom help output."""

    def test_sbom_appears_in_artifact_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        assert "sbom" in result.output

    def test_sbom_help_shows_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "sbom", "--help"])

        assert result.exit_code == 0
        assert "--generate" in result.output
        assert "--attach" in result.output
        assert "--show" in result.output
        assert "--project" in result.output
        assert "--registry" in result.output
        assert "--tag" in result.output


class TestArtifactSbomValidation:
    """Tests for artifact sbom input validation."""

    def test_sbom_requires_at_least_one_action(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "sbom"])

        assert result.exit_code != 0
        assert "At least one action required" in result.output

    def test_sbom_show_requires_registry_and_tag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "sbom", "--show"])

        assert result.exit_code != 0
        assert "--registry" in result.output or "required" in result.output.lower()

    def test_sbom_show_cannot_combine_with_generate(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sbom",
                "--show",
                "--generate",
                "-r",
                "oci://example.com/repo",
                "-t",
                "v1.0.0",
            ],
        )

        assert result.exit_code != 0
        assert "cannot be combined" in result.output.lower()

    def test_sbom_attach_without_generate_requires_sbom_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sbom",
                "--attach",
                "-r",
                "oci://example.com/repo",
                "-t",
                "v1.0.0",
            ],
        )

        assert result.exit_code != 0
        assert "--sbom-file" in result.output


class TestArtifactSbomGenerate:
    """Tests for SBOM generation via CLI."""

    @patch("floe_core.oci.attestation.generate_sbom")
    def test_sbom_generate_success(self, mock_generate: MagicMock, tmp_path: Path) -> None:
        mock_sbom = {
            "spdxVersion": "SPDX-2.3",
            "packages": [{"name": "click", "versionInfo": "8.1.0"}],
        }
        mock_generate.return_value = mock_sbom

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["artifact", "sbom", "--generate", "--project", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "spdxVersion" in result.output
        assert "SPDX-2.3" in result.output

    @patch("floe_core.oci.attestation.generate_sbom")
    def test_sbom_generate_to_file(self, mock_generate: MagicMock, tmp_path: Path) -> None:
        mock_sbom = {"spdxVersion": "SPDX-2.3", "packages": []}
        mock_generate.return_value = mock_sbom

        output_file = tmp_path / "sbom.json"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sbom",
                "--generate",
                "--project",
                str(tmp_path),
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        saved_sbom = json.loads(output_file.read_text())
        assert saved_sbom["spdxVersion"] == "SPDX-2.3"

    @patch("floe_core.oci.attestation.generate_sbom")
    def test_sbom_generate_syft_not_found(self, mock_generate: MagicMock, tmp_path: Path) -> None:
        from floe_core.oci.attestation import SyftNotFoundError

        mock_generate.side_effect = SyftNotFoundError()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["artifact", "sbom", "--generate", "--project", str(tmp_path)],
        )

        assert result.exit_code != 0
        assert "syft" in result.output.lower()


class TestArtifactSbomAttach:
    """Tests for SBOM attachment via CLI."""

    @patch("floe_core.oci.attestation.attach_attestation")
    @patch("floe_core.oci.attestation.generate_sbom")
    def test_sbom_generate_and_attach_success(
        self,
        mock_generate: MagicMock,
        mock_attach: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_sbom = {"spdxVersion": "SPDX-2.3", "packages": []}
        mock_generate.return_value = mock_sbom

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sbom",
                "--generate",
                "--attach",
                "--project",
                str(tmp_path),
                "-r",
                "oci://example.com/repo",
                "-t",
                "v1.0.0",
            ],
        )

        assert result.exit_code == 0
        mock_generate.assert_called_once()
        mock_attach.assert_called_once()

    @patch("floe_core.oci.attestation.attach_attestation")
    def test_sbom_attach_existing_file(self, mock_attach: MagicMock, tmp_path: Path) -> None:
        sbom_file = tmp_path / "sbom.json"
        sbom_file.write_text('{"spdxVersion": "SPDX-2.3"}')

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sbom",
                "--attach",
                "--sbom-file",
                str(sbom_file),
                "-r",
                "oci://example.com/repo",
                "-t",
                "v1.0.0",
            ],
        )

        assert result.exit_code == 0
        mock_attach.assert_called_once()


class TestArtifactSbomShow:
    """Tests for SBOM retrieval via CLI."""

    @patch("floe_core.oci.attestation.retrieve_sbom")
    def test_sbom_show_success(self, mock_retrieve: MagicMock) -> None:
        mock_sbom = {
            "spdxVersion": "SPDX-2.3",
            "packages": [{"name": "click", "versionInfo": "8.1.0"}],
        }
        mock_retrieve.return_value = mock_sbom

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sbom",
                "--show",
                "-r",
                "oci://example.com/repo",
                "-t",
                "v1.0.0",
            ],
        )

        assert result.exit_code == 0
        assert "spdxVersion" in result.output
        assert "SPDX-2.3" in result.output

    @patch("floe_core.oci.attestation.retrieve_sbom")
    def test_sbom_show_not_found(self, mock_retrieve: MagicMock) -> None:
        mock_retrieve.return_value = None

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sbom",
                "--show",
                "-r",
                "oci://example.com/repo",
                "-t",
                "v1.0.0",
            ],
        )

        assert result.exit_code == 0
        assert "No SBOM" in result.output or "not found" in result.output.lower()


class TestArtifactInspect:
    """Tests for artifact inspect command with --show-sbom."""

    def test_inspect_appears_in_artifact_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        assert "inspect" in result.output

    def test_inspect_help_shows_sbom_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "inspect", "--help"])

        assert result.exit_code == 0
        assert "--show-sbom" in result.output

    def test_inspect_requires_registry_and_tag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "inspect"])

        assert result.exit_code != 0
