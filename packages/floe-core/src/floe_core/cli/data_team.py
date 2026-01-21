"""Data Team stub commands.

Task ID: T054, T055, T056, T057
Phase: 7 - User Story 5 (Data Team Stubs)
User Story: US5 - Data Team Compile Stub
Requirements: FR-040, FR-041, FR-042, FR-043

This module provides stub commands for Data Team workflows.
These are placeholders for future implementation:
- compile: Data team spec compilation
- validate: Data team floe.yaml validation
- run: Pipeline execution
- test: dbt test execution

Example:
    $ floe compile  # Shows "not yet implemented" message
    $ floe validate --help  # Shows help text

See Also:
    - specs/11-cli-unification/spec.md: CLI Unification specification
    - specs/11-cli-unification/plan.md: Implementation plan
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
constraints and compile it for execution.

NOTE: This command is not yet implemented.
For Platform Team compilation, use: floe platform compile

Example:
    $ floe compile --spec floe.yaml
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


__all__: list[str] = [
    "compile_command",
    "validate_command",
    "run_command",
    "test_command",
]
