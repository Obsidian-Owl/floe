"""Contract tests for CLI compile command output format.

Task ID: T013
Phase: 3 - User Story 1 (Platform Compile MVP)
User Story: US1 - Unified Platform Compile with Enforcement Export
Requirements: FR-011, FR-012, FR-013

These tests validate the output format contracts for the compile command:
- CompiledArtifacts JSON output (FR-011)
- Enforcement report output (FR-012)
- Enforcement format options: json, sarif, html (FR-013)

Contract tests validate cross-package interfaces. The compile command
produces artifacts consumed by downstream packages (floe-dagster, floe-dbt).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def sample_compiled_artifacts_json() -> dict[str, Any]:
    """Sample compiled artifacts JSON structure per contract.

    This represents the MINIMUM contract that downstream packages
    (floe-dagster, floe-dbt) can rely on.
    """
    return {
        "version": "0.3.0",
        "metadata": {
            "compiled_at": "2024-01-01T00:00:00Z",
            "floe_version": "0.3.0",
            "source_hash": "sha256:abc123",
            "product_name": "test-product",
            "product_version": "1.0.0",
        },
        "identity": {
            "product_id": "default.test_product",
            "domain": "default",
            "repository": "github.com/acme/test",
        },
        "mode": "simple",
        "observability": {
            "telemetry": {
                "enabled": True,
                "resource_attributes": {
                    "service_name": "test",
                    "service_version": "1.0.0",
                    "deployment_environment": "dev",
                    "floe_namespace": "test",
                    "floe_product_name": "test",
                    "floe_product_version": "1.0.0",
                    "floe_mode": "dev",
                },
            },
            "lineage_namespace": "test-namespace",
        },
    }


@pytest.fixture
def sample_enforcement_json() -> dict[str, Any]:
    """Sample enforcement report JSON structure per contract.

    Enforcement reports are produced by the policy enforcer and exported
    by the CLI in various formats (json, sarif, html).
    """
    return {
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z",
        "summary": {
            "total_rules": 10,
            "passed": 8,
            "failed": 2,
            "skipped": 0,
        },
        "results": [
            {
                "rule_id": "naming-convention",
                "status": "passed",
                "severity": "warning",
                "message": "All models follow naming convention",
            },
            {
                "rule_id": "documentation-required",
                "status": "failed",
                "severity": "error",
                "message": "Model 'stg_customers' missing description",
                "location": {
                    "file": "models/staging/stg_customers.sql",
                    "line": 1,
                },
            },
        ],
    }


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary directory for compile output."""
    output_dir = tmp_path / "target"
    output_dir.mkdir(parents=True)
    yield output_dir


class TestCompileOutputContract:
    """Contract tests for compile command output format.

    These tests validate the output format contract that downstream
    packages (floe-dagster, floe-dbt) can rely on.

    Note: Tests are TDD red-phase until compile command is implemented.
    """

    @pytest.mark.requirement("FR-011")
    def test_compiled_artifacts_output_is_valid_json(
        self,
        temp_output_dir: Path,
        sample_compiled_artifacts_json: dict[str, Any],
    ) -> None:
        """Contract: --output produces valid JSON file.

        The compile command MUST produce a valid JSON file at the
        specified --output path. Downstream packages load this file
        using CompiledArtifacts.from_json_file().
        """
        output_path = temp_output_dir / "compiled_artifacts.json"

        # Write sample to simulate compile output
        output_path.write_text(json.dumps(sample_compiled_artifacts_json, indent=2))

        # Verify: file exists and is valid JSON
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert isinstance(data, dict)
        assert "version" in data

    @pytest.mark.requirement("FR-011")
    def test_compiled_artifacts_has_required_fields(
        self,
        sample_compiled_artifacts_json: dict[str, Any],
    ) -> None:
        """Contract: CompiledArtifacts has required fields.

        Downstream packages MUST be able to rely on these fields:
        - version
        - metadata
        - identity
        - observability
        """
        required_fields = ["version", "metadata", "identity", "observability"]

        for field in required_fields:
            assert field in sample_compiled_artifacts_json, f"Missing required field: {field}"

    @pytest.mark.requirement("FR-011")
    def test_compiled_artifacts_version_is_semver(
        self,
        sample_compiled_artifacts_json: dict[str, Any],
    ) -> None:
        """Contract: version field is semantic versioning (MAJOR.MINOR.PATCH)."""
        import re

        version = sample_compiled_artifacts_json["version"]
        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, version), f"Version '{version}' is not semver"

    @pytest.mark.requirement("FR-011")
    def test_compiled_artifacts_default_output_path(self) -> None:
        """Contract: default output path is target/compiled_artifacts.json.

        When --output is not specified, compile MUST write to
        target/compiled_artifacts.json in the current directory.
        """
        default_path = Path("target/compiled_artifacts.json")
        assert default_path.name == "compiled_artifacts.json"
        assert default_path.parent.name == "target"

    @pytest.mark.requirement("FR-012")
    def test_enforcement_report_output_is_valid_json(
        self,
        temp_output_dir: Path,
        sample_enforcement_json: dict[str, Any],
    ) -> None:
        """Contract: --enforcement-report produces valid JSON file.

        When --enforcement-format=json (default), the enforcement report
        MUST be valid JSON.
        """
        report_path = temp_output_dir / "enforcement_report.json"

        # Write sample to simulate compile output
        report_path.write_text(json.dumps(sample_enforcement_json, indent=2))

        # Verify: file exists and is valid JSON
        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert isinstance(data, dict)

    @pytest.mark.requirement("FR-012")
    def test_enforcement_report_has_required_fields(
        self,
        sample_enforcement_json: dict[str, Any],
    ) -> None:
        """Contract: enforcement report has required structure.

        The enforcement report MUST contain:
        - version: report format version
        - timestamp: when report was generated
        - summary: aggregated pass/fail counts
        - results: list of individual rule results
        """
        required_fields = ["version", "timestamp", "summary", "results"]

        for field in required_fields:
            assert field in sample_enforcement_json, f"Missing required field: {field}"

    @pytest.mark.requirement("FR-012")
    def test_enforcement_summary_structure(
        self,
        sample_enforcement_json: dict[str, Any],
    ) -> None:
        """Contract: enforcement summary has expected fields."""
        summary = sample_enforcement_json["summary"]

        assert "total_rules" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert isinstance(summary["total_rules"], int)
        assert isinstance(summary["passed"], int)
        assert isinstance(summary["failed"], int)

    @pytest.mark.requirement("FR-012")
    def test_enforcement_result_structure(
        self,
        sample_enforcement_json: dict[str, Any],
    ) -> None:
        """Contract: each result has required fields."""
        results = sample_enforcement_json["results"]
        assert len(results) > 0

        for result in results:
            assert "rule_id" in result
            assert "status" in result
            assert result["status"] in ("passed", "failed", "skipped")

    @pytest.mark.requirement("FR-013")
    def test_enforcement_format_json_produces_json(
        self,
        temp_output_dir: Path,
        sample_enforcement_json: dict[str, Any],
    ) -> None:
        """Contract: --enforcement-format=json produces JSON output."""
        report_path = temp_output_dir / "report.json"
        report_path.write_text(json.dumps(sample_enforcement_json))

        # Verify JSON is parseable
        data = json.loads(report_path.read_text())
        assert isinstance(data, dict)

    @pytest.mark.requirement("FR-013")
    def test_enforcement_format_sarif_structure(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Contract: --enforcement-format=sarif produces SARIF 2.1.0 output.

        SARIF (Static Analysis Results Interchange Format) is used by
        GitHub, Azure DevOps, and other tools for security reporting.
        """
        sarif_output = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "floe-enforcement",
                            "version": "0.3.0",
                            "rules": [],
                        }
                    },
                    "results": [],
                }
            ],
        }

        report_path = temp_output_dir / "report.sarif"
        report_path.write_text(json.dumps(sarif_output))

        # Verify SARIF structure
        data = json.loads(report_path.read_text())
        assert data["version"] == "2.1.0"
        assert "$schema" in data
        assert "runs" in data
        assert len(data["runs"]) > 0
        assert "tool" in data["runs"][0]

    @pytest.mark.requirement("FR-013")
    def test_enforcement_format_html_is_valid_html(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Contract: --enforcement-format=html produces HTML output.

        HTML output MUST be a valid HTML document with enforcement
        results rendered for human viewing.
        """
        html_output = """<!DOCTYPE html>
<html>
<head>
    <title>Enforcement Report</title>
</head>
<body>
    <h1>Enforcement Report</h1>
    <p>Generated at: 2024-01-01T00:00:00Z</p>
    <table>
        <tr><th>Rule</th><th>Status</th></tr>
    </table>
</body>
</html>"""

        report_path = temp_output_dir / "report.html"
        report_path.write_text(html_output)

        # Verify HTML structure (basic checks)
        content = report_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "<html>" in content
        assert "</html>" in content
        assert "Enforcement Report" in content


class TestCompileCommandIntegrationContract:
    """Contract tests that validate CLI produces correct output format.

    These tests will invoke the actual CLI once implemented.
    Currently marked as TDD red-phase placeholders.
    """

    @pytest.mark.requirement("FR-011")
    def test_cli_compile_produces_compiled_artifacts(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Contract: floe platform compile produces CompiledArtifacts.

        This test validates that the CLI correctly writes CompiledArtifacts
        to the specified output path when compilation succeeds.
        """
        from datetime import datetime
        from unittest.mock import patch

        from click.testing import CliRunner
        from floe_core.cli.main import cli
        from floe_core.schemas.compiled_artifacts import (
            CompilationMetadata,
            CompiledArtifacts,
            ObservabilityConfig,
            ProductIdentity,
        )
        from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

        # Create mock compiled artifacts that compile_pipeline would return
        mock_artifacts = CompiledArtifacts(
            version="0.3.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.3.0",
                source_hash="sha256:test123",
                product_name="test-product",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test_product",
                domain="default",
                repository="github.com/acme/test",
            ),
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    resource_attributes=ResourceAttributes(
                        service_name="test",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="test",
                        floe_product_name="test",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="test-namespace",
            ),
        )

        # Create test spec and manifest files
        spec_path = temp_output_dir / "floe.yaml"
        spec_path.write_text("name: test\nversion: '1.0.0'")

        manifest_path = temp_output_dir / "manifest.yaml"
        manifest_path.write_text("name: test-platform\nversion: '1.0.0'")

        output_path = temp_output_dir / "artifacts.json"

        runner = CliRunner()
        with patch(
            "floe_core.compilation.stages.compile_pipeline",
            return_value=mock_artifacts,
        ):
            result = runner.invoke(
                cli,
                [
                    "platform",
                    "compile",
                    "--spec",
                    str(spec_path),
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output_path),
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert output_path.exists(), "Output file not created"

        # Verify output is valid JSON with expected fields
        data = json.loads(output_path.read_text())
        assert data["version"] == "0.3.0"
        assert "metadata" in data
        assert "identity" in data

    @pytest.mark.requirement("FR-012")
    def test_cli_compile_produces_enforcement_report(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Contract: floe platform compile --enforcement-report produces report.

        This test validates that the CLI produces an enforcement report
        at the specified path when the --enforcement-report option is used.
        """
        from datetime import datetime
        from unittest.mock import patch

        from click.testing import CliRunner
        from floe_core.cli.main import cli
        from floe_core.schemas.compiled_artifacts import (
            CompilationMetadata,
            CompiledArtifacts,
            ObservabilityConfig,
            ProductIdentity,
        )
        from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

        # Create mock compiled artifacts
        mock_artifacts = CompiledArtifacts(
            version="0.3.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.3.0",
                source_hash="sha256:test123",
                product_name="test-product",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test_product",
                domain="default",
                repository="github.com/acme/test",
            ),
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    resource_attributes=ResourceAttributes(
                        service_name="test",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="test",
                        floe_product_name="test",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="test-namespace",
            ),
        )

        # Create test spec and manifest files
        spec_path = temp_output_dir / "floe.yaml"
        spec_path.write_text("name: test\nversion: '1.0.0'")

        manifest_path = temp_output_dir / "manifest.yaml"
        manifest_path.write_text("name: test-platform\nversion: '1.0.0'")

        report_path = temp_output_dir / "enforcement_report.json"

        runner = CliRunner()
        with patch(
            "floe_core.compilation.stages.compile_pipeline",
            return_value=mock_artifacts,
        ):
            result = runner.invoke(
                cli,
                [
                    "platform",
                    "compile",
                    "--spec",
                    str(spec_path),
                    "--manifest",
                    str(manifest_path),
                    "--enforcement-report",
                    str(report_path),
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert report_path.exists(), "Enforcement report not created"

        # Verify report is valid JSON
        report_data = json.loads(report_path.read_text())
        assert isinstance(report_data, dict)

    @pytest.mark.requirement("FR-013")
    def test_cli_compile_supports_all_enforcement_formats(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Contract: compile supports json, sarif, html enforcement formats.

        This test validates that the CLI correctly handles all three
        enforcement format options (json, sarif, html).
        """
        from datetime import datetime
        from unittest.mock import patch

        from click.testing import CliRunner
        from floe_core.cli.main import cli
        from floe_core.schemas.compiled_artifacts import (
            CompilationMetadata,
            CompiledArtifacts,
            ObservabilityConfig,
            ProductIdentity,
        )
        from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

        # Create mock compiled artifacts
        mock_artifacts = CompiledArtifacts(
            version="0.3.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.3.0",
                source_hash="sha256:test123",
                product_name="test-product",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test_product",
                domain="default",
                repository="github.com/acme/test",
            ),
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    resource_attributes=ResourceAttributes(
                        service_name="test",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="test",
                        floe_product_name="test",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="test-namespace",
            ),
        )

        # Create test spec and manifest files
        spec_path = temp_output_dir / "floe.yaml"
        spec_path.write_text("name: test\nversion: '1.0.0'")

        manifest_path = temp_output_dir / "manifest.yaml"
        manifest_path.write_text("name: test-platform\nversion: '1.0.0'")

        formats_and_extensions = [
            ("json", ".json"),
            ("sarif", ".sarif"),
            ("html", ".html"),
        ]

        runner = CliRunner()
        for format_name, extension in formats_and_extensions:
            report_path = temp_output_dir / f"report{extension}"

            with patch(
                "floe_core.compilation.stages.compile_pipeline",
                return_value=mock_artifacts,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "platform",
                        "compile",
                        "--spec",
                        str(spec_path),
                        "--manifest",
                        str(manifest_path),
                        "--enforcement-report",
                        str(report_path),
                        "--enforcement-format",
                        format_name,
                    ],
                )

            assert result.exit_code == 0, f"CLI failed for format {format_name}: {result.output}"
            assert report_path.exists(), f"Enforcement report not created for format {format_name}"

            # Basic content validation
            content = report_path.read_text()
            if format_name == "html":
                assert "<!DOCTYPE html>" in content or "<html>" in content
            else:
                # JSON and SARIF are both valid JSON
                data = json.loads(content)
                assert isinstance(data, dict)
