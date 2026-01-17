"""Unit tests for floe compile CLI command.

Tests the compile command including argument parsing, exit codes,
and output generation.

Requirements:
    - FR-037: floe compile CLI
    - FR-038: CLI exit codes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


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
        args = parser.parse_args([
            "--spec", "floe.yaml",
            "--manifest", "manifest.yaml",
            "--output", "build/",
            "--dry-run",
            "--validate-only",
            "--verbose",
        ])

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
        args = parser.parse_args([
            "--spec", "floe.yaml",
            "--manifest", "manifest.yaml",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(output_dir),
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(nested_output),
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(output_dir),
            "--dry-run",
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(output_dir),
            "--validate-only",
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(output_dir),
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(tmp_path / "output"),
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(tmp_path / "nonexistent.yaml"),
            "--manifest", str(manifest_path),
            "--output", str(tmp_path / "output"),
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(tmp_path / "output"),
            "--quiet",
        ])

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
        args = parser.parse_args([
            "--spec", str(spec_path),
            "--manifest", str(manifest_path),
            "--output", str(tmp_path / "output"),
            "--quiet",
        ])

        exit_code = run_compile(args)
        assert exit_code == 2  # RESOLVE stage error
