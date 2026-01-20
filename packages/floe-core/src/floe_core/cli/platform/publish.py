"""Platform publish command stub.

Task ID: T023
Phase: 3 - User Story 1 (Platform Compile MVP)
Requirements: FR-017 - `floe platform publish` MUST exist as a command stub

This is a placeholder command. Full implementation deferred to a future epic.

Example:
    $ floe platform publish
    $ floe platform publish --help
"""

from __future__ import annotations

import click

from floe_core.cli.utils import info


@click.command(
    name="publish",
    help="Publish compiled artifacts to registry (FR-017). [STUB - not yet implemented]",
)
def publish_command() -> None:
    """Publish compiled artifacts to OCI registry.

    This is a stub command. Full implementation is deferred to a future epic.
    """
    info("Platform publish command is not yet implemented.")
    info("This is a placeholder for future functionality.")
    raise click.ClickException("Command not yet implemented. See roadmap for timeline.")


__all__: list[str] = ["publish_command"]
