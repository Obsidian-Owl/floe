"""Data Team validate command.

Task ID: T054
Phase: 7 - User Story 5 (Data Team Stubs)
User Story: US5 - Data Team Validate Stub
Requirements: FR-041

This command will validate floe.yaml against the platform
manifest schema without compiling. Currently a stub.

Example:
    $ floe validate --spec floe.yaml
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
    name="validate",
    help="""\b
Validate Data Team floe.yaml (FR-041).

This command will validate your floe.yaml against the
platform manifest schema without compiling.

NOTE: This command is not yet implemented.

Example:
    $ floe validate --spec floe.yaml
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def validate_command() -> None:
    """Validate Data Team floe.yaml (stub).

    Currently outputs a "not yet implemented" message.
    Full implementation will validate floe.yaml against
    manifest.yaml constraints.
    """
    _stub_message("validate")


__all__: list[str] = ["validate_command"]
