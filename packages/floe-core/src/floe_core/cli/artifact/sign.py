"""Artifact sign CLI command.

Task ID: T019
Phase: 3 - User Story 1 (Keyless Signing)
Requirements: FR-001, FR-011

This module provides the `floe artifact sign` command for signing
OCI artifacts using Sigstore keyless (OIDC) or key-based signing.

Example:
    $ floe artifact sign --registry oci://harbor.example.com/floe \\
        --tag v1.0.0 --keyless

Environment Variables:
    FLOE_REGISTRY_USERNAME: Registry username for basic auth
    FLOE_REGISTRY_PASSWORD: Registry password for basic auth
    FLOE_REGISTRY_TOKEN: Bearer token for token auth
    ACTIONS_ID_TOKEN_REQUEST_TOKEN: GitHub Actions OIDC token
    ACTIONS_ID_TOKEN_REQUEST_URL: GitHub Actions OIDC URL

See Also:
    - specs/8b-artifact-signing/spec.md: Artifact Signing specification
    - specs/8b-artifact-signing/research.md: sigstore-python patterns
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NoReturn

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success

if TYPE_CHECKING:
    from floe_core.schemas.oci import RegistryConfig
    from floe_core.schemas.signing import SignatureMetadata, SigningConfig


@click.command(
    name="sign",
    help="""\b
Sign an artifact in OCI registry (FR-001).

Signs an artifact at the specified tag using Sigstore.
Default mode is keyless (OIDC-based), which requires
ambient credentials from CI/CD environments (GitHub Actions,
GitLab CI) or browser-based OAuth flow for local development.

The signature bundle and metadata are stored as OCI annotations
on the artifact (FR-011).

Examples:
    # Keyless signing in CI/CD (auto-detects OIDC token)
    $ floe artifact sign -r oci://harbor.example.com/floe -t v1.0.0

    # Explicit keyless mode
    $ floe artifact sign -r oci://harbor.example.com/floe -t v1.0.0 --keyless

    # Key-based signing (not yet implemented)
    $ floe artifact sign -r oci://harbor.example.com/floe -t v1.0.0 \\
        --key /path/to/cosign.key
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
    help="Tag of the artifact to sign (e.g., v1.0.0).",
)
@click.option(
    "--keyless/--no-keyless",
    default=True,
    help="Use keyless (OIDC) signing [default: keyless].",
)
@click.option(
    "--key",
    "-k",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to private key for key-based signing (not yet supported).",
)
@click.option(
    "--oidc-issuer",
    type=str,
    default="https://token.actions.githubusercontent.com",
    help="OIDC issuer URL for keyless signing.",
)
def sign_command(
    registry: str,
    tag: str,
    keyless: bool,
    key: str | None,
    oidc_issuer: str,
) -> None:
    """Sign an artifact in OCI registry."""
    if key is not None:
        error_exit(
            "Key-based signing not yet implemented. Use --keyless mode.",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    signing_config = _build_signing_config(keyless, oidc_issuer)
    registry_config = _build_registry_config(registry)
    _sign_artifact(registry_config, registry, tag, signing_config)


def _build_signing_config(keyless: bool, oidc_issuer: str) -> SigningConfig:
    """Build SigningConfig from CLI options."""
    from pydantic import HttpUrl

    from floe_core.schemas.signing import SigningConfig

    if keyless:
        return SigningConfig(
            mode="keyless",
            oidc_issuer=HttpUrl(oidc_issuer),
        )
    else:
        error_exit(
            "Key-based signing requires --key option.",
            exit_code=ExitCode.VALIDATION_ERROR,
        )


def _handle_sign_error(e: Exception) -> NoReturn:
    """Handle sign errors with appropriate exit codes."""
    error_type = type(e).__name__

    error_mappings: list[tuple[str, str, ExitCode]] = [
        ("OIDCToken", f"OIDC token acquisition failed: {e}", ExitCode.GENERAL_ERROR),
        ("Signing", f"Signing failed: {e}", ExitCode.GENERAL_ERROR),
        ("Authentication", f"Registry authentication failed: {e}", ExitCode.GENERAL_ERROR),
        ("NotFound", f"Artifact not found: {e}", ExitCode.VALIDATION_ERROR),
    ]

    for keyword, message, exit_code in error_mappings:
        if keyword in error_type:
            error_exit(message, exit_code=exit_code)

    error_exit(f"Sign failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _sign_artifact(
    registry_config: RegistryConfig,
    registry: str,
    tag: str,
    signing_config: SigningConfig,
) -> None:
    """Sign artifact in OCI registry."""
    from floe_core.oci import OCIClient

    try:
        client = OCIClient.from_registry_config(registry_config)
        info(f"Signing {registry}:{tag}...")
        metadata = client.sign(tag=tag, signing_config=signing_config)
        success(f"Signed artifact (Rekor index: {metadata.rekor_log_index})")
        click.echo(f"Signer: {metadata.subject}")
        if metadata.issuer:
            click.echo(f"Issuer: {metadata.issuer}")
    except Exception as e:
        _handle_sign_error(e)


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


__all__: list[str] = ["sign_command"]
