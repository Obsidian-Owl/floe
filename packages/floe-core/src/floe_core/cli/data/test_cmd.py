"""Data Team test command.

Task ID: T056
Phase: 7 - User Story 5 (Data Team Stubs)
User Story: US5 - Data Team Test Stub
Requirements: FR-043

This command will execute dbt tests for data models
to validate data quality and constraints. Currently a stub.

Note: Named test_cmd.py (not test.py) to avoid pytest collection conflicts.

Example:
    $ floe test --select customers
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
    name="test",
    help="""\b
Run dbt tests (FR-043).

This command will execute dbt tests for your data models
to validate data quality and constraints.

NOTE: This command is not yet implemented.

Example:
    $ floe test --select customers
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def test_command() -> None:
    """Run dbt tests (stub).

    Currently outputs a "not yet implemented" message.
    Full implementation will execute dbt test command
    with the configured compute target.
    """
    _stub_message("test")


__all__: list[str] = ["test_command"]
