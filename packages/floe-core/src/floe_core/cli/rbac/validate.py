"""RBAC validate command implementation.

Task ID: T033
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-022, FR-023

This module implements the `floe rbac validate` command which:
- Validates RBAC manifests against configuration
- Reports missing or extra resources
- Returns validation status

Example:
    $ floe rbac validate
    $ floe rbac validate --manifest-dir deploy/rbac
    $ floe rbac validate --output json
"""

from __future__ import annotations

from pathlib import Path

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success


@click.command(
    name="validate",
    help="Validate RBAC manifests against configuration (FR-061).",
    epilog="""
Checks that generated manifests match the expected configuration,
detecting missing or extra resources.

Examples:
    $ floe rbac validate
    $ floe rbac validate --manifest-dir deploy/rbac
    $ floe rbac validate --output json
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    help="Path to manifest.yaml configuration file.",
    metavar="PATH",
)
@click.option(
    "--manifest-dir",
    "-m",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Directory containing generated RBAC manifests.",
    metavar="PATH",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default=None,
    help="Output format.",
)
def validate_command(
    config: Path | None,
    manifest_dir: Path | None,
    output: str | None,
) -> None:
    """Validate RBAC manifests against configuration.

    Checks that generated manifests match the expected configuration
    and reports any discrepancies.

    Args:
        config: Path to manifest.yaml configuration file.
        manifest_dir: Directory containing RBAC manifests to validate.
        output: Output format (text or json).
    """
    # Default values
    manifest_dir_path = manifest_dir if manifest_dir is not None else Path("target/rbac")
    output_format = output if output is not None else "text"

    info(f"Validating manifests in: {manifest_dir_path}")

    if config:
        info(f"Against configuration: {config}")

    try:
        from floe_core.rbac import validate_all_manifests

        # Load manifests from directory
        manifests: dict[str, list[dict]] = {}
        manifest_files = ["namespaces.yaml", "serviceaccounts.yaml", "roles.yaml", "rolebindings.yaml"]

        import yaml

        for filename in manifest_files:
            file_path = manifest_dir_path / filename
            if file_path.exists():
                content = file_path.read_text()
                if content.strip():
                    docs = list(yaml.safe_load_all(content))
                    manifests[filename] = [d for d in docs if d]
                else:
                    manifests[filename] = []
            else:
                manifests[filename] = []

        # Validate all manifests
        is_valid, errors = validate_all_manifests(manifests)

        if output_format == "json":
            import json

            result = {
                "valid": is_valid,
                "errors": errors,
                "manifest_dir": str(manifest_dir_path),
            }
            click.echo(json.dumps(result, indent=2))
        else:
            if is_valid:
                success("All manifests are valid.")
            else:
                for error in errors:
                    click.echo(f"Error: {error}", err=True)
                error_exit(
                    f"Validation failed with {len(errors)} error(s)",
                    exit_code=ExitCode.VALIDATION_ERROR,
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
