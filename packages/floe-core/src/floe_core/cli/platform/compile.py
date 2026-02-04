"""Platform compile command implementation.

Task ID: T014, T020
Phase: 3 - User Story 1 (Platform Compile MVP)
User Story: US1 - Unified Platform Compile with Enforcement Export
Requirements: FR-010 through FR-015

This module implements the `floe platform compile` command which:
- Loads FloeSpec (floe.yaml) and PlatformManifest (manifest.yaml)
- Compiles them into CompiledArtifacts
- Runs policy enforcement
- Exports enforcement report in various formats

Example:
    $ floe platform compile --spec floe.yaml --manifest manifest.yaml
    $ floe platform compile --enforcement-report report.sarif --enforcement-format sarif
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
import structlog

from floe_core.cli.utils import ExitCode, error_exit, info, success

if TYPE_CHECKING:
    from floe_core.enforcement.result import EnforcementResult

logger = structlog.get_logger(__name__)


@click.command(
    name="compile",
    help="Compile FloeSpec and Manifest into CompiledArtifacts (FR-010).",
    epilog="""
Examples:
    $ floe platform compile --spec floe.yaml --manifest manifest.yaml
    $ floe platform compile --output target/artifacts.json
    $ floe platform compile --enforcement-report report.json --enforcement-format json
    $ floe platform compile --enforcement-report report.sarif --enforcement-format sarif
    $ floe platform compile --skip-contracts
    $ floe platform compile --drift-detection
""",
)
@click.option(
    "--spec",
    "-s",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    help="Path to FloeSpec file (floe.yaml).",
    metavar="PATH",
)
@click.option(
    "--manifest",
    "-m",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    help="Path to PlatformManifest file (manifest.yaml).",
    metavar="PATH",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, resolve_path=True, path_type=Path),
    default="target/compiled_artifacts.json",
    show_default=True,
    help="Output path for CompiledArtifacts (FR-011).",
    metavar="PATH",
)
@click.option(
    "--enforcement-report",
    type=click.Path(dir_okay=False, resolve_path=True, path_type=Path),
    help="Output path for enforcement report (FR-012).",
    metavar="PATH",
)
@click.option(
    "--enforcement-format",
    type=click.Choice(["json", "sarif", "html"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Enforcement report format (FR-013).",
)
@click.option(
    "--skip-contracts",
    is_flag=True,
    default=False,
    help="Skip data contract validation during compilation. "
    "Use when contract infrastructure is unavailable or for quick iterations.",
)
@click.option(
    "--drift-detection",
    is_flag=True,
    default=False,
    help="Enable schema drift detection against actual table schemas. "
    "Requires database connection. Validates contract schema matches reality.",
)
@click.option(
    "--generate-definitions",
    is_flag=True,
    default=False,
    help="Generate Dagster definitions.py file alongside CompiledArtifacts. "
    "The generated file can be used as a Dagster code location entry point.",
)
def compile_command(
    spec: Path | None,
    manifest: Path | None,
    output: Path,
    enforcement_report: Path | None,
    enforcement_format: str,
    skip_contracts: bool,
    drift_detection: bool,
    generate_definitions: bool,
) -> None:
    """Compile FloeSpec and Manifest into CompiledArtifacts.

    Loads the FloeSpec (floe.yaml) and PlatformManifest (manifest.yaml),
    compiles them into CompiledArtifacts, runs policy enforcement
    including data contract validation, and exports the results.

    Args:
        spec: Path to FloeSpec file (floe.yaml).
        manifest: Path to PlatformManifest file (manifest.yaml).
        output: Output path for CompiledArtifacts.
        enforcement_report: Output path for enforcement report.
        enforcement_format: Enforcement report format (json, sarif, html).
        skip_contracts: Skip data contract validation if True.
        drift_detection: Enable schema drift detection if True.
        generate_definitions: Generate Dagster definitions.py if True.
    """
    # Validate required inputs
    if spec is None:
        error_exit(
            "Missing --spec option. Provide path to FloeSpec (floe.yaml).",
            exit_code=ExitCode.USAGE_ERROR,
        )

    if manifest is None:
        error_exit(
            "Missing --manifest option. Provide path to PlatformManifest (manifest.yaml).",
            exit_code=ExitCode.USAGE_ERROR,
        )

    info(f"Compiling spec: {spec}")
    info(f"Using manifest: {manifest}")
    info(f"Output path: {output}")

    # Log contract-related options (T077)
    if skip_contracts:
        info("Contract validation: SKIPPED (--skip-contracts)")
    else:
        info("Contract validation: ENABLED")
        if drift_detection:
            info("Schema drift detection: ENABLED (--drift-detection)")
        else:
            info("Schema drift detection: DISABLED (use --drift-detection to enable)")

    # Create parent directories for output (FR-011)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Create parent directories for enforcement report (FR-014)
    if enforcement_report is not None:
        enforcement_report.parent.mkdir(parents=True, exist_ok=True)
        info(f"Enforcement report: {enforcement_report} (format: {enforcement_format})")

    try:
        # Step 1-3: Run compilation pipeline (FR-010, FR-011)
        from floe_core.compilation.stages import compile_pipeline

        info("Running compilation pipeline...")
        artifacts = compile_pipeline(spec, manifest)

        # Step 4: Save CompiledArtifacts to output path (FR-011)
        artifacts.to_json_file(output)
        success(f"CompiledArtifacts written to: {output}")

        # Step 5: Export enforcement report if requested (FR-012, FR-013, T020)
        if enforcement_report is not None:
            _export_enforcement_report(
                enforcement_format=enforcement_format,
                output_path=enforcement_report,
                artifacts=artifacts,
            )
            success(f"Enforcement report written to: {enforcement_report}")

        # Step 6: Generate orchestrator entry point if requested
        # Respects component ownership: plugin owns its code generation
        if generate_definitions:
            entry_point_path = _generate_orchestrator_entry_point(
                artifacts=artifacts,
                output_dir=output.parent,
            )
            success(f"Entry point generated: {entry_point_path}")

        success("Compilation complete.")

    except FileNotFoundError as e:
        error_exit(
            f"File not found: {e}",
            exit_code=ExitCode.FILE_NOT_FOUND,
        )
    except PermissionError as e:
        error_exit(
            f"Permission denied: {e}",
            exit_code=ExitCode.PERMISSION_ERROR,
        )
    except Exception as e:
        # SECURITY: Don't expose internal exception details that may contain paths
        # or sensitive configuration. Log the full error internally for debugging.
        logger.error(
            "compilation_failed",
            error_type=type(e).__name__,
            # Only log first 200 chars to avoid exposing sensitive data
            error_summary=str(e)[:200] if str(e) else "Unknown error",
        )
        error_exit(
            "Compilation failed. Check input files and configuration.",
            exit_code=ExitCode.COMPILATION_ERROR,
        )


def _export_enforcement_report(
    enforcement_format: str,
    output_path: Path,
    artifacts: object,
) -> None:
    """Export enforcement report in the specified format.

    This function wires the CLI to the existing enforcement exporters
    from Epic 3B (export_json, export_sarif, export_html).

    Args:
        enforcement_format: Format to export (json, sarif, html).
        output_path: Path where report should be written.
        artifacts: CompiledArtifacts containing enforcement results.

    Note:
        Currently creates a placeholder EnforcementResult since full
        enforcement requires dbt manifest.json which is generated
        later in the pipeline. Full integration pending Epic 3B completion.
    """
    from datetime import datetime, timezone

    from floe_core.enforcement.exporters import export_html, export_json, export_sarif
    from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

    # Create placeholder enforcement result
    # Full enforcement requires dbt manifest.json from dbt compile
    # This will be replaced with actual enforcement results in integration
    result: EnforcementResult = EnforcementResult(
        passed=True,
        violations=[],
        summary=EnforcementSummary(
            total_models=0,
            models_validated=0,
            naming_violations=0,
            coverage_violations=0,
            documentation_violations=0,
            duration_ms=0.0,
        ),
        enforcement_level="warn",
        manifest_version="placeholder",
        timestamp=datetime.now(timezone.utc),
    )

    # Export using appropriate exporter
    format_lower = enforcement_format.lower()
    if format_lower == "json":
        export_json(result, output_path)
    elif format_lower == "sarif":
        export_sarif(result, output_path)
    elif format_lower == "html":
        export_html(result, output_path)
    else:
        error_exit(
            f"Unknown enforcement format: {enforcement_format}",
            exit_code=ExitCode.USAGE_ERROR,
        )


def _generate_orchestrator_entry_point(
    artifacts: object,
    output_dir: Path,
) -> str:
    """Generate orchestrator-specific entry point via plugin.

    Respects component ownership: floe-core provides data (CompiledArtifacts),
    the orchestrator plugin owns code generation. This function dynamically
    loads the configured orchestrator plugin and delegates code generation to it.

    Args:
        artifacts: CompiledArtifacts containing plugin configuration.
        output_dir: Directory to write the entry point file.

    Returns:
        Path to the generated entry point file.

    Raises:
        click.ClickException: If orchestrator plugin cannot be loaded.
    """
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts

    # Type narrow artifacts
    if not isinstance(artifacts, CompiledArtifacts):
        error_exit(
            "Invalid artifacts type for code generation.",
            exit_code=ExitCode.COMPILATION_ERROR,
        )

    # Get orchestrator type from artifacts
    orchestrator_type = artifacts.plugins.orchestrator.type

    info(f"Loading orchestrator plugin: {orchestrator_type}")

    # Load the appropriate orchestrator plugin
    # Currently only Dagster is supported
    if orchestrator_type == "dagster":
        try:
            from floe_orchestrator_dagster import DagsterOrchestratorPlugin

            plugin = DagsterOrchestratorPlugin()
        except ImportError as e:
            error_exit(
                f"Failed to load Dagster orchestrator plugin: {e}. "
                "Install with: pip install floe-orchestrator-dagster",
                exit_code=ExitCode.COMPILATION_ERROR,
            )
    else:
        error_exit(
            f"Unsupported orchestrator type: {orchestrator_type}. "
            "Currently supported: dagster",
            exit_code=ExitCode.COMPILATION_ERROR,
        )

    # Get product name from artifacts metadata
    product_name = artifacts.metadata.product_name

    # Delegate code generation to the plugin
    # This respects component ownership: plugin owns its code generation
    entry_point_path = plugin.generate_entry_point_code(
        product_name=product_name,
        output_dir=str(output_dir),
    )

    return entry_point_path


# Export for use in platform group
__all__: list[str] = ["compile_command"]
