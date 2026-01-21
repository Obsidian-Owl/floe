"""RBAC diff command implementation.

Task ID: T035
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-026, FR-027, FR-063

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
from typing import TYPE_CHECKING, Any

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success, warning

if TYPE_CHECKING:
    pass


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
            from kubernetes import client
            from kubernetes import config as k8s_config
        except ImportError:
            error_exit(
                "kubernetes package not installed. Install with: pip install kubernetes",
                exit_code=ExitCode.GENERAL_ERROR,
            )

        # Try to import yaml
        import yaml

        # Import type-safe diff functions
        from floe_core.rbac.diff import compute_rbac_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        # Load kubeconfig
        if kubeconfig:
            k8s_config.load_kube_config(config_file=str(kubeconfig))
        else:
            try:
                k8s_config.load_incluster_config()
            except k8s_config.ConfigException:
                k8s_config.load_kube_config()

        # Load expected manifests
        expected_resources: list[dict[str, Any]] = []
        manifest_files = ["roles.yaml", "rolebindings.yaml", "serviceaccounts.yaml"]

        for filename in manifest_files:
            file_path = manifest_dir / filename
            if file_path.exists():
                content = file_path.read_text()
                if content.strip():
                    docs = list(yaml.safe_load_all(content))
                    for doc in docs:
                        if doc:
                            expected_resources.append(doc)

        # Get deployed resources
        rbac_api = client.RbacAuthorizationV1Api()
        core_api = client.CoreV1Api()

        actual_resources: list[dict[str, Any]] = []

        # Get deployed roles
        for role in rbac_api.list_namespaced_role(namespace).items:
            actual_resources.append(_k8s_to_dict(role, "Role"))

        # Get deployed role bindings
        for rb in rbac_api.list_namespaced_role_binding(namespace).items:
            actual_resources.append(_k8s_to_dict(rb, "RoleBinding"))

        # Get deployed service accounts (skip default)
        for sa in core_api.list_namespaced_service_account(namespace).items:
            if sa.metadata.name != "default":
                actual_resources.append(_k8s_to_dict(sa, "ServiceAccount"))

        # Use type-safe diff function
        diff_result = compute_rbac_diff(
            expected_resources=expected_resources,
            actual_resources=actual_resources,
            expected_source=str(manifest_dir),
            actual_source=f"cluster:{namespace}",
        )

        # Output results using type-safe models
        if output_format == "json":
            click.echo(diff_result.model_dump_json(indent=2))
        else:
            if not diff_result.has_differences():
                success("No differences found. Cluster matches expected manifests.")
            else:
                total_changes = (
                    diff_result.added_count
                    + diff_result.removed_count
                    + diff_result.modified_count
                )
                warning(f"Found {total_changes} difference(s):")

                by_type = diff_result.diffs_by_change_type()

                if by_type[DiffChangeType.ADDED]:
                    click.echo("\nTo be created (in manifest but not deployed):")
                    for diff in by_type[DiffChangeType.ADDED]:
                        click.echo(f"  + {diff.resource_kind}/{diff.resource_name}")

                if by_type[DiffChangeType.REMOVED]:
                    click.echo("\nTo be removed (deployed but not in manifest):")
                    for diff in by_type[DiffChangeType.REMOVED]:
                        click.echo(f"  - {diff.resource_kind}/{diff.resource_name}")

                if by_type[DiffChangeType.MODIFIED]:
                    click.echo("\nTo be modified:")
                    for diff in by_type[DiffChangeType.MODIFIED]:
                        click.echo(f"  ~ {diff.resource_kind}/{diff.resource_name}")
                        for detail in diff.diff_details:
                            click.echo(f"      {detail}")

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


def _k8s_to_dict(resource: Any, kind: str) -> dict[str, Any]:
    """Convert a Kubernetes API resource to a dictionary.

    Args:
        resource: Kubernetes API resource object.
        kind: K8s resource kind.

    Returns:
        Dictionary representation of the resource.
    """
    result: dict[str, Any] = {
        "kind": kind,
        "apiVersion": "v1" if kind == "ServiceAccount" else "rbac.authorization.k8s.io/v1",
        "metadata": {
            "name": resource.metadata.name,
            "namespace": resource.metadata.namespace,
        },
    }

    # Add role-specific fields
    if kind == "Role" and hasattr(resource, "rules") and resource.rules:
        result["rules"] = [
            {
                "apiGroups": rule.api_groups or [],
                "resources": rule.resources or [],
                "verbs": rule.verbs or [],
                "resourceNames": rule.resource_names or [],
            }
            for rule in resource.rules
        ]

    # Add role binding-specific fields
    if kind == "RoleBinding":
        if hasattr(resource, "role_ref") and resource.role_ref:
            result["roleRef"] = {
                "apiGroup": resource.role_ref.api_group,
                "kind": resource.role_ref.kind,
                "name": resource.role_ref.name,
            }
        if hasattr(resource, "subjects") and resource.subjects:
            result["subjects"] = [
                {
                    "kind": subj.kind,
                    "name": subj.name,
                    "namespace": subj.namespace,
                }
                for subj in resource.subjects
            ]

    return result


__all__: list[str] = ["diff_command"]
