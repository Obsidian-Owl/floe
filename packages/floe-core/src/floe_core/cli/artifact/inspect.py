"""Artifact inspect CLI command.

Task ID: T047
Phase: 5 - User Story 3 (SBOM Generation and Attestation)
Requirements: FR-017

This module provides the `floe artifact inspect` command for viewing
artifact metadata, signatures, and SBOM attestations in OCI registries.

Example:
    $ floe artifact inspect -r oci://harbor.example.com/floe -t v1.0.0
    $ floe artifact inspect -r oci://harbor.example.com/floe -t v1.0.0 --show-sbom

See Also:
    - specs/8b-artifact-signing/spec.md: Artifact Signing specification
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, NoReturn

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success, warning

if TYPE_CHECKING:
    from floe_core.schemas.oci import RegistryConfig


@click.command(
    name="inspect",
    help="""\b
Inspect an artifact in OCI registry.

Displays artifact metadata including:
- Digest and size
- Creation timestamp
- Labels and annotations
- Signature status (if signed)
- SBOM information (with --show-sbom)

Examples:
    # Basic inspection
    $ floe artifact inspect -r oci://harbor.example.com/floe -t v1.0.0

    # Show SBOM if present
    $ floe artifact inspect -r oci://harbor.example.com/floe -t v1.0.0 --show-sbom

    # Show signature details
    $ floe artifact inspect -r oci://harbor.example.com/floe -t v1.0.0 --show-signatures
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--registry",
    "-r",
    type=str,
    required=True,
    help="OCI registry URI (e.g., oci://harbor.example.com/namespace).",
)
@click.option(
    "--tag",
    "-t",
    type=str,
    required=True,
    help="Tag of the artifact to inspect (e.g., v1.0.0).",
)
@click.option(
    "--show-sbom",
    is_flag=True,
    help="Display SBOM attestation if present.",
)
@click.option(
    "--show-signatures",
    is_flag=True,
    help="Display detailed signature information.",
)
@click.option(
    "--json-output",
    "json_output",
    is_flag=True,
    help="Output as JSON instead of formatted text.",
)
def inspect_command(
    registry: str,
    tag: str,
    show_sbom: bool,
    show_signatures: bool,
    json_output: bool,
) -> None:
    """Inspect an artifact in OCI registry."""
    registry_config = _build_registry_config(registry)

    artifact_info = _inspect_artifact(registry_config, registry, tag)

    if show_sbom:
        sbom_info = _get_sbom_info(registry, tag)
        artifact_info["sbom"] = sbom_info

    if show_signatures:
        sig_info = _get_signature_info(registry, tag)
        artifact_info["signatures"] = sig_info

    if json_output:
        click.echo(json.dumps(artifact_info, indent=2, default=str))
    else:
        _print_formatted(artifact_info, show_sbom, show_signatures)


def _inspect_artifact(
    registry_config: RegistryConfig,
    registry: str,
    tag: str,
) -> dict:
    """Fetch artifact metadata from registry."""
    from floe_core.oci import OCIClient

    try:
        client = OCIClient.from_registry_config(registry_config)
        manifest = client.inspect(tag=tag)

        return {
            "reference": f"{registry}:{tag}",
            "digest": manifest.digest,
            "size": manifest.size,
            "artifact_type": manifest.artifact_type,
            "created": manifest.created_at.isoformat() if manifest.created_at else None,
            "annotations": dict(manifest.annotations) if manifest.annotations else {},
        }

    except Exception as e:
        error_exit(f"Inspection failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _get_sbom_info(registry: str, tag: str) -> dict | None:
    """Retrieve SBOM information from artifact."""
    from floe_core.oci.attestation import (
        AttestationError,
        CosignNotFoundError,
        retrieve_sbom,
    )

    artifact_ref = _build_artifact_ref(registry, tag)

    try:
        sbom = retrieve_sbom(artifact_ref)

        if sbom is None:
            return None

        packages = sbom.get("packages", [])
        return {
            "format": "SPDX",
            "package_count": len(packages),
            "packages": [
                {
                    "name": pkg.get("name", "unknown"),
                    "version": pkg.get("versionInfo", "unknown"),
                }
                for pkg in packages[:10]  # Limit to first 10 for summary
            ],
            "truncated": len(packages) > 10,
            "full_sbom": sbom if len(packages) <= 10 else None,
        }

    except CosignNotFoundError:
        return {"error": "cosign CLI not installed"}
    except AttestationError as e:
        return {"error": str(e)}


def _get_signature_info(registry: str, tag: str) -> dict | None:
    """Retrieve signature information from artifact."""
    # Get signature details from annotations
    # This is a simplified version - full implementation would verify
    artifact_ref = _build_artifact_ref(registry, tag)

    try:
        from floe_core.oci.attestation import retrieve_attestations

        attestations = retrieve_attestations(artifact_ref)

        # Check for signature annotations in the artifact
        return {
            "signed": len(attestations) > 0,
            "attestation_count": len(attestations),
            "attestations": [
                {
                    "predicate_type": att.predicate_type,
                    "subjects": [s.name for s in att.subject],
                }
                for att in attestations
            ],
        }

    except Exception as e:
        return {"error": str(e)}


def _print_formatted(
    info: dict,
    show_sbom: bool,
    show_signatures: bool,
) -> None:
    """Print formatted inspection output."""
    click.echo(click.style("Artifact Information", bold=True))
    click.echo(f"  Reference: {info['reference']}")
    click.echo(f"  Digest:    {info['digest']}")
    click.echo(f"  Size:      {_format_size(info['size'])}")
    if info.get("created"):
        click.echo(f"  Created:   {info['created']}")

    annotations = info.get("annotations", {})
    if annotations:
        click.echo()
        click.echo(click.style("Annotations", bold=True))
        for key, value in annotations.items():
            # Truncate long values
            display_value = value[:60] + "..." if len(str(value)) > 60 else value
            click.echo(f"  {key}: {display_value}")

    if show_sbom:
        click.echo()
        click.echo(click.style("SBOM Information", bold=True))
        sbom = info.get("sbom")
        if sbom is None:
            click.echo("  No SBOM attestation found")
        elif "error" in sbom:
            click.echo(f"  Error: {sbom['error']}")
        else:
            click.echo(f"  Format:   {sbom['format']}")
            click.echo(f"  Packages: {sbom['package_count']}")
            if sbom.get("packages"):
                click.echo("  Top packages:")
                for pkg in sbom["packages"]:
                    click.echo(f"    - {pkg['name']}@{pkg['version']}")
            if sbom.get("truncated"):
                click.echo(f"  ... and {sbom['package_count'] - 10} more")

    if show_signatures:
        click.echo()
        click.echo(click.style("Signature Information", bold=True))
        sigs = info.get("signatures")
        if sigs is None:
            click.echo("  No signature information available")
        elif "error" in sigs:
            click.echo(f"  Error: {sigs['error']}")
        else:
            click.echo(f"  Signed: {sigs['signed']}")
            click.echo(f"  Attestations: {sigs['attestation_count']}")
            for att in sigs.get("attestations", []):
                click.echo(f"    - Type: {att['predicate_type']}")


def _format_size(size_bytes: int) -> str:
    """Format byte size to human readable."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _build_artifact_ref(registry: str, tag: str) -> str:
    """Build OCI artifact reference from registry and tag."""
    if registry.startswith("oci://"):
        registry = registry[6:]
    registry = registry.rstrip("/")
    return f"{registry}:{tag}"


def _build_registry_config(registry_uri: str) -> RegistryConfig:
    """Build RegistryConfig from URI and environment."""
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
    from floe_core.schemas.secrets import SecretReference, SecretSource

    username = os.environ.get("FLOE_REGISTRY_USERNAME", "")
    password = os.environ.get("FLOE_REGISTRY_PASSWORD", "")
    token = os.environ.get("FLOE_REGISTRY_TOKEN", "")

    if token:
        auth = RegistryAuth(
            type=AuthType.TOKEN,
            credentials_ref=SecretReference(
                source=SecretSource.ENV,
                name="registry-token",
            ),
        )
    elif username and password:
        auth = RegistryAuth(
            type=AuthType.BASIC,
            credentials_ref=SecretReference(
                source=SecretSource.ENV,
                name="registry-credentials",
            ),
        )
    else:
        aws_role_arn = os.environ.get("AWS_ROLE_ARN", "")
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")

        if aws_role_arn or aws_access_key:
            auth = RegistryAuth(type=AuthType.AWS_IRSA, credentials_ref=None)
        else:
            auth = RegistryAuth(type=AuthType.ANONYMOUS, credentials_ref=None)

    return RegistryConfig(
        uri=registry_uri,
        auth=auth,
    )


__all__: list[str] = ["inspect_command"]
