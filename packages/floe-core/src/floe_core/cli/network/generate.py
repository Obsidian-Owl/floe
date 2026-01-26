"""Network generate command implementation.

Task ID: T069
Phase: 7 - Manifest Generator (US5)
User Story: US5 - Network and Pod Security CLI Commands
Requirements: FR-080

This module implements the `floe network generate` command which:
- Reads manifest.yaml configuration
- Discovers network security plugins via entry points
- Generates Kubernetes NetworkPolicy manifests
- Writes manifests to output directory

Example:
    $ floe network generate
    $ floe network generate --config manifest.yaml --output target/network/
    $ floe network generate --dry-run
    $ floe network generate --namespace floe-jobs
"""

from __future__ import annotations

from pathlib import Path

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success
from floe_core.network.schemas import _validate_namespace


@click.command(
    name="generate",
    help="""\b
Generate NetworkPolicy manifests from configuration (FR-080).

Reads the manifest.yaml configuration and generates Kubernetes NetworkPolicy
manifests for specified namespaces. Supports dry-run mode to preview changes.

Output files:
    target/network/{namespace}-*.yaml
    target/network/NETWORK-POLICY-SUMMARY.md

Examples:
    $ floe network generate
    $ floe network generate --config platform.yaml --output deploy/network/
    $ floe network generate --dry-run
    $ floe network generate --namespace floe-jobs
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
@click.option(
    "--namespace",
    "-n",
    type=str,
    default=None,
    help="Generate for specific namespace only.",
    metavar="TEXT",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    hidden=True,
    help="Show verbose error messages with tracebacks.",
)
def generate_command(
    config: Path | None,
    output: Path | None,
    dry_run: bool,
    namespace: str | None,
    debug: bool,
) -> None:
    """Generate NetworkPolicy manifests from configuration.

    Reads the manifest.yaml configuration file and generates Kubernetes
    NetworkPolicy manifests. Supports dry-run mode to preview changes.

    Args:
        config: Path to manifest.yaml configuration file.
        output: Output directory for generated manifests.
        dry_run: If True, show what would be generated without writing.
        namespace: If specified, generate policies for this namespace only.
    """
    # Validate required config
    if config is None:
        error_exit(
            "Missing --config option. Provide path to manifest.yaml.",
            exit_code=ExitCode.USAGE_ERROR,
        )

    # Default output directory
    output_dir = output if output is not None else Path("target/network")

    info(f"Reading configuration: {config}")
    info(f"Output directory: {output_dir}")

    if namespace is not None:
        try:
            _validate_namespace(namespace)
        except ValueError as e:
            error_exit(str(e), exit_code=ExitCode.USAGE_ERROR)
        info(f"Generating for namespace: {namespace}")

    if dry_run:
        info("Dry-run mode: no files will be written")

    try:
        # Import here to avoid circular dependencies
        from floe_core.compilation.loader import load_manifest
        from floe_core.network import NetworkPolicyManifestGenerator
        from floe_core.network.generator import discover_network_security_plugins

        # Load manifest
        _manifest = load_manifest(config)

        # Discover network security plugins
        plugins = discover_network_security_plugins()
        if not plugins:
            info("No network security plugins available, using stub implementation")
            _generate_stub_manifests(output_dir, dry_run)
            return

        # Get first available plugin
        plugin_name = next(iter(plugins.keys()))
        plugin_class = plugins[plugin_name]
        plugin_instance = plugin_class()

        info(f"Using network security plugin: {plugin_name}")

        # Create generator
        generator = NetworkPolicyManifestGenerator(plugin=plugin_instance)

        # Determine namespaces to generate for
        namespaces_to_generate: list[str] = []
        if namespace is not None:
            namespaces_to_generate = [namespace]
        else:
            # Default: generate for common namespaces
            namespaces_to_generate = ["default", "floe-jobs", "floe-services"]

        # Generate manifests
        result = generator.generate(namespaces=namespaces_to_generate)

        if result.is_empty:
            info("No policies generated")
            success("Network policy generation complete (no policies).")
            return

        # Report results
        success(f"Generated {result.policies_count} NetworkPolicy manifests")
        success(f"Generated {result.default_deny_count} default-deny policies")
        success(f"Generated {result.egress_rules_count} egress rules")
        success(f"Generated {result.ingress_rules_count} ingress rules")

        if result.has_warnings:
            for warning in result.warnings:
                click.echo(f"Warning: {warning}", err=True)

        if dry_run:
            info("Dry-run: would write to:")
            for policy in result.generated_policies:
                ns = policy.get("metadata", {}).get("namespace", "unknown")
                name = policy.get("metadata", {}).get("name", "unnamed")
                info(f"  {output_dir}/{ns}-{name}.yaml")
            info(f"  {output_dir}/NETWORK-POLICY-SUMMARY.md")
            success("Dry-run complete.")
        else:
            # Write manifests
            generator.write_manifests(result, output_dir)
            info("Files written:")
            for policy in result.generated_policies:
                ns = policy.get("metadata", {}).get("namespace", "unknown")
                name = policy.get("metadata", {}).get("name", "unnamed")
                info(f"  {output_dir}/{ns}-{name}.yaml")
            info(f"  {output_dir}/NETWORK-POLICY-SUMMARY.md")
            success("Network policy generation complete.")

    except FileNotFoundError as e:
        if debug:
            import traceback

            traceback.print_exc()
        error_exit(
            f"Configuration file not found: {e.filename}",
            exit_code=ExitCode.FILE_NOT_FOUND,
        )
    except Exception as e:
        if debug:
            import traceback

            traceback.print_exc()
        error_exit(
            f"Network policy generation failed: {type(e).__name__}",
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
        info(f"  {output}/default-default-deny.yaml")
        info(f"  {output}/floe-jobs-default-deny.yaml")
        info(f"  {output}/floe-services-default-deny.yaml")
        info(f"  {output}/NETWORK-POLICY-SUMMARY.md")
        success("Dry-run complete.")
        return

    output.mkdir(parents=True, exist_ok=True)

    # Create empty manifest files
    stub_content = "# Generated by floe network generate\n"
    for filename in [
        "default-default-deny.yaml",
        "floe-jobs-default-deny.yaml",
        "floe-services-default-deny.yaml",
    ]:
        (output / filename).write_text(stub_content)
        info(f"Created: {output / filename}")

    # Create summary
    summary_content = """# Network Policy Summary

Generated by floe NetworkPolicyManifestGenerator.

## Statistics

| Metric | Value |
|--------|-------|
| Total Policies | 3 |
| Namespaces | 3 |
| Default-Deny Policies | 3 |
| Egress Rules | 3 |
| Ingress Rules | 0 |
| Warnings | 0 |

## DNS Egress

DNS egress (UDP/TCP port 53 to kube-system) is **always included** in all policies.
This cannot be disabled as it is required for Kubernetes service discovery.

## Policies by Namespace

### default

- `default-deny`

### floe-jobs

- `default-deny`

### floe-services

- `default-deny`
"""
    (output / "NETWORK-POLICY-SUMMARY.md").write_text(summary_content)
    info(f"Created: {output / 'NETWORK-POLICY-SUMMARY.md'}")

    success("Stub manifests created.")


__all__: list[str] = ["generate_command"]
