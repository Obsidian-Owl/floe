"""Unit tests for artifact sign CLI command.

Task ID: T019
Phase: 3 - User Story 1 (Keyless Signing)
Requirements: FR-001, FR-011

These tests verify the artifact sign command:
- Parses --registry, --tag, --key, --keyless options correctly
- Validates mutually exclusive --key and --keyless options
- Handles keyless (OIDC) signing mode
- Handles key-based signing with file paths and KMS URIs
- Provides meaningful error messages
- Authenticates with registry using environment variables
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli
from floe_core.schemas.oci import AuthType
from floe_core.schemas.secrets import SecretSource


class TestArtifactSignHelp:
    """Tests for artifact sign help output.

    Task: T019
    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_appears_in_artifact_help(self) -> None:
        """Test that sign command is listed in artifact group."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        assert "sign" in result.output

    @pytest.mark.requirement("FR-001")
    def test_sign_help_shows_options(self) -> None:
        """Test that sign help shows required options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "sign", "--help"])

        assert result.exit_code == 0
        assert "--registry" in result.output or "-r" in result.output
        assert "--tag" in result.output or "-t" in result.output
        assert "--keyless" in result.output
        assert "--key" in result.output or "-k" in result.output

    @pytest.mark.requirement("FR-001")
    def test_sign_help_shows_description(self) -> None:
        """Test that sign help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "sign", "--help"])

        assert result.exit_code == 0
        # Should describe what the command does
        assert "sign" in result.output.lower() or "artifact" in result.output.lower()


class TestArtifactSignValidation:
    """Tests for artifact sign input validation.

    Task: T019
    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_requires_registry_option(self) -> None:
        """Test that sign fails without --registry."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["artifact", "sign", "--tag", "v1.0.0"],
        )

        # Should fail with usage error
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-001")
    def test_sign_requires_tag_option(self) -> None:
        """Test that sign fails without --tag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["artifact", "sign", "--registry", "oci://example.com/repo"],
        )

        # Should fail with usage error
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-001")
    def test_sign_key_and_keyless_mutually_exclusive(self) -> None:
        """Test that --key and --keyless are mutually exclusive."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create a dummy key file
            Path("cosign.key").write_text("dummy key")

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--key",
                    "cosign.key",
                    "--keyless",
                ],
            )

            # Should fail because options are mutually exclusive
            assert result.exit_code != 0
            assert "mutually exclusive" in result.output.lower()

    @pytest.mark.requirement("FR-001")
    def test_sign_key_file_not_found(self) -> None:
        """Test that sign validates key file exists."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "sign",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
                "--key",
                "nonexistent.key",
                "--no-keyless",
            ],
        )

        # Should fail because file doesn't exist
        assert result.exit_code != 0
        assert (
            "not found" in result.output.lower()
            or "does not exist" in result.output.lower()
        )


class TestArtifactSignKeyless:
    """Tests for keyless (OIDC) signing mode.

    Task: T019
    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_keyless_default_mode(self) -> None:
        """Test that keyless is the default signing mode."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            # Should call _sign_artifact with keyless config
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            signing_config = call_args[0][3]  # 4th positional arg
            assert signing_config.mode == "keyless"

    @pytest.mark.requirement("FR-001")
    def test_sign_keyless_explicit_flag(self) -> None:
        """Test explicit --keyless flag."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--keyless",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            signing_config = call_args[0][3]
            assert signing_config.mode == "keyless"

    @pytest.mark.requirement("FR-001")
    def test_sign_keyless_custom_oidc_issuer(self) -> None:
        """Test keyless signing with custom OIDC issuer."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            custom_issuer = "https://custom.issuer.example.com"
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--oidc-issuer",
                    custom_issuer,
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            signing_config = call_args[0][3]
            assert signing_config.mode == "keyless"
            assert str(signing_config.oidc_issuer) == custom_issuer + "/"

    @pytest.mark.requirement("FR-001")
    def test_sign_keyless_default_oidc_issuer(self) -> None:
        """Test keyless signing uses default GitHub Actions OIDC issuer."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            signing_config = call_args[0][3]
            assert signing_config.mode == "keyless"
            assert "token.actions.githubusercontent.com" in str(
                signing_config.oidc_issuer
            )


class TestArtifactSignKeyBased:
    """Tests for key-based signing mode.

    Task: T019
    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_key_based_with_file_path(self) -> None:
        """Test key-based signing with local key file."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create a dummy key file
            Path("cosign.key").write_text("dummy key content")

            with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
                with patch(
                    "floe_core.oci.signing.check_cosign_available", return_value=True
                ):
                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "sign",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--key",
                            "cosign.key",
                            "--no-keyless",
                        ],
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"
                    mock_sign.assert_called_once()
                    call_args = mock_sign.call_args
                    signing_config = call_args[0][3]
                    assert signing_config.mode == "key-based"
                    assert signing_config.private_key_ref is not None
                    assert signing_config.private_key_ref.source == SecretSource.ENV

    @pytest.mark.requirement("FR-001")
    def test_sign_key_based_with_aws_kms(self) -> None:
        """Test key-based signing with AWS KMS URI."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            with patch(
                "floe_core.oci.signing.check_cosign_available", return_value=True
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "sign",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--key",
                        "awskms://arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
                        "--no-keyless",
                    ],
                )

                assert result.exit_code == 0, f"Failed: {result.output}"
                mock_sign.assert_called_once()
                call_args = mock_sign.call_args
                signing_config = call_args[0][3]
                assert signing_config.mode == "key-based"
                assert signing_config.private_key_ref is not None

    @pytest.mark.requirement("FR-001")
    def test_sign_key_based_with_gcp_kms(self) -> None:
        """Test key-based signing with GCP KMS URI."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            with patch(
                "floe_core.oci.signing.check_cosign_available", return_value=True
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "sign",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--key",
                        "gcpkms://projects/my-project/locations/us/keyRings/my-ring/cryptoKeys/my-key",
                        "--no-keyless",
                    ],
                )

                assert result.exit_code == 0, f"Failed: {result.output}"
                mock_sign.assert_called_once()
                call_args = mock_sign.call_args
                signing_config = call_args[0][3]
                assert signing_config.mode == "key-based"

    @pytest.mark.requirement("FR-001")
    def test_sign_key_based_with_azure_kms(self) -> None:
        """Test key-based signing with Azure KMS URI."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            with patch(
                "floe_core.oci.signing.check_cosign_available", return_value=True
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "sign",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--key",
                        "azurekms://my-vault.vault.azure.net/keys/my-key/version",
                        "--no-keyless",
                    ],
                )

                assert result.exit_code == 0, f"Failed: {result.output}"
                mock_sign.assert_called_once()
                call_args = mock_sign.call_args
                signing_config = call_args[0][3]
                assert signing_config.mode == "key-based"

    @pytest.mark.requirement("FR-001")
    def test_sign_key_based_with_hashivault_kms(self) -> None:
        """Test key-based signing with HashiCorp Vault KMS URI."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            with patch(
                "floe_core.oci.signing.check_cosign_available", return_value=True
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "sign",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--key",
                        "hashivault://vault.example.com/v1/transit/keys/my-key",
                        "--no-keyless",
                    ],
                )

                assert result.exit_code == 0, f"Failed: {result.output}"
                mock_sign.assert_called_once()
                call_args = mock_sign.call_args
                signing_config = call_args[0][3]
                assert signing_config.mode == "key-based"

    @pytest.mark.requirement("FR-001")
    def test_sign_key_based_cosign_not_available(self) -> None:
        """Test key-based signing fails when cosign is not available."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("cosign.key").write_text("dummy key")

            with patch(
                "floe_core.oci.signing.check_cosign_available", return_value=False
            ):
                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "sign",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--key",
                        "cosign.key",
                        "--no-keyless",
                    ],
                )

                assert result.exit_code != 0
                assert "cosign" in result.output.lower()


class TestArtifactSignRegistryAuth:
    """Tests for registry authentication configuration.

    Task: T019
    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_registry_auth_token(self) -> None:
        """Test registry authentication with bearer token."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={"FLOE_REGISTRY_TOKEN": "my-bearer-token"},
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            registry_config = call_args[0][0]
            assert registry_config.auth.type == AuthType.TOKEN

    @pytest.mark.requirement("FR-001")
    def test_sign_registry_auth_basic(self) -> None:
        """Test registry authentication with basic auth (username/password)."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
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
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            registry_config = call_args[0][0]
            assert registry_config.auth.type == AuthType.BASIC

    @pytest.mark.requirement("FR-001")
    def test_sign_registry_auth_aws_irsa(self) -> None:
        """Test registry authentication with AWS IRSA."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={"AWS_ROLE_ARN": "arn:aws:iam::123456789012:role/my-role"},
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            registry_config = call_args[0][0]
            assert registry_config.auth.type == AuthType.AWS_IRSA

    @pytest.mark.requirement("FR-001")
    def test_sign_registry_auth_aws_access_key(self) -> None:
        """Test registry authentication with AWS access key."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"},
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            registry_config = call_args[0][0]
            assert registry_config.auth.type == AuthType.AWS_IRSA

    @pytest.mark.requirement("FR-001")
    def test_sign_registry_auth_anonymous(self) -> None:
        """Test registry authentication with anonymous access."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            registry_config = call_args[0][0]
            assert registry_config.auth.type == AuthType.ANONYMOUS

    @pytest.mark.requirement("FR-001")
    def test_sign_registry_auth_token_precedence(self) -> None:
        """Test that token auth takes precedence over basic auth."""
        runner = CliRunner()

        with patch("floe_core.cli.artifact.sign._sign_artifact") as mock_sign:
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
                env={
                    "FLOE_REGISTRY_TOKEN": "my-token",
                    "FLOE_REGISTRY_USERNAME": "user",
                    "FLOE_REGISTRY_PASSWORD": "pass",
                },
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            mock_sign.assert_called_once()
            call_args = mock_sign.call_args
            registry_config = call_args[0][0]
            # Token should take precedence
            assert registry_config.auth.type == AuthType.TOKEN


class TestArtifactSignExecution:
    """Tests for artifact sign execution.

    Task: T019
    Requirement: FR-001, FR-011
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_calls_oci_client(self) -> None:
        """Test that sign command uses OCIClient to sign artifact."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.rekor_log_index = 12345
            mock_metadata.subject = "sha256:abc123"
            mock_metadata.issuer = "https://token.actions.githubusercontent.com"
            mock_metadata.certificate_fingerprint = "abc123def456"
            mock_client.sign.return_value = mock_metadata
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            # Should call sign on the client
            mock_client.sign.assert_called_once()

    @pytest.mark.requirement("FR-011")
    def test_sign_outputs_rekor_index_on_success(self) -> None:
        """Test that sign outputs Rekor index on success."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.rekor_log_index = 12345
            mock_metadata.subject = "sha256:abc123"
            mock_metadata.issuer = "https://token.actions.githubusercontent.com"
            mock_metadata.certificate_fingerprint = "abc123def456"
            mock_client.sign.return_value = mock_metadata
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            # Should output the Rekor index
            assert "12345" in result.output

    @pytest.mark.requirement("FR-011")
    def test_sign_outputs_offline_message_when_no_rekor(self) -> None:
        """Test that sign outputs offline message when no Rekor entry."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.rekor_log_index = None
            mock_metadata.subject = "sha256:abc123"
            mock_metadata.issuer = None
            mock_metadata.certificate_fingerprint = None
            mock_client.sign.return_value = mock_metadata
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            # Should output offline message
            assert "offline" in result.output.lower()

    @pytest.mark.requirement("FR-001")
    def test_sign_outputs_subject_and_issuer(self) -> None:
        """Test that sign outputs subject and issuer information."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.rekor_log_index = 12345
            mock_metadata.subject = "sha256:abc123def456"
            mock_metadata.issuer = "https://token.actions.githubusercontent.com"
            mock_metadata.certificate_fingerprint = "fingerprint123"
            mock_client.sign.return_value = mock_metadata
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            # Should output subject
            assert "sha256:abc123def456" in result.output
            # Should output issuer
            assert "token.actions.githubusercontent.com" in result.output
            # Should output fingerprint
            assert "fingerprint123" in result.output

    @pytest.mark.requirement("FR-001")
    def test_sign_keyless_mode_label(self) -> None:
        """Test that sign outputs keyless mode label."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.rekor_log_index = 12345
            mock_metadata.subject = "sha256:abc123"
            mock_metadata.issuer = None
            mock_metadata.certificate_fingerprint = None
            mock_client.sign.return_value = mock_metadata
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            assert result.exit_code == 0, f"Failed: {result.output}"
            # Should mention keyless mode
            assert "keyless" in result.output.lower()

    @pytest.mark.requirement("FR-001")
    def test_sign_key_based_mode_label(self) -> None:
        """Test that sign outputs key-based mode label."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("cosign.key").write_text("dummy key")

            with patch("floe_core.oci.OCIClient") as mock_client_class:
                with patch(
                    "floe_core.oci.signing.check_cosign_available", return_value=True
                ):
                    mock_client = MagicMock()
                    mock_metadata = MagicMock()
                    mock_metadata.rekor_log_index = 12345
                    mock_metadata.subject = "sha256:abc123"
                    mock_metadata.issuer = None
                    mock_metadata.certificate_fingerprint = None
                    mock_client.sign.return_value = mock_metadata
                    mock_client_class.from_registry_config.return_value = mock_client

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "sign",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--key",
                            "cosign.key",
                            "--no-keyless",
                        ],
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"
                    # Should mention key-based mode
                    assert "key-based" in result.output.lower()


class TestArtifactSignEdgeCases:
    """Tests for artifact sign edge cases and uncovered branches.

    Task: T019
    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_keyless_false_without_key_option(self) -> None:
        """Test that --no-keyless without --key fails with validation error."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "artifact",
                "sign",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
                "--no-keyless",
            ],
        )

        # Should fail because --no-keyless requires --key
        assert result.exit_code != 0
        assert "key-based signing requires --key" in result.output.lower()

    @pytest.mark.requirement("FR-001")
    def test_sign_key_file_exists_but_validate_key_path_fails(self) -> None:
        """Test key-based signing when validate_key_path fails."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create a file that exists but validate_key_path might reject
            Path("invalid.key").write_text("content")

            with patch("floe_core.cli.utils.validate_key_path") as mock_validate:
                # Make validate_key_path return a path that doesn't exist
                mock_validate.return_value = Path("/nonexistent/path/to/key")

                with patch(
                    "floe_core.oci.signing.check_cosign_available", return_value=True
                ):
                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "sign",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--key",
                            "invalid.key",
                            "--no-keyless",
                        ],
                    )

                    # Should fail because validated path doesn't exist
                    assert result.exit_code != 0
                    assert "not found" in result.output.lower()


class TestArtifactSignErrors:
    """Tests for artifact sign error handling.

    Task: T019
    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_sign_handles_oidc_token_error(self) -> None:
        """Test that sign handles OIDC token acquisition errors."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()

            class OIDCTokenError(Exception):
                """Mock OIDC token error."""

                pass

            mock_client.sign.side_effect = OIDCTokenError("Token acquisition failed")
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail with non-zero exit code
            assert result.exit_code != 0
            # Should show OIDC error message
            assert "oidc" in result.output.lower() or "token" in result.output.lower()

    @pytest.mark.requirement("FR-001")
    def test_sign_handles_signing_error(self) -> None:
        """Test that sign handles signing operation errors."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()

            class SigningError(Exception):
                """Mock signing error."""

                pass

            mock_client.sign.side_effect = SigningError("Signing operation failed")
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail with non-zero exit code
            assert result.exit_code != 0
            # Should show signing error message
            assert "sign" in result.output.lower()

    @pytest.mark.requirement("FR-001")
    def test_sign_handles_authentication_error(self) -> None:
        """Test that sign handles registry authentication errors."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            from floe_core.oci.errors import AuthenticationError

            mock_client = MagicMock()
            mock_client.sign.side_effect = AuthenticationError(
                "example.com", "Authentication failed"
            )
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
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

    @pytest.mark.requirement("FR-001")
    def test_sign_handles_artifact_not_found_error(self) -> None:
        """Test that sign handles artifact not found errors."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()

            class NotFoundError(Exception):
                """Mock not found error."""

                pass

            mock_client.sign.side_effect = NotFoundError("Artifact not found")
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail with non-zero exit code
            assert result.exit_code != 0
            # Should show not found error message
            assert "not found" in result.output.lower()

    @pytest.mark.requirement("FR-001")
    def test_sign_handles_generic_error(self) -> None:
        """Test that sign handles generic errors gracefully."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.sign.side_effect = RuntimeError("Unexpected error")
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "sign",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                ],
            )

            # Should fail with non-zero exit code
            assert result.exit_code != 0
            # Should show error message
            assert "error" in result.output.lower() or "failed" in result.output.lower()


__all__: list[str] = [
    "TestArtifactSignHelp",
    "TestArtifactSignValidation",
    "TestArtifactSignKeyless",
    "TestArtifactSignKeyBased",
    "TestArtifactSignRegistryAuth",
    "TestArtifactSignExecution",
    "TestArtifactSignEdgeCases",
    "TestArtifactSignErrors",
]
