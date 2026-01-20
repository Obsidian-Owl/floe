"""Platform deploy command stub.

Task ID: T024
Phase: 3 - User Story 1 (Platform Compile MVP)
Requirements: FR-018 - `floe platform deploy` MUST exist as a command stub

This is a placeholder command. Full implementation deferred to a future epic.

Example:
    $ floe platform deploy
    $ floe platform deploy --help
"""

from __future__ import annotations

import click

from floe_core.cli.utils import info


@click.command(
    name="deploy",
    help="Deploy platform to environment (FR-018). [STUB - not yet implemented]",
)
def deploy_command() -> None:
    """Deploy platform to target environment.

    This is a stub command. Full implementation is deferred to a future epic.
    """
    info("Platform deploy command is not yet implemented.")
    info("This is a placeholder for future functionality.")
    raise click.ClickException("Command not yet implemented. See roadmap for timeline.")


__all__: list[str] = ["deploy_command"]
