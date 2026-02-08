"""Artifact verify CLI command.

Task ID: T032
Phase: 4 - User Story 2 (Signature Verification)
Requirements: FR-009, FR-010, FR-011

This module provides the `floe artifact verify` command for verifying
signatures on OCI artifacts against trusted issuers.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NoReturn

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success, warning

if TYPE_CHECKING:
    from floe_core.schemas.oci import RegistryConfig
    from floe_core.schemas.signing import VerificationPolicy, VerificationResult


@click.command(
    name="verify",
    help="""\b
Verify artifact signature (FR-009).

Verifies the signature on an artifact at the specified tag against
configured trusted issuers (keyless) or public key (key-based).

For keyless verification, requires at least one --issuer/--subject
pair to specify who is allowed to have signed the artifact.

For key-based verification, requires --key to specify the public key.

Exit codes:
  0: Verification passed (signature valid, signer trusted)
  6: Verification failed (unsigned, invalid, or untrusted signer)

Examples:
    # Verify keyless signature with GitHub Actions signer
    $ floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0 \\
        --issuer https://token.actions.githubusercontent.com \\
        --subject "repo:acme/floe:ref:refs/heads/main"

    # Verify with regex subject pattern
    $ floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0 \\
        --issuer https://token.actions.githubusercontent.com \\
        --subject-regex "repo:acme/.*:ref:refs/heads/main"

    # Verify key-based signature with public key
    $ floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0 \\
        --key /path/to/cosign.pub

    # Verify key-based signature with KMS
    $ floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0 \\
        --key awskms://alias/my-signing-key

    # Warn-only mode (don't fail on invalid signature)
    $ floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0 \\
        --issuer https://token.actions.githubusercontent.com \\
        --subject "repo:acme/floe:ref:refs/heads/main" \\
        --enforcement warn

    # Export verification bundle for offline/air-gapped use
    $ floe artifact verify -r oci://harbor.example.com/floe -t v1.0.0 \\
        --issuer https://token.actions.githubusercontent.com \\
        --subject "repo:acme/floe:ref:refs/heads/main" \\
        --export-bundle bundle.json

    # Inspect offline bundle info (does NOT perform cryptographic verification)
    $ floe artifact verify --bundle-info bundle.json
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
    help="Tag of the artifact to verify (e.g., v1.0.0).",
)
@click.option(
    "--issuer",
    "-i",
    type=str,
    default=None,
    help="OIDC issuer URL to trust (for keyless verification).",
)
@click.option(
    "--subject",
    "-s",
    type=str,
    default=None,
    help="Exact certificate subject to match (for keyless verification).",
)
@click.option(
    "--subject-regex",
    type=str,
    default=None,
    help="Regex pattern for subject matching (for keyless verification).",
)
@click.option(
    "--key",
    "-k",
    type=str,
    default=None,
    help="Public key path or KMS URI for key-based verification.",
)
@click.option(
    "--enforcement",
    type=click.Choice(["enforce", "warn", "off"]),
    default="enforce",
    help="Enforcement level [default: enforce].",
)
@click.option(
    "--require-rekor/--no-require-rekor",
    default=True,
    help="Require Rekor transparency log entry [default: True for keyless, False for key-based].",
)
@click.option(
    "--export-bundle",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Export verification bundle to file for offline/air-gapped verification (FR-015).",
)
@click.option(
    "--bundle-info",
    "bundle_info",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="Inspect offline bundle info (DOES NOT perform cryptographic verification).",
)
def verify_command(
    registry: str,
    tag: str,
    issuer: str | None,
    subject: str | None,
    subject_regex: str | None,
    key: str | None,
    enforcement: str,
    require_rekor: bool,
    export_bundle: str | None,
    bundle_info: str | None,
) -> None:
    """Verify an artifact signature in OCI registry."""
    if bundle_info:
        _display_bundle_info(bundle_info)
        return

    is_key_based = key is not None
    is_keyless = issuer is not None

    if not is_key_based and not is_keyless:
        error_exit(
            "Either --issuer (keyless) or --key (key-based) is required.",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if is_key_based and is_keyless:
        error_exit(
            "--key and --issuer are mutually exclusive.",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if is_keyless:
        assert issuer is not None  # Guaranteed by is_keyless check
        if not subject and not subject_regex:
            error_exit(
                "Either --subject or --subject-regex is required for keyless verification.",
                exit_code=ExitCode.VALIDATION_ERROR,
            )

        if subject and subject_regex:
            error_exit(
                "--subject and --subject-regex are mutually exclusive.",
                exit_code=ExitCode.VALIDATION_ERROR,
            )

        policy = _build_verification_policy(
            issuer=issuer,
            subject=subject,
            subject_regex=subject_regex,
            enforcement=enforcement,
            require_rekor=require_rekor,
        )
    else:
        assert key is not None  # Guarded by is_key_based check above
        policy = _build_key_based_verification_policy(
            key_ref=key,
            enforcement=enforcement,
            require_rekor=False,
        )

    registry_config = _build_registry_config(registry, policy)
    _verify_artifact(registry_config, registry, tag, export_bundle)


def _build_verification_policy(
    issuer: str,
    subject: str | None,
    subject_regex: str | None,
    enforcement: str,
    require_rekor: bool,
) -> VerificationPolicy:
    """Build VerificationPolicy for keyless verification from CLI options."""
    from pydantic import HttpUrl

    from floe_core.schemas.signing import TrustedIssuer, VerificationPolicy

    trusted_issuer = TrustedIssuer(
        issuer=HttpUrl(issuer),
        subject=subject,
        subject_regex=subject_regex,
    )

    return VerificationPolicy(
        enabled=True,
        enforcement=enforcement,  # type: ignore[arg-type]
        trusted_issuers=[trusted_issuer],
        require_rekor=require_rekor,
    )


def _build_key_based_verification_policy(
    key_ref: str,
    enforcement: str,
    require_rekor: bool,
) -> VerificationPolicy:
    """Build VerificationPolicy for key-based verification from CLI options."""
    import os

    from floe_core.oci.verification import check_cosign_available
    from floe_core.schemas.secrets import SecretReference, SecretSource
    from floe_core.schemas.signing import VerificationPolicy

    if not check_cosign_available():
        error_exit(
            "cosign CLI not found. Key-based verification requires cosign. "
            "Install with: brew install cosign (macOS) or "
            "https://github.com/sigstore/cosign#installation",
            exit_code=ExitCode.GENERAL_ERROR,
        )

    is_kms = key_ref.startswith(
        ("awskms://", "gcpkms://", "azurekms://", "hashivault://")
    )

    if is_kms:
        os.environ["FLOE_VERIFY_KEY"] = key_ref
        public_key_ref = SecretReference(
            source=SecretSource.ENV,
            name="verify-key",
        )
    else:
        from floe_core.cli.utils import validate_key_path

        validated_path = validate_key_path(key_ref)
        if not validated_path.exists():
            error_exit(
                f"Public key file not found: {key_ref}",
                exit_code=ExitCode.VALIDATION_ERROR,
            )
        os.environ["FLOE_VERIFY_KEY"] = str(validated_path)
        public_key_ref = SecretReference(
            source=SecretSource.ENV,
            name="verify-key",
        )

    return VerificationPolicy(
        enabled=True,
        enforcement=enforcement,  # type: ignore[arg-type]
        trusted_issuers=[],
        require_rekor=require_rekor,
        public_key_ref=public_key_ref,
    )


def _handle_verify_error(e: Exception) -> NoReturn:
    """Handle verify errors with appropriate exit codes."""
    error_type = type(e).__name__

    if "SignatureVerification" in error_type:
        error_exit(f"Verification failed: {e}", exit_code=ExitCode.SIGNATURE_ERROR)
    elif "NotFound" in error_type:
        error_exit(f"Artifact not found: {e}", exit_code=ExitCode.VALIDATION_ERROR)
    elif "Authentication" in error_type:
        error_exit(
            f"Registry authentication failed: {e}", exit_code=ExitCode.GENERAL_ERROR
        )

    error_exit(f"Verify failed: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _verify_artifact(
    registry_config: RegistryConfig,
    registry: str,
    tag: str,
    export_bundle_path: str | None = None,
) -> None:
    """Verify artifact signature."""
    from floe_core.oci import OCIClient
    from floe_core.oci.verification import (
        VerificationClient,
        export_verification_bundle,
    )
    from floe_core.schemas.signing import SignatureMetadata

    try:
        client = OCIClient.from_registry_config(registry_config)
        info(f"Verifying {registry}:{tag}...")

        policy = registry_config.verification
        assert policy is not None, "Verification policy required for verify command"

        manifest = client.inspect(tag)
        if not manifest.annotations:
            _handle_unsigned_artifact(policy)
            return

        signature_metadata = SignatureMetadata.from_annotations(manifest.annotations)
        if signature_metadata is None:
            _handle_unsigned_artifact(policy)
            return

        artifact_ref = f"{registry}:{tag}"
        content, digest = client._fetch_from_registry(
            tag
        )  # noqa: SLF001 - internal access needed

        verification_client = VerificationClient(policy)
        result = verification_client.verify(
            content=content,
            metadata=signature_metadata,
            artifact_ref=artifact_ref,
            artifact_digest=digest,
        )

        if result.is_valid:
            success("Signature verified successfully")
            click.echo(f"  Status: {result.status}")
            click.echo(f"  Signer: {result.signer_identity}")
            if result.issuer:
                click.echo(f"  Issuer: {result.issuer}")
            click.echo(f"  Rekor verified: {result.rekor_verified}")

            if export_bundle_path:
                bundle = export_verification_bundle(digest, signature_metadata)
                with open(export_bundle_path, "w") as f:
                    f.write(bundle.model_dump_json(indent=2))
                success(f"Verification bundle exported to: {export_bundle_path}")
        else:
            _handle_invalid_signature(result, policy)

    except Exception as e:
        _handle_verify_error(e)


def _display_bundle_info(bundle_path: str) -> None:
    import json

    from floe_core.schemas.signing import VerificationBundle

    try:
        with open(bundle_path) as f:
            bundle_data = json.load(f)

        bundle = VerificationBundle.model_validate(bundle_data)

        warning(
            "NOTICE: This displays bundle info only - NO cryptographic verification performed"
        )
        info(f"Bundle path: {bundle_path}")
        click.echo(f"  Artifact digest: {bundle.artifact_digest}")
        click.echo(f"  Bundle version: {bundle.version}")
        click.echo(f"  Created at: {bundle.created_at.isoformat()}")
        click.echo(f"  Has Rekor entry: {bundle.rekor_entry is not None}")
        click.echo(f"  Certificate chain entries: {len(bundle.certificate_chain)}")

        info("Bundle parsed successfully (use --key or --issuer with live registry)")

    except json.JSONDecodeError as e:
        error_exit(f"Invalid bundle JSON: {e}", exit_code=ExitCode.VALIDATION_ERROR)
    except Exception as e:
        error_exit(f"Failed to load bundle: {e}", exit_code=ExitCode.GENERAL_ERROR)


def _handle_unsigned_artifact(policy: VerificationPolicy) -> None:
    """Handle unsigned artifact based on enforcement level."""
    if policy.enforcement == "enforce":
        error_exit("Artifact is not signed", exit_code=ExitCode.SIGNATURE_ERROR)
    elif policy.enforcement == "warn":
        warning("Artifact is not signed (enforcement=warn)")
    else:
        info("Artifact is not signed (enforcement=off)")


def _handle_invalid_signature(
    result: VerificationResult, policy: VerificationPolicy
) -> None:
    """Handle invalid signature based on enforcement level."""
    msg = f"Signature invalid: {result.failure_reason}"
    if policy.enforcement == "enforce":
        error_exit(msg, exit_code=ExitCode.SIGNATURE_ERROR)
    elif policy.enforcement == "warn":
        warning(f"{msg} (enforcement=warn)")
    else:
        info(f"{msg} (enforcement=off)")


def _build_registry_config(
    registry_uri: str, verification_policy: VerificationPolicy
) -> RegistryConfig:
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
        verification=verification_policy,
    )


__all__: list[str] = ["verify_command"]
