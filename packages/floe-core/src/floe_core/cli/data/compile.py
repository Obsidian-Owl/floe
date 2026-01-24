"""Data Team compile command.

Task ID: T053
Phase: 7 - User Story 5 (Data Team Stubs)
User Story: US5 - Data Team Compile Stub
Requirements: FR-040

This command will validate floe.yaml against platform constraints
and compile it for execution. Currently a stub.

Example:
    $ floe compile --spec floe.yaml
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
    name="compile",
    help="""\b
Compile Data Team floe.yaml (FR-040).

This command will validate your floe.yaml against platform
constraints and compile it for execution, including data contract validation.

NOTE: This command is not yet implemented.
For Platform Team compilation, use: floe platform compile

Options (planned):
  --skip-contracts    Skip data contract validation
  --drift-detection   Enable schema drift detection against actual tables

Example:
    $ floe compile --spec floe.yaml
    $ floe compile --spec floe.yaml --skip-contracts
    $ floe compile --spec floe.yaml --drift-detection
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def compile_command() -> None:
    """Compile Data Team spec (stub).

    Currently outputs a "not yet implemented" message.
    Full implementation will validate floe.yaml against manifest.yaml
    constraints and produce execution artifacts.
    """
    _stub_message("compile", "floe platform compile")


__all__: list[str] = ["compile_command"]
