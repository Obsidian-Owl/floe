"""Helm values generate command implementation.

Task ID: T062
Phase: 5 - User Story 3 (Helm Values Generator)
User Story: US3 - Generate Helm Values from Artifacts
Requirements: FR-060, FR-062, FR-063, FR-064

This module implements the `floe helm generate` command which:
- Reads CompiledArtifacts from file or OCI registry
- Generates environment-specific Helm values files
- Supports plugin value contribution and user overrides

Example:
    $ floe helm generate --artifact target/compiled_artifacts.json
    $ floe helm generate --artifact target/compiled_artifacts.json --env staging --env prod
    $ floe helm generate --output values-staging.yaml --set dagster.replicas=3
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success
from floe_core.compilation.errors import (
    COMPOSITION_RENDERER_PRECONDITION_FAILED,
    CompilationError,
    CompilationException,
)
from floe_core.compilation.stages import CompilationStage
from floe_core.helm import (
    HelmValuesConfig,
    HelmValuesGenerator,
)
from floe_core.helm.parsing import parse_set_values
from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    CompiledArtifacts,
    CredentialRef,
    StorageDeploymentBinding,
)

# Type alias for Helm values
HelmValues = dict[str, Any]


def _load_compiled_artifacts(artifact_path: Path) -> CompiledArtifacts:
    """Load compiled artifacts from JSON or YAML."""
    if artifact_path.suffix.lower() in (".yaml", ".yml"):
        return CompiledArtifacts.from_yaml_file(artifact_path)
    return CompiledArtifacts.from_json_file(artifact_path)


def _renderer_precondition_failed(
    message: str,
    *,
    context: dict[str, Any] | None = None,
) -> CompilationException:
    """Build a structured Helm renderer precondition failure."""
    return CompilationException(
        CompilationError(
            stage=CompilationStage.GENERATE,
            code=COMPOSITION_RENDERER_PRECONDITION_FAILED,
            message=message,
            suggestion=(
                "Recompile with required deployment bindings or fix the artifact before rendering."
            ),
            context=context,
        )
    )


def _storage_helm_values(artifacts: CompiledArtifacts) -> dict[str, Any]:
    """Derive Helm storage values from compiled storage deployment binding."""
    if artifacts.deployment is None or artifacts.deployment.storage is None:
        return {}

    storage = artifacts.deployment.storage
    if storage.provider != "minio":
        return {}

    catalog = artifacts.deployment.catalog
    if catalog is None:
        msg = "MinIO Helm values require catalog deployment binding"
        raise _renderer_precondition_failed(msg)
    if catalog.provider != "polaris":
        msg = "MinIO Helm values require Polaris catalog deployment binding"
        raise _renderer_precondition_failed(
            msg,
            context={"storage_provider": storage.provider, "catalog_provider": catalog.provider},
        )

    return _minio_storage_helm_values(storage, catalog)


def _require_kubernetes_secret_ref(
    ref: CredentialRef | None,
    logical_key: str,
    *,
    context: dict[str, Any] | None = None,
) -> CredentialRef:
    """Return a Kubernetes Secret credential ref or raise a Helm-specific error."""
    if ref is not None and ref.source == "kubernetes-secret" and ref.key is not None:
        return ref
    msg = f"MinIO Helm values require Kubernetes Secret credential reference for {logical_key}"
    raise _renderer_precondition_failed(msg, context=context)


def _storage_credential_ref(
    storage: StorageDeploymentBinding,
    logical_key: str,
    *,
    context: dict[str, Any] | None = None,
) -> CredentialRef:
    """Return a storage credential ref or raise a structured renderer precondition."""
    try:
        return storage.credentials.as_credential_ref(logical_key)
    except ValueError:
        msg = f"MinIO Helm values require Kubernetes Secret credential reference for {logical_key}"
        raise _renderer_precondition_failed(msg, context=context) from None


def _minio_storage_helm_values(
    storage: StorageDeploymentBinding,
    catalog: CatalogDeploymentBinding,
) -> dict[str, Any]:
    """Derive MinIO and Polaris values from typed deployment bindings."""
    bucket_names = []
    for bucket in storage.buckets:
        if bucket.name not in bucket_names:
            bucket_names.append(bucket.name)
    provider_context = {"storage_provider": storage.provider, "catalog_provider": catalog.provider}
    if not bucket_names:
        msg = "MinIO Helm values require storage bucket requirements"
        raise _renderer_precondition_failed(msg, context=provider_context)

    access_key_ref = _storage_credential_ref(
        storage,
        "accessKeyId",
        context=provider_context,
    )
    secret_key_ref = _storage_credential_ref(
        storage,
        "secretAccessKey",
        context=provider_context,
    )
    if (
        access_key_ref.source != "kubernetes-secret"
        or secret_key_ref.source != "kubernetes-secret"
        or access_key_ref.key is None
        or secret_key_ref.key is None
    ):
        msg = "MinIO Helm values require Kubernetes Secret credential references"
        raise _renderer_precondition_failed(msg, context=provider_context)
    if access_key_ref.name != secret_key_ref.name:
        msg = "MinIO Helm values require access and secret keys in the same Kubernetes Secret"
        raise _renderer_precondition_failed(msg, context=provider_context)

    polaris = catalog.polaris
    if polaris is None:
        msg = "Floe platform Helm values require Polaris catalog deployment details"
        raise ValueError(msg)
    polaris_access_ref = _require_kubernetes_secret_ref(
        polaris.credential_refs.get("accessKeyId"),
        "accessKeyId",
        context=provider_context,
    )
    polaris_secret_ref = _require_kubernetes_secret_ref(
        polaris.credential_refs.get("secretAccessKey"),
        "secretAccessKey",
        context=provider_context,
    )
    if polaris_access_ref.name != polaris_secret_ref.name:
        msg = "Polaris Helm values require access and secret keys in the same Kubernetes Secret"
        raise _renderer_precondition_failed(msg, context=provider_context)

    return {
        "minio": {
            "enabled": True,
            "fullnameOverride": "floe-platform-minio",
            "auth": {"existingSecret": access_key_ref.name},
            "defaultBuckets": ",".join(bucket_names),
            "provisioning": {"enabled": False, "fallbackJob": True},
        },
        "polaris": {
            "storage": {
                "s3": {
                    "enabled": True,
                    "endpoint": polaris.endpoint_internal,
                    "region": storage.endpoint.region,
                    "pathStyleAccess": polaris.path_style_access,
                    "stsEnabled": not polaris.sts_unavailable,
                    "credentialSecretName": polaris_access_ref.name,
                    "accessKeySecretKey": polaris_access_ref.key,
                    "secretKeySecretKey": polaris_secret_ref.key,
                }
            },
            "bootstrap": {
                "defaultBaseLocation": polaris.default_base_location,
                "allowedLocations": polaris.allowed_locations,
            },
        },
    }


@click.command(
    name="generate",
    help="""\b
Generate Helm values from CompiledArtifacts (FR-060).

Reads CompiledArtifacts and generates environment-specific Helm values
files for floe platform deployment. Supports multiple environments,
plugin contributions, and user overrides.

Output:
    Single file:  values-{env}.yaml
    Multi-env:    values-dev.yaml, values-staging.yaml, values-prod.yaml

Examples:
    $ floe helm generate --artifact target/compiled_artifacts.json
    $ floe helm generate --artifact target/compiled_artifacts.json --env prod
    $ floe helm generate --env dev --env staging --output-dir target/helm
    $ floe helm generate --artifact oci://registry/floe:v1.0 --set replicas=3
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--artifact",
    "-a",
    type=str,
    default=None,
    help="Path to compiled_artifacts.json or OCI reference (oci://...).",
    metavar="PATH|OCI",
)
@click.option(
    "--env",
    "-e",
    "environments",
    type=click.Choice(["dev", "staging", "prod"]),
    multiple=True,
    default=("dev",),
    help="Target environment(s). Can be specified multiple times.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(resolve_path=True, path_type=Path),
    default=None,
    help="Output file path (single env) or directory (multi env).",
    metavar="PATH",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Output directory for multi-environment generation.",
    metavar="DIR",
)
@click.option(
    "--set",
    "set_values",
    multiple=True,
    help="Override values using key=value syntax. Can be repeated.",
    metavar="KEY=VALUE",
)
@click.option(
    "--values",
    "-f",
    "values_files",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    multiple=True,
    help="Additional values files to merge. Can be repeated.",
    metavar="PATH",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be generated without writing files.",
)
def generate_command(
    artifact: str | None,
    environments: tuple[str, ...],
    output: Path | None,
    output_dir: Path | None,
    set_values: tuple[str, ...],
    values_files: tuple[Path, ...],
    dry_run: bool,
) -> None:
    """Generate Helm values from CompiledArtifacts.

    Generates environment-specific Helm values files from CompiledArtifacts.
    Supports plugin contribution, multi-environment generation, and user overrides.

    Args:
        artifact: Path to compiled_artifacts.json or OCI reference.
        environments: Target environments (dev, staging, prod).
        output: Output file or directory path.
        output_dir: Output directory for multi-env generation.
        set_values: Override values using key=value syntax.
        values_files: Additional values files to merge.
        dry_run: If True, show what would be generated without writing.
    """
    # Parse --set values into dict
    user_overrides: dict[str, Any] = parse_set_values(set_values)

    # Load additional values files
    additional_values: list[dict[str, Any]] = []
    if values_files:
        import yaml

        for values_file in values_files:
            info(f"Loading values from: {values_file}")
            try:
                with values_file.open() as f:
                    loaded = yaml.safe_load(f)
                    if loaded:
                        additional_values.append(loaded)
            except Exception as e:
                error_exit(
                    f"Failed to load values file: {values_file}: {e}",
                    exit_code=ExitCode.FILE_NOT_FOUND,
                )

    # Load base values from artifact if provided
    base_values: dict[str, Any] = {}
    if artifact:
        if artifact.startswith("oci://"):
            info(f"OCI artifact support planned: {artifact}")
            info("Using default configuration for now.")
        else:
            artifact_path = Path(artifact)
            if not artifact_path.exists():
                error_exit(
                    f"Artifact file not found: {artifact}",
                    exit_code=ExitCode.FILE_NOT_FOUND,
                )
            info(f"Loading artifact: {artifact_path}")
            try:
                artifacts = _load_compiled_artifacts(artifact_path)
                base_values = _storage_helm_values(artifacts)
            except Exception as e:
                error_exit(
                    f"Failed to load artifact: {artifact_path}: {e}",
                    exit_code=ExitCode.GENERAL_ERROR,
                )

    # Create generator with configuration
    config = HelmValuesConfig.with_defaults(environment=environments[0])
    generator = HelmValuesGenerator(config, base_values=base_values)

    # Add additional values files as plugin values
    for vals in additional_values:
        generator.add_plugin_values(vals)

    # Set user overrides
    if user_overrides:
        generator.set_user_overrides(user_overrides)

    # Determine output mode
    multi_env = len(environments) > 1
    target_dir = output_dir or output or Path("target/helm")

    if dry_run:
        info("Dry-run mode: no files will be written")

    try:
        if multi_env:
            # Generate for all environments
            _dir = target_dir if target_dir.suffix == "" else target_dir.parent
            if dry_run:
                info(f"Would generate values for environments: {', '.join(environments)}")
                for env in environments:
                    info(f"  {_dir}/values-{env}.yaml")
                success("Dry-run complete.")
                return

            paths = generator.write_environment_values(
                _dir,
                list(environments),
                filename_template="values-{env}.yaml",
            )
            success(f"Generated {len(paths)} values files:")
            for p in paths:
                info(f"  {p}")
        else:
            # Single environment (guaranteed non-empty by default=("dev",))
            env = environments[0] if environments else "dev"
            if output and output.suffix.lower() in (".yaml", ".yml"):
                target_file = output
            else:
                target_file = (output or Path("target/helm")) / f"values-{env}.yaml"

            if dry_run:
                info(f"Would generate: {target_file}")
                values = generator.generate()
                info(f"Values would contain {len(values)} top-level keys")
                success("Dry-run complete.")
                return

            values = generator.generate()
            written = generator.write_values(target_file, values)
            success(f"Generated: {written}")

    except Exception as e:
        error_exit(
            f"Helm values generation failed: {e}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


__all__: list[str] = ["generate_command"]
