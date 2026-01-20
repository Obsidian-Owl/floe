"""RBAC management CLI commands.

This module provides CLI commands for Kubernetes RBAC management:
    floe rbac generate: Generate RBAC manifests from configuration
    floe rbac validate: Validate RBAC manifests
    floe rbac audit: Audit cluster RBAC against policy
    floe rbac diff: Compare expected vs deployed RBAC

Example:
    $ floe rbac generate --config manifest.yaml --output target/rbac/
    $ floe rbac validate --config manifest.yaml --manifest-dir target/rbac/
    $ floe rbac audit --namespace floe --kubeconfig ~/.kube/config
    $ floe rbac diff --manifest-dir target/rbac/ --namespace floe

See Also:
    - specs/11-cli-unification/spec.md: CLI Unification specification
    - User Story 2: RBAC Command Migration
    - Epic 7B: K8s RBAC Plugin
"""

from __future__ import annotations

import click

from floe_core.cli.rbac.audit import audit_command
from floe_core.cli.rbac.diff import diff_command
from floe_core.cli.rbac.generate import generate_command
from floe_core.cli.rbac.validate import validate_command


@click.group(
    name="rbac",
    help="RBAC management commands for Kubernetes security.",
)
def rbac() -> None:
    """RBAC command group.

    Commands for generating, validating, auditing, and comparing
    Kubernetes Role-Based Access Control configurations.
    """
    pass


# Register subcommands
rbac.add_command(generate_command)
rbac.add_command(validate_command)
rbac.add_command(audit_command)
rbac.add_command(diff_command)


__all__: list[str] = ["rbac"]
