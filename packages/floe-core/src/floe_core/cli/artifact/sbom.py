"""Artifact SBOM CLI command.

Task ID: T046
Phase: 5 - User Story 3 (SBOM Generation and Attestation)
Requirements: FR-014, FR-016, FR-017

This module provides the `floe artifact sbom` command for generating,
attaching, and viewing Software Bill of Materials (SBOM) for OCI artifacts.

Example:
    $ floe artifact sbom --generate --project ./my-project
    $ floe artifact sbom --attach -r oci://harbor.example.com/floe -t v1.0.0
    $ floe artifact sbom --show -r oci://harbor.example.com/floe -t v1.0.0

External Dependencies:
    - syft: SBOM generation (https://github.com/anchore/syft)
    - cosign: Attestation attachment (https://github.com/sigstore/cosign)

See Also:
    - specs/8b-artifact-signing/spec.md: Artifact Signing specification
    - specs/8b-artifact-signing/research.md: syft/cosign patterns
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success, warning

if TYPE_CHECKING:
    pass


@click.command(
    name="sbom",
    help="""\b
Generate, attach, or view SBOM for OCI artifacts (FR-014, FR-016, FR-017).

SBOM (Software Bill of Materials) provides a list of all software
components and dependencies in an artifact. This command supports:

  --generate: Create SBOM from project directory using syft
  --attach: Attach SBOM as in-toto attestation to artifact
  --show: Display SBOM attached to artifact

Examples:
    # Generate SBOM for current project
    $ floe artifact sbom --generate

    # Generate SBOM for specific project directory
    $ floe artifact sbom --generate --project ./my-project

    # Generate and attach SBOM to artifact in one step
    $ floe artifact sbom --generate --attach \\
        -r oci://harbor.example.com/floe -t v1.0.0

    # Attach existing SBOM file to artifact
    $ floe artifact sbom --attach --sbom-file ./sbom.spdx.json \\
        -r oci://harbor.example.com/floe -t v1.0.0

    # View SBOM attached to artifact
    $ floe artifact sbom --show \\
        -r oci://harbor.example.com/floe -t v1.0.0
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--generate",
    is_flag=True,
    help="Generate SBOM from project directory using syft.",
)
@click.option(
    "--attach",
    is_flag=True,
    help="Attach SBOM as in-toto attestation to artifact.",
)
@click.option(
    "--show",
    is_flag=True,
    help="Display SBOM attached to artifact.",
)
@click.option(
    "--project",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=".",
    help="Project directory to scan for SBOM generation [default: current directory].",
)
@click.option(
    "--sbom-file",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Existing SBOM file to attach (instead of generating).",
)
@click.option(
    "--registry",
    "-r",
    type=str,
    help="OCI registry URI (required for --attach and --show).",
)
@click.option(
    "--tag",
    "-t",
    type=str,
    help="Tag of the artifact (required for --attach and --show).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    help="Output file for generated SBOM (default: stdout).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["spdx-json", "cyclonedx-json"]),
    default="spdx-json",
    help="SBOM output format [default: spdx-json].",
)
def sbom_command(
    generate: bool,
    attach: bool,
    show: bool,
    project: str,
    sbom_file: str | None,
    registry: str | None,
    tag: str | None,
    output: str | None,
    output_format: str,
) -> None:
    """Generate, attach, or view SBOM for OCI artifacts."""
    # Validate mutually exclusive options
    actions = [generate, attach, show]
    action_count = sum(actions)

    if action_count == 0:
        error_exit(
            "At least one action required: --generate, --attach, or --show",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    # Allow generate + attach together
    if show and (generate or attach):
        error_exit(
            "--show cannot be combined with --generate or --attach",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    # Validate registry/tag requirements
    if (attach or show) and not (registry and tag):
        error_exit(
            "--registry and --tag are required for --attach and --show",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if show:
        _show_sbom(registry, tag)
    elif generate and attach:
        _generate_and_attach(project, registry, tag, output_format)
    elif generate:
        _generate_sbom(project, output, output_format)
    elif attach:
        if not sbom_file:
            error_exit(
                "--sbom-file required when using --attach without --generate",
                exit_code=ExitCode.VALIDATION_ERROR,
            )
        _attach_sbom(sbom_file, registry, tag)


def _generate_sbom(
    project: str,
    output: str | None,
    output_format: str,
) -> dict[str, Any]:
    """Generate SBOM for project directory."""
    from floe_core.oci.attestation import (
        SBOMGenerationError,
        SyftNotFoundError,
        generate_sbom,
    )

    project_path = Path(project)
    info(f"Generating SBOM for {project_path}...")

    try:
        sbom = generate_sbom(project_path, output_format=output_format)
        package_count = len(sbom.get("packages", []))

        if output:
            output_path = Path(output)
            output_path.write_text(json.dumps(sbom, indent=2))
            success(f"SBOM written to {output_path} ({package_count} packages)")
        else:
            click.echo(json.dumps(sbom, indent=2))
            info(f"Generated SBOM with {package_count} packages")

        return sbom

    except SyftNotFoundError:
        error_exit(
            "syft CLI not found. Install with: brew install syft",
            exit_code=ExitCode.GENERAL_ERROR,
        )
    except SBOMGenerationError as e:
        error_exit(f"SBOM generation failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _attach_sbom(
    sbom_file: str,
    registry: str | None,
    tag: str | None,
) -> None:
    """Attach existing SBOM file as attestation."""
    from floe_core.oci.attestation import (
        AttestationAttachError,
        CosignNotFoundError,
        attach_attestation,
    )

    if not registry or not tag:
        error_exit(
            "--registry and --tag required for attachment",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    sbom_path = Path(sbom_file)
    artifact_ref = _build_artifact_ref(registry, tag)

    info(f"Attaching SBOM to {artifact_ref}...")

    try:
        attach_attestation(artifact_ref, sbom_path, keyless=True)
        success(f"SBOM attestation attached to {artifact_ref}")
    except CosignNotFoundError:
        error_exit(
            "cosign CLI not found. Install with: brew install cosign",
            exit_code=ExitCode.GENERAL_ERROR,
        )
    except AttestationAttachError as e:
        error_exit(f"Attestation attachment failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _generate_and_attach(
    project: str,
    registry: str | None,
    tag: str | None,
    output_format: str,
) -> None:
    """Generate SBOM and attach as attestation."""
    from floe_core.oci.attestation import (
        AttestationAttachError,
        CosignNotFoundError,
        SBOMGenerationError,
        SyftNotFoundError,
        attach_attestation,
        generate_sbom,
    )

    if not registry or not tag:
        error_exit(
            "--registry and --tag required for attachment",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    project_path = Path(project)
    artifact_ref = _build_artifact_ref(registry, tag)

    info(f"Generating SBOM for {project_path}...")

    try:
        sbom = generate_sbom(project_path, output_format=output_format)
        package_count = len(sbom.get("packages", []))
        info(f"Generated SBOM with {package_count} packages")

        # Write SBOM to temp file for attachment
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
        ) as f:
            json.dump(sbom, f, indent=2)
            temp_path = Path(f.name)

        try:
            info(f"Attaching SBOM to {artifact_ref}...")
            attach_attestation(artifact_ref, temp_path, keyless=True)
            success(f"SBOM attestation attached to {artifact_ref} ({package_count} packages)")
        finally:
            temp_path.unlink(missing_ok=True)

    except SyftNotFoundError:
        error_exit(
            "syft CLI not found. Install with: brew install syft",
            exit_code=ExitCode.GENERAL_ERROR,
        )
    except SBOMGenerationError as e:
        error_exit(f"SBOM generation failed: {e}", exit_code=ExitCode.GENERAL_ERROR)
    except CosignNotFoundError:
        error_exit(
            "cosign CLI not found. Install with: brew install cosign",
            exit_code=ExitCode.GENERAL_ERROR,
        )
    except AttestationAttachError as e:
        error_exit(f"Attestation attachment failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _show_sbom(
    registry: str | None,
    tag: str | None,
) -> None:
    """Display SBOM attached to artifact."""
    from floe_core.oci.attestation import (
        AttestationError,
        CosignNotFoundError,
        retrieve_sbom,
    )

    if not registry or not tag:
        error_exit(
            "--registry and --tag required",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    artifact_ref = _build_artifact_ref(registry, tag)
    info(f"Retrieving SBOM from {artifact_ref}...")

    try:
        sbom = retrieve_sbom(artifact_ref)

        if sbom is None:
            warning(f"No SBOM attestation found for {artifact_ref}")
            return

        package_count = len(sbom.get("packages", []))
        click.echo(json.dumps(sbom, indent=2))
        info(f"SBOM contains {package_count} packages")

    except CosignNotFoundError:
        error_exit(
            "cosign CLI not found. Install with: brew install cosign",
            exit_code=ExitCode.GENERAL_ERROR,
        )
    except AttestationError as e:
        error_exit(f"Failed to retrieve SBOM: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _build_artifact_ref(registry: str, tag: str) -> str:
    """Build OCI artifact reference from registry and tag."""
    # Strip oci:// prefix if present
    if registry.startswith("oci://"):
        registry = registry[6:]

    # Strip trailing slash
    registry = registry.rstrip("/")

    return f"{registry}:{tag}"


__all__: list[str] = ["sbom_command"]
