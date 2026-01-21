"""Platform test command stub.

Task ID: T022
Phase: 3 - User Story 1 (Platform Compile MVP)
Requirements: FR-016 - `floe platform test` MUST exist as a command stub

This is a placeholder command. Full implementation deferred to a future epic.

Example:
    $ floe platform test
    $ floe platform test --help
"""

from __future__ import annotations

import click

from floe_core.cli.utils import info


@click.command(
    name="test",
    help="Run platform tests (FR-016). [STUB - not yet implemented]",
)
def test_command() -> None:
    """Run platform tests.

    This is a stub command. Full implementation is deferred to a future epic.
    """
    info("Platform test command is not yet implemented.")
    info("This is a placeholder for future functionality.")
    raise click.ClickException("Command not yet implemented. See roadmap for timeline.")


__all__: list[str] = ["test_command"]
