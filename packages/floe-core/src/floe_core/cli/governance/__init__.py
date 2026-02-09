"""Governance management CLI commands.

This module provides CLI commands for governance management:
    floe governance status: Display governance check status
    floe governance audit: Run governance audit checks
    floe governance report: Generate governance reports

Example:
    $ floe governance status
    $ floe governance audit --manifest manifest.yaml --spec floe.yaml
    $ floe governance report --format sarif --output report.sarif

Task: T044
Requirements: Infrastructure (CLI scaffolding)

See Also:
    - specs/3e-governance-integration/spec.md: Governance Integration specification
    - Epic 3E: Governance Integration
"""

from __future__ import annotations

import click

from floe_core.cli.governance.audit import audit_command
from floe_core.cli.governance.report import report_command
from floe_core.cli.governance.status import status_command


@click.group(
    name="governance",
    help="Governance management commands for policy enforcement, auditing, and reporting.",
    invoke_without_command=True,
)
@click.pass_context
def governance_group(ctx: click.Context) -> None:
    """Governance command group.

    Commands for checking governance status, running audits, and
    generating compliance reports.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Register subcommands
governance_group.add_command(status_command)
governance_group.add_command(audit_command)
governance_group.add_command(report_command)


__all__: list[str] = ["governance_group"]
