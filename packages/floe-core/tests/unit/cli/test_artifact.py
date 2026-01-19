"""Unit tests for floe artifact push, pull, and inspect CLI commands.

Tests the artifact push/pull/inspect commands including argument parsing,
exit codes, and OCI operations.

Task: T020, T029, T034
Requirements: FR-026, FR-027, FR-028
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


class TestArtifactPushParser:
    """Tests for artifact push CLI argument parser."""

    @pytest.mark.requirement("8A-FR-026")
    def test_parser_requires_source(self) -> None:
        """Test that --source is required."""
        from floe_core.cli.artifact import create_push_parser

        parser = create_push_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--tag", "v1.0.0"])

    @pytest.mark.requirement("8A-FR-026")
    def test_parser_requires_tag(self) -> None:
        """Test that --tag is required."""
        from floe_core.cli.artifact import create_push_parser

        parser = create_push_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--source", "compiled_artifacts.json"])

    @pytest.mark.requirement("8A-FR-026")
    def test_parser_accepts_all_args(self) -> None:
        """Test that parser accepts all expected arguments."""
        from floe_core.cli.artifact import create_push_parser

        parser = create_push_parser()
        args = parser.parse_args(
            [
                "--source",
                "target/compiled_artifacts.json",
                "--tag",
                "v1.0.0",
                "--manifest",
                "manifest.yaml",
                "--verbose",
                "--quiet",
            ]
        )

        assert args.source == Path("target/compiled_artifacts.json")
        assert args.tag == "v1.0.0"
        assert args.manifest == Path("manifest.yaml")
        assert args.verbose is True
        assert args.quiet is True

    @pytest.mark.requirement("8A-FR-026")
    def test_parser_default_manifest_path(self) -> None:
        """Test that manifest defaults to manifest.yaml."""
        from floe_core.cli.artifact import create_push_parser

        parser = create_push_parser()
        args = parser.parse_args(
            [
                "--source",
                "compiled_artifacts.json",
                "--tag",
                "v1.0.0",
            ]
        )

        assert args.manifest == Path("manifest.yaml")


class TestArtifactPushCommand:
    """Tests for artifact push command execution."""

    @pytest.mark.requirement("8A-FR-026")
    def test_push_success_returns_zero(self, tmp_path: Path) -> None:
        """Test successful push returns exit code 0."""
        from floe_core.cli.artifact import run_push

        # Create mock artifacts file
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text('{"version": "0.2.0"}')

        # Create mock manifest file
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        # Create args namespace
        import argparse

        args = argparse.Namespace(
            source=artifacts_path,
            tag="v1.0.0",
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        # Mock CompiledArtifacts.from_json_file and OCIClient
        # Use full paths since imports are inside run_push function
        mock_artifacts = MagicMock()

        with (
            patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file"
            ) as mock_from_json,
            patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest,
        ):
            mock_from_json.return_value = mock_artifacts
            mock_client = MagicMock()
            mock_client.push.return_value = "sha256:abc123"
            mock_from_manifest.return_value = mock_client

            exit_code = run_push(args)

        assert exit_code == 0
        mock_client.push.assert_called_once_with(mock_artifacts, tag="v1.0.0")

    @pytest.mark.requirement("8A-FR-026")
    def test_push_authentication_error_returns_two(self, tmp_path: Path) -> None:
        """Test authentication error returns exit code 2."""
        from floe_core.cli.artifact import run_push
        from floe_core.oci.errors import AuthenticationError

        # Create mock files
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text('{"version": "0.2.0"}')

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            source=artifacts_path,
            tag="v1.0.0",
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        mock_artifacts = MagicMock()

        with (
            patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file"
            ) as mock_from_json,
            patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest,
        ):
            mock_from_json.return_value = mock_artifacts
            mock_client = MagicMock()
            mock_client.push.side_effect = AuthenticationError(
                "harbor.example.com", "Invalid credentials"
            )
            mock_from_manifest.return_value = mock_client

            exit_code = run_push(args)

        assert exit_code == 2

    @pytest.mark.requirement("8A-FR-026")
    def test_push_immutability_error_returns_four(self, tmp_path: Path) -> None:
        """Test immutability violation returns exit code 4."""
        from floe_core.cli.artifact import run_push
        from floe_core.oci.errors import ImmutabilityViolationError

        # Create mock files
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text('{"version": "0.2.0"}')

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            source=artifacts_path,
            tag="v1.0.0",
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        mock_artifacts = MagicMock()

        with (
            patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file"
            ) as mock_from_json,
            patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest,
        ):
            mock_from_json.return_value = mock_artifacts
            mock_client = MagicMock()
            mock_client.push.side_effect = ImmutabilityViolationError(
                tag="v1.0.0", registry="harbor.example.com"
            )
            mock_from_manifest.return_value = mock_client

            exit_code = run_push(args)

        assert exit_code == 4

    @pytest.mark.requirement("8A-FR-026")
    def test_push_general_error_returns_one(self, tmp_path: Path) -> None:
        """Test general error returns exit code 1."""
        from floe_core.cli.artifact import run_push
        from floe_core.oci.errors import OCIError

        # Create mock files
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text('{"version": "0.2.0"}')

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            source=artifacts_path,
            tag="v1.0.0",
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        mock_artifacts = MagicMock()

        with (
            patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file"
            ) as mock_from_json,
            patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest,
        ):
            mock_from_json.return_value = mock_artifacts
            mock_client = MagicMock()
            mock_client.push.side_effect = OCIError("Network failure")
            mock_from_manifest.return_value = mock_client

            exit_code = run_push(args)

        assert exit_code == 1

    @pytest.mark.requirement("8A-FR-026")
    def test_push_source_not_found_returns_one(self, tmp_path: Path) -> None:
        """Test missing source file returns exit code 1."""
        import argparse

        from floe_core.cli.artifact import run_push

        args = argparse.Namespace(
            source=tmp_path / "nonexistent.json",
            tag="v1.0.0",
            manifest=tmp_path / "manifest.yaml",
            verbose=False,
            quiet=True,
        )

        exit_code = run_push(args)

        assert exit_code == 1


class TestArtifactPullParser:
    """Tests for artifact pull CLI argument parser.

    Task: T029
    Requirements: FR-027
    """

    @pytest.mark.requirement("8A-FR-027")
    def test_parser_requires_tag(self) -> None:
        """Test that --tag is required."""
        from floe_core.cli.artifact import create_pull_parser

        parser = create_pull_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--output", "artifacts/"])

    @pytest.mark.requirement("8A-FR-027")
    def test_parser_requires_output(self) -> None:
        """Test that --output is required."""
        from floe_core.cli.artifact import create_pull_parser

        parser = create_pull_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--tag", "v1.0.0"])

    @pytest.mark.requirement("8A-FR-027")
    def test_parser_accepts_all_args(self) -> None:
        """Test that parser accepts all expected arguments."""
        from floe_core.cli.artifact import create_pull_parser

        parser = create_pull_parser()
        args = parser.parse_args(
            [
                "--tag",
                "v1.0.0",
                "--output",
                "./artifacts/",
                "--manifest",
                "manifest.yaml",
                "--verbose",
                "--quiet",
            ]
        )

        assert args.tag == "v1.0.0"
        assert args.output == Path("./artifacts/")
        assert args.manifest == Path("manifest.yaml")
        assert args.verbose is True
        assert args.quiet is True

    @pytest.mark.requirement("8A-FR-027")
    def test_parser_default_manifest_path(self) -> None:
        """Test that manifest defaults to manifest.yaml."""
        from floe_core.cli.artifact import create_pull_parser

        parser = create_pull_parser()
        args = parser.parse_args(
            [
                "--tag",
                "v1.0.0",
                "--output",
                "artifacts/",
            ]
        )

        assert args.manifest == Path("manifest.yaml")


class TestArtifactPullCommand:
    """Tests for artifact pull command execution.

    Task: T029
    Requirements: FR-027
    """

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_success_returns_zero(self, tmp_path: Path) -> None:
        """Test successful pull returns exit code 0."""
        from floe_core.cli.artifact import run_pull

        # Create output directory
        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        # Create mock manifest file
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        # Create args namespace
        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=output_dir,
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        # Mock OCIClient
        mock_artifacts = MagicMock()
        mock_artifacts.to_json_file = MagicMock()

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.pull.return_value = mock_artifacts
            mock_from_manifest.return_value = mock_client

            exit_code = run_pull(args)

        assert exit_code == 0
        mock_client.pull.assert_called_once_with(tag="v1.0.0")
        # Verify the output path is correct (not just that it was called)
        expected_path = output_dir / "compiled_artifacts.json"
        mock_artifacts.to_json_file.assert_called_once_with(expected_path)

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_not_found_returns_three(self, tmp_path: Path) -> None:
        """Test artifact not found returns exit code 3."""
        from floe_core.cli.artifact import run_pull
        from floe_core.oci.errors import ArtifactNotFoundError

        # Create output directory
        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        # Create mock manifest file
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=output_dir,
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.pull.side_effect = ArtifactNotFoundError(
                tag="v1.0.0", registry="harbor.example.com"
            )
            mock_from_manifest.return_value = mock_client

            exit_code = run_pull(args)

        assert exit_code == 3

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_authentication_error_returns_two(self, tmp_path: Path) -> None:
        """Test authentication error returns exit code 2."""
        from floe_core.cli.artifact import run_pull
        from floe_core.oci.errors import AuthenticationError

        # Create output directory
        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=output_dir,
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.pull.side_effect = AuthenticationError(
                "harbor.example.com", "Invalid credentials"
            )
            mock_from_manifest.return_value = mock_client

            exit_code = run_pull(args)

        assert exit_code == 2

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_general_error_returns_one(self, tmp_path: Path) -> None:
        """Test general error returns exit code 1."""
        from floe_core.cli.artifact import run_pull
        from floe_core.oci.errors import OCIError

        # Create output directory
        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=output_dir,
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.pull.side_effect = OCIError("Network failure")
            mock_from_manifest.return_value = mock_client

            exit_code = run_pull(args)

        assert exit_code == 1

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_output_dir_not_found_returns_one(self, tmp_path: Path) -> None:
        """Test missing output directory returns exit code 1."""
        from floe_core.cli.artifact import run_pull

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=tmp_path / "nonexistent_dir",
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        exit_code = run_pull(args)

        assert exit_code == 1


class TestArtifactInspectParser:
    """Tests for artifact inspect CLI argument parser.

    Task: T034
    Requirements: FR-028
    """

    @pytest.mark.requirement("8A-FR-028")
    def test_parser_requires_tag(self) -> None:
        """Test that --tag is required."""
        from floe_core.cli.artifact import create_inspect_parser

        parser = create_inspect_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    @pytest.mark.requirement("8A-FR-028")
    def test_parser_accepts_all_args(self) -> None:
        """Test that parser accepts all expected arguments."""
        from floe_core.cli.artifact import create_inspect_parser

        parser = create_inspect_parser()
        args = parser.parse_args(
            [
                "--tag",
                "v1.0.0",
                "--manifest",
                "manifest.yaml",
                "--json",
                "--verbose",
                "--quiet",
            ]
        )

        assert args.tag == "v1.0.0"
        assert args.manifest == Path("manifest.yaml")
        assert args.json_output is True
        assert args.verbose is True
        assert args.quiet is True

    @pytest.mark.requirement("8A-FR-028")
    def test_parser_default_manifest_path(self) -> None:
        """Test that manifest defaults to manifest.yaml."""
        from floe_core.cli.artifact import create_inspect_parser

        parser = create_inspect_parser()
        args = parser.parse_args(["--tag", "v1.0.0"])

        assert args.manifest == Path("manifest.yaml")

    @pytest.mark.requirement("8A-FR-028")
    def test_parser_json_flag_defaults_false(self) -> None:
        """Test that --json flag defaults to False."""
        from floe_core.cli.artifact import create_inspect_parser

        parser = create_inspect_parser()
        args = parser.parse_args(["--tag", "v1.0.0"])

        assert args.json_output is False


class TestArtifactInspectCommand:
    """Tests for artifact inspect command execution.

    Task: T034
    Requirements: FR-028
    """

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_success_returns_zero(self, tmp_path: Path) -> None:
        """Test successful inspect returns exit code 0."""
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_inspect
        from floe_core.schemas.oci import ArtifactLayer, ArtifactManifest, SignatureStatus

        # Create mock manifest file
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        # Create mock artifact manifest
        mock_manifest = ArtifactManifest(
            digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
            artifact_type="application/vnd.floe.compiled-artifacts.v1+json",
            size=12345,
            created_at=datetime.now(timezone.utc),
            annotations={
                "io.floe.product.name": "test-product",
                "io.floe.product.version": "1.0.0",
            },
            layers=[
                ArtifactLayer(
                    digest="sha256:def456789012345678901234567890123456789012345678901234567890abcd",
                    media_type="application/vnd.floe.compiled-artifacts.v1+json",
                    size=12345,
                    annotations={},
                )
            ],
            signature_status=SignatureStatus.UNSIGNED,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 0
        mock_client.inspect.assert_called_once_with(tag="v1.0.0")

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_not_found_returns_three(self, tmp_path: Path) -> None:
        """Test artifact not found returns exit code 3."""
        from floe_core.cli.artifact import run_inspect
        from floe_core.oci.errors import ArtifactNotFoundError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.side_effect = ArtifactNotFoundError(
                tag="v1.0.0", registry="harbor.example.com"
            )
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 3

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_authentication_error_returns_two(self, tmp_path: Path) -> None:
        """Test authentication error returns exit code 2."""
        from floe_core.cli.artifact import run_inspect
        from floe_core.oci.errors import AuthenticationError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.side_effect = AuthenticationError(
                "harbor.example.com", "Invalid credentials"
            )
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 2

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_general_error_returns_one(self, tmp_path: Path) -> None:
        """Test general error returns exit code 1."""
        from floe_core.cli.artifact import run_inspect
        from floe_core.oci.errors import OCIError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.side_effect = OCIError("Network failure")
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 1

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test inspect --json outputs valid JSON."""
        import json
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_inspect
        from floe_core.schemas.oci import ArtifactLayer, ArtifactManifest, SignatureStatus

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=True,
            verbose=False,
            quiet=True,
        )

        mock_manifest = ArtifactManifest(
            digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
            artifact_type="application/vnd.floe.compiled-artifacts.v1+json",
            size=12345,
            created_at=datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc),
            annotations={
                "io.floe.product.name": "test-product",
                "io.floe.product.version": "1.0.0",
            },
            layers=[
                ArtifactLayer(
                    digest="sha256:def456789012345678901234567890123456789012345678901234567890abcd",
                    media_type="application/vnd.floe.compiled-artifacts.v1+json",
                    size=12345,
                    annotations={},
                )
            ],
            signature_status=SignatureStatus.UNSIGNED,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 0

        # Verify JSON output is valid
        captured = capsys.readouterr()
        output_data = json.loads(captured.out)

        assert output_data["digest"] == mock_manifest.digest
        assert output_data["artifact_type"] == mock_manifest.artifact_type
        assert output_data["size"] == mock_manifest.size
        assert output_data["product_name"] == "test-product"
        assert output_data["signature_status"] == "unsigned"


class TestArtifactListParser:
    """Tests for artifact list CLI argument parser.

    Task: T039
    Requirements: FR-029
    """

    @pytest.mark.requirement("8A-FR-029")
    def test_parser_accepts_filter(self) -> None:
        """Test that --filter is optional."""
        from floe_core.cli.artifact import create_list_parser

        parser = create_list_parser()
        args = parser.parse_args(["--filter", "v1.*"])

        assert args.filter == "v1.*"

    @pytest.mark.requirement("8A-FR-029")
    def test_parser_accepts_all_args(self) -> None:
        """Test that parser accepts all expected arguments."""
        from floe_core.cli.artifact import create_list_parser

        parser = create_list_parser()
        args = parser.parse_args(
            [
                "--filter",
                "v1.*",
                "--manifest",
                "manifest.yaml",
                "--json",
                "--verbose",
                "--quiet",
            ]
        )

        assert args.filter == "v1.*"
        assert args.manifest == Path("manifest.yaml")
        assert args.json_output is True
        assert args.verbose is True
        assert args.quiet is True

    @pytest.mark.requirement("8A-FR-029")
    def test_parser_default_values(self) -> None:
        """Test that defaults are set correctly."""
        from floe_core.cli.artifact import create_list_parser

        parser = create_list_parser()
        args = parser.parse_args([])

        assert args.filter is None
        assert args.manifest == Path("manifest.yaml")
        assert args.json_output is False
        assert args.verbose is False
        assert args.quiet is False


class TestArtifactListCommand:
    """Tests for artifact list command execution.

    Task: T039
    Requirements: FR-029
    """

    @pytest.mark.requirement("8A-FR-029")
    def test_list_success_returns_zero(self, tmp_path: Path) -> None:
        """Test successful list returns exit code 0."""
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_list
        from floe_core.schemas.oci import ArtifactTag

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter=None,
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        # Create mock tags
        mock_tags = [
            ArtifactTag(
                name="v1.0.0",
                digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
                created_at=datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc),
                size=12345,
            ),
            ArtifactTag(
                name="v1.1.0",
                digest="sha256:def456789012345678901234567890123456789012345678901234567890abcd",
                created_at=datetime(2026, 1, 18, 10, 0, 0, tzinfo=timezone.utc),
                size=11000,
            ),
        ]

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.list.return_value = mock_tags
            mock_from_manifest.return_value = mock_client

            exit_code = run_list(args)

        assert exit_code == 0
        mock_client.list.assert_called_once_with(filter_pattern=None)

    @pytest.mark.requirement("8A-FR-029")
    def test_list_with_filter(self, tmp_path: Path) -> None:
        """Test list with filter pattern."""
        from floe_core.cli.artifact import run_list

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter="v1.*",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.list.return_value = []
            mock_from_manifest.return_value = mock_client

            exit_code = run_list(args)

        assert exit_code == 0
        mock_client.list.assert_called_once_with(filter_pattern="v1.*")

    @pytest.mark.requirement("8A-FR-029")
    def test_list_authentication_error_returns_two(self, tmp_path: Path) -> None:
        """Test authentication error returns exit code 2."""
        from floe_core.cli.artifact import run_list
        from floe_core.oci.errors import AuthenticationError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter=None,
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.list.side_effect = AuthenticationError(
                "harbor.example.com", "Invalid credentials"
            )
            mock_from_manifest.return_value = mock_client

            exit_code = run_list(args)

        assert exit_code == 2

    @pytest.mark.requirement("8A-FR-029")
    def test_list_general_error_returns_one(self, tmp_path: Path) -> None:
        """Test general error returns exit code 1."""
        from floe_core.cli.artifact import run_list
        from floe_core.oci.errors import OCIError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter=None,
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.list.side_effect = OCIError("Network failure")
            mock_from_manifest.return_value = mock_client

            exit_code = run_list(args)

        assert exit_code == 1

    @pytest.mark.requirement("8A-FR-029")
    def test_list_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test list --json outputs valid JSON array."""
        import json
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_list
        from floe_core.schemas.oci import ArtifactTag

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter=None,
            manifest=manifest_path,
            json_output=True,
            verbose=False,
            quiet=True,
        )

        mock_tags = [
            ArtifactTag(
                name="v1.0.0",
                digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
                created_at=datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc),
                size=12345,
            ),
        ]

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.list.return_value = mock_tags
            mock_from_manifest.return_value = mock_client

            exit_code = run_list(args)

        assert exit_code == 0

        # Verify JSON output is valid
        captured = capsys.readouterr()
        output_data = json.loads(captured.out)

        assert isinstance(output_data, list)
        assert len(output_data) == 1
        assert output_data[0]["name"] == "v1.0.0"
        expected_digest = "sha256:abc123def456789012345678901234567890123456789012345678901234abcd"
        assert output_data[0]["digest"] == expected_digest
        assert output_data[0]["size"] == 12345


class TestCacheStatusParser:
    """Tests for artifact cache status CLI argument parser."""

    @pytest.mark.requirement("8A-FR-030")
    def test_parser_default_values(self) -> None:
        """Test that parser has correct default values."""
        from floe_core.cli.artifact import create_cache_status_parser

        parser = create_cache_status_parser()
        args = parser.parse_args([])

        assert args.manifest == Path("manifest.yaml")
        assert args.verbose is False
        assert args.quiet is False
        assert args.json is False

    @pytest.mark.requirement("8A-FR-030")
    def test_parser_accepts_all_args(self) -> None:
        """Test that parser accepts all expected arguments."""
        from floe_core.cli.artifact import create_cache_status_parser

        parser = create_cache_status_parser()
        args = parser.parse_args(
            [
                "--manifest",
                "custom_manifest.yaml",
                "--verbose",
                "--json",
            ]
        )

        assert args.manifest == Path("custom_manifest.yaml")
        assert args.verbose is True
        assert args.json is True


class TestCacheStatusCommand:
    """Tests for artifact cache status command execution."""

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_status_returns_success(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that cache status returns success with valid cache."""
        import argparse

        from floe_core.cli.artifact import run_cache_status

        # Create a mock manifest with cache config
        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        args = argparse.Namespace(
            manifest=manifest_path,
            verbose=False,
            quiet=False,
            json=False,
        )

        exit_code = run_cache_status(args)

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Cache Path:" in captured.out
        assert "Total Size:" in captured.out
        assert "Entries:" in captured.out

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_status_json_output(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that cache status returns valid JSON output."""
        import argparse
        import json as json_module

        from floe_core.cli.artifact import run_cache_status

        # Create a mock manifest with cache config
        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 5
    ttl_hours: 12
""")

        args = argparse.Namespace(
            manifest=manifest_path,
            verbose=False,
            quiet=False,
            json=True,
        )

        # Mock the logger to prevent stdout pollution
        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_status(args)

        assert exit_code == 0

        captured = capsys.readouterr()
        output = json_module.loads(captured.out)

        assert "path" in output
        assert "entry_count" in output
        assert "total_size_bytes" in output
        assert "max_size_gb" in output
        assert output["max_size_gb"] == 5
        assert output["ttl_hours"] == 12

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_status_quiet_mode(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that cache status respects quiet mode."""
        import argparse

        from floe_core.cli.artifact import run_cache_status

        args = argparse.Namespace(
            manifest=tmp_path / "nonexistent.yaml",
            verbose=False,
            quiet=True,
            json=False,
        )

        # Mock the logger to prevent stdout pollution
        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_status(args)

        assert exit_code == 0

        captured = capsys.readouterr()
        assert captured.out == ""  # No output in quiet mode


class TestCacheClearParser:
    """Tests for artifact cache clear CLI argument parser."""

    @pytest.mark.requirement("8A-FR-030")
    def test_parser_default_values(self) -> None:
        """Test that parser has correct default values."""
        from floe_core.cli.artifact import create_cache_clear_parser

        parser = create_cache_clear_parser()
        args = parser.parse_args([])

        assert args.manifest == Path("manifest.yaml")
        assert args.tag is None
        assert args.yes is False
        assert args.verbose is False
        assert args.quiet is False

    @pytest.mark.requirement("8A-FR-030")
    def test_parser_accepts_all_args(self) -> None:
        """Test that parser accepts all expected arguments."""
        from floe_core.cli.artifact import create_cache_clear_parser

        parser = create_cache_clear_parser()
        args = parser.parse_args(
            [
                "--manifest",
                "custom_manifest.yaml",
                "--tag",
                "v1.0.0",
                "--yes",
                "--verbose",
            ]
        )

        assert args.manifest == Path("custom_manifest.yaml")
        assert args.tag == "v1.0.0"
        assert args.yes is True
        assert args.verbose is True


class TestCacheClearCommand:
    """Tests for artifact cache clear command execution."""

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_all_returns_success(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that cache clear all returns success."""
        import argparse
        import hashlib

        from floe_core.cli.artifact import run_cache_clear
        from floe_core.oci.cache import CacheManager
        from floe_core.schemas.oci import CacheConfig

        # Create a manifest with cache config
        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        # Pre-populate the cache with an entry
        config = CacheConfig(path=cache_path, max_size_gb=10, ttl_hours=24)
        manager = CacheManager(config)
        content = b'{"version": "0.2.0", "test": "clear"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        args = argparse.Namespace(
            manifest=manifest_path,
            tag=None,
            yes=True,  # Skip confirmation
            verbose=False,
            quiet=False,
        )

        # Mock the logger to prevent stdout pollution
        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_clear(args)

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Cleared" in captured.out
        assert "1 cached artifact(s)" in captured.out

        # Verify cache is empty
        new_stats = manager.stats()
        assert new_stats["entry_count"] == 0

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_by_tag(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that cache clear with --tag only clears matching entries."""
        import argparse
        import hashlib

        from floe_core.cli.artifact import run_cache_clear
        from floe_core.oci.cache import CacheManager
        from floe_core.schemas.oci import CacheConfig

        # Create a manifest with cache config
        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        # Pre-populate the cache with two entries
        config = CacheConfig(path=cache_path, max_size_gb=10, ttl_hours=24)
        manager = CacheManager(config)

        content1 = b'{"version": "1.0.0"}'
        digest1 = f"sha256:{hashlib.sha256(content1).hexdigest()}"
        manager.put(
            digest=digest1,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content1,
        )

        content2 = b'{"version": "2.0.0"}'
        digest2 = f"sha256:{hashlib.sha256(content2).hexdigest()}"
        manager.put(
            digest=digest2,
            tag="v2.0.0",
            registry="oci://harbor.example.com/floe",
            content=content2,
        )

        # Verify both entries exist
        assert manager.stats()["entry_count"] == 2

        args = argparse.Namespace(
            manifest=manifest_path,
            tag="v1.0.0",  # Only clear v1.0.0
            yes=True,
            verbose=False,
            quiet=False,
        )

        # Mock the logger to prevent stdout pollution
        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_clear(args)

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "v1.0.0" in captured.out

        # Verify only v2.0.0 remains
        new_stats = manager.stats()
        assert new_stats["entry_count"] == 1

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_empty_cache(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that cache clear on empty cache returns success."""
        import argparse

        from floe_core.cli.artifact import run_cache_clear

        # Create a manifest with cache config
        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        args = argparse.Namespace(
            manifest=manifest_path,
            tag=None,
            yes=True,
            verbose=False,
            quiet=False,
        )

        # Mock the logger to prevent stdout pollution
        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_clear(args)

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Cache is empty" in captured.out

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_not_configured(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that cache clear returns success when cache is not configured."""
        import argparse

        from floe_core.cli.artifact import run_cache_clear

        args = argparse.Namespace(
            manifest=tmp_path / "nonexistent.yaml",
            tag=None,
            yes=True,
            verbose=False,
            quiet=False,
        )

        # Mock the logger to prevent stdout pollution
        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_clear(args)

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Cache not configured" in captured.out


class TestHelperFunctions:
    """Tests for helper functions in artifact module."""

    @pytest.mark.requirement("8A-FR-028")
    def test_format_size_bytes(self) -> None:
        """Test _format_size with bytes."""
        from floe_core.cli.artifact import _format_size

        assert _format_size(0) == "0 B"
        assert _format_size(500) == "500 B"
        assert _format_size(1023) == "1023 B"

    @pytest.mark.requirement("8A-FR-028")
    def test_format_size_kilobytes(self) -> None:
        """Test _format_size with kilobytes."""
        from floe_core.cli.artifact import _format_size

        assert _format_size(1024) == "1.0 KB"
        assert _format_size(1536) == "1.5 KB"
        assert _format_size(1024 * 100) == "100.0 KB"

    @pytest.mark.requirement("8A-FR-028")
    def test_format_size_megabytes(self) -> None:
        """Test _format_size with megabytes."""
        from floe_core.cli.artifact import _format_size

        assert _format_size(1024 * 1024) == "1.0 MB"
        assert _format_size(1024 * 1024 * 5) == "5.0 MB"
        assert _format_size(int(1024 * 1024 * 2.5)) == "2.5 MB"

    @pytest.mark.requirement("8A-FR-028")
    def test_format_size_gigabytes(self) -> None:
        """Test _format_size with gigabytes."""
        from floe_core.cli.artifact import _format_size

        assert _format_size(1024 * 1024 * 1024) == "1.0 GB"
        assert _format_size(1024 * 1024 * 1024 * 2) == "2.0 GB"

    @pytest.mark.requirement("8A-FR-029")
    def test_format_date(self) -> None:
        """Test _format_date function."""
        from datetime import datetime, timezone

        from floe_core.cli.artifact import _format_date

        dt = datetime(2026, 1, 19, 10, 30, 0, tzinfo=timezone.utc)
        assert _format_date(dt) == "2026-01-19"

    @pytest.mark.requirement("8A-FR-029")
    def test_truncate_digest_short(self) -> None:
        """Test _truncate_digest with short digest."""
        from floe_core.cli.artifact import _truncate_digest

        assert _truncate_digest("sha256:abc", 15) == "sha256:abc"
        assert _truncate_digest("short", 10) == "short"

    @pytest.mark.requirement("8A-FR-029")
    def test_truncate_digest_long(self) -> None:
        """Test _truncate_digest with long digest."""
        from floe_core.cli.artifact import _truncate_digest

        long_digest = "sha256:abc123def456789012345678901234567890"
        # 15 chars: s,h,a,2,5,6,:,a,b,c,1,2,3,d,e = "sha256:abc123de"
        assert _truncate_digest(long_digest, 15) == "sha256:abc123de..."
        # 20 chars: s,h,a,2,5,6,:,a,b,c,1,2,3,d,e,f,4,5,6,7 = "sha256:abc123def4567"
        assert _truncate_digest(long_digest, 20) == "sha256:abc123def4567..."


class TestCircuitBreakerErrors:
    """Tests for CircuitBreakerOpenError handling in CLI commands."""

    @pytest.mark.requirement("8A-FR-026")
    def test_push_circuit_breaker_error_returns_five(self, tmp_path: Path) -> None:
        """Test circuit breaker error returns exit code 5."""
        from floe_core.cli.artifact import run_push
        from floe_core.oci.errors import CircuitBreakerOpenError

        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text('{"version": "0.2.0"}')

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            source=artifacts_path,
            tag="v1.0.0",
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        mock_artifacts = MagicMock()

        with (
            patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file"
            ) as mock_from_json,
            patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest,
        ):
            mock_from_json.return_value = mock_artifacts
            mock_client = MagicMock()
            mock_client.push.side_effect = CircuitBreakerOpenError("harbor.example.com", 60)
            mock_from_manifest.return_value = mock_client

            exit_code = run_push(args)

        assert exit_code == 5

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_circuit_breaker_error_returns_five(self, tmp_path: Path) -> None:
        """Test circuit breaker error returns exit code 5."""
        from floe_core.cli.artifact import run_pull
        from floe_core.oci.errors import CircuitBreakerOpenError

        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=output_dir,
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.pull.side_effect = CircuitBreakerOpenError("harbor.example.com", 60)
            mock_from_manifest.return_value = mock_client

            exit_code = run_pull(args)

        assert exit_code == 5

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_circuit_breaker_error_returns_five(self, tmp_path: Path) -> None:
        """Test circuit breaker error returns exit code 5."""
        from floe_core.cli.artifact import run_inspect
        from floe_core.oci.errors import CircuitBreakerOpenError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.side_effect = CircuitBreakerOpenError("harbor.example.com", 60)
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 5

    @pytest.mark.requirement("8A-FR-029")
    def test_list_circuit_breaker_error_returns_five(self, tmp_path: Path) -> None:
        """Test circuit breaker error returns exit code 5."""
        from floe_core.cli.artifact import run_list
        from floe_core.oci.errors import CircuitBreakerOpenError

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter=None,
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.list.side_effect = CircuitBreakerOpenError("harbor.example.com", 60)
            mock_from_manifest.return_value = mock_client

            exit_code = run_list(args)

        assert exit_code == 5


class TestUnexpectedExceptions:
    """Tests for unexpected exception handling in CLI commands."""

    @pytest.mark.requirement("8A-FR-026")
    def test_push_unexpected_exception_returns_one(self, tmp_path: Path) -> None:
        """Test unexpected exception returns exit code 1."""
        from floe_core.cli.artifact import run_push

        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text('{"version": "0.2.0"}')

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            source=artifacts_path,
            tag="v1.0.0",
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        with (
            patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file"
            ) as mock_from_json,
        ):
            mock_from_json.side_effect = RuntimeError("Unexpected error")

            exit_code = run_push(args)

        assert exit_code == 1

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_unexpected_exception_returns_one(self, tmp_path: Path) -> None:
        """Test unexpected exception returns exit code 1."""
        from floe_core.cli.artifact import run_pull

        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=output_dir,
            manifest=manifest_path,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_from_manifest.side_effect = RuntimeError("Unexpected error")

            exit_code = run_pull(args)

        assert exit_code == 1

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_unexpected_exception_returns_one(self, tmp_path: Path) -> None:
        """Test unexpected exception returns exit code 1."""
        from floe_core.cli.artifact import run_inspect

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_from_manifest.side_effect = RuntimeError("Unexpected error")

            exit_code = run_inspect(args)

        assert exit_code == 1

    @pytest.mark.requirement("8A-FR-029")
    def test_list_unexpected_exception_returns_one(self, tmp_path: Path) -> None:
        """Test unexpected exception returns exit code 1."""
        from floe_core.cli.artifact import run_list

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter=None,
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=True,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_from_manifest.side_effect = RuntimeError("Unexpected error")

            exit_code = run_list(args)

        assert exit_code == 1


class TestVerboseMode:
    """Tests for verbose mode output in CLI commands."""

    @pytest.mark.requirement("8A-FR-026")
    def test_push_verbose_mode(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test push command verbose mode outputs additional info."""
        from floe_core.cli.artifact import run_push

        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts_path.write_text('{"version": "0.2.0"}')

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            source=artifacts_path,
            tag="v1.0.0",
            manifest=manifest_path,
            verbose=True,
            quiet=False,
        )

        mock_artifacts = MagicMock()
        mock_artifacts.metadata.product_name = "test-product"
        mock_artifacts.metadata.product_version = "1.0.0"

        with (
            patch(
                "floe_core.schemas.compiled_artifacts.CompiledArtifacts.from_json_file"
            ) as mock_from_json,
            patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest,
        ):
            mock_from_json.return_value = mock_artifacts
            mock_client = MagicMock()
            mock_client.push.return_value = "sha256:abc123"
            mock_client.registry_uri = "oci://harbor.example.com/floe"
            mock_from_manifest.return_value = mock_client

            exit_code = run_push(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Pushed artifact with digest: sha256:abc123" in captured.out

    @pytest.mark.requirement("8A-FR-027")
    def test_pull_verbose_mode(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test pull command verbose mode outputs additional info."""
        from floe_core.cli.artifact import run_pull

        output_dir = tmp_path / "artifacts"
        output_dir.mkdir()

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            output=output_dir,
            manifest=manifest_path,
            verbose=True,
            quiet=False,
        )

        mock_artifacts = MagicMock()
        mock_artifacts.to_json_file = MagicMock()

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.pull.return_value = mock_artifacts
            mock_client.registry_uri = "oci://harbor.example.com/floe"
            mock_from_manifest.return_value = mock_client

            exit_code = run_pull(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Pulled artifact to:" in captured.out

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_verbose_mode_shows_layers(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test inspect command verbose mode shows layer details."""
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_inspect
        from floe_core.schemas.oci import ArtifactLayer, ArtifactManifest, SignatureStatus

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=True,
            quiet=False,
        )

        mock_manifest = ArtifactManifest(
            digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
            artifact_type="application/vnd.floe.compiled-artifacts.v1+json",
            size=12345,
            created_at=datetime.now(timezone.utc),
            annotations={},
            layers=[
                ArtifactLayer(
                    digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
                    media_type="application/vnd.floe.compiled-artifacts.v1+json",
                    size=5000,
                    annotations={},
                ),
                ArtifactLayer(
                    digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
                    media_type="application/vnd.floe.compiled-artifacts.v1+json",
                    size=7345,
                    annotations={},
                ),
            ],
            signature_status=SignatureStatus.UNSIGNED,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_client.registry_uri = "oci://harbor.example.com/floe"
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        # Verbose mode should show layers
        assert "Layers (2):" in captured.out

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_status_verbose_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test cache status command verbose mode shows additional info."""
        import argparse

        from floe_core.cli.artifact import run_cache_status

        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        args = argparse.Namespace(
            manifest=manifest_path,
            verbose=True,
            quiet=False,
            json=False,
        )

        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_status(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        # Verbose mode shows TTL and max size
        assert "TTL Hours:" in captured.out
        assert "Max Size GB:" in captured.out


class TestCacheClearAborted:
    """Tests for cache clear confirmation abort."""

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_aborted_by_user(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test cache clear aborts when user declines confirmation."""
        import argparse
        import hashlib

        from floe_core.cli.artifact import run_cache_clear
        from floe_core.oci.cache import CacheManager
        from floe_core.schemas.oci import CacheConfig

        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        # Pre-populate the cache
        config = CacheConfig(path=cache_path, max_size_gb=10, ttl_hours=24)
        manager = CacheManager(config)
        content = b'{"version": "0.2.0"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        args = argparse.Namespace(
            manifest=manifest_path,
            tag=None,
            yes=False,  # Will prompt for confirmation
            verbose=False,
            quiet=False,
        )

        # Mock input to decline
        with (
            patch("floe_core.cli.artifact.logger"),
            patch("builtins.input", return_value="n"),
        ):
            exit_code = run_cache_clear(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Aborted" in captured.out

        # Cache should still have the entry
        stats = manager.stats()
        assert stats["entry_count"] == 1

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_by_tag_aborted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test cache clear by tag aborts when user declines."""
        import argparse
        import hashlib

        from floe_core.cli.artifact import run_cache_clear
        from floe_core.oci.cache import CacheManager
        from floe_core.schemas.oci import CacheConfig

        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        # Pre-populate the cache
        config = CacheConfig(path=cache_path, max_size_gb=10, ttl_hours=24)
        manager = CacheManager(config)
        content = b'{"version": "0.2.0"}'
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        manager.put(
            digest=digest,
            tag="v1.0.0",
            registry="oci://harbor.example.com/floe",
            content=content,
        )

        args = argparse.Namespace(
            manifest=manifest_path,
            tag="v1.0.0",
            yes=False,
            verbose=False,
            quiet=False,
        )

        # Mock input to decline
        with (
            patch("floe_core.cli.artifact.logger"),
            patch("builtins.input", return_value="no"),
        ):
            exit_code = run_cache_clear(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Aborted" in captured.out


class TestCacheStatusError:
    """Tests for cache status error handling."""

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_status_error_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test cache status returns 1 on unexpected error."""
        import argparse

        from floe_core.cli.artifact import run_cache_status

        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        args = argparse.Namespace(
            manifest=manifest_path,
            verbose=False,
            quiet=False,
            json=False,
        )

        with (
            patch("floe_core.cli.artifact.logger"),
            patch(
                "floe_core.oci.cache.CacheManager",
                side_effect=RuntimeError("Failed to init"),
            ),
        ):
            exit_code = run_cache_status(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err


class TestCacheClearError:
    """Tests for cache clear error handling."""

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_error_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test cache clear returns 1 on unexpected error."""
        import argparse

        from floe_core.cli.artifact import run_cache_clear

        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        args = argparse.Namespace(
            manifest=manifest_path,
            tag=None,
            yes=True,
            verbose=False,
            quiet=False,
        )

        with (
            patch("floe_core.cli.artifact.logger"),
            patch(
                "floe_core.oci.cache.CacheManager",
                side_effect=RuntimeError("Failed to init"),
            ),
        ):
            exit_code = run_cache_clear(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err


class TestCacheClearTagNotFound:
    """Tests for cache clear when tag not found."""

    @pytest.mark.requirement("8A-FR-030")
    def test_cache_clear_tag_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test cache clear returns success when tag not found."""
        import argparse

        from floe_core.cli.artifact import run_cache_clear

        manifest_path = tmp_path / "manifest.yaml"
        cache_path = tmp_path / "cache"
        manifest_path.write_text(f"""
oci:
  cache:
    enabled: true
    path: "{cache_path}"
    max_size_gb: 10
    ttl_hours: 24
""")

        args = argparse.Namespace(
            manifest=manifest_path,
            tag="nonexistent",
            yes=True,
            verbose=False,
            quiet=False,
        )

        with patch("floe_core.cli.artifact.logger"):
            exit_code = run_cache_clear(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No cached artifacts found with tag" in captured.out


class TestInspectHumanReadableOutput:
    """Tests for inspect command human-readable output variations."""

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_product_name_only(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test inspect shows product name when version is missing."""
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_inspect
        from floe_core.schemas.oci import ArtifactLayer, ArtifactManifest, SignatureStatus

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=False,
        )

        mock_manifest = ArtifactManifest(
            digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
            artifact_type="application/vnd.floe.compiled-artifacts.v1+json",
            size=12345,
            created_at=datetime.now(timezone.utc),
            annotations={
                "io.floe.product.name": "test-product",
                # No version annotation
            },
            layers=[
                ArtifactLayer(
                    digest="sha256:def456789012345678901234567890123456789012345678901234567890abcd",
                    media_type="application/vnd.floe.compiled-artifacts.v1+json",
                    size=12345,
                    annotations={},
                )
            ],
            signature_status=SignatureStatus.UNSIGNED,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Product:       test-product" in captured.out

    @pytest.mark.requirement("8A-FR-028")
    def test_inspect_no_product_info(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test inspect shows N/A when no product info."""
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_inspect
        from floe_core.schemas.oci import ArtifactLayer, ArtifactManifest, SignatureStatus

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            tag="v1.0.0",
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=False,
        )

        mock_manifest = ArtifactManifest(
            digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
            artifact_type="application/vnd.floe.compiled-artifacts.v1+json",
            size=12345,
            created_at=datetime.now(timezone.utc),
            annotations={},  # No product annotations
            layers=[
                ArtifactLayer(
                    digest="sha256:def456789012345678901234567890123456789012345678901234567890abcd",
                    media_type="application/vnd.floe.compiled-artifacts.v1+json",
                    size=12345,
                    annotations={},
                )
            ],
            signature_status=SignatureStatus.UNSIGNED,
        )

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.inspect.return_value = mock_manifest
            mock_from_manifest.return_value = mock_client

            exit_code = run_inspect(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Product:       N/A" in captured.out


class TestListTableOutput:
    """Tests for list command table output edge cases."""

    @pytest.mark.requirement("8A-FR-029")
    def test_list_truncates_long_tag_names(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test list command truncates long tag names in table."""
        from datetime import datetime, timezone

        from floe_core.cli.artifact import run_list
        from floe_core.schemas.oci import ArtifactTag

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
artifacts:
  registry:
    uri: "oci://harbor.example.com/floe"
    auth:
      type: aws-irsa
""")

        import argparse

        args = argparse.Namespace(
            filter=None,
            manifest=manifest_path,
            json_output=False,
            verbose=False,
            quiet=False,
        )

        mock_tags = [
            ArtifactTag(
                name="very-long-tag-name-that-exceeds-15-chars",
                digest="sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
                created_at=datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc),
                size=12345,
            ),
        ]

        with patch("floe_core.oci.client.OCIClient.from_manifest") as mock_from_manifest:
            mock_client = MagicMock()
            mock_client.list.return_value = mock_tags
            mock_from_manifest.return_value = mock_client

            exit_code = run_list(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        # Should truncate to 12 chars + "..."
        assert "very-long-ta..." in captured.out
