"""Platform team CLI commands.

This module provides CLI commands for Platform Team operations:
    floe platform compile: Compile FloeSpec + Manifest into CompiledArtifacts
    floe platform test: Run platform tests (stub)
    floe platform publish: Publish artifacts (stub)
    floe platform deploy: Deploy to environment (stub)
    floe platform status: Check deployment status (stub)

Example:
    $ floe platform compile --spec floe.yaml --manifest manifest.yaml
    $ floe platform compile --enforcement-report report.sarif --enforcement-format sarif

See Also:
    - specs/11-cli-unification/spec.md: CLI Unification specification
    - User Story 1: Unified Platform Compile with Enforcement Export
"""

from __future__ import annotations

import click


@click.group(
    name="platform",
    help="Platform team commands for governance and deployment.",
)
def platform() -> None:
    """Platform team command group.

    Commands for compiling configurations, running platform tests,
    publishing artifacts, and managing deployments.
    """
    pass


__all__: list[str] = ["platform"]
