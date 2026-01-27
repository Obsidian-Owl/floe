"""Artifact management CLI commands.

This module provides CLI commands for OCI registry artifact operations:
    floe artifact pull: Pull CompiledArtifacts from OCI registry
    floe artifact push: Push CompiledArtifacts to OCI registry
    floe artifact sign: Sign artifacts with Sigstore
    floe artifact verify: Verify artifact signatures
    floe artifact inspect: Inspect artifact metadata and attestations
    floe artifact sbom: Generate, attach, and view SBOMs

Example:
    $ floe artifact pull -r oci://harbor.example.com/floe -t v1.0.0 --environment production
    $ floe artifact push --artifact target/compiled_artifacts.json --registry ghcr.io/org/floe
    $ floe artifact sign -r oci://harbor.example.com/floe -t v1.0.0
    $ floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0
    $ floe artifact inspect -r oci://harbor.example.com/floe -t v1.0.0 --show-sbom
    $ floe artifact sbom --generate --attach -r oci://harbor.example.com/floe -t v1.0.0

See Also:
    - specs/11-cli-unification/spec.md: CLI Unification specification
    - specs/8b-artifact-signing/spec.md: Artifact Signing specification
    - User Story 4: Verification Policy Configuration
"""

from __future__ import annotations

import click

from floe_core.cli.artifact.inspect import inspect_command
from floe_core.cli.artifact.pull import pull_command
from floe_core.cli.artifact.push import push_command
from floe_core.cli.artifact.sbom import sbom_command
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
artifact.add_command(inspect_command)
artifact.add_command(pull_command)
artifact.add_command(push_command)
artifact.add_command(sbom_command)
artifact.add_command(sign_command)
artifact.add_command(verify_command)


__all__: list[str] = ["artifact"]
