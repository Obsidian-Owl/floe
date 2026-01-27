"""Artifact pull CLI command.

Task ID: T055, T056
Phase: 6 - User Story 4 (Verification Policy Configuration)
User Story: US4 - Verification Policy Configuration
Requirements: FR-009, FR-010, FR-043

This module provides the `floe artifact pull` command for pulling
CompiledArtifacts from OCI registries with verification policy enforcement.

Example:
    $ floe artifact pull --registry oci://harbor.example.com/floe --tag v1.0.0

Environment Variables:
    FLOE_REGISTRY_USERNAME: Registry username for basic auth
    FLOE_REGISTRY_PASSWORD: Registry password for basic auth
    FLOE_REGISTRY_TOKEN: Bearer token for token auth
    FLOE_ENVIRONMENT: Environment name for verification policy lookup

See Also:
    - specs/8b-artifact-signing/spec.md: Artifact Signing specification
    - specs/08a-oci-client/spec.md: OCI Client specification
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success

if TYPE_CHECKING:
    from floe_core.schemas.oci import RegistryConfig
    from floe_core.schemas.signing import VerificationPolicy


@click.command(
    name="pull",
    help="""\b
Pull CompiledArtifacts from OCI registry (FR-043).

Pulls a CompiledArtifacts from an OCI-compliant registry and optionally
saves to a file. Applies verification policies based on the configured
environment.

The --environment flag (or FLOE_ENVIRONMENT env var) determines which
verification policy rules apply (e.g., production may enforce signatures
while development allows unsigned artifacts).

Authentication is resolved from environment variables:
  FLOE_REGISTRY_USERNAME / FLOE_REGISTRY_PASSWORD (basic auth)
  FLOE_REGISTRY_TOKEN (bearer token auth)
  AWS credentials (for ECR, uses IAM/IRSA)

Examples:
    $ floe artifact pull -r oci://harbor.example.com/floe -t v1.0.0

    $ floe artifact pull -r oci://harbor.example.com/floe -t v1.0.0 \\
        -o target/pulled_artifacts.json

    $ floe artifact pull -r oci://harbor.example.com/floe -t v1.0.0 \\
        --environment production
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
    help="Tag to pull (e.g., v1.0.0, latest-dev).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path for pulled artifact JSON. If not specified, outputs to stdout.",
)
@click.option(
    "--environment",
    "-e",
    type=str,
    default=None,
    envvar="FLOE_ENVIRONMENT",
    help="Environment name for verification policy lookup (e.g., production, staging, development).",
)
@click.option(
    "--manifest",
    "-m",
    type=click.Path(exists=True),
    default=None,
    help="Path to manifest.yaml with verification policy configuration.",
)
def pull_command(
    registry: str,
    tag: str,
    output: str | None,
    environment: str | None,
    manifest: str | None,
) -> None:
    """Pull CompiledArtifacts from OCI registry."""
    from floe_core.schemas.oci import RegistryConfig

    registry_config = _build_registry_config(registry, manifest)
    artifacts_json = _pull_from_registry(registry_config, registry, tag, environment)

    if output:
        from floe_core.cli.utils import validate_output_path

        validated_output = validate_output_path(output)
        _write_output(artifacts_json, validated_output)
        success(f"Pulled artifact saved to: {validated_output}")
    else:
        click.echo(artifacts_json)


def _build_registry_config(registry_uri: str, manifest_path: str | None) -> RegistryConfig:
    """Build RegistryConfig from URI, manifest, and environment."""
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
    from floe_core.schemas.secrets import SecretReference, SecretSource
    from floe_core.schemas.signing import VerificationPolicy

    verification_policy = None
    if manifest_path:
        verification_policy = _load_verification_policy(Path(manifest_path))

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
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        aws_role_arn = os.environ.get("AWS_ROLE_ARN", "")

        if aws_role_arn:
            auth = RegistryAuth(type=AuthType.AWS_IRSA, credentials_ref=None)
        elif aws_access_key:
            auth = RegistryAuth(type=AuthType.AWS_IRSA, credentials_ref=None)
        else:
            auth = RegistryAuth(type=AuthType.ANONYMOUS, credentials_ref=None)

    return RegistryConfig(
        uri=registry_uri,
        auth=auth,
        verification=verification_policy,
    )


def _load_verification_policy(manifest_path: Path) -> VerificationPolicy | None:
    import yaml
    from pydantic import ValidationError

    from floe_core.cli.utils import sanitize_error
    from floe_core.schemas.signing import VerificationPolicy

    try:
        with manifest_path.open() as f:
            manifest_data = yaml.safe_load(f)
    except FileNotFoundError:
        return None
    except yaml.YAMLError as e:
        error_exit(
            f"Invalid YAML in manifest: {sanitize_error(e)}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if manifest_data is None:
        return None

    artifacts_config = manifest_data.get("artifacts", {})
    verification_data = artifacts_config.get("verification")

    if verification_data is None:
        return None

    try:
        return VerificationPolicy.model_validate(verification_data)
    except ValidationError as e:
        error_exit(
            f"Invalid verification policy in manifest: {sanitize_error(e)}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )


def _handle_pull_error(e: Exception) -> NoReturn:
    """Handle pull errors with appropriate exit codes."""
    error_type = type(e).__name__

    error_mappings: list[tuple[str, str, ExitCode]] = [
        ("Authentication", f"Authentication failed: {e}", ExitCode.GENERAL_ERROR),
        ("Unavailable", f"Registry unavailable: {e}", ExitCode.GENERAL_ERROR),
        ("NotFound", f"Artifact not found: {e}", ExitCode.FILE_NOT_FOUND),
        ("SignatureVerification", f"Signature verification failed: {e}", ExitCode.VALIDATION_ERROR),
    ]

    for keyword, message, exit_code in error_mappings:
        if keyword in error_type:
            error_exit(message, exit_code=exit_code)

    error_exit(f"Pull failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _pull_from_registry(
    registry_config: RegistryConfig,
    registry: str,
    tag: str,
    environment: str | None,
) -> str:
    """Pull artifacts from OCI registry."""
    from floe_core.oci import OCIClient

    try:
        client = OCIClient.from_registry_config(registry_config)
        info(f"Pulling from {registry}:{tag}...")

        if environment:
            info(f"Using environment: {environment}")

        artifacts = client.pull(tag=tag, environment=environment)
        return artifacts.model_dump_json(indent=2)
    except Exception as e:
        _handle_pull_error(e)


def _write_output(content: str, output_path: Path) -> None:
    """Write pulled artifact to file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
    except Exception as e:
        error_exit(f"Failed to write output file: {e}", exit_code=ExitCode.GENERAL_ERROR)


__all__: list[str] = ["pull_command"]
