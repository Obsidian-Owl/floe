"""Command-line interface for the floe data platform.

This module provides the Click-based CLI with hierarchical command groups.

Command Groups:
    floe platform: Platform team commands (compile, test, publish, deploy, status)
    floe rbac: RBAC management commands (generate, validate, audit, diff)
    floe artifact: OCI registry artifact commands (push)

Data Team Commands (root level):
    floe compile: Data team spec validation (stub)
    floe validate: Data team floe.yaml validation (stub)
    floe run: Pipeline execution (stub)
    floe test: dbt test execution (stub)

Example:
    $ floe --help
    $ floe --version
    $ floe platform compile --spec floe.yaml --manifest manifest.yaml

Exit Codes:
    0: Success
    1: General error
    2: Usage error (invalid arguments)
    3: File not found
    4: Permission error
    5: Validation error
    6: Compilation error
    7: Network error

See Also:
    - specs/11-cli-unification/spec.md: CLI Unification specification
    - ADR-0047: CLI Architecture decision
"""

from __future__ import annotations

from floe_core.cli.main import cli, main
from floe_core.cli.utils import ExitCode, error, error_exit, success, warn

__all__: list[str] = [
    # Entry points
    "main",
    "cli",
    # Utilities
    "ExitCode",
    "error",
    "error_exit",
    "warn",
    "success",
]
