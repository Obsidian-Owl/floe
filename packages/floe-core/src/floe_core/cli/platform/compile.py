"""Platform compile command implementation.

Task ID: T014
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

from floe_core.cli.utils import ExitCode, error, error_exit, info

if TYPE_CHECKING:
    pass


@click.command(
    name="compile",
    help="Compile FloeSpec and Manifest into CompiledArtifacts (FR-010).",
    epilog="""
Examples:
    $ floe platform compile --spec floe.yaml --manifest manifest.yaml
    $ floe platform compile --output target/artifacts.json
    $ floe platform compile --enforcement-report report.json --enforcement-format json
    $ floe platform compile --enforcement-report report.sarif --enforcement-format sarif
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
def compile_command(
    spec: Path | None,
    manifest: Path | None,
    output: Path,
    enforcement_report: Path | None,
    enforcement_format: str,
) -> None:
    """Compile FloeSpec and Manifest into CompiledArtifacts.

    Loads the FloeSpec (floe.yaml) and PlatformManifest (manifest.yaml),
    compiles them into CompiledArtifacts, runs policy enforcement,
    and exports the results.

    Args:
        spec: Path to FloeSpec file (floe.yaml).
        manifest: Path to PlatformManifest file (manifest.yaml).
        output: Output path for CompiledArtifacts.
        enforcement_report: Output path for enforcement report.
        enforcement_format: Enforcement report format (json, sarif, html).
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

    # Create parent directories for output (FR-011)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Create parent directories for enforcement report (FR-014)
    if enforcement_report is not None:
        enforcement_report.parent.mkdir(parents=True, exist_ok=True)
        info(f"Enforcement report: {enforcement_report} (format: {enforcement_format})")

    try:
        # TODO: T015-T020 will implement actual compilation logic
        # For now, this is a skeleton that validates inputs
        #
        # Planned implementation:
        # 1. Load FloeSpec from spec path
        # 2. Load PlatformManifest from manifest path
        # 3. Compile into CompiledArtifacts
        # 4. Run policy enforcement
        # 5. Export CompiledArtifacts to output path
        # 6. Export enforcement report if requested

        # Placeholder: indicate skeleton is not yet fully implemented
        error(
            "Compile command skeleton. Full implementation in T015-T020.",
            spec=str(spec),
            manifest=str(manifest),
        )
        error_exit(
            "Compilation not yet implemented. See T015-T020.",
            exit_code=ExitCode.COMPILATION_ERROR,
        )

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
        error_exit(
            f"Compilation failed: {e}",
            exit_code=ExitCode.COMPILATION_ERROR,
        )


# Export for use in platform group
__all__: list[str] = ["compile_command"]
