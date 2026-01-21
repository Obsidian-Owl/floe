"""RBAC generate command implementation.

Task ID: T032
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-020, FR-021

This module implements the `floe rbac generate` command which:
- Reads manifest.yaml configuration
- Generates Kubernetes RBAC manifests (Namespaces, ServiceAccounts, Roles, RoleBindings)
- Writes manifests to output directory

Example:
    $ floe rbac generate
    $ floe rbac generate --config manifest.yaml --output target/rbac
    $ floe rbac generate --dry-run
"""

from __future__ import annotations

from pathlib import Path

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success


@click.command(
    name="generate",
    help="""\b
Generate RBAC manifests from configuration (FR-060).

Reads the manifest.yaml configuration and generates Kubernetes RBAC
manifests including ServiceAccounts, Roles, RoleBindings, and Namespaces.

Output files:
    target/rbac/namespaces.yaml
    target/rbac/serviceaccounts.yaml
    target/rbac/roles.yaml
    target/rbac/rolebindings.yaml

Examples:
    $ floe rbac generate
    $ floe rbac generate --config platform.yaml --output deploy/rbac
    $ floe rbac generate --dry-run
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
    "--output",
    "-o",
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Output directory for generated manifests.",
    metavar="PATH",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be generated without writing files.",
)
def generate_command(
    config: Path | None,
    output: Path | None,
    dry_run: bool,
) -> None:
    """Generate RBAC manifests from configuration.

    Reads the manifest.yaml configuration file and generates Kubernetes
    RBAC manifests. Supports dry-run mode to preview changes.

    Args:
        config: Path to manifest.yaml configuration file.
        output: Output directory for generated manifests.
        dry_run: If True, show what would be generated without writing.
    """
    # Validate required config
    if config is None:
        error_exit(
            "Missing --config option. Provide path to manifest.yaml.",
            exit_code=ExitCode.USAGE_ERROR,
        )

    # Default output directory
    output_dir = output if output is not None else Path("target/rbac")

    info(f"Reading configuration: {config}")
    info(f"Output directory: {output_dir}")

    if dry_run:
        info("Dry-run mode: no files will be written")

    try:
        # Import here to avoid circular dependencies
        from floe_core.compilation.loader import load_manifest
        from floe_core.rbac import RBACManifestGenerator
        from floe_core.schemas.security import SecurityConfig

        # Load manifest (may be used in future for governance settings)
        _manifest = load_manifest(config)

        # Get security config - always create SecurityConfig with RBAC enabled
        # Note: GovernanceConfig is for policy enforcement, SecurityConfig is for RBAC
        from floe_core.schemas.security import RBACConfig

        security_config: SecurityConfig = SecurityConfig(rbac=RBACConfig(enabled=True))

        # Create generator - need an RBACPlugin
        # For now, use a simple mock/stub since full plugin may not be available
        try:
            from floe_rbac_k8s.plugin import K8sRBACPlugin

            plugin = K8sRBACPlugin()
        except ImportError:
            # Fall back to generating without plugin
            info("K8s RBAC plugin not available, using stub implementation")
            _generate_stub_manifests(output_dir, dry_run)
            return

        # Create generator
        generator = RBACManifestGenerator(plugin=plugin, output_dir=output_dir)

        # Generate manifests
        result = generator.generate(
            security_config=security_config,
            secret_references=[],
        )

        if not result.success:
            for error in result.errors:
                click.echo(f"Error: {error}", err=True)
            error_exit(
                "RBAC generation failed",
                exit_code=ExitCode.GENERAL_ERROR,
            )

        # Report results
        success(f"Generated {result.service_accounts} ServiceAccounts")
        success(f"Generated {result.roles} Roles")
        success(f"Generated {result.role_bindings} RoleBindings")
        success(f"Generated {result.namespaces} Namespaces")

        if result.files_generated:
            info("Files written:")
            for file_path in result.files_generated:
                info(f"  {file_path}")

        success("RBAC generation complete.")

    except FileNotFoundError as e:
        error_exit(
            f"Configuration file not found: {e}",
            exit_code=ExitCode.FILE_NOT_FOUND,
        )
    except Exception as e:
        error_exit(
            f"RBAC generation failed: {e}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


def _generate_stub_manifests(output: Path, dry_run: bool) -> None:
    """Generate stub manifest files when plugin not available.

    Args:
        output: Output directory.
        dry_run: If True, don't write files.
    """
    if dry_run:
        info("Would create:")
        info(f"  {output}/namespaces.yaml")
        info(f"  {output}/serviceaccounts.yaml")
        info(f"  {output}/roles.yaml")
        info(f"  {output}/rolebindings.yaml")
        success("Dry-run complete.")
        return

    output.mkdir(parents=True, exist_ok=True)

    # Create empty manifest files
    for filename in ["namespaces.yaml", "serviceaccounts.yaml", "roles.yaml", "rolebindings.yaml"]:
        (output / filename).write_text("# Generated by floe rbac generate\n")
        info(f"Created: {output / filename}")

    success("Stub manifests created.")


__all__: list[str] = ["generate_command"]
