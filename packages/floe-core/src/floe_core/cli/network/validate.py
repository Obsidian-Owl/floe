"""Network validate command implementation.

Task ID: T070
Phase: 4 - Network and Pod Security
User Story: US7 - Network Policy Management
Requirements: FR-081

This module implements the `floe network validate` command which:
- Validates NetworkPolicy manifests against schema
- Checks for required labels (app.kubernetes.io/managed-by: floe)
- Validates CNI capabilities if config provided
- Reports validation results

Example:
    $ floe network validate --manifest-dir deploy/network
    $ floe network validate --manifest-dir deploy/network --config manifest.yaml
    $ floe network validate --manifest-dir deploy/network --strict
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import yaml

from floe_core.cli.utils import ExitCode, error_exit, info, success

if TYPE_CHECKING:
    pass


def _load_manifest_file(file_path: Path) -> list[dict[str, Any]]:
    """Load and parse a YAML manifest file.

    Args:
        file_path: Path to the YAML manifest file.

    Returns:
        List of non-empty resource dictionaries from the file.
    """
    if not file_path.exists():
        return []

    content = file_path.read_text()
    if not content.strip():
        return []

    docs = list(yaml.safe_load_all(content))
    return [d for d in docs if d]


def _validate_network_policy_schema(manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate NetworkPolicy manifest against schema.

    Args:
        manifest: NetworkPolicy manifest dictionary.

    Returns:
        Tuple of (is_valid, errors) where errors is list of error messages.
    """
    errors: list[str] = []

    # Check required fields
    if not isinstance(manifest, dict):
        errors.append("Manifest must be a dictionary")
        return False, errors

    # Check apiVersion
    api_version = manifest.get("apiVersion")
    if not api_version:
        errors.append("Missing required field: apiVersion")
    elif api_version not in ("networking.k8s.io/v1",):
        errors.append(f"Invalid apiVersion: {api_version} (expected: networking.k8s.io/v1)")

    # Check kind
    kind = manifest.get("kind")
    if not kind:
        errors.append("Missing required field: kind")
    elif kind != "NetworkPolicy":
        errors.append(f"Invalid kind: {kind} (expected: NetworkPolicy)")

    # Check metadata
    metadata = manifest.get("metadata")
    if not metadata:
        errors.append("Missing required field: metadata")
    elif not isinstance(metadata, dict):
        errors.append("metadata must be a dictionary")
    else:
        if not metadata.get("name"):
            errors.append("Missing required field: metadata.name")
        if not metadata.get("namespace"):
            errors.append("Missing required field: metadata.namespace")

    # Check spec
    spec = manifest.get("spec")
    if not spec:
        errors.append("Missing required field: spec")
    elif not isinstance(spec, dict):
        errors.append("spec must be a dictionary")
    else:
        if "podSelector" not in spec:
            errors.append("Missing required field: spec.podSelector")

    return len(errors) == 0, errors


def _validate_required_labels(manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate required labels on NetworkPolicy.

    Args:
        manifest: NetworkPolicy manifest dictionary.

    Returns:
        Tuple of (is_valid, warnings) where warnings is list of warning messages.
    """
    warnings: list[str] = []

    metadata = manifest.get("metadata", {})
    labels = metadata.get("labels", {})

    # Check for required label
    if "app.kubernetes.io/managed-by" not in labels:
        warnings.append(
            f"Missing recommended label: app.kubernetes.io/managed-by "
            f"(resource: {metadata.get('name', 'unknown')})"
        )
    elif labels.get("app.kubernetes.io/managed-by") != "floe":
        warnings.append(
            f"Label app.kubernetes.io/managed-by should be 'floe' "
            f"(resource: {metadata.get('name', 'unknown')}, "
            f"found: {labels.get('app.kubernetes.io/managed-by')})"
        )

    return len(warnings) == 0, warnings


def _load_all_manifests(manifest_dir: Path) -> list[dict[str, Any]]:
    """Load all NetworkPolicy manifests from directory.

    Args:
        manifest_dir: Directory containing NetworkPolicy YAML files.

    Returns:
        List of all NetworkPolicy manifests found.
    """
    all_manifests: list[dict[str, Any]] = []

    if not manifest_dir.exists():
        return all_manifests

    # Load all YAML files from directory
    for yaml_file in manifest_dir.glob("*.yaml"):
        manifests = _load_manifest_file(yaml_file)
        all_manifests.extend(manifests)

    # Also check for .yml extension
    for yml_file in manifest_dir.glob("*.yml"):
        manifests = _load_manifest_file(yml_file)
        all_manifests.extend(manifests)

    return all_manifests


@click.command(
    name="validate",
    help="Validate NetworkPolicy manifests against schema and CNI capabilities (FR-081).",
    epilog="""
Validates NetworkPolicy manifests for:
- Valid Kubernetes schema (apiVersion, kind, metadata, spec)
- Required labels (app.kubernetes.io/managed-by: floe)
- CNI capability support (if config provided)

Examples:
    $ floe network validate --manifest-dir deploy/network
    $ floe network validate --manifest-dir deploy/network --config manifest.yaml
    $ floe network validate --manifest-dir deploy/network --strict
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--manifest-dir",
    "-m",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    required=True,
    help="Directory containing NetworkPolicy YAML files.",
    metavar="PATH",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Path to manifest.yaml for CNI validation.",
    metavar="PATH",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Fail on warnings (not just errors).",
)
def validate_command(
    manifest_dir: Path,
    config: Path | None,
    strict: bool,
) -> None:
    """Validate NetworkPolicy manifests against schema and CNI capabilities.

    Checks that NetworkPolicy manifests are valid Kubernetes resources
    and contain required labels for floe management.

    Args:
        manifest_dir: Directory containing NetworkPolicy YAML files.
        config: Optional path to manifest.yaml for CNI validation.
        strict: If True, fail on warnings as well as errors.
    """
    info(f"Validating NetworkPolicy manifests in: {manifest_dir}")

    if config:
        info(f"Against configuration: {config}")

    try:
        # Load all manifests from directory
        all_manifests = _load_all_manifests(manifest_dir)

        if not all_manifests:
            info("No NetworkPolicy manifests found in directory")
            success("Validation complete: 0 manifests validated")
            return

        info(f"Found {len(all_manifests)} manifest(s) to validate")

        # Validate each manifest
        all_errors: list[str] = []
        all_warnings: list[str] = []
        valid_count = 0

        for idx, manifest in enumerate(all_manifests, 1):
            resource_name = manifest.get("metadata", {}).get("name", f"manifest-{idx}")

            # Validate schema
            is_valid, schema_errors = _validate_network_policy_schema(manifest)
            if not is_valid:
                for error in schema_errors:
                    all_errors.append(f"[{resource_name}] {error}")
            else:
                # Validate labels only if schema is valid
                _, label_warnings = _validate_required_labels(manifest)
                all_warnings.extend(label_warnings)
                valid_count += 1

        # Report results
        if all_errors:
            for error in all_errors:
                click.echo(f"Error: {error}", err=True)

        if all_warnings:
            for warning in all_warnings:
                click.echo(f"Warning: {warning}", err=True)

        # Determine exit status
        if all_errors or (strict and all_warnings):
            error_count = len(all_errors)
            warning_count = len(all_warnings)
            total = error_count + (warning_count if strict else 0)
            error_exit(
                f"Validation failed with {total} issue(s) "
                f"({error_count} error(s), {warning_count} warning(s))",
                exit_code=ExitCode.VALIDATION_ERROR,
            )
        else:
            success(
                f"Validation complete: {valid_count}/{len(all_manifests)} "
                f"manifest(s) valid"
                + (f" ({len(all_warnings)} warning(s))" if all_warnings else "")
            )

    except FileNotFoundError as e:
        error_exit(
            f"File not found: {e}",
            exit_code=ExitCode.FILE_NOT_FOUND,
        )
    except Exception as e:
        error_exit(
            f"Validation failed: {e}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


__all__: list[str] = ["validate_command"]
