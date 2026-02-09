"""Main entry point for the floe CLI.

This module provides the Click-based CLI with hierarchical command groups.

Command Groups:
    floe platform: Platform team commands (compile, test, publish, deploy, status)
    floe rbac: RBAC management commands (generate, validate, audit, diff)
    floe artifact: OCI registry artifact commands (push)
    floe sla: SLA compliance reporting commands (report)
    floe governance: Governance management commands (status, audit, report)

Data Team Commands (root level):
    floe compile: Data team spec compilation (stub)
    floe validate: Data team floe.yaml validation (stub)
    floe run: Pipeline execution (stub)
    floe test: dbt test execution (stub)

Example:
    $ floe --help
    $ floe platform compile --spec floe.yaml --manifest manifest.yaml
    $ floe rbac generate --config manifest.yaml

See Also:
    - spec.md: Epic 11 (CLI Unification) specification
    - ADR-0047: CLI Architecture decision
"""

from __future__ import annotations

import sys
from importlib.metadata import version as get_version
from typing import TYPE_CHECKING

import click

# Import command groups
from floe_core.cli.artifact import artifact
from floe_core.cli.data import (
    compile_command,
    run_command,
    test_command,
    validate_command,
)
from floe_core.cli.governance import governance_group
from floe_core.cli.helm import helm
from floe_core.cli.network import network
from floe_core.cli.platform import platform
from floe_core.cli.rbac import rbac
from floe_core.cli.sla.report import report as sla_report

if TYPE_CHECKING:
    pass


def _get_version() -> str:
    """Get the floe-core package version.

    Returns:
        Version string from package metadata, or 'unknown' if not installed.
    """
    try:
        return get_version("floe-core")
    except Exception:
        return "unknown"


@click.group(
    name="floe",
    help="floe - Open platform for building internal data platforms.",
    epilog="Use 'floe <command> --help' for command-specific help.",
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
)
@click.version_option(
    version=_get_version(),
    prog_name="floe",
    message="%(prog)s %(version)s",
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Root command group for the floe CLI.

    The floe CLI provides commands for both Platform Teams and Data Teams
    to manage data platform configuration, governance, and deployment.
    """
    # Ensure context object exists for passing state between commands
    ctx.ensure_object(dict)


# Register command groups
cli.add_command(platform)
cli.add_command(rbac)
cli.add_command(network)
cli.add_command(artifact)
cli.add_command(helm)
cli.add_command(governance_group)


# Register SLA command group
@cli.group(name="sla", help="SLA compliance reporting commands.")
def sla() -> None:
    """SLA compliance reporting command group.

    Provides commands for generating SLA compliance reports from
    contract monitoring data (Epic 3D).
    """
    pass


sla.add_command(sla_report)

# Register Data Team stub commands (root level)
cli.add_command(compile_command)
cli.add_command(validate_command)
cli.add_command(run_command)
cli.add_command(test_command)


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the floe CLI.

    Args:
        argv: Command-line arguments (uses sys.argv if None).
    """
    try:
        # Click handles argument parsing and dispatch
        cli(args=argv, standalone_mode=False)
    except click.ClickException as e:
        e.show()
        sys.exit(e.exit_code)
    except click.Abort:
        click.echo("Aborted!", err=True)
        sys.exit(1)
    except Exception as e:
        # Log unexpected errors to stderr
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
