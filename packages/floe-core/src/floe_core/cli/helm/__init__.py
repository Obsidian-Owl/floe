"""Helm management CLI commands.

This module provides CLI commands for Helm chart operations:
    floe helm generate: Generate values.yaml from CompiledArtifacts
    floe helm template: Preview rendered Helm templates (future)
    floe helm lint: Validate chart syntax (future)

The helm command group bridges floe configuration (CompiledArtifacts)
with Kubernetes deployment (Helm charts), enabling automated values
generation based on platform specification.

Example:
    $ floe helm generate --artifact target/compiled_artifacts.json --env staging
    $ floe helm generate --artifact oci://registry/floe:v1.0.0 --output values-staging.yaml

See Also:
    - specs/9b-helm-deployment/spec.md: Epic 9B specification
    - User Story 3: Generate Helm Values from Artifacts
"""

from __future__ import annotations

import click


@click.group(
    name="helm",
    help="Helm chart management commands for floe deployment.",
)
def helm() -> None:
    """Helm command group.

    Commands for generating Helm values from CompiledArtifacts,
    validating charts, and previewing rendered templates.
    """
    pass


# Subcommands will be added in future tasks:
# - generate.py (T062): floe helm generate
# - template.py: floe helm template (wrapper)
# - lint.py: floe helm lint (wrapper)


__all__: list[str] = ["helm"]
