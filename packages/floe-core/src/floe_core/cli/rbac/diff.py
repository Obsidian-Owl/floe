"""RBAC diff command implementation.

Task ID: T035
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-026, FR-027, FR-063

Refactored: T021 (Extract Method to reduce CC from 27 to ≤10)

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
    from floe_core.schemas.rbac_diff import RBACDiffResult


# =============================================================================
# Extracted Helper Functions (T021 - Reduce Cyclomatic Complexity)
# =============================================================================


def _validate_required_options(
    manifest_dir: Path | None,
    namespace: str | None,
) -> tuple[Path, str]:
    """Validate required CLI options and return them.

    Args:
        manifest_dir: Directory containing expected RBAC manifests.
        namespace: Namespace to diff.

    Returns:
        Tuple of validated (manifest_dir, namespace).

    Raises:
        SystemExit: If required options are missing.
    """
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
    # Type narrowing - error_exit calls sys.exit so we never reach here if None
    return manifest_dir, namespace


def _load_kubeconfig(kubeconfig: Path | None) -> None:
    """Load Kubernetes configuration.

    Args:
        kubeconfig: Optional path to kubeconfig file.

    Raises:
        SystemExit: If kubernetes package not installed.
    """
    try:
        from kubernetes import config as k8s_config
    except ImportError:
        error_exit(
            "kubernetes package not installed. Install with: pip install kubernetes",
            exit_code=ExitCode.GENERAL_ERROR,
        )

    if kubeconfig:
        k8s_config.load_kube_config(config_file=str(kubeconfig))
    else:
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()


def _load_expected_manifests(manifest_dir: Path) -> list[dict[str, Any]]:
    """Load expected RBAC resources from manifest files.

    Args:
        manifest_dir: Directory containing RBAC manifest files.

    Returns:
        List of resource dictionaries from manifest files.
    """
    import yaml

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

    return expected_resources


def _fetch_deployed_resources(namespace: str) -> list[dict[str, Any]]:
    """Fetch deployed RBAC resources from the cluster.

    Args:
        namespace: Kubernetes namespace to fetch from.

    Returns:
        List of resource dictionaries from the cluster.
    """
    from kubernetes import client

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

    return actual_resources


def _output_diff_as_text(diff_result: RBACDiffResult) -> None:
    """Output diff result in text format.

    Args:
        diff_result: The computed RBAC diff result.
    """
    from floe_core.schemas.rbac_diff import DiffChangeType

    if not diff_result.has_differences():
        success("No differences found. Cluster matches expected manifests.")
        return

    total_changes = (
        diff_result.added_count + diff_result.removed_count + diff_result.modified_count
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
        "apiVersion": _get_api_version(kind),
        "metadata": {
            "name": resource.metadata.name,
            "namespace": resource.metadata.namespace,
        },
    }

    # Add kind-specific fields
    _add_role_fields(result, resource, kind)
    _add_role_binding_fields(result, resource, kind)

    return result


def _get_api_version(kind: str) -> str:
    """Get the API version for a resource kind.

    Args:
        kind: K8s resource kind.

    Returns:
        API version string.
    """
    return "v1" if kind == "ServiceAccount" else "rbac.authorization.k8s.io/v1"


def _add_role_fields(result: dict[str, Any], resource: Any, kind: str) -> None:
    """Add role-specific fields to the result dictionary.

    Args:
        result: Result dictionary to modify.
        resource: Kubernetes API resource object.
        kind: K8s resource kind.
    """
    if kind != "Role":
        return
    if not hasattr(resource, "rules") or not resource.rules:
        return

    result["rules"] = [
        {
            "apiGroups": rule.api_groups or [],
            "resources": rule.resources or [],
            "verbs": rule.verbs or [],
            "resourceNames": rule.resource_names or [],
        }
        for rule in resource.rules
    ]


def _add_role_binding_fields(result: dict[str, Any], resource: Any, kind: str) -> None:
    """Add role binding-specific fields to the result dictionary.

    Args:
        result: Result dictionary to modify.
        resource: Kubernetes API resource object.
        kind: K8s resource kind.
    """
    if kind != "RoleBinding":
        return

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


# =============================================================================
# Main Command
# =============================================================================


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
    validated_manifest_dir, validated_namespace = _validate_required_options(
        manifest_dir, namespace
    )
    output_format = output if output is not None else "text"

    info(f"Comparing manifests in: {validated_manifest_dir}")
    info(f"Against namespace: {validated_namespace}")

    if kubeconfig:
        info(f"Using kubeconfig: {kubeconfig}")

    try:
        from floe_core.rbac.diff import compute_rbac_diff

        # Load kubeconfig
        _load_kubeconfig(kubeconfig)

        # Load expected manifests
        expected_resources = _load_expected_manifests(validated_manifest_dir)

        # Fetch deployed resources
        actual_resources = _fetch_deployed_resources(validated_namespace)

        # Compute diff using type-safe function
        diff_result = compute_rbac_diff(
            expected_resources=expected_resources,
            actual_resources=actual_resources,
            expected_source=str(validated_manifest_dir),
            actual_source=f"cluster:{validated_namespace}",
        )

        # Output results
        if output_format == "json":
            click.echo(diff_result.model_dump_json(indent=2))
        else:
            _output_diff_as_text(diff_result)

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
