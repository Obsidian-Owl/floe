"""Artifact push CLI command.

Task ID: T049, T050, T051, T052
Phase: 6 - User Story 4 (Artifact Push)
User Story: US4 - Artifact Push Command Migration
Requirements: FR-040, FR-041, FR-042

This module provides the `floe artifact push` command for pushing
CompiledArtifacts to OCI registries.

Example:
    $ floe artifact push --artifact target/compiled_artifacts.json \\
        --registry oci://harbor.example.com/floe \\
        --tag v1.0.0

Environment Variables:
    FLOE_REGISTRY_USERNAME: Registry username for basic auth
    FLOE_REGISTRY_PASSWORD: Registry password for basic auth
    FLOE_REGISTRY_TOKEN: Bearer token for token auth

See Also:
    - specs/11-cli-unification/spec.md: CLI Unification specification
    - specs/08a-oci-client/spec.md: OCI Client specification
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts
    from floe_core.schemas.oci import RegistryConfig


@click.command(
    name="push",
    help="""\b
Push CompiledArtifacts to OCI registry (FR-040).

Pushes a CompiledArtifacts JSON file to an OCI-compliant registry
with the specified tag. Supports semver tags (immutable) and
mutable tags (latest-*, dev-*, snapshot-*).

Authentication is resolved from environment variables:
  FLOE_REGISTRY_USERNAME / FLOE_REGISTRY_PASSWORD (basic auth)
  FLOE_REGISTRY_TOKEN (bearer token auth)
  AWS credentials (for ECR, uses IAM/IRSA)

Examples:
    $ floe artifact push -a target/compiled_artifacts.json \\
        -r oci://harbor.example.com/floe -t v1.0.0

    $ floe artifact push --artifact compiled.json \\
        --registry oci://ghcr.io/org/floe --tag latest-dev
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--artifact",
    "-a",
    type=click.Path(exists=False),
    required=True,
    help="Path to CompiledArtifacts JSON file.",
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
    help="Tag for the artifact (e.g., v1.0.0, latest-dev).",
)
@click.option(
    "--sign/--no-sign",
    default=False,
    help="Sign the artifact after push using keyless (OIDC) signing.",
)
@click.option(
    "--oidc-issuer",
    type=str,
    default="https://token.actions.githubusercontent.com",
    help="OIDC issuer URL for signing (only used with --sign).",
)
def push_command(
    artifact: str,
    registry: str,
    tag: str,
    sign: bool,
    oidc_issuer: str,
) -> None:
    """Push CompiledArtifacts to OCI registry.

    Args:
        artifact: Path to CompiledArtifacts JSON file.
        registry: OCI registry URI.
        tag: Tag for the artifact.
    """
    artifact_path = Path(artifact)
    if not artifact_path.exists():
        error_exit(
            f"Artifact file not found: {artifact_path}",
            exit_code=ExitCode.FILE_NOT_FOUND,
        )

    artifacts = _load_artifacts(artifact_path)
    registry_config = _build_registry_config(registry)
    _push_to_registry(artifacts, registry_config, registry, tag)

    if sign:
        _sign_artifact(registry_config, registry, tag, oidc_issuer)


def _load_artifacts(artifact_path: Path) -> CompiledArtifacts:
    """Load and validate CompiledArtifacts from file.

    Args:
        artifact_path: Path to the artifact JSON file.

    Returns:
        Validated CompiledArtifacts instance.

    Raises:
        SystemExit: If loading fails (via error_exit).
    """
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts

    try:
        return CompiledArtifacts.from_json_file(artifact_path)
    except Exception as e:
        error_exit(
            f"Invalid artifact file: {e}",
            exit_code=ExitCode.VALIDATION_ERROR,
        )


def _handle_push_error(e: Exception) -> NoReturn:
    """Handle push errors with appropriate exit codes.

    Args:
        e: Exception from push operation.

    Raises:
        SystemExit: Always exits with appropriate code.
    """
    error_type = type(e).__name__

    # Map error types to messages and exit codes
    error_mappings: list[tuple[str, str, ExitCode]] = [
        ("Authentication", f"Authentication failed: {e}", ExitCode.GENERAL_ERROR),
        ("Unavailable", f"Registry unavailable: {e}", ExitCode.GENERAL_ERROR),
        (
            "Immutability",
            f"Cannot overwrite immutable tag: {e}",
            ExitCode.VALIDATION_ERROR,
        ),
    ]

    for keyword, message, exit_code in error_mappings:
        if keyword in error_type:
            error_exit(message, exit_code=exit_code)

    # Default case
    error_exit(f"Push failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _push_to_registry(
    artifacts: CompiledArtifacts,
    registry_config: RegistryConfig,
    registry: str,
    tag: str,
) -> None:
    """Push artifacts to OCI registry.

    Args:
        artifacts: CompiledArtifacts to push.
        registry_config: Registry configuration.
        registry: Registry URI (for display).
        tag: Tag for the artifact.

    Raises:
        SystemExit: If push fails (via error_exit).
    """
    from floe_core.oci import OCIClient

    try:
        client = OCIClient.from_registry_config(registry_config)
        info(f"Pushing to {registry}:{tag}...")
        digest = client.push(artifacts, tag=tag)
        success(f"Pushed artifact with digest: {digest}")
        click.echo(digest)
    except Exception as e:
        _handle_push_error(e)


def _build_registry_config(registry_uri: str) -> RegistryConfig:
    """Build RegistryConfig from URI and environment.

    Args:
        registry_uri: OCI registry URI.

    Returns:
        RegistryConfig with auth from environment variables.

    Raises:
        ValueError: If registry URI is invalid.
    """
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
    from floe_core.schemas.secrets import SecretReference, SecretSource

    # Determine auth type from environment
    # SECURITY NOTE: We only check if credentials are SET (non-empty), never log values.
    # Actual credential values are handled via SecretReference, which defers resolution
    # to the OCI client at push time. No credential values are stored or logged here.
    username = os.environ.get("FLOE_REGISTRY_USERNAME", "")
    password = os.environ.get("FLOE_REGISTRY_PASSWORD", "")
    token = os.environ.get("FLOE_REGISTRY_TOKEN", "")

    if token:
        # Token auth - reference the environment variable via SecretReference
        auth = RegistryAuth(
            type=AuthType.TOKEN,
            credentials_ref=SecretReference(
                source=SecretSource.ENV,
                name="registry-token",
            ),
        )
    elif username and password:
        # Basic auth - reference the credentials via SecretReference
        auth = RegistryAuth(
            type=AuthType.BASIC,
            credentials_ref=SecretReference(
                source=SecretSource.ENV,
                name="registry-credentials",
            ),
        )
    else:
        # Check for AWS credentials (ECR)
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        aws_role_arn = os.environ.get("AWS_ROLE_ARN", "")

        if aws_role_arn:
            auth = RegistryAuth(type=AuthType.AWS_IRSA, credentials_ref=None)
        elif aws_access_key:
            # AWS_ENV is not a valid AuthType, use AWS_IRSA for IAM credentials
            auth = RegistryAuth(type=AuthType.AWS_IRSA, credentials_ref=None)
        else:
            # Default to anonymous (may fail on push)
            auth = RegistryAuth(type=AuthType.ANONYMOUS, credentials_ref=None)

    return RegistryConfig(
        uri=registry_uri,
        auth=auth,
    )


def _sign_artifact(
    registry_config: RegistryConfig,
    registry: str,
    tag: str,
    oidc_issuer: str,
) -> None:
    """Sign artifact after push using keyless signing."""
    from pydantic import HttpUrl

    from floe_core.oci import OCIClient
    from floe_core.schemas.signing import SigningConfig

    signing_config = SigningConfig(
        mode="keyless",
        oidc_issuer=HttpUrl(oidc_issuer),
    )

    try:
        client = OCIClient.from_registry_config(registry_config)
        info(f"Signing {registry}:{tag}...")
        metadata = client.sign(tag=tag, signing_config=signing_config)
        success(f"Signed artifact (Rekor index: {metadata.rekor_log_index})")
    except Exception as e:
        error_exit(f"Signing failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


__all__: list[str] = ["push_command"]
