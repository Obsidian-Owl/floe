"""Unit tests for floe compile CLI command.

Tests the compile command including argument parsing, exit codes,
and output generation.

Requirements:
    - FR-037: floe compile CLI
    - FR-038: CLI exit codes
    - FR-011: Multiple output formats
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    pass


@pytest.fixture(autouse=True)
def patch_version_compat() -> Any:
    """Patch version compatibility to allow DuckDB plugin (1.0) with platform (0.1)."""
    with patch("floe_core.plugin_registry.is_compatible", return_value=True):
        yield


class TestCreateParser:
    """Tests for CLI argument parser."""

    @pytest.mark.requirement("FR-037")
    def test_parser_requires_spec(self) -> None:
        """Test that --spec is required."""
        from floe_core.cli.compile import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--manifest", "manifest.yaml"])

    @pytest.mark.requirement("FR-037")
    def test_parser_requires_manifest(self) -> None:
        """Test that --manifest is required."""
        from floe_core.cli.compile import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--spec", "floe.yaml"])

    @pytest.mark.requirement("FR-037")
    def test_parser_accepts_all_args(self) -> None:
        """Test that parser accepts all expected arguments."""
        from floe_core.cli.compile import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                "floe.yaml",
                "--manifest",
                "manifest.yaml",
                "--output",
                "build/",
                "--dry-run",
                "--validate-only",
                "--verbose",
            ]
        )

        assert args.spec == Path("floe.yaml")
        assert args.manifest == Path("manifest.yaml")
        assert args.output == Path("build/")
        assert args.dry_run is True
        assert args.validate_only is True
        assert args.verbose is True

    @pytest.mark.requirement("FR-037")
    def test_parser_default_output(self) -> None:
        """Test that output defaults to target/."""
        from floe_core.cli.compile import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                "floe.yaml",
                "--manifest",
                "manifest.yaml",
            ]
        )

        assert args.output == Path("target")


class TestRunCompile:
    """Tests for run_compile function."""

    @pytest.mark.requirement("FR-037")
    def test_run_compile_success(self, tmp_path: Path) -> None:
        """Test successful compilation."""
        from floe_core.cli.compile import create_parser, run_compile

        # Create test files
        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        output_dir = tmp_path / "output"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        assert (output_dir / "compiled_artifacts.json").exists()

    @pytest.mark.requirement("FR-037")
    def test_run_compile_creates_output_dir(self, tmp_path: Path) -> None:
        """Test that output directory is created if it doesn't exist."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        nested_output = tmp_path / "deeply" / "nested" / "output"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(nested_output),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        assert nested_output.exists()
        assert (nested_output / "compiled_artifacts.json").exists()

    @pytest.mark.requirement("FR-037")
    def test_run_compile_dry_run(self, tmp_path: Path) -> None:
        """Test dry-run mode doesn't write files."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        output_dir = tmp_path / "output"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--dry-run",
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        assert not (output_dir / "compiled_artifacts.json").exists()

    @pytest.mark.requirement("FR-037")
    def test_run_compile_validate_only(self, tmp_path: Path) -> None:
        """Test validate-only mode doesn't write files."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        output_dir = tmp_path / "output"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--validate-only",
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        assert not (output_dir / "compiled_artifacts.json").exists()

    @pytest.mark.requirement("FR-037")
    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        """Test that output is valid JSON."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        output_dir = tmp_path / "output"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--quiet",
            ]
        )

        run_compile(args)

        output_path = output_dir / "compiled_artifacts.json"
        data = json.loads(output_path.read_text())

        assert data["version"] == "0.2.0"
        assert "metadata" in data
        assert "plugins" in data


class TestExitCodes:
    """Tests for CLI exit codes based on compilation stage."""

    @pytest.mark.requirement("FR-038")
    def test_exit_code_0_on_success(self, tmp_path: Path) -> None:
        """Test exit code 0 on successful compilation."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(tmp_path / "output"),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)
        assert exit_code == 0

    @pytest.mark.requirement("FR-038")
    def test_exit_code_1_on_file_not_found(self, tmp_path: Path) -> None:
        """Test exit code 1 on file not found (LOAD stage)."""
        from floe_core.cli.compile import create_parser, run_compile

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(tmp_path / "nonexistent.yaml"),
                "--manifest",
                str(manifest_path),
                "--output",
                str(tmp_path / "output"),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)
        assert exit_code == 1  # LOAD stage error

    @pytest.mark.requirement("FR-038")
    def test_exit_code_1_on_validation_error(self, tmp_path: Path) -> None:
        """Test exit code 1 on validation error (LOAD stage)."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  # Missing version!
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
""")

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(tmp_path / "output"),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)
        assert exit_code == 1  # LOAD/VALIDATE stage error

    @pytest.mark.requirement("FR-038")
    def test_exit_code_2_on_resolve_error(self, tmp_path: Path) -> None:
        """Test exit code 2 on resolve error (RESOLVE stage)."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text("""
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
""")

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  orchestrator:
    type: dagster
""")  # Missing compute plugin!

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(tmp_path / "output"),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)
        assert exit_code == 2  # RESOLVE stage error


class TestOutputFormat:
    """Tests for --format flag and output format handling (T061).

    These tests validate FR-011: Multiple output formats support.
    Tests are written in TDD style - they FAIL until --format flag
    is implemented in T064.

    Requirements: FR-011
    """

    @pytest.fixture
    def spec_content(self) -> str:
        """Standard spec content for format tests."""
        return """
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
"""

    @pytest.fixture
    def manifest_content(self) -> str:
        """Standard manifest content for format tests."""
        return """
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
"""

    @pytest.fixture
    def setup_files(
        self,
        tmp_path: Path,
        spec_content: str,
        manifest_content: str,
    ) -> tuple[Path, Path, Path]:
        """Create test spec, manifest, and output directory.

        Returns:
            Tuple of (spec_path, manifest_path, output_dir).
        """
        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(spec_content)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(manifest_content)

        output_dir = tmp_path / "output"

        return spec_path, manifest_path, output_dir

    @pytest.mark.requirement("FR-011")
    def test_format_flag_exists(self) -> None:
        """Test that --format flag is accepted by parser."""
        from floe_core.cli.compile import create_parser

        parser = create_parser()

        # This should NOT raise - --format should be accepted
        args = parser.parse_args(
            [
                "--spec",
                "floe.yaml",
                "--manifest",
                "manifest.yaml",
                "--format",
                "json",
            ]
        )

        assert args.format == "json"

    @pytest.mark.requirement("FR-011")
    def test_format_json_produces_json_output(
        self,
        setup_files: tuple[Path, Path, Path],
    ) -> None:
        """Test that --format json produces JSON output file."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path, manifest_path, output_dir = setup_files

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--format",
                "json",
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        assert (output_dir / "compiled_artifacts.json").exists()

        # Verify it's valid JSON
        content = (output_dir / "compiled_artifacts.json").read_text()
        data = json.loads(content)
        assert data["version"] == "0.2.0"

    @pytest.mark.requirement("FR-011")
    def test_format_yaml_produces_yaml_output(
        self,
        setup_files: tuple[Path, Path, Path],
    ) -> None:
        """Test that --format yaml produces YAML output file."""
        import yaml

        from floe_core.cli.compile import create_parser, run_compile

        spec_path, manifest_path, output_dir = setup_files

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--format",
                "yaml",
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        assert (output_dir / "compiled_artifacts.yaml").exists()

        # Verify it's valid YAML
        content = (output_dir / "compiled_artifacts.yaml").read_text()
        data = yaml.safe_load(content)
        assert data["version"] == "0.2.0"

    @pytest.mark.requirement("FR-011")
    def test_default_format_is_json(
        self,
        setup_files: tuple[Path, Path, Path],
    ) -> None:
        """Test that default format (no --format flag) is JSON."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path, manifest_path, output_dir = setup_files

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--quiet",
            ]
        )

        # Default should be None (detect from extension, fallback to JSON)
        assert args.format is None

        exit_code = run_compile(args)

        assert exit_code == 0
        # Output should be .json by default
        assert (output_dir / "compiled_artifacts.json").exists()

    @pytest.mark.requirement("FR-011")
    def test_format_detection_from_output_extension_json(
        self,
        tmp_path: Path,
        spec_content: str,
        manifest_content: str,
    ) -> None:
        """Test format detection from .json file extension."""
        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(spec_content)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(manifest_content)

        # Specify explicit output file with .json extension
        output_file = tmp_path / "output" / "my_artifacts.json"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_file),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        # Should write to the exact path specified
        assert output_file.exists()

        # Content should be JSON
        content = output_file.read_text()
        data = json.loads(content)
        assert data["version"] == "0.2.0"

    @pytest.mark.requirement("FR-011")
    def test_format_detection_from_output_extension_yaml(
        self,
        tmp_path: Path,
        spec_content: str,
        manifest_content: str,
    ) -> None:
        """Test format detection from .yaml file extension."""
        import yaml

        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(spec_content)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(manifest_content)

        # Specify explicit output file with .yaml extension
        output_file = tmp_path / "output" / "my_artifacts.yaml"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_file),
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        # Should write to the exact path specified
        assert output_file.exists()

        # Content should be YAML
        content = output_file.read_text()
        data = yaml.safe_load(content)
        assert data["version"] == "0.2.0"

    @pytest.mark.requirement("FR-011")
    def test_format_flag_overrides_extension(
        self,
        tmp_path: Path,
        spec_content: str,
        manifest_content: str,
    ) -> None:
        """Test that explicit --format flag overrides file extension detection.

        When --format yaml is specified but output path is directory,
        the output should be YAML regardless.
        """
        import yaml

        from floe_core.cli.compile import create_parser, run_compile

        spec_path = tmp_path / "floe.yaml"
        spec_path.write_text(spec_content)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(manifest_content)

        output_dir = tmp_path / "output"

        parser = create_parser()
        args = parser.parse_args(
            [
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_dir),
                "--format",
                "yaml",
                "--quiet",
            ]
        )

        exit_code = run_compile(args)

        assert exit_code == 0
        # Should use .yaml extension from --format flag
        assert (output_dir / "compiled_artifacts.yaml").exists()
        assert not (output_dir / "compiled_artifacts.json").exists()

        # Content should be YAML
        content = (output_dir / "compiled_artifacts.yaml").read_text()
        data = yaml.safe_load(content)
        assert data["version"] == "0.2.0"

    @pytest.mark.requirement("FR-011")
    def test_invalid_format_rejected(self) -> None:
        """Test that invalid format value is rejected."""
        from floe_core.cli.compile import create_parser

        parser = create_parser()

        # Should reject invalid format
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "--spec",
                    "floe.yaml",
                    "--manifest",
                    "manifest.yaml",
                    "--format",
                    "xml",  # Invalid format
                ]
            )
