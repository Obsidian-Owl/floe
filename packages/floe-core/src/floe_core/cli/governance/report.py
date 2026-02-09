"""Governance report CLI command.

Task: T047
Requirements: FR-026

Generates governance compliance reports in SARIF, JSON, or HTML format.
"""

from __future__ import annotations

from pathlib import Path

import click

from floe_core.cli.governance._factory import create_governance_integrator
from floe_core.enforcement.exporters import (  # noqa: F401
    export_html,
    export_json,
    export_sarif,
)

FORMAT_TO_EXTENSION: dict[str, str] = {
    "sarif": ".sarif",
    "json": ".json",
    "html": ".html",
}


@click.command(name="report", help="Generate governance compliance report.")
@click.option(
    "--format",
    "report_format",
    required=True,
    type=click.Choice(["sarif", "json", "html"]),
    help="Report format (sarif, json, or html).",
)
@click.option(
    "--output",
    "output_path",
    required=False,
    type=click.Path(),
    default=None,
    help="Output file path (default: target/governance-report.<format>).",
)
@click.option(
    "--manifest",
    required=True,
    type=click.Path(),
    help="Path to manifest.yaml",
)
@click.option(
    "--spec",
    required=True,
    type=click.Path(),
    help="Path to floe.yaml spec",
)
def report_command(
    report_format: str,
    output_path: str | None,
    manifest: str,
    spec: str,
) -> None:
    """Generate governance compliance report.

    Runs governance checks and exports results in the specified format.
    """
    integrator = create_governance_integrator(
        manifest_path=Path(manifest),
        spec_path=Path(spec),
    )

    result = integrator.run_checks(
        project_dir=Path("."),
        token=None,
        principal=None,
        dry_run=False,
        enforcement_level="strict",
    )

    # Determine output path
    if output_path is not None:
        resolved_path = Path(output_path)
    else:
        ext = FORMAT_TO_EXTENSION[report_format]
        resolved_path = Path(f"target/governance-report{ext}")

    # Delegate to the appropriate exporter
    if report_format == "sarif":
        written_path = export_sarif(result, resolved_path)
    elif report_format == "html":
        written_path = export_html(result, resolved_path)
    else:
        written_path = export_json(result, resolved_path)

    click.echo(f"Report written to {written_path}")
