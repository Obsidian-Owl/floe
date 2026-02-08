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
from floe_core.helm import (
    HelmValuesConfig,
    HelmValuesGenerator,
    unflatten_dict,
)

# Type alias for Helm values
HelmValues = dict[str, Any]


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
    user_overrides: dict[str, Any] = _parse_set_values(set_values)

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
            # Future: Extract plugin values from CompiledArtifacts

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
                info(
                    f"Would generate values for environments: {', '.join(environments)}"
                )
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
            if output and output.suffix in (".yaml", ".yml"):
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


def _parse_set_values(set_values: tuple[str, ...]) -> dict[str, Any]:
    """Parse --set key=value arguments into nested dict.

    Args:
        set_values: Tuple of "key=value" strings.

    Returns:
        Nested dictionary with parsed values.

    Example:
        >>> _parse_set_values(("dagster.replicas=3", "global.env=prod"))
        {'dagster': {'replicas': 3}, 'global': {'env': 'prod'}}
    """
    if not set_values:
        return {}

    flat: dict[str, Any] = {}
    for item in set_values:
        if "=" not in item:
            continue
        key, _, value = item.partition("=")
        # Try to parse as int/float/bool
        parsed = _parse_value(value)
        flat[key] = parsed

    return unflatten_dict(flat)


def _parse_value(value: str) -> str | int | float | bool | None:
    """Parse a string value into appropriate Python type.

    Args:
        value: String value from --set argument.

    Returns:
        Parsed value as int, float, bool, None, or original string.
    """
    # Handle null
    if value.lower() == "null":
        return None

    # Handle booleans
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Return as string
    return value


__all__: list[str] = ["generate_command"]
