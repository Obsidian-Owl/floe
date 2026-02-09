"""Governance audit CLI command.

Task: T046
Requirements: FR-025

Runs all governance checks (RBAC, secret scanning, policy enforcement)
and displays results to stdout without producing compiled artifacts.
"""

from __future__ import annotations

import sys
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

    result = integrator.run_checks(
        project_dir=Path("."),
        token=None,
        principal=None,
        dry_run=dry_run,
        enforcement_level=enforcement_level,
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
