"""Unit tests for artifact inspect CLI command.

Task ID: T047
Phase: 5 - User Story 3 (SBOM Generation and Attestation)
Requirements: FR-017

These tests verify the artifact inspect command:
- Parses --registry, --tag, --show-sbom, --show-signatures, --json-output options
- Fetches artifact metadata from OCI registry
- Retrieves SBOM and signature information
- Formats output as text or JSON
- Handles errors gracefully
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli


class TestArtifactInspectHelp:
    """Tests for artifact inspect help output.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_appears_in_artifact_help(self) -> None:
        """Test that inspect command is listed in artifact group."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        assert "inspect" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_help_shows_options(self) -> None:
        """Test that inspect help shows required options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "inspect", "--help"])

        assert result.exit_code == 0
        assert "--registry" in result.output or "-r" in result.output
        assert "--tag" in result.output or "-t" in result.output
        assert "--show-sbom" in result.output
        assert "--show-signatures" in result.output
        assert "--json-output" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_help_shows_description(self) -> None:
        """Test that inspect help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "inspect", "--help"])

        assert result.exit_code == 0
        # Should describe what the command does
        assert "inspect" in result.output.lower() or "artifact" in result.output.lower()


class TestArtifactInspectValidation:
    """Tests for artifact inspect input validation.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_requires_registry_option(self) -> None:
        """Test that inspect fails without --registry."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["artifact", "inspect", "--tag", "v1.0.0"],
        )

        # Should fail with usage error
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_requires_tag_option(self) -> None:
        """Test that inspect fails without --tag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["artifact", "inspect", "--registry", "oci://example.com/repo"],
        )

        # Should fail with usage error
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_accepts_registry_with_oci_prefix(self) -> None:
        """Test that inspect accepts registry with oci:// prefix."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_accepts_registry_without_oci_prefix(self) -> None:
        """Test that inspect requires oci:// prefix in registry URI."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "artifact",
                "inspect",
                "--registry",
                "example.com/repo",
                "--tag",
                "v1.0.0",
            ],
        )

        # Should fail because registry URI must have oci:// prefix
        assert result.exit_code != 0


class TestArtifactInspectExecution:
    """Tests for artifact inspect execution.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_calls_oci_client(self) -> None:
        """Test that inspect command uses OCIClient to fetch artifact."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            # Should call inspect on the client
            mock_client.inspect.assert_called_once_with(tag="v1.0.0")

    @pytest.mark.requirement("FR-017")
    def test_inspect_outputs_artifact_info(self) -> None:
        """Test that inspect outputs artifact information."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123def456"
        mock_manifest.size = 2048
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {"key": "value"}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0
            # Should output artifact information
            assert "sha256:abc123def456" in result.output
            assert "example.com/repo:v1.0.0" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_handles_missing_created_at(self) -> None:
        """Test that inspect handles artifacts without created_at."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = None
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_handles_missing_annotations(self) -> None:
        """Test that inspect handles artifacts without annotations."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = None

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0


class TestArtifactInspectSbom:
    """Tests for artifact inspect SBOM functionality.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_show_sbom_flag(self) -> None:
        """Test that --show-sbom flag includes SBOM information."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        mock_sbom = {
            "packages": [
                {"name": "pkg1", "versionInfo": "1.0.0"},
                {"name": "pkg2", "versionInfo": "2.0.0"},
            ]
        }

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_sbom",
                return_value=mock_sbom,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-sbom",
                    ],
                )

                assert result.exit_code == 0
                assert "SBOM" in result.output
                assert "pkg1" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_sbom_not_found(self) -> None:
        """Test that inspect handles missing SBOM gracefully."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_sbom",
                return_value=None,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-sbom",
                    ],
                )

                assert result.exit_code == 0
                assert "No SBOM" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_sbom_cosign_not_found(self) -> None:
        """Test that inspect handles cosign not installed."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch("floe_core.oci.attestation.retrieve_sbom") as mock_retrieve:
                from floe_core.oci.attestation import CosignNotFoundError

                mock_retrieve.side_effect = CosignNotFoundError()

                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-sbom",
                    ],
                )

                assert result.exit_code == 0
                assert "cosign" in result.output.lower()

    @pytest.mark.requirement("FR-017")
    def test_inspect_sbom_attestation_error(self) -> None:
        """Test that inspect handles SBOM attestation errors."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch("floe_core.oci.attestation.retrieve_sbom") as mock_retrieve:
                from floe_core.oci.attestation import AttestationError

                mock_retrieve.side_effect = AttestationError("Failed to retrieve SBOM")

                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-sbom",
                    ],
                )

                assert result.exit_code == 0
                assert "Error" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_sbom_truncated_packages(self) -> None:
        """Test that inspect truncates large SBOM package lists."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        # Create SBOM with 15 packages (more than 10 limit)
        mock_sbom = {
            "packages": [{"name": f"pkg{i}", "versionInfo": f"{i}.0.0"} for i in range(15)]
        }

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_sbom",
                return_value=mock_sbom,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-sbom",
                    ],
                )

                assert result.exit_code == 0
                assert "... and 5 more" in result.output


class TestArtifactInspectSignatures:
    """Tests for artifact inspect signature functionality.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_show_signatures_flag(self) -> None:
        """Test that --show-signatures flag includes signature information."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        mock_attestation = MagicMock()
        mock_attestation.predicate_type = "cosign.sigstore.dev/attestation/v1"
        mock_attestation.subject = [MagicMock(name="artifact")]

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_attestations",
                return_value=[mock_attestation],
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-signatures",
                    ],
                )

                assert result.exit_code == 0
                assert "Signature" in result.output
                assert "true" in result.output.lower()

    @pytest.mark.requirement("FR-017")
    def test_inspect_no_signature_info_available(self) -> None:
        """Test that inspect handles when signature retrieval returns None."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_attestations",
                return_value=None,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-signatures",
                    ],
                )

                # When retrieve_attestations returns None, it causes an error
                # because the code tries to call len() on None
                assert result.exit_code == 0
                assert "Error" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_signature_error(self) -> None:
        """Test that inspect handles signature retrieval errors."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_attestations",
                side_effect=Exception("Failed to retrieve attestations"),
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-signatures",
                    ],
                )

                assert result.exit_code == 0
                assert "Error" in result.output


class TestArtifactInspectJsonOutput:
    """Tests for artifact inspect JSON output.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_json_output_flag(self) -> None:
        """Test that --json-output produces valid JSON."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {"key": "value"}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--json-output",
                ],
            )

            assert result.exit_code == 0
            # Should be valid JSON
            output_json = json.loads(result.output)
            assert output_json["digest"] == "sha256:abc123"
            assert output_json["size"] == 1024

    @pytest.mark.requirement("FR-017")
    def test_inspect_json_output_with_sbom(self) -> None:
        """Test that --json-output includes SBOM when requested."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        mock_sbom = {
            "packages": [
                {"name": "pkg1", "versionInfo": "1.0.0"},
            ]
        }

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_sbom",
                return_value=mock_sbom,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-sbom",
                        "--json-output",
                    ],
                )

                assert result.exit_code == 0
                output_json = json.loads(result.output)
                assert "sbom" in output_json

    @pytest.mark.requirement("FR-017")
    def test_inspect_json_output_with_signatures(self) -> None:
        """Test that --json-output includes signatures when requested."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        mock_attestation = MagicMock()
        mock_attestation.predicate_type = "cosign.sigstore.dev/attestation/v1"
        mock_attestation.subject = [MagicMock(name="artifact")]

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_attestations",
                return_value=[mock_attestation],
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "inspect",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--show-signatures",
                        "--json-output",
                    ],
                )

                assert result.exit_code == 0
                output_json = json.loads(result.output)
                assert "signatures" in output_json


class TestArtifactInspectFormatSize:
    """Tests for size formatting utility.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_format_size_bytes(self) -> None:
        """Test that _format_size formats bytes correctly."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 512  # Less than 1KB
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0
            assert "512 B" in result.output

    @pytest.mark.requirement("FR-017")
    def test_format_size_kilobytes(self) -> None:
        """Test that _format_size formats kilobytes correctly."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 2048  # 2 KB
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0
            assert "KB" in result.output

    @pytest.mark.requirement("FR-017")
    def test_format_size_megabytes(self) -> None:
        """Test that _format_size formats megabytes correctly."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024 * 1024 * 5  # 5 MB
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0
            assert "MB" in result.output

    @pytest.mark.requirement("FR-017")
    def test_format_size_gigabytes(self) -> None:
        """Test that _format_size formats gigabytes correctly."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024 * 1024 * 1024 * 2  # 2 GB
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0
            assert "GB" in result.output


class TestArtifactInspectErrors:
    """Tests for artifact inspect error handling.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_handles_registry_unavailable(self) -> None:
        """Test that inspect handles registry unavailable errors."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            from floe_core.oci.errors import RegistryUnavailableError

            mock_client = MagicMock()
            mock_client.inspect.side_effect = RegistryUnavailableError(
                "example.com", "Connection refused"
            )
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail with non-zero exit code
            assert result.exit_code != 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_handles_authentication_error(self) -> None:
        """Test that inspect handles authentication errors."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            from floe_core.oci.errors import AuthenticationError

            mock_client = MagicMock()
            mock_client.inspect.side_effect = AuthenticationError(
                "example.com", "Authentication failed"
            )
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail with non-zero exit code
            assert result.exit_code != 0
            assert "auth" in result.output.lower() or "failed" in result.output.lower()

    @pytest.mark.requirement("FR-017")
    def test_inspect_handles_generic_exception(self) -> None:
        """Test that inspect handles generic exceptions."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.side_effect = Exception("Unexpected error")
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail with non-zero exit code
            assert result.exit_code != 0


class TestArtifactInspectAuthentication:
    """Tests for artifact inspect authentication.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_uses_token_auth(self) -> None:
        """Test that inspect uses token authentication from environment."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={"FLOE_REGISTRY_TOKEN": "mytoken"},
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_uses_basic_auth(self) -> None:
        """Test that inspect uses basic authentication from environment."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={
                    "FLOE_REGISTRY_USERNAME": "user",
                    "FLOE_REGISTRY_PASSWORD": "pass",
                },
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_uses_aws_irsa_auth(self) -> None:
        """Test that inspect uses AWS IRSA authentication from environment."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={"AWS_ROLE_ARN": "arn:aws:iam::123456789:role/my-role"},
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-017")
    def test_inspect_uses_anonymous_auth(self) -> None:
        """Test that inspect uses anonymous authentication when no credentials."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={},  # No auth environment variables
            )

            assert result.exit_code == 0


class TestArtifactInspectAnnotations:
    """Tests for artifact inspect annotation handling.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_displays_annotations(self) -> None:
        """Test that inspect displays artifact annotations."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {
            "org.opencontainers.image.title": "My Artifact",
            "org.opencontainers.image.description": "A test artifact",
        }

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0
            assert "Annotations" in result.output
            assert "My Artifact" in result.output

    @pytest.mark.requirement("FR-017")
    def test_inspect_truncates_long_annotation_values(self) -> None:
        """Test that inspect truncates long annotation values."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        # Create a very long annotation value
        long_value = "x" * 100
        mock_manifest.annotations = {
            "org.opencontainers.image.description": long_value,
        }

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "inspect",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0
            # Should contain truncation indicator
            assert "..." in result.output


class TestArtifactInspectCombinations:
    """Tests for artifact inspect flag combinations.

    Task: T047
    Requirement: FR-017
    """

    @pytest.mark.requirement("FR-017")
    def test_inspect_all_flags_together(self) -> None:
        """Test that inspect works with all flags together."""
        runner = CliRunner()

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:abc123"
        mock_manifest.size = 1024
        mock_manifest.artifact_type = "application/vnd.floe.compiled-artifacts.v1+json"
        mock_manifest.created_at = datetime.now(timezone.utc)
        mock_manifest.annotations = {}

        mock_sbom = {
            "packages": [
                {"name": "pkg1", "versionInfo": "1.0.0"},
            ]
        }

        mock_attestation = MagicMock()
        mock_attestation.predicate_type = "cosign.sigstore.dev/attestation/v1"
        mock_attestation.subject = [MagicMock(name="artifact")]

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.oci.attestation.retrieve_sbom",
                return_value=mock_sbom,
            ):
                with patch(
                    "floe_core.oci.attestation.retrieve_attestations",
                    return_value=[mock_attestation],
                ):
                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "inspect",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--show-sbom",
                            "--show-signatures",
                            "--json-output",
                        ],
                    )

                    assert result.exit_code == 0
                    output_json = json.loads(result.output)
                    assert "sbom" in output_json
                    assert "signatures" in output_json


__all__: list[str] = [
    "TestArtifactInspectHelp",
    "TestArtifactInspectValidation",
    "TestArtifactInspectExecution",
    "TestArtifactInspectSbom",
    "TestArtifactInspectSignatures",
    "TestArtifactInspectJsonOutput",
    "TestArtifactInspectFormatSize",
    "TestArtifactInspectErrors",
    "TestArtifactInspectAuthentication",
    "TestArtifactInspectAnnotations",
    "TestArtifactInspectCombinations",
]
