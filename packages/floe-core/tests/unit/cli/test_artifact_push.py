"""Unit tests for artifact push CLI command.

Task ID: T048
Phase: 6 - User Story 4 (Artifact Push)
User Story: US4 - Artifact Push Command Migration
Requirements: FR-040, FR-041, FR-042

These tests verify the artifact push command:
- Parses --artifact and --registry options correctly
- Validates artifact file exists
- Handles authentication via environment variables
- Provides meaningful error messages
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli


class TestArtifactPushHelp:
    """Tests for artifact push help output.

    Task: T048
    Requirement: FR-040
    """

    @pytest.mark.requirement("FR-040")
    def test_push_appears_in_artifact_help(self) -> None:
        """Test that push command is listed in artifact group."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        assert "push" in result.output

    @pytest.mark.requirement("FR-040")
    def test_push_help_shows_options(self) -> None:
        """Test that push help shows required options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "push", "--help"])

        assert result.exit_code == 0
        assert "--artifact" in result.output or "-a" in result.output
        assert "--registry" in result.output or "-r" in result.output
        assert "--tag" in result.output or "-t" in result.output

    @pytest.mark.requirement("FR-040")
    def test_push_help_shows_description(self) -> None:
        """Test that push help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "push", "--help"])

        assert result.exit_code == 0
        # Should describe what the command does
        assert "push" in result.output.lower() or "oci" in result.output.lower()


class TestArtifactPushValidation:
    """Tests for artifact push input validation.

    Task: T048
    Requirement: FR-041
    """

    @pytest.mark.requirement("FR-041")
    def test_push_requires_artifact_option(self) -> None:
        """Test that push fails without --artifact."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["artifact", "push", "--registry", "oci://example.com/repo", "--tag", "v1.0.0"],
        )

        # Should fail with usage error
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-041")
    def test_push_requires_registry_option(self) -> None:
        """Test that push fails without --registry."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create dummy artifact file
            Path("compiled_artifacts.json").write_text('{"version": "2.0.0"}')

            result = runner.invoke(
                cli,
                ["artifact", "push", "--artifact", "compiled_artifacts.json", "--tag", "v1.0.0"],
            )

            # Should fail with usage error
            assert result.exit_code != 0

    @pytest.mark.requirement("FR-041")
    def test_push_requires_tag_option(self) -> None:
        """Test that push fails without --tag."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create dummy artifact file
            Path("compiled_artifacts.json").write_text('{"version": "2.0.0"}')

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "push",
                    "--artifact",
                    "compiled_artifacts.json",
                    "--registry",
                    "oci://example.com/repo",
                ],
            )

            # Should fail with usage error
            assert result.exit_code != 0

    @pytest.mark.requirement("FR-041")
    def test_push_validates_artifact_exists(self) -> None:
        """Test that push validates artifact file exists."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "push",
                "--artifact",
                "nonexistent.json",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
            ],
        )

        # Should fail because file doesn't exist
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "does not exist" in result.output.lower()


class TestArtifactPushExecution:
    """Tests for artifact push execution.

    Task: T048
    Requirement: FR-041
    """

    @pytest.mark.requirement("FR-041")
    def test_push_calls_oci_client(self) -> None:
        """Test that push command uses OCIClient to push artifact."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create file (content doesn't matter, we mock the loader)
            Path("compiled_artifacts.json").write_text("{}")

            # Mock both the loader and the client
            mock_artifacts = MagicMock()
            with patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file",
                return_value=mock_artifacts,
            ):
                with patch("floe_core.oci.OCIClient") as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.push.return_value = "sha256:abc123"
                    mock_client_class.from_registry_config.return_value = mock_client

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "push",
                            "--artifact",
                            "compiled_artifacts.json",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                        ],
                    )

                    # Should succeed
                    assert result.exit_code == 0, f"Failed: {result.output}"
                    # Should call push on the client
                    mock_client.push.assert_called_once()

    @pytest.mark.requirement("FR-041")
    def test_push_outputs_digest_on_success(self) -> None:
        """Test that push outputs digest on success."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create file (content doesn't matter, we mock the loader)
            Path("compiled_artifacts.json").write_text("{}")

            mock_artifacts = MagicMock()
            with patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file",
                return_value=mock_artifacts,
            ):
                with patch("floe_core.oci.OCIClient") as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.push.return_value = "sha256:abc123def456"
                    mock_client_class.from_registry_config.return_value = mock_client

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "push",
                            "--artifact",
                            "compiled_artifacts.json",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                        ],
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"
                    # Should output the digest
                    assert "sha256:abc123def456" in result.output


class TestArtifactPushAuthentication:
    """Tests for artifact push authentication.

    Task: T048
    Requirement: FR-042
    """

    @pytest.mark.requirement("FR-042")
    def test_push_uses_env_credentials(self) -> None:
        """Test that push uses environment variable credentials."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("compiled_artifacts.json").write_text("{}")

            mock_artifacts = MagicMock()
            with patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file",
                return_value=mock_artifacts,
            ):
                with patch("floe_core.oci.OCIClient") as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.push.return_value = "sha256:abc123"
                    mock_client_class.from_registry_config.return_value = mock_client

                    # Set environment variables for auth
                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "push",
                            "--artifact",
                            "compiled_artifacts.json",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                        ],
                        env={
                            "FLOE_REGISTRY_USERNAME": "testuser",
                            "FLOE_REGISTRY_PASSWORD": "testpass",
                        },
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"

    @pytest.mark.requirement("FR-042")
    def test_push_handles_auth_error(self) -> None:
        """Test that push handles authentication errors gracefully."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("compiled_artifacts.json").write_text("{}")

            mock_artifacts = MagicMock()
            with patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file",
                return_value=mock_artifacts,
            ):
                with patch("floe_core.oci.OCIClient") as mock_client_class:
                    from floe_core.oci.errors import AuthenticationError

                    mock_client = MagicMock()
                    mock_client.push.side_effect = AuthenticationError(
                        "example.com", "Authentication failed"
                    )
                    mock_client_class.from_registry_config.return_value = mock_client

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "push",
                            "--artifact",
                            "compiled_artifacts.json",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                        ],
                    )

                    # Should fail with non-zero exit code
                    assert result.exit_code != 0
                    # Should show auth error message
                    assert "auth" in result.output.lower() or "failed" in result.output.lower()


class TestArtifactPushErrors:
    """Tests for artifact push error handling.

    Task: T048
    Requirement: FR-041
    """

    @pytest.mark.requirement("FR-041")
    def test_push_handles_registry_unavailable(self) -> None:
        """Test that push handles registry unavailable errors."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("compiled_artifacts.json").write_text("{}")

            mock_artifacts = MagicMock()
            with patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file",
                return_value=mock_artifacts,
            ):
                with patch("floe_core.oci.OCIClient") as mock_client_class:
                    from floe_core.oci.errors import RegistryUnavailableError

                    mock_client = MagicMock()
                    mock_client.push.side_effect = RegistryUnavailableError(
                        "example.com", "Connection refused"
                    )
                    mock_client_class.from_registry_config.return_value = mock_client

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "push",
                            "--artifact",
                            "compiled_artifacts.json",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                        ],
                    )

                    # Should fail with non-zero exit code
                    assert result.exit_code != 0

    @pytest.mark.requirement("FR-041")
    def test_push_handles_invalid_artifact(self) -> None:
        """Test that push handles invalid artifact JSON."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create invalid artifact file
            Path("compiled_artifacts.json").write_text("not valid json")

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "push",
                    "--artifact",
                    "compiled_artifacts.json",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail
            assert result.exit_code != 0
            # Should mention validation or parsing error
            assert "error" in result.output.lower() or "invalid" in result.output.lower()


__all__: list[str] = [
    "TestArtifactPushHelp",
    "TestArtifactPushValidation",
    "TestArtifactPushExecution",
    "TestArtifactPushAuthentication",
    "TestArtifactPushErrors",
]
