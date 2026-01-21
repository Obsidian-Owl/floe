"""Data Team run command.

Task ID: T055
Phase: 7 - User Story 5 (Data Team Stubs)
User Story: US5 - Data Team Run Stub
Requirements: FR-042

This command will execute the data pipeline based on the
compiled artifacts and platform configuration. Currently a stub.

Example:
    $ floe run --target production
"""

from __future__ import annotations

import click


def _stub_message(command: str, alternative: str | None = None) -> None:
    """Output stub message to stderr.

    Args:
        command: Name of the stub command.
        alternative: Optional alternative command to suggest.
    """
    msg = f"This command ({command}) is not yet implemented."
    if alternative:
        msg += f" See {alternative} for Platform Team usage."
    click.echo(msg, err=True)


@click.command(
    name="run",
    help="""\b
Run Data Team pipeline (FR-042).

This command will execute your data pipeline based on the
compiled artifacts and platform configuration.

NOTE: This command is not yet implemented.

Example:
    $ floe run --target production
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def run_command() -> None:
    """Run Data Team pipeline (stub).

    Currently outputs a "not yet implemented" message.
    Full implementation will trigger pipeline execution
    via the configured orchestrator.
    """
    _stub_message("run")


__all__: list[str] = ["run_command"]
