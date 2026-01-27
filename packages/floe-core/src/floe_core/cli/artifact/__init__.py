"""Artifact management CLI commands.

This module provides CLI commands for OCI registry artifact operations:
    floe artifact push: Push CompiledArtifacts to OCI registry

Example:
    $ floe artifact push --artifact target/compiled_artifacts.json --registry ghcr.io/org/floe

See Also:
    - specs/11-cli-unification/spec.md: CLI Unification specification
    - User Story 4: Artifact Push Command Migration
"""

from __future__ import annotations

import click

from floe_core.cli.artifact.push import push_command
from floe_core.cli.artifact.sign import sign_command
from floe_core.cli.artifact.verify import verify_command


@click.group(
    name="artifact",
    help="OCI artifact management commands.",
)
def artifact() -> None:
    """Artifact command group.

    Commands for pushing and managing CompiledArtifacts
    in OCI registries.
    """
    pass


# Register subcommands
artifact.add_command(push_command)
artifact.add_command(sign_command)
artifact.add_command(verify_command)


__all__: list[str] = ["artifact"]
