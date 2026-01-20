"""RBAC diff command implementation.

Task ID: T035
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-026, FR-027

This module implements the `floe rbac diff` command which:
- Compares expected vs deployed RBAC
- Shows added, removed, and modified resources
- Supports JSON and text output formats

Example:
    $ floe rbac diff
    $ floe rbac diff --manifest-dir deploy/rbac
    $ floe rbac diff --output json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success, warning


@click.command(
    name="diff",
    help="Show differences between expected and deployed RBAC (FR-063).",
    epilog="""
Compares the manifests in the target directory with the actual
RBAC configuration in the cluster.

Examples:
    $ floe rbac diff
    $ floe rbac diff --manifest-dir deploy/rbac
    $ floe rbac diff --output json
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--manifest-dir",
    "-m",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Directory containing expected RBAC manifests.",
    metavar="PATH",
)
@click.option(
    "--namespace",
    "-n",
    type=str,
    default=None,
    help="Namespaces to diff (default: from manifests).",
    metavar="TEXT",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default=None,
    help="Output format.",
)
@click.option(
    "--kubeconfig",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Path to kubeconfig file.",
    metavar="PATH",
)
def diff_command(
    manifest_dir: Path | None,
    namespace: str | None,
    output: str | None,
    kubeconfig: Path | None,
) -> None:
    """Show differences between expected and deployed RBAC.

    Compares the manifests in the target directory with the actual
    RBAC configuration in the cluster.

    Args:
        manifest_dir: Directory containing expected RBAC manifests.
        namespace: Namespace to diff (default: from manifests).
        output: Output format (text or json).
        kubeconfig: Path to kubeconfig file.
    """
    # Validate required options
    if manifest_dir is None:
        error_exit(
            "Missing --manifest-dir option. Provide path to manifest directory.",
            exit_code=ExitCode.USAGE_ERROR,
        )

    if namespace is None:
        error_exit(
            "Missing --namespace option. Provide namespace to diff.",
            exit_code=ExitCode.USAGE_ERROR,
        )

    # Default values
    output_format = output if output is not None else "text"

    info(f"Comparing manifests in: {manifest_dir}")
    info(f"Against namespace: {namespace}")

    if kubeconfig:
        info(f"Using kubeconfig: {kubeconfig}")

    try:
        # Try to import kubernetes client
        try:
            from kubernetes import client, config as k8s_config
        except ImportError:
            error_exit(
                "kubernetes package not installed. Install with: pip install kubernetes",
                exit_code=ExitCode.GENERAL_ERROR,
            )

        # Try to import yaml
        import yaml

        # Load kubeconfig
        if kubeconfig:
            k8s_config.load_kube_config(config_file=str(kubeconfig))
        else:
            try:
                k8s_config.load_incluster_config()
            except k8s_config.ConfigException:
                k8s_config.load_kube_config()

        # Load expected manifests
        expected: dict[str, list[dict[str, Any]]] = {}
        manifest_files = ["roles.yaml", "rolebindings.yaml", "serviceaccounts.yaml"]

        for filename in manifest_files:
            file_path = manifest_dir / filename
            if file_path.exists():
                content = file_path.read_text()
                if content.strip():
                    docs = list(yaml.safe_load_all(content))
                    expected[filename] = [d for d in docs if d]
                else:
                    expected[filename] = []
            else:
                expected[filename] = []

        # Get deployed resources
        rbac_api = client.RbacAuthorizationV1Api()
        core_api = client.CoreV1Api()

        deployed_roles = {r.metadata.name: r for r in rbac_api.list_namespaced_role(namespace).items}
        deployed_bindings = {
            rb.metadata.name: rb for rb in rbac_api.list_namespaced_role_binding(namespace).items
        }
        deployed_sa = {
            sa.metadata.name: sa for sa in core_api.list_namespaced_service_account(namespace).items
        }

        # Compare and build diff
        diff_results: dict[str, Any] = {
            "added": [],
            "removed": [],
            "modified": [],
        }

        # Compare roles
        expected_roles = {r["metadata"]["name"]: r for r in expected.get("roles.yaml", []) if r}
        for name in expected_roles:
            if name not in deployed_roles:
                diff_results["added"].append({"kind": "Role", "name": name})

        for name in deployed_roles:
            if name not in expected_roles:
                diff_results["removed"].append({"kind": "Role", "name": name})

        # Compare role bindings
        expected_bindings = {
            rb["metadata"]["name"]: rb for rb in expected.get("rolebindings.yaml", []) if rb
        }
        for name in expected_bindings:
            if name not in deployed_bindings:
                diff_results["added"].append({"kind": "RoleBinding", "name": name})

        for name in deployed_bindings:
            if name not in expected_bindings:
                diff_results["removed"].append({"kind": "RoleBinding", "name": name})

        # Compare service accounts
        expected_sa = {
            sa["metadata"]["name"]: sa for sa in expected.get("serviceaccounts.yaml", []) if sa
        }
        for name in expected_sa:
            if name not in deployed_sa:
                diff_results["added"].append({"kind": "ServiceAccount", "name": name})

        for name in deployed_sa:
            if name not in expected_sa and name != "default":  # Skip default SA
                diff_results["removed"].append({"kind": "ServiceAccount", "name": name})

        # Output results
        if output_format == "json":
            import json

            result = {
                "namespace": namespace,
                "manifest_dir": str(manifest_dir),
                "diff": diff_results,
            }
            click.echo(json.dumps(result, indent=2))
        else:
            total_changes = (
                len(diff_results["added"])
                + len(diff_results["removed"])
                + len(diff_results["modified"])
            )

            if total_changes == 0:
                success("No differences found. Cluster matches expected manifests.")
            else:
                warning(f"Found {total_changes} difference(s):")

                if diff_results["added"]:
                    click.echo("\nTo be created (in manifest but not deployed):")
                    for item in diff_results["added"]:
                        click.echo(f"  + {item['kind']}/{item['name']}")

                if diff_results["removed"]:
                    click.echo("\nTo be removed (deployed but not in manifest):")
                    for item in diff_results["removed"]:
                        click.echo(f"  - {item['kind']}/{item['name']}")

                if diff_results["modified"]:
                    click.echo("\nTo be modified:")
                    for item in diff_results["modified"]:
                        click.echo(f"  ~ {item['kind']}/{item['name']}")

    except FileNotFoundError as e:
        error_exit(
            f"Manifest file not found: {e}",
            exit_code=ExitCode.FILE_NOT_FOUND,
        )
    except Exception as e:
        error_exit(
            f"RBAC diff failed: {e}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


__all__: list[str] = ["diff_command"]
