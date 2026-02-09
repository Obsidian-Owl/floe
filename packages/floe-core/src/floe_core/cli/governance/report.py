"""Governance report CLI command.

Task: T044 (stub), T047 (implementation)
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


def create_governance_integrator(
    manifest_path: Path,
    spec_path: Path,
) -> GovernanceIntegrator:
    """Create GovernanceIntegrator from manifest and spec files.

    Args:
        manifest_path: Path to manifest.yaml
        spec_path: Path to floe.yaml spec

    Returns:
        Configured GovernanceIntegrator instance.

    Raises:
        NotImplementedError: Stub — implemented in T047.
    """
    raise NotImplementedError("T047: Implement create_governance_integrator")


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

    Raises:
        NotImplementedError: Stub — implemented in T047.
    """
    raise NotImplementedError("T047: Implement report command")
