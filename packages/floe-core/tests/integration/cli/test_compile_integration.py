"""Integration tests for the platform compile command.

Task ID: T026
Phase: 3 - User Story 1 (Platform Compile MVP)
User Story: US1 - Unified Platform Compile with Enforcement Export
Requirements: FR-010 through FR-015

These tests validate the complete compile command workflow with real files:
- Full compilation pipeline execution with quickstart fixtures
- CompiledArtifacts output file creation and content validation
- Enforcement report generation in all formats (JSON, SARIF, HTML)
- Directory creation for nested output paths

Unlike unit tests, these tests:
- Use real configuration files (quickstart fixtures)
- Execute the full compile_pipeline() function
- Verify actual file contents match expected schemas
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestCompileIntegrationWithRealFiles:
    """Integration tests for compile command with real fixtures.

    Task: T026
    Requirements: FR-010, FR-011
    """

    @pytest.mark.requirement("011-FR-010")
    def test_compile_with_quickstart_fixtures_creates_artifacts(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        quickstart_manifest_yaml: Path,
        output_dir: Path,
    ) -> None:
        """Test that compile creates CompiledArtifacts with real fixtures.

        Validates end-to-end compilation with quickstart floe.yaml and manifest.yaml.
        Verifies that compiled_artifacts.json is created with valid content.
        """
        from floe_core.cli.main import cli

        output_path = output_dir / "compiled_artifacts.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
            ],
        )

        # Should succeed
        assert result.exit_code == 0, (
            f"Compile failed with exit code {result.exit_code}.\nOutput: {result.output}"
        )

        # Verify output file exists
        assert output_path.exists(), f"Expected output file at {output_path}"

        # Verify content is valid JSON with expected schema
        content = json.loads(output_path.read_text())
        assert "version" in content, "CompiledArtifacts must have version field"
        assert "metadata" in content, "CompiledArtifacts must have metadata field"
        assert "identity" in content, "CompiledArtifacts must have identity field"
        assert "dbt_profiles" in content, "CompiledArtifacts must have dbt_profiles"
        assert "transforms" in content, "CompiledArtifacts must have transforms field"

    @pytest.mark.requirement("011-FR-011")
    def test_compile_creates_nested_output_directories(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        quickstart_manifest_yaml: Path,
        tmp_path: Path,
    ) -> None:
        """Test that compile creates nested directories for output path.

        Validates that deeply nested output paths are created automatically.
        """
        from floe_core.cli.main import cli

        # Deeply nested path that doesn't exist
        output_path = tmp_path / "a" / "b" / "c" / "compiled_artifacts.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert output_path.exists(), "Nested directories should be created"
        assert output_path.parent.exists(), "Parent directories should exist"


class TestEnforcementReportIntegration:
    """Integration tests for enforcement report generation.

    Task: T026
    Requirements: FR-012, FR-013, FR-014
    """

    @pytest.mark.requirement("011-FR-012")
    def test_compile_with_enforcement_report_json(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        quickstart_manifest_yaml: Path,
        output_dir: Path,
    ) -> None:
        """Test that compile generates JSON enforcement report.

        Validates that --enforcement-report with --enforcement-format json
        creates a valid JSON file with EnforcementResult schema.
        """
        from floe_core.cli.main import cli

        output_path = output_dir / "compiled_artifacts.json"
        report_path = output_dir / "enforcement.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
                "--enforcement-report",
                str(report_path),
                "--enforcement-format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert report_path.exists(), "Enforcement report should be created"

        # Verify JSON content
        content = json.loads(report_path.read_text())
        assert "passed" in content, "EnforcementResult must have passed field"
        assert "violations" in content, "EnforcementResult must have violations field"
        assert "summary" in content, "EnforcementResult must have summary field"
        assert "enforcement_level" in content, "EnforcementResult must have enforcement_level"

    @pytest.mark.requirement("011-FR-012")
    @pytest.mark.requirement("011-FR-013")
    def test_compile_with_enforcement_report_sarif(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        quickstart_manifest_yaml: Path,
        output_dir: Path,
    ) -> None:
        """Test that compile generates SARIF enforcement report.

        Validates that --enforcement-report with --enforcement-format sarif
        creates a valid SARIF 2.1.0 file.
        """
        from floe_core.cli.main import cli

        output_path = output_dir / "compiled_artifacts.json"
        report_path = output_dir / "enforcement.sarif"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
                "--enforcement-report",
                str(report_path),
                "--enforcement-format",
                "sarif",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert report_path.exists(), "SARIF report should be created"

        # Verify SARIF 2.1.0 structure
        content = json.loads(report_path.read_text())
        assert content.get("version") == "2.1.0", "SARIF version must be 2.1.0"
        assert "$schema" in content, "SARIF must have $schema"
        assert "runs" in content, "SARIF must have runs array"
        assert len(content["runs"]) >= 1, "SARIF must have at least one run"
        assert "tool" in content["runs"][0], "SARIF run must have tool"

    @pytest.mark.requirement("011-FR-012")
    @pytest.mark.requirement("011-FR-013")
    def test_compile_with_enforcement_report_html(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        quickstart_manifest_yaml: Path,
        output_dir: Path,
    ) -> None:
        """Test that compile generates HTML enforcement report.

        Validates that --enforcement-report with --enforcement-format html
        creates a valid HTML file.
        """
        from floe_core.cli.main import cli

        output_path = output_dir / "compiled_artifacts.json"
        report_path = output_dir / "enforcement.html"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
                "--enforcement-report",
                str(report_path),
                "--enforcement-format",
                "html",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert report_path.exists(), "HTML report should be created"

        # Verify HTML structure
        content = report_path.read_text()
        assert "<html" in content.lower(), "HTML report must have <html> tag"
        assert "</html>" in content.lower(), "HTML report must have closing </html> tag"

    @pytest.mark.requirement("011-FR-014")
    def test_compile_creates_nested_enforcement_report_directories(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        quickstart_manifest_yaml: Path,
        tmp_path: Path,
    ) -> None:
        """Test that compile creates nested directories for enforcement report.

        Validates that deeply nested report paths are created automatically.
        """
        from floe_core.cli.main import cli

        output_path = tmp_path / "artifacts" / "compiled_artifacts.json"
        report_path = tmp_path / "reports" / "deep" / "nested" / "enforcement.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
                "--enforcement-report",
                str(report_path),
                "--enforcement-format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert report_path.exists(), "Nested report directories should be created"


class TestCompileProductMetadata:
    """Integration tests for product metadata in compiled artifacts.

    Task: T026
    Requirements: FR-010
    """

    @pytest.mark.requirement("011-FR-010")
    def test_compile_preserves_product_metadata(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        quickstart_manifest_yaml: Path,
        output_dir: Path,
    ) -> None:
        """Test that compile preserves product metadata from floe.yaml.

        Validates that product name, version, and owner are in compiled artifacts.
        The schema stores metadata in the 'metadata' and 'identity' fields.
        """
        from floe_core.cli.main import cli

        output_path = output_dir / "compiled_artifacts.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"

        content = json.loads(output_path.read_text())

        # Verify product metadata from quickstart floe.yaml
        # Schema uses 'metadata' for product info and 'identity' for identification
        metadata = content.get("metadata", {})
        assert metadata.get("product_name") == "customer-360", "Product name should match floe.yaml"
        assert metadata.get("product_version") == "1.0.0", "Product version should match floe.yaml"

        # Verify identity contains product_id derived from product name
        identity = content.get("identity", {})
        assert "customer_360" in identity.get("product_id", ""), (
            "Product ID should contain normalized product name"
        )


class TestCompileErrorHandling:
    """Integration tests for compile error handling.

    Task: T026
    Requirements: FR-015
    """

    @pytest.mark.requirement("011-FR-015")
    def test_compile_returns_nonzero_on_missing_spec(
        self,
        cli_runner: CliRunner,
        quickstart_manifest_yaml: Path,
        output_dir: Path,
    ) -> None:
        """Test that compile returns non-zero exit code when spec not provided.

        Validates proper error handling for missing --spec option.
        """
        from floe_core.cli.main import cli

        output_path = output_dir / "compiled_artifacts.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--manifest",
                str(quickstart_manifest_yaml),
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code != 0, "Should fail when spec not provided"
        # Error message should mention spec
        assert "spec" in result.output.lower(), "Error should mention spec"

    @pytest.mark.requirement("011-FR-015")
    def test_compile_returns_nonzero_on_missing_manifest(
        self,
        cli_runner: CliRunner,
        quickstart_floe_yaml: Path,
        output_dir: Path,
    ) -> None:
        """Test that compile returns non-zero exit code when manifest not provided.

        Validates proper error handling for missing --manifest option.
        """
        from floe_core.cli.main import cli

        output_path = output_dir / "compiled_artifacts.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(quickstart_floe_yaml),
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code != 0, "Should fail when manifest not provided"
        # Error message should mention manifest
        assert "manifest" in result.output.lower(), "Error should mention manifest"


__all__: list[str] = [
    "TestCompileIntegrationWithRealFiles",
    "TestEnforcementReportIntegration",
    "TestCompileProductMetadata",
    "TestCompileErrorHandling",
]
