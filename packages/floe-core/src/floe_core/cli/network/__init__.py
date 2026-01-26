"""Network security management CLI commands.

This module provides CLI commands for Kubernetes NetworkPolicy management:
    floe network generate: Generate NetworkPolicy manifests from configuration
    floe network validate: Validate NetworkPolicy manifests
    floe network audit: Audit cluster NetworkPolicies against policy
    floe network diff: Compare expected vs deployed NetworkPolicies
    floe network check-cni: Verify CNI plugin supports NetworkPolicies

Example:
    $ floe network generate --config manifest.yaml --output target/network/
    $ floe network validate --config manifest.yaml --manifest-dir target/network/
    $ floe network audit --namespace floe --kubeconfig ~/.kube/config
    $ floe network diff --manifest-dir target/network/ --namespace floe
    $ floe network check-cni --kubeconfig ~/.kube/config

See Also:
    - specs/7c-network-pod-security/spec.md: Network and Pod Security specification
    - Epic 7C: Network and Pod Security
"""

from __future__ import annotations

import click

from floe_core.cli.network.audit import audit_command
from floe_core.cli.network.check_cni import check_cni_command
from floe_core.cli.network.diff import diff_command
from floe_core.cli.network.generate import generate_command
from floe_core.cli.network.validate import validate_command


@click.group(
    name="network",
    help="Network security management commands for Kubernetes NetworkPolicies.",
)
def network() -> None:
    """Network command group.

    Commands for generating, validating, auditing, and comparing
    Kubernetes NetworkPolicy configurations.
    """
    pass


# Register subcommands (T069-T078)
network.add_command(generate_command)
network.add_command(validate_command)
network.add_command(audit_command)
network.add_command(diff_command)
network.add_command(check_cni_command)


__all__: list[str] = ["network"]
