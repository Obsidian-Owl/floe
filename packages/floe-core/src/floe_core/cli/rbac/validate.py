"""RBAC validate command implementation.

Task ID: T033
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-022, FR-023, FR-061

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
from typing import TYPE_CHECKING, Any

import click

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
    import yaml

    if not file_path.exists():
        return []

    content = file_path.read_text()
    if not content.strip():
        return []

    docs = list(yaml.safe_load_all(content))
    return [d for d in docs if d]


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
        from floe_core.rbac.validate import validate_manifest_against_config
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationStatus,
        )

        # Load manifests from directory
        manifest_files = [
            "namespaces.yaml",
            "serviceaccounts.yaml",
            "roles.yaml",
            "rolebindings.yaml",
        ]
        manifests: dict[str, list[dict[str, Any]]] = {
            filename: _load_manifest_file(manifest_dir_path / filename)
            for filename in manifest_files
        }

        import yaml

        # Validate all manifests using existing function
        is_valid, errors = validate_all_manifests(manifests)

        # Build type-safe validation result
        all_issues = []

        # If config provided, also validate against expected resources
        if config:
            config_content = config.read_text()
            config_data = yaml.safe_load(config_content) or {}

            # Extract expected resources from config
            expected_sa = config_data.get("rbac", {}).get("service_accounts", [])
            expected_roles = config_data.get("rbac", {}).get("roles", [])

            # Convert expected to manifest format for comparison
            expected_sa_manifests = [
                {"metadata": {"name": sa.get("name"), "namespace": sa.get("namespace")}}
                for sa in expected_sa
            ]
            expected_role_manifests = [
                {"metadata": {"name": r.get("name"), "namespace": r.get("namespace")}}
                for r in expected_roles
            ]

            # Validate service accounts
            sa_issues = validate_manifest_against_config(
                manifests.get("serviceaccounts.yaml", []),
                expected_sa_manifests,
                "ServiceAccount",
            )
            all_issues.extend(sa_issues)

            # Validate roles
            role_issues = validate_manifest_against_config(
                manifests.get("roles.yaml", []),
                expected_role_manifests,
                "Role",
            )
            all_issues.extend(role_issues)

        # Determine status
        if not is_valid or all_issues:
            status = ValidationStatus.INVALID
        else:
            status = ValidationStatus.VALID

        # Build result model
        result = RBACValidationResult(
            status=status,
            config_path=str(config) if config else "N/A",
            manifest_dir=str(manifest_dir_path),
            issues=all_issues,
            service_accounts_validated=len(manifests.get("serviceaccounts.yaml", [])),
            roles_validated=len(manifests.get("roles.yaml", [])),
            role_bindings_validated=len(manifests.get("rolebindings.yaml", [])),
        )

        if output_format == "json":
            click.echo(result.model_dump_json(indent=2))
        else:
            if result.is_valid:
                success("All manifests are valid.")
            else:
                for issue in result.issues:
                    click.echo(
                        f"Error: [{issue.issue_type.value}] "
                        f"{issue.resource_kind}/{issue.resource_name}: {issue.message}",
                        err=True,
                    )
                for error in errors:
                    click.echo(f"Error: {error}", err=True)
                error_exit(
                    f"Validation failed with {len(result.issues) + len(errors)} error(s)",
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
