"""Unit tests for floe artifact push and pull CLI commands.

Tests the artifact push/pull commands including argument parsing, exit codes,
and OCI operations.

Task: T020, T029
Requirements: FR-026, FR-027
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
        mock_artifacts.to_json_file.assert_called_once()

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
