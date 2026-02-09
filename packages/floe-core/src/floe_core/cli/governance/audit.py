"""Governance audit CLI command.

Task: T046
Requirements: FR-025

Runs all governance checks (RBAC, secret scanning, policy enforcement)
and displays results to stdout without producing compiled artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, cast

import click

from floe_core.cli.governance._factory import (
    create_governance_integrator,
    get_token_and_principal,
)


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
    are found and the result does not pass.
    """
    integrator = create_governance_integrator(
        manifest_path=Path(manifest),
        spec_path=Path(spec),
    )

    token, principal = get_token_and_principal()

    result = integrator.run_checks(
        project_dir=Path("."),
        token=token,
        principal=principal,
        dry_run=dry_run,
        enforcement_level=cast(Literal["off", "warn", "strict"], enforcement_level),
    )

    # Display results
    if result.passed:
        click.echo("Governance audit passed. All checks clean.")
    else:
        click.echo("Governance audit failed.")
        click.echo("")
        for violation in result.violations:
            severity_tag = violation.severity.upper()
            click.echo(f"  [{severity_tag}] {violation.error_code}: {violation.message}")
            click.echo(f"         Model: {violation.model_name}")
            click.echo(f"         Type:  {violation.policy_type}")
            if violation.suggestion:
                click.echo(f"         Fix:   {violation.suggestion}")
            click.echo("")

        total = len(result.violations)
        click.echo(f"Total violations: {total}")
        sys.exit(1)
