"""Data Team CLI commands.

Task ID: T053-T058
Phase: 7 - User Story 5 (Data Team Stubs)
User Story: US5 - Data Team Command Stubs
Requirements: FR-040, FR-041, FR-042, FR-043

This package provides stub commands for Data Team workflows.
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
    - ADR-0047: CLI Architecture (target structure)
"""

from __future__ import annotations

from floe_core.cli.data.compile import compile_command
from floe_core.cli.data.run import run_command
from floe_core.cli.data.test_cmd import test_command
from floe_core.cli.data.validate import validate_command

__all__: list[str] = [
    "compile_command",
    "validate_command",
    "run_command",
    "test_command",
]
