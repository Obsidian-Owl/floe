"""Governance audit CLI command.

Task: T044 (stub), T046 (implementation)
Requirements: FR-025

Runs all governance checks (RBAC, secret scanning, policy enforcement)
and displays results to stdout.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

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
        NotImplementedError: Stub — implemented in T046.
    """
    raise NotImplementedError("T046: Implement create_governance_integrator")


@click.command(name="audit", help="Run governance audit checks.")
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
@click.option(
    "--enforcement-level",
    type=click.Choice(["off", "warn", "strict"]),
    default="strict",
    help="Enforcement level (default: strict).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run audit without failing on violations.",
)
def audit_command(
    manifest: str,
    spec: str,
    enforcement_level: str,
    dry_run: bool,
) -> None:
    """Run governance audit checks.

    Executes all governance checks (RBAC, secret scanning, policy enforcement,
    network policies) and displays the results. Exits non-zero if violations
    are found in strict mode.

    Raises:
        NotImplementedError: Stub — implemented in T046.
    """
    raise NotImplementedError("T046: Implement audit command")
