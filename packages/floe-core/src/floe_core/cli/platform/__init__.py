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

from floe_core.cli.platform.compile import compile_command
from floe_core.cli.platform.deploy import deploy_command
from floe_core.cli.platform.promote import promote_command
from floe_core.cli.platform.publish import publish_command
from floe_core.cli.platform.status import status_command
from floe_core.cli.platform.test_cmd import test_command


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


# Register subcommands
platform.add_command(compile_command)
platform.add_command(test_command)
platform.add_command(publish_command)
platform.add_command(deploy_command)
platform.add_command(promote_command)
platform.add_command(status_command)


__all__: list[str] = ["platform"]
