"""Unit tests for artifact verify CLI command.

Task ID: T032
Phase: 4 - User Story 2 (Signature Verification)
Requirements: FR-009, FR-010, FR-011

These tests verify the artifact verify command:
- Parses --issuer, --subject, --key options correctly
- Validates mutual exclusivity constraints
- Handles keyless and key-based verification modes
- Enforces signature verification at different levels
- Exports and inspects verification bundles
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli
from floe_core.cli.utils import ExitCode


class TestArtifactVerifyHelp:
    """Tests for artifact verify help output.

    Task: T032
    Requirement: FR-009
    """

    @pytest.mark.requirement("FR-009")
    def test_verify_appears_in_artifact_help(self) -> None:
        """Test that verify command is listed in artifact group."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        assert "verify" in result.output

    @pytest.mark.requirement("FR-009")
    def test_verify_help_shows_options(self) -> None:
        """Test that verify help shows required options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "verify", "--help"])

        assert result.exit_code == 0
        assert "--registry" in result.output or "-r" in result.output
        assert "--tag" in result.output or "-t" in result.output
        assert "--issuer" in result.output or "-i" in result.output
        assert "--key" in result.output or "-k" in result.output

    @pytest.mark.requirement("FR-009")
    def test_verify_help_shows_description(self) -> None:
        """Test that verify help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "verify", "--help"])

        assert result.exit_code == 0
        assert "verify" in result.output.lower() or "signature" in result.output.lower()


class TestArtifactVerifyValidation:
    """Tests for artifact verify input validation.

    Task: T032
    Requirement: FR-009
    """

    @pytest.mark.requirement("FR-009")
    def test_verify_requires_registry_option(self) -> None:
        """Test that verify fails without --registry."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "verify",
                "--tag",
                "v1.0.0",
                "--issuer",
                "https://token.actions.githubusercontent.com",
                "--subject",
                "repo:acme/floe:ref:refs/heads/main",
            ],
        )

        assert result.exit_code != 0

    @pytest.mark.requirement("FR-009")
    def test_verify_requires_tag_option(self) -> None:
        """Test that verify fails without --tag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "verify",
                "--registry",
                "oci://example.com/repo",
                "--issuer",
                "https://token.actions.githubusercontent.com",
                "--subject",
                "repo:acme/floe:ref:refs/heads/main",
            ],
        )

        assert result.exit_code != 0

    @pytest.mark.requirement("FR-009")
    def test_verify_requires_issuer_or_key(self) -> None:
        """Test that verify requires either --issuer or --key."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "verify",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
            ],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "issuer" in result.output.lower() or "key" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_issuer_and_key_mutually_exclusive(self) -> None:
        """Test that --issuer and --key are mutually exclusive."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "verify",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
                "--issuer",
                "https://token.actions.githubusercontent.com",
                "--subject",
                "repo:acme/floe:ref:refs/heads/main",
                "--key",
                "/path/to/key.pub",
            ],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "mutually exclusive" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_keyless_requires_subject_or_subject_regex(self) -> None:
        """Test that keyless verification requires --subject or --subject-regex."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "verify",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
                "--issuer",
                "https://token.actions.githubusercontent.com",
            ],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "subject" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_subject_and_subject_regex_mutually_exclusive(self) -> None:
        """Test that --subject and --subject-regex are mutually exclusive."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "verify",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
                "--issuer",
                "https://token.actions.githubusercontent.com",
                "--subject",
                "repo:acme/floe:ref:refs/heads/main",
                "--subject-regex",
                "repo:acme/.*:ref:refs/heads/main",
            ],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "mutually exclusive" in result.output.lower()


class TestArtifactVerifyKeyless:
    """Tests for keyless verification mode.

    Task: T032
    Requirement: FR-009
    """

    @pytest.mark.requirement("FR-009")
    def test_verify_keyless_with_subject(self) -> None:
        """Test keyless verification with exact subject."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = True
                    mock_result.status = "valid"
                    mock_result.signer_identity = "test@example.com"
                    mock_result.issuer = "https://token.actions.githubusercontent.com"
                    mock_result.rekor_verified = True
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                        ],
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"
                    assert "verified successfully" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_keyless_with_subject_regex(self) -> None:
        """Test keyless verification with subject regex pattern."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = True
                    mock_result.status = "valid"
                    mock_result.signer_identity = "test@example.com"
                    mock_result.issuer = "https://token.actions.githubusercontent.com"
                    mock_result.rekor_verified = True
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject-regex",
                            "repo:acme/.*:ref:refs/heads/main",
                        ],
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"
                    assert "verified successfully" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_keyless_with_rekor_required(self) -> None:
        """Test keyless verification with Rekor transparency log required."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = True
                    mock_result.status = "valid"
                    mock_result.signer_identity = "test@example.com"
                    mock_result.issuer = "https://token.actions.githubusercontent.com"
                    mock_result.rekor_verified = True
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                            "--require-rekor",
                        ],
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"


class TestArtifactVerifyKeyBased:
    """Tests for key-based verification mode.

    Task: T032
    Requirement: FR-010
    """

    @pytest.mark.requirement("FR-010")
    def test_verify_key_based_with_file_path(self) -> None:
        """Test key-based verification with public key file."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create a dummy public key file
            Path("cosign.pub").write_text(
                "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
            )

            with patch(
                "floe_core.oci.verification.check_cosign_available", return_value=True
            ):
                with patch("floe_core.oci.OCIClient") as mock_client_class:
                    mock_client = MagicMock()
                    mock_manifest = MagicMock()
                    mock_manifest.annotations = {
                        "cosign.sigstore.dev/signature": "sig_data",
                    }
                    mock_client.inspect.return_value = mock_manifest
                    mock_client._fetch_from_registry.return_value = (
                        b"content",
                        "sha256:abc123",
                    )
                    mock_client_class.from_registry_config.return_value = mock_client

                    with patch(
                        "floe_core.schemas.signing.SignatureMetadata.from_annotations"
                    ) as mock_from_annot:
                        mock_sig_metadata = MagicMock()
                        mock_from_annot.return_value = mock_sig_metadata

                        with patch(
                            "floe_core.oci.verification.VerificationClient"
                        ) as mock_verif_class:
                            mock_verif = MagicMock()
                            mock_result = MagicMock()
                            mock_result.is_valid = True
                            mock_result.status = "valid"
                            mock_result.signer_identity = "test@example.com"
                            mock_result.issuer = None
                            mock_result.rekor_verified = False
                            mock_verif.verify.return_value = mock_result
                            mock_verif_class.return_value = mock_verif

                            result = runner.invoke(
                                cli,
                                [
                                    "artifact",
                                    "verify",
                                    "--registry",
                                    "oci://example.com/repo",
                                    "--tag",
                                    "v1.0.0",
                                    "--key",
                                    "cosign.pub",
                                ],
                            )

                            assert result.exit_code == 0, f"Failed: {result.output}"
                            assert "verified successfully" in result.output.lower()

    @pytest.mark.requirement("FR-010")
    def test_verify_key_based_with_kms_uri(self) -> None:
        """Test key-based verification with KMS URI."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.verification.check_cosign_available", return_value=True
        ):
            with patch("floe_core.oci.OCIClient") as mock_client_class:
                mock_client = MagicMock()
                mock_manifest = MagicMock()
                mock_manifest.annotations = {
                    "cosign.sigstore.dev/signature": "sig_data",
                }
                mock_client.inspect.return_value = mock_manifest
                mock_client._fetch_from_registry.return_value = (
                    b"content",
                    "sha256:abc123",
                )
                mock_client_class.from_registry_config.return_value = mock_client

                with patch(
                    "floe_core.schemas.signing.SignatureMetadata.from_annotations"
                ) as mock_from_annot:
                    mock_sig_metadata = MagicMock()
                    mock_from_annot.return_value = mock_sig_metadata

                    with patch(
                        "floe_core.oci.verification.VerificationClient"
                    ) as mock_verif_class:
                        mock_verif = MagicMock()
                        mock_result = MagicMock()
                        mock_result.is_valid = True
                        mock_result.status = "valid"
                        mock_result.signer_identity = "test@example.com"
                        mock_result.issuer = None
                        mock_result.rekor_verified = False
                        mock_verif.verify.return_value = mock_result
                        mock_verif_class.return_value = mock_verif

                        result = runner.invoke(
                            cli,
                            [
                                "artifact",
                                "verify",
                                "--registry",
                                "oci://example.com/repo",
                                "--tag",
                                "v1.0.0",
                                "--key",
                                "awskms://alias/my-signing-key",
                            ],
                        )

                        assert result.exit_code == 0, f"Failed: {result.output}"
                        assert "verified successfully" in result.output.lower()

    @pytest.mark.requirement("FR-010")
    def test_verify_key_based_cosign_not_available(self) -> None:
        """Test key-based verification fails when cosign is not available."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.verification.check_cosign_available", return_value=False
        ):
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--key",
                    "awskms://alias/my-signing-key",
                ],
            )

            assert result.exit_code == ExitCode.GENERAL_ERROR
            assert "cosign" in result.output.lower()

    @pytest.mark.requirement("FR-010")
    def test_verify_key_based_file_not_found(self) -> None:
        """Test key-based verification fails when key file not found."""
        runner = CliRunner()

        with patch(
            "floe_core.oci.verification.check_cosign_available", return_value=True
        ):
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--key",
                    "/nonexistent/path/to/key.pub",
                ],
            )

            assert result.exit_code == ExitCode.VALIDATION_ERROR
            # Error message mentions path validation
            assert (
                "path" in result.output.lower() or "directory" in result.output.lower()
            )


class TestArtifactVerifyUnsignedArtifact:
    """Tests for unsigned artifact handling.

    Task: T032
    Requirement: FR-009
    """

    @pytest.mark.requirement("FR-009")
    def test_verify_unsigned_artifact_with_annotations_but_no_metadata(self) -> None:
        """Test handling when annotations exist but no signature metadata."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            # Annotations exist but are not valid signature metadata
            mock_manifest.annotations = {"some": "annotation"}
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                # from_annotations returns None when annotations don't contain signature data
                mock_from_annot.return_value = None

                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "verify",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--issuer",
                        "https://token.actions.githubusercontent.com",
                        "--subject",
                        "repo:acme/floe:ref:refs/heads/main",
                        "--enforcement",
                        "enforce",
                    ],
                )

                assert result.exit_code == ExitCode.SIGNATURE_ERROR
                assert "not signed" in result.output.lower()


class TestArtifactVerifyEnforcement:
    """Tests for enforcement level handling.

    Task: T032
    Requirement: FR-011
    """

    @pytest.mark.requirement("FR-011")
    def test_verify_enforcement_enforce_unsigned(self) -> None:
        """Test enforce mode fails on unsigned artifact."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = None
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--issuer",
                    "https://token.actions.githubusercontent.com",
                    "--subject",
                    "repo:acme/floe:ref:refs/heads/main",
                    "--enforcement",
                    "enforce",
                ],
            )

            assert result.exit_code == ExitCode.SIGNATURE_ERROR
            assert "not signed" in result.output.lower()

    @pytest.mark.requirement("FR-011")
    def test_verify_enforcement_warn_unsigned(self) -> None:
        """Test warn mode warns on unsigned artifact."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = None
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--issuer",
                    "https://token.actions.githubusercontent.com",
                    "--subject",
                    "repo:acme/floe:ref:refs/heads/main",
                    "--enforcement",
                    "warn",
                ],
            )

            assert result.exit_code == 0
            assert "not signed" in result.output.lower()

    @pytest.mark.requirement("FR-011")
    def test_verify_enforcement_off_unsigned(self) -> None:
        """Test off mode ignores unsigned artifact."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = None
            mock_client.inspect.return_value = mock_manifest
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--issuer",
                    "https://token.actions.githubusercontent.com",
                    "--subject",
                    "repo:acme/floe:ref:refs/heads/main",
                    "--enforcement",
                    "off",
                ],
            )

            assert result.exit_code == 0

    @pytest.mark.requirement("FR-011")
    def test_verify_enforcement_enforce_invalid_signature(self) -> None:
        """Test enforce mode fails on invalid signature."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = False
                    mock_result.failure_reason = "Signature verification failed"
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                            "--enforcement",
                            "enforce",
                        ],
                    )

                    assert result.exit_code == ExitCode.SIGNATURE_ERROR
                    assert (
                        "invalid" in result.output.lower()
                        or "failed" in result.output.lower()
                    )

    @pytest.mark.requirement("FR-011")
    def test_verify_enforcement_warn_invalid_signature(self) -> None:
        """Test warn mode warns on invalid signature."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = False
                    mock_result.failure_reason = "Signature verification failed"
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                            "--enforcement",
                            "warn",
                        ],
                    )

                    assert result.exit_code == 0
                    assert (
                        "invalid" in result.output.lower()
                        or "failed" in result.output.lower()
                    )

    @pytest.mark.requirement("FR-011")
    def test_verify_enforcement_off_invalid_signature(self) -> None:
        """Test off mode ignores invalid signature."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = False
                    mock_result.failure_reason = "Signature verification failed"
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                            "--enforcement",
                            "off",
                        ],
                    )

                    assert result.exit_code == 0


class TestArtifactVerifyBundleExport:
    """Tests for verification bundle export.

    Task: T032
    Requirement: FR-015
    """

    @pytest.mark.requirement("FR-015")
    def test_verify_export_bundle_on_success(self) -> None:
        """Test that verification bundle is exported on successful verification."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            with patch("floe_core.oci.OCIClient") as mock_client_class:
                mock_client = MagicMock()
                mock_manifest = MagicMock()
                mock_manifest.annotations = {
                    "cosign.sigstore.dev/signature": "sig_data",
                    "cosign.sigstore.dev/certificate": "cert_data",
                }
                mock_client.inspect.return_value = mock_manifest
                mock_client._fetch_from_registry.return_value = (
                    b"content",
                    "sha256:abc123",
                )
                mock_client_class.from_registry_config.return_value = mock_client

                with patch(
                    "floe_core.schemas.signing.SignatureMetadata.from_annotations"
                ) as mock_from_annot:
                    mock_sig_metadata = MagicMock()
                    mock_from_annot.return_value = mock_sig_metadata

                    with patch(
                        "floe_core.oci.verification.VerificationClient"
                    ) as mock_verif_class:
                        mock_verif = MagicMock()
                        mock_result = MagicMock()
                        mock_result.is_valid = True
                        mock_result.status = "valid"
                        mock_result.signer_identity = "test@example.com"
                        mock_result.issuer = (
                            "https://token.actions.githubusercontent.com"
                        )
                        mock_result.rekor_verified = True
                        mock_verif.verify.return_value = mock_result
                        mock_verif_class.return_value = mock_verif

                        with patch(
                            "floe_core.oci.verification.export_verification_bundle"
                        ) as mock_export:
                            mock_bundle = MagicMock()
                            mock_bundle.model_dump_json.return_value = (
                                '{"version": "1.0"}'
                            )
                            mock_export.return_value = mock_bundle

                            result = runner.invoke(
                                cli,
                                [
                                    "artifact",
                                    "verify",
                                    "--registry",
                                    "oci://example.com/repo",
                                    "--tag",
                                    "v1.0.0",
                                    "--issuer",
                                    "https://token.actions.githubusercontent.com",
                                    "--subject",
                                    "repo:acme/floe:ref:refs/heads/main",
                                    "--export-bundle",
                                    "bundle.json",
                                ],
                            )

                            assert result.exit_code == 0, f"Failed: {result.output}"
                            assert Path("bundle.json").exists()
                            assert "bundle exported" in result.output.lower()


class TestArtifactVerifyBundleInfo:
    """Tests for verification bundle info display.

    Task: T032
    Requirement: FR-015
    """

    @pytest.mark.requirement("FR-015")
    def test_verify_bundle_info_valid_bundle(self) -> None:
        """Test displaying info from valid verification bundle."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            bundle_data = {
                "version": "1.0",
                "artifact_digest": "sha256:abc123",
                "created_at": "2024-01-27T00:00:00Z",
                "rekor_entry": {"uuid": "test-uuid"},
                "certificate_chain": [{"cert": "data1"}, {"cert": "data2"}],
            }
            Path("bundle.json").write_text(json.dumps(bundle_data))

            with patch(
                "floe_core.schemas.signing.VerificationBundle.model_validate"
            ) as mock_validate:
                mock_bundle = MagicMock()
                mock_bundle.artifact_digest = "sha256:abc123"
                mock_bundle.version = "1.0"
                mock_bundle.created_at.isoformat.return_value = "2024-01-27T00:00:00Z"
                mock_bundle.rekor_entry = {"uuid": "test-uuid"}
                mock_bundle.certificate_chain = [{"cert": "data1"}, {"cert": "data2"}]
                mock_validate.return_value = mock_bundle

                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "verify",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--bundle-info",
                        "bundle.json",
                    ],
                )

                assert result.exit_code == 0, f"Failed: {result.output}"
                assert "bundle" in result.output.lower()
                assert "sha256:abc123" in result.output

    @pytest.mark.requirement("FR-015")
    def test_verify_bundle_info_invalid_json(self) -> None:
        """Test bundle info fails with invalid JSON."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("bundle.json").write_text("not valid json {")

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--bundle-info",
                    "bundle.json",
                ],
            )

            assert result.exit_code == ExitCode.VALIDATION_ERROR
            assert "invalid" in result.output.lower() or "json" in result.output.lower()

    @pytest.mark.requirement("FR-015")
    def test_verify_bundle_info_validation_error(self) -> None:
        """Test bundle info fails when validation fails."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            bundle_data = {
                "version": "1.0",
                "artifact_digest": "sha256:abc123",
                "created_at": "2024-01-27T00:00:00Z",
                "rekor_entry": None,
                "certificate_chain": [],
            }
            Path("bundle.json").write_text(json.dumps(bundle_data))

            with patch(
                "floe_core.schemas.signing.VerificationBundle.model_validate"
            ) as mock_validate:
                # Simulate validation error
                mock_validate.side_effect = ValueError("Invalid bundle structure")

                result = runner.invoke(
                    cli,
                    [
                        "artifact",
                        "verify",
                        "--registry",
                        "oci://example.com/repo",
                        "--tag",
                        "v1.0.0",
                        "--bundle-info",
                        "bundle.json",
                    ],
                )

                assert result.exit_code == ExitCode.GENERAL_ERROR
                assert "failed" in result.output.lower()


class TestArtifactVerifyErrors:
    """Tests for error handling.

    Task: T032
    Requirement: FR-009
    """

    @pytest.mark.requirement("FR-009")
    def test_verify_handles_signature_verification_error(self) -> None:
        """Test handling of SignatureVerificationError."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    from floe_core.oci.errors import SignatureVerificationError

                    mock_verif = MagicMock()
                    mock_verif.verify.side_effect = SignatureVerificationError(
                        "oci://example.com/repo:v1.0.0", "Invalid signature"
                    )
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                        ],
                    )

                    assert result.exit_code == ExitCode.SIGNATURE_ERROR
                    assert "verification failed" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_handles_artifact_not_found_error(self) -> None:
        """Test handling of ArtifactNotFoundError."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            from floe_core.oci.errors import ArtifactNotFoundError

            mock_client = MagicMock()
            mock_client.inspect.side_effect = ArtifactNotFoundError(
                "example.com", "Artifact not found"
            )
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--issuer",
                    "https://token.actions.githubusercontent.com",
                    "--subject",
                    "repo:acme/floe:ref:refs/heads/main",
                ],
            )

            assert result.exit_code == ExitCode.VALIDATION_ERROR
            assert "not found" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_handles_authentication_error(self) -> None:
        """Test handling of AuthenticationError."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            from floe_core.oci.errors import AuthenticationError

            mock_client = MagicMock()
            mock_client.inspect.side_effect = AuthenticationError(
                "example.com", "Auth failed"
            )
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--issuer",
                    "https://token.actions.githubusercontent.com",
                    "--subject",
                    "repo:acme/floe:ref:refs/heads/main",
                ],
            )

            assert result.exit_code == ExitCode.GENERAL_ERROR
            assert "authentication" in result.output.lower()

    @pytest.mark.requirement("FR-009")
    def test_verify_handles_generic_error(self) -> None:
        """Test handling of generic exceptions."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.inspect.side_effect = RuntimeError("Unexpected error")
            mock_client_class.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "verify",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--issuer",
                    "https://token.actions.githubusercontent.com",
                    "--subject",
                    "repo:acme/floe:ref:refs/heads/main",
                ],
            )

            assert result.exit_code == ExitCode.GENERAL_ERROR


class TestArtifactVerifyRegistryConfig:
    """Tests for registry configuration building.

    Task: T032
    Requirement: FR-009
    """

    @pytest.mark.requirement("FR-009")
    def test_verify_builds_config_with_token_auth(self) -> None:
        """Test registry config with token authentication."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = True
                    mock_result.status = "valid"
                    mock_result.signer_identity = "test@example.com"
                    mock_result.issuer = "https://token.actions.githubusercontent.com"
                    mock_result.rekor_verified = True
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                        ],
                        env={"FLOE_REGISTRY_TOKEN": "test-token"},
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"

    @pytest.mark.requirement("FR-009")
    def test_verify_builds_config_with_basic_auth(self) -> None:
        """Test registry config with basic authentication."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = True
                    mock_result.status = "valid"
                    mock_result.signer_identity = "test@example.com"
                    mock_result.issuer = "https://token.actions.githubusercontent.com"
                    mock_result.rekor_verified = True
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                        ],
                        env={
                            "FLOE_REGISTRY_USERNAME": "testuser",
                            "FLOE_REGISTRY_PASSWORD": "testpass",
                        },
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"

    @pytest.mark.requirement("FR-009")
    def test_verify_builds_config_with_aws_irsa(self) -> None:
        """Test registry config with AWS IRSA authentication."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = True
                    mock_result.status = "valid"
                    mock_result.signer_identity = "test@example.com"
                    mock_result.issuer = "https://token.actions.githubusercontent.com"
                    mock_result.rekor_verified = True
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                        ],
                        env={"AWS_ROLE_ARN": "arn:aws:iam::123456789:role/test-role"},
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"

    @pytest.mark.requirement("FR-009")
    def test_verify_builds_config_with_anonymous_auth(self) -> None:
        """Test registry config with anonymous authentication."""
        runner = CliRunner()

        with patch("floe_core.oci.OCIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_manifest = MagicMock()
            mock_manifest.annotations = {
                "cosign.sigstore.dev/signature": "sig_data",
                "cosign.sigstore.dev/certificate": "cert_data",
            }
            mock_client.inspect.return_value = mock_manifest
            mock_client._fetch_from_registry.return_value = (
                b"content",
                "sha256:abc123",
            )
            mock_client_class.from_registry_config.return_value = mock_client

            with patch(
                "floe_core.schemas.signing.SignatureMetadata.from_annotations"
            ) as mock_from_annot:
                mock_sig_metadata = MagicMock()
                mock_from_annot.return_value = mock_sig_metadata

                with patch(
                    "floe_core.oci.verification.VerificationClient"
                ) as mock_verif_class:
                    mock_verif = MagicMock()
                    mock_result = MagicMock()
                    mock_result.is_valid = True
                    mock_result.status = "valid"
                    mock_result.signer_identity = "test@example.com"
                    mock_result.issuer = "https://token.actions.githubusercontent.com"
                    mock_result.rekor_verified = True
                    mock_verif.verify.return_value = mock_result
                    mock_verif_class.return_value = mock_verif

                    result = runner.invoke(
                        cli,
                        [
                            "artifact",
                            "verify",
                            "--registry",
                            "oci://example.com/repo",
                            "--tag",
                            "v1.0.0",
                            "--issuer",
                            "https://token.actions.githubusercontent.com",
                            "--subject",
                            "repo:acme/floe:ref:refs/heads/main",
                        ],
                    )

                    assert result.exit_code == 0, f"Failed: {result.output}"


__all__: list[str] = [
    "TestArtifactVerifyHelp",
    "TestArtifactVerifyValidation",
    "TestArtifactVerifyKeyless",
    "TestArtifactVerifyKeyBased",
    "TestArtifactVerifyUnsignedArtifact",
    "TestArtifactVerifyEnforcement",
    "TestArtifactVerifyBundleExport",
    "TestArtifactVerifyBundleInfo",
    "TestArtifactVerifyErrors",
    "TestArtifactVerifyRegistryConfig",
]
