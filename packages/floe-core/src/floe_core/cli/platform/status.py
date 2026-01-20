"""Platform status command stub.

Task ID: T025
Phase: 3 - User Story 1 (Platform Compile MVP)
Requirements: FR-019 - `floe platform status` MUST exist as a command stub

This is a placeholder command. Full implementation deferred to a future epic.

Example:
    $ floe platform status
    $ floe platform status --help
"""

from __future__ import annotations

import click

from floe_core.cli.utils import info


@click.command(
    name="status",
    help="Check deployment status (FR-019). [STUB - not yet implemented]",
)
def status_command() -> None:
    """Check deployment status.

    This is a stub command. Full implementation is deferred to a future epic.
    """
    info("Platform status command is not yet implemented.")
    info("This is a placeholder for future functionality.")
    raise click.ClickException("Command not yet implemented. See roadmap for timeline.")


__all__: list[str] = ["status_command"]
