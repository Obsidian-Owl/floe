"""Governance report CLI command.

Task: T047
Requirements: FR-026

Generates governance compliance reports in SARIF, JSON, or HTML format.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from floe_core.enforcement.exporters import (  # noqa: F401
    export_html,
    export_json,
    export_sarif,
)

if TYPE_CHECKING:
    from floe_core.governance.integrator import GovernanceIntegrator

FORMAT_TO_EXTENSION: dict[str, str] = {
    "sarif": ".sarif",
    "json": ".json",
    "html": ".html",
}


def create_governance_integrator(
    manifest_path: Path,
    spec_path: Path,
) -> GovernanceIntegrator:
    """Create GovernanceIntegrator from manifest and spec files.

    Loads the manifest YAML, extracts GovernanceConfig, and creates
    a GovernanceIntegrator with the appropriate plugins.

    Args:
        manifest_path: Path to manifest.yaml
        spec_path: Path to floe.yaml spec

    Returns:
        Configured GovernanceIntegrator instance.
    """
    import yaml

    from floe_core.governance.integrator import GovernanceIntegrator
    from floe_core.schemas.manifest import GovernanceConfig

    manifest_data = yaml.safe_load(manifest_path.read_text())
    governance_data = manifest_data.get("governance", {})
    governance_config = GovernanceConfig(**governance_data)

    return GovernanceIntegrator(
        governance_config=governance_config,
        identity_plugin=None,
    )


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
