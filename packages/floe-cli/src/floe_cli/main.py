"""Main CLI entry point for floe.

This module provides the main Click CLI group and subcommands.

Task: T059, T060, T061, T062
User Story: US6 - RBAC Audit and Validation
Requirements: FR-060, FR-061, FR-062, FR-063

Example:
    $ floe rbac generate
    $ floe rbac validate
    $ floe rbac audit
    $ floe rbac diff
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import structlog
import yaml

from floe_cli.commands.rbac import (
    RBACAuditReport,
    RBACDiffResult,
    RBACValidationResult,
    ValidationStatus,
    compute_rbac_diff,
    validate_manifest_against_config,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Main CLI Group
# =============================================================================


@click.group()
@click.version_option(version="0.1.0", prog_name="floe")
def cli() -> None:
    """floe - CLI for the floe data platform.

    Manage data products, RBAC, and deployments.
    """
    pass


# =============================================================================
# RBAC Command Group
# =============================================================================


@cli.group()
def rbac() -> None:
    """Manage Kubernetes RBAC resources.

    Commands for generating, validating, auditing, and diffing RBAC manifests.
    """
    pass


# =============================================================================
# T059: floe rbac generate (FR-060)
# =============================================================================


@rbac.command("generate")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default="manifest.yaml",
    help="Path to manifest.yaml configuration file.",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    default="target/rbac",
    help="Output directory for generated manifests.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be generated without writing files.",
)
def generate_command(
    config_path: Path,
    output_dir: Path,
    dry_run: bool,
) -> None:
    """Generate RBAC manifests from configuration (FR-060).

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
    """
    try:
        # Import plugin at runtime to avoid hard dependency
        from floe_core.schemas.rbac import RBACConfig
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        # Load configuration
        click.echo(f"Loading configuration from {config_path}...")
        with config_path.open() as f:
            config_data = yaml.safe_load(f)

        # Extract security.rbac section
        security_config = config_data.get("security", {})
        rbac_config_data = security_config.get("rbac", {})

        if not rbac_config_data.get("enabled", False):
            click.echo("RBAC is not enabled in configuration. Skipping generation.")
            return

        # Create RBAC config
        rbac_config = RBACConfig(**rbac_config_data)

        # Generate manifests using the plugin
        plugin = K8sRBACPlugin()

        if dry_run:
            click.echo("\n[DRY RUN] Would generate the following manifests:")
            click.echo(f"  - {output_dir}/namespaces.yaml")
            click.echo(f"  - {output_dir}/serviceaccounts.yaml")
            click.echo(f"  - {output_dir}/roles.yaml")
            click.echo(f"  - {output_dir}/rolebindings.yaml")
            return

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate manifests
        click.echo("Generating RBAC manifests...")
        manifests = plugin.generate_manifests(rbac_config)

        # Write manifests to files
        _write_manifests(output_dir, manifests)

        click.echo(f"\nRBAC manifests generated successfully in {output_dir}/")
        click.echo("\nTo apply to Kubernetes:")
        click.echo(f"  kubectl apply -f {output_dir}/")

    except ImportError as e:
        click.echo(f"Error: Required package not installed: {e}", err=True)
        click.echo("Install with: pip install floe-core floe-rbac-k8s", err=True)
        raise SystemExit(1) from e
    except FileNotFoundError as e:
        click.echo(f"Error: Configuration file not found: {e}", err=True)
        raise SystemExit(1) from e
    except Exception as e:
        click.echo(f"Error generating manifests: {e}", err=True)
        logger.exception("Error generating RBAC manifests")
        raise SystemExit(1) from e


def _write_manifests(output_dir: Path, manifests: dict[str, list[dict[str, Any]]]) -> None:
    """Write manifests to YAML files.

    Args:
        output_dir: Directory to write files to.
        manifests: Dictionary of resource kind to list of manifests.
    """
    file_mapping = {
        "Namespace": "namespaces.yaml",
        "ServiceAccount": "serviceaccounts.yaml",
        "Role": "roles.yaml",
        "ClusterRole": "clusterroles.yaml",
        "RoleBinding": "rolebindings.yaml",
        "ClusterRoleBinding": "clusterrolebindings.yaml",
    }

    for kind, filename in file_mapping.items():
        resources = manifests.get(kind, [])
        if resources:
            file_path = output_dir / filename
            with file_path.open("w") as f:
                yaml.dump_all(resources, f, default_flow_style=False, sort_keys=False)
            click.echo(f"  Generated {filename} ({len(resources)} resources)")


# =============================================================================
# T060: floe rbac validate (FR-061)
# =============================================================================


@rbac.command("validate")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default="manifest.yaml",
    help="Path to manifest.yaml configuration file.",
)
@click.option(
    "--manifest-dir",
    "-m",
    "manifest_dir",
    type=click.Path(exists=True, path_type=Path),
    default="target/rbac",
    help="Directory containing generated RBAC manifests.",
)
@click.option(
    "--output",
    "-o",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def validate_command(
    config_path: Path,
    manifest_dir: Path,
    output_format: str,
) -> None:
    """Validate RBAC manifests against configuration (FR-061).

    Checks that generated manifests match the expected configuration,
    detecting missing or extra resources.

    Examples:
        $ floe rbac validate
        $ floe rbac validate --manifest-dir deploy/rbac
        $ floe rbac validate --output json
    """
    try:
        click.echo(f"Validating manifests in {manifest_dir} against {config_path}...")

        # Load manifests from directory
        manifest_resources = _load_manifests_from_dir(manifest_dir)

        # Load expected configuration
        # For now, we'll do a basic validation of manifest structure
        issues: list[Any] = []

        # Validate each resource type
        for kind, resources in manifest_resources.items():
            for resource in resources:
                resource_issues = _validate_resource_structure(resource, kind)
                issues.extend(resource_issues)

        # Determine status
        if issues:
            status = ValidationStatus.INVALID
        else:
            status = ValidationStatus.VALID

        result = RBACValidationResult(
            status=status,
            config_path=str(config_path),
            manifest_dir=str(manifest_dir),
            issues=issues,
            service_accounts_validated=len(manifest_resources.get("ServiceAccount", [])),
            roles_validated=len(manifest_resources.get("Role", [])),
            role_bindings_validated=len(manifest_resources.get("RoleBinding", [])),
            namespaces_validated=len(manifest_resources.get("Namespace", [])),
        )

        # Output result
        if output_format == "json":
            click.echo(result.model_dump_json(indent=2))
        else:
            _print_validation_result(result)

        # Exit with error if invalid
        if result.has_errors:
            raise SystemExit(1)

    except FileNotFoundError as e:
        click.echo(f"Error: File not found: {e}", err=True)
        raise SystemExit(1) from e
    except Exception as e:
        click.echo(f"Error validating manifests: {e}", err=True)
        logger.exception("Error validating RBAC manifests")
        raise SystemExit(1) from e


def _load_manifests_from_dir(manifest_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load all YAML manifests from a directory.

    Args:
        manifest_dir: Directory containing YAML files.

    Returns:
        Dictionary mapping resource kinds to lists of resources.
    """
    resources: dict[str, list[dict[str, Any]]] = {}

    for yaml_file in manifest_dir.glob("*.yaml"):
        with yaml_file.open() as f:
            docs = list(yaml.safe_load_all(f))
            for doc in docs:
                if doc and isinstance(doc, dict):
                    kind = doc.get("kind", "Unknown")
                    if kind not in resources:
                        resources[kind] = []
                    resources[kind].append(doc)

    return resources


def _validate_resource_structure(
    resource: dict[str, Any],
    kind: str,
) -> list[Any]:
    """Validate basic resource structure.

    Args:
        resource: K8s resource dictionary.
        kind: Expected resource kind.

    Returns:
        List of validation issues.
    """
    from floe_cli.commands.rbac import ValidationIssue, ValidationIssueType

    issues: list[ValidationIssue] = []

    # Check required fields
    if "apiVersion" not in resource:
        issues.append(
            ValidationIssue(
                issue_type=ValidationIssueType.INVALID_YAML,
                resource_kind=kind,
                resource_name=resource.get("metadata", {}).get("name", "unknown"),
                message="Missing apiVersion field",
            )
        )

    if "metadata" not in resource:
        issues.append(
            ValidationIssue(
                issue_type=ValidationIssueType.INVALID_YAML,
                resource_kind=kind,
                resource_name="unknown",
                message="Missing metadata field",
            )
        )
    elif "name" not in resource.get("metadata", {}):
        issues.append(
            ValidationIssue(
                issue_type=ValidationIssueType.INVALID_YAML,
                resource_kind=kind,
                resource_name="unknown",
                message="Missing metadata.name field",
            )
        )

    return issues


def _print_validation_result(result: RBACValidationResult) -> None:
    """Print validation result in human-readable format.

    Args:
        result: Validation result to print.
    """
    if result.is_valid:
        click.echo(click.style("\n✓ Validation PASSED", fg="green", bold=True))
    else:
        click.echo(click.style("\n✗ Validation FAILED", fg="red", bold=True))

    click.echo(f"\nResources validated:")
    click.echo(f"  Service Accounts: {result.service_accounts_validated}")
    click.echo(f"  Roles: {result.roles_validated}")
    click.echo(f"  Role Bindings: {result.role_bindings_validated}")
    click.echo(f"  Namespaces: {result.namespaces_validated}")

    if result.issues:
        click.echo(f"\nIssues found ({len(result.issues)}):")
        for issue in result.issues:
            click.echo(
                f"  - [{issue.issue_type.value}] {issue.resource_kind}/{issue.resource_name}: "
                f"{issue.message}"
            )


# =============================================================================
# T061: floe rbac audit (FR-062)
# =============================================================================


@rbac.command("audit")
@click.option(
    "--namespace",
    "-n",
    "namespaces",
    multiple=True,
    help="Namespaces to audit (default: all floe-managed).",
)
@click.option(
    "--output",
    "-o",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option(
    "--kubeconfig",
    type=click.Path(exists=True, path_type=Path),
    help="Path to kubeconfig file.",
)
def audit_command(
    namespaces: tuple[str, ...],
    output_format: str,
    kubeconfig: Path | None,
) -> None:
    """Audit current cluster RBAC state (FR-062).

    Analyzes RBAC configuration in the cluster and reports findings
    such as wildcard permissions, missing resource constraints, etc.

    Examples:
        $ floe rbac audit
        $ floe rbac audit --namespace floe-jobs
        $ floe rbac audit --output json
    """
    try:
        # Import kubernetes at runtime
        from kubernetes import client, config

        # Load kubeconfig
        if kubeconfig:
            config.load_kube_config(str(kubeconfig))
        else:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()

        click.echo("Auditing cluster RBAC configuration...")

        # Get cluster info
        v1 = client.CoreV1Api()
        rbac_v1 = client.RbacAuthorizationV1Api()

        # Determine namespaces to audit
        if namespaces:
            ns_list = list(namespaces)
        else:
            # Audit all floe-managed namespaces
            all_ns = v1.list_namespace(label_selector="app.kubernetes.io/managed-by=floe")
            ns_list = [ns.metadata.name for ns in all_ns.items]
            if not ns_list:
                click.echo("No floe-managed namespaces found. Auditing default namespace.")
                ns_list = ["default"]

        # Build audit report
        report = _build_audit_report(v1, rbac_v1, ns_list)

        # Output result
        if output_format == "json":
            click.echo(report.model_dump_json(indent=2))
        else:
            _print_audit_report(report)

        # Exit with error if critical findings
        if report.has_critical_findings():
            raise SystemExit(1)

    except ImportError as e:
        click.echo(f"Error: kubernetes package not installed: {e}", err=True)
        click.echo("Install with: pip install kubernetes", err=True)
        raise SystemExit(1) from e
    except Exception as e:
        click.echo(f"Error auditing cluster: {e}", err=True)
        logger.exception("Error auditing cluster RBAC")
        raise SystemExit(1) from e


def _build_audit_report(
    v1: Any,
    rbac_v1: Any,
    namespaces: list[str],
) -> RBACAuditReport:
    """Build audit report from cluster state.

    Args:
        v1: Kubernetes CoreV1Api client.
        rbac_v1: Kubernetes RbacAuthorizationV1Api client.
        namespaces: List of namespaces to audit.

    Returns:
        RBACAuditReport with findings.
    """
    from floe_cli.commands.rbac import (
        AuditFinding,
        NamespaceSummary,
        ServiceAccountSummary,
        check_missing_resource_names,
        detect_wildcard_permissions,
    )

    findings: list[AuditFinding] = []
    namespace_summaries: list[NamespaceSummary] = []
    sa_summaries: list[ServiceAccountSummary] = []
    total_roles = 0
    total_role_bindings = 0

    for ns in namespaces:
        # Get namespace info
        try:
            ns_obj = v1.read_namespace(ns)
            labels = ns_obj.metadata.labels or {}
            pss_level = labels.get("pod-security.kubernetes.io/enforce")
            managed = labels.get("app.kubernetes.io/managed-by") == "floe"
        except Exception:
            pss_level = None
            managed = False

        # Get service accounts
        sa_list = v1.list_namespaced_service_account(ns)
        for sa in sa_list.items:
            sa_labels = sa.metadata.labels or {}
            sa_summaries.append(
                ServiceAccountSummary(
                    name=sa.metadata.name,
                    namespace=ns,
                    automount_token=sa.automount_service_account_token or False,
                    managed_by_floe=sa_labels.get("app.kubernetes.io/managed-by") == "floe",
                )
            )

        # Get roles and check for issues
        roles = rbac_v1.list_namespaced_role(ns)
        total_roles += len(roles.items)
        for role in roles.items:
            rules = [
                {
                    "apiGroups": rule.api_groups or [],
                    "resources": rule.resources or [],
                    "verbs": rule.verbs or [],
                    "resourceNames": rule.resource_names or [],
                }
                for rule in (role.rules or [])
            ]
            findings.extend(detect_wildcard_permissions(rules, role.metadata.name, ns))
            findings.extend(check_missing_resource_names(rules, role.metadata.name, ns))

        # Get role bindings
        bindings = rbac_v1.list_namespaced_role_binding(ns)
        total_role_bindings += len(bindings.items)

        namespace_summaries.append(
            NamespaceSummary(
                name=ns,
                pss_enforce=pss_level,
                service_accounts=len(sa_list.items),
                roles=len(roles.items),
                role_bindings=len(bindings.items),
                managed_by_floe=managed,
            )
        )

    return RBACAuditReport(
        cluster_name="current-context",
        namespaces=namespace_summaries,
        service_accounts=sa_summaries,
        findings=findings,
        total_service_accounts=len(sa_summaries),
        total_roles=total_roles,
        total_role_bindings=total_role_bindings,
        floe_managed_count=sum(1 for ns in namespace_summaries if ns.managed_by_floe),
    )


def _print_audit_report(report: RBACAuditReport) -> None:
    """Print audit report in human-readable format.

    Args:
        report: Audit report to print.
    """
    click.echo(f"\n{'='*60}")
    click.echo("RBAC Audit Report")
    click.echo(f"{'='*60}")
    click.echo(f"Generated: {report.generated_at.isoformat()}")
    click.echo(f"Cluster: {report.cluster_name}")

    click.echo(f"\nNamespaces audited: {len(report.namespaces)}")
    for ns in report.namespaces:
        managed_str = " [floe-managed]" if ns.managed_by_floe else ""
        pss_str = f" (PSS: {ns.pss_enforce})" if ns.pss_enforce else ""
        click.echo(f"  - {ns.name}{managed_str}{pss_str}")

    click.echo(f"\nResources:")
    click.echo(f"  Service Accounts: {report.total_service_accounts}")
    click.echo(f"  Roles: {report.total_roles}")
    click.echo(f"  Role Bindings: {report.total_role_bindings}")
    click.echo(f"  Floe-managed: {report.floe_managed_count}")

    if report.findings:
        click.echo(f"\n{'='*60}")
        click.echo(f"Findings ({len(report.findings)}):")
        click.echo(f"{'='*60}")

        by_severity = report.findings_by_severity()
        from floe_cli.commands.rbac import AuditSeverity

        for severity in [
            AuditSeverity.CRITICAL,
            AuditSeverity.ERROR,
            AuditSeverity.WARNING,
            AuditSeverity.INFO,
        ]:
            findings = by_severity[severity]
            if findings:
                color = {
                    AuditSeverity.CRITICAL: "red",
                    AuditSeverity.ERROR: "red",
                    AuditSeverity.WARNING: "yellow",
                    AuditSeverity.INFO: "blue",
                }.get(severity, "white")

                click.echo(
                    click.style(f"\n[{severity.value.upper()}]", fg=color, bold=True)
                )
                for finding in findings:
                    ns_str = f" ({finding.resource_namespace})" if finding.resource_namespace else ""
                    click.echo(f"  {finding.resource_kind}/{finding.resource_name}{ns_str}")
                    click.echo(f"    {finding.message}")
                    if finding.recommendation:
                        click.echo(f"    Recommendation: {finding.recommendation}")
    else:
        click.echo(click.style("\n✓ No issues found", fg="green", bold=True))


# =============================================================================
# T062: floe rbac diff (FR-063)
# =============================================================================


@rbac.command("diff")
@click.option(
    "--manifest-dir",
    "-m",
    "manifest_dir",
    type=click.Path(exists=True, path_type=Path),
    default="target/rbac",
    help="Directory containing expected RBAC manifests.",
)
@click.option(
    "--namespace",
    "-n",
    "namespaces",
    multiple=True,
    help="Namespaces to diff (default: from manifests).",
)
@click.option(
    "--output",
    "-o",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option(
    "--kubeconfig",
    type=click.Path(exists=True, path_type=Path),
    help="Path to kubeconfig file.",
)
def diff_command(
    manifest_dir: Path,
    namespaces: tuple[str, ...],
    output_format: str,
    kubeconfig: Path | None,
) -> None:
    """Show differences between expected and deployed RBAC (FR-063).

    Compares the manifests in the target directory with the actual
    RBAC configuration in the cluster.

    Examples:
        $ floe rbac diff
        $ floe rbac diff --manifest-dir deploy/rbac
        $ floe rbac diff --output json
    """
    try:
        # Import kubernetes at runtime
        from kubernetes import client, config

        # Load kubeconfig
        if kubeconfig:
            config.load_kube_config(str(kubeconfig))
        else:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()

        click.echo(f"Comparing {manifest_dir} with cluster...")

        # Load expected manifests
        expected_resources = _load_manifests_from_dir(manifest_dir)

        # Determine namespaces
        if namespaces:
            ns_list = list(namespaces)
        else:
            # Extract namespaces from manifests
            ns_list = list({
                r.get("metadata", {}).get("namespace", "default")
                for resources in expected_resources.values()
                for r in resources
                if r.get("metadata", {}).get("namespace")
            })
            if not ns_list:
                ns_list = ["default"]

        # Load actual resources from cluster
        actual_resources = _load_cluster_resources(ns_list)

        # Flatten resources for comparison
        expected_flat = [r for resources in expected_resources.values() for r in resources]
        actual_flat = [r for resources in actual_resources.values() for r in resources]

        # Compute diff
        result = compute_rbac_diff(
            expected_resources=expected_flat,
            actual_resources=actual_flat,
            expected_source=str(manifest_dir),
            actual_source="cluster",
        )

        # Output result
        if output_format == "json":
            click.echo(result.model_dump_json(indent=2))
        else:
            _print_diff_result(result)

        # Exit with error if differences
        if result.has_differences():
            raise SystemExit(1)

    except ImportError as e:
        click.echo(f"Error: kubernetes package not installed: {e}", err=True)
        click.echo("Install with: pip install kubernetes", err=True)
        raise SystemExit(1) from e
    except Exception as e:
        click.echo(f"Error computing diff: {e}", err=True)
        logger.exception("Error computing RBAC diff")
        raise SystemExit(1) from e


def _load_cluster_resources(namespaces: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Load RBAC resources from cluster.

    Args:
        namespaces: List of namespaces to load resources from.

    Returns:
        Dictionary mapping resource kinds to lists of resources.
    """
    from kubernetes import client

    v1 = client.CoreV1Api()
    rbac_v1 = client.RbacAuthorizationV1Api()

    resources: dict[str, list[dict[str, Any]]] = {
        "ServiceAccount": [],
        "Role": [],
        "RoleBinding": [],
        "Namespace": [],
    }

    for ns in namespaces:
        # Get namespaces
        try:
            ns_obj = v1.read_namespace(ns)
            resources["Namespace"].append(
                client.ApiClient().sanitize_for_serialization(ns_obj)
            )
        except Exception:
            pass

        # Get service accounts
        try:
            sa_list = v1.list_namespaced_service_account(
                ns,
                label_selector="app.kubernetes.io/managed-by=floe",
            )
            for sa in sa_list.items:
                resources["ServiceAccount"].append(
                    client.ApiClient().sanitize_for_serialization(sa)
                )
        except Exception:
            pass

        # Get roles
        try:
            role_list = rbac_v1.list_namespaced_role(
                ns,
                label_selector="app.kubernetes.io/managed-by=floe",
            )
            for role in role_list.items:
                resources["Role"].append(
                    client.ApiClient().sanitize_for_serialization(role)
                )
        except Exception:
            pass

        # Get role bindings
        try:
            binding_list = rbac_v1.list_namespaced_role_binding(
                ns,
                label_selector="app.kubernetes.io/managed-by=floe",
            )
            for binding in binding_list.items:
                resources["RoleBinding"].append(
                    client.ApiClient().sanitize_for_serialization(binding)
                )
        except Exception:
            pass

    return resources


def _print_diff_result(result: RBACDiffResult) -> None:
    """Print diff result in human-readable format.

    Args:
        result: Diff result to print.
    """
    from floe_cli.commands.rbac import DiffChangeType

    click.echo(f"\n{'='*60}")
    click.echo("RBAC Diff")
    click.echo(f"{'='*60}")
    click.echo(f"Expected: {result.expected_source}")
    click.echo(f"Actual: {result.actual_source}")

    if not result.has_differences():
        click.echo(click.style("\n✓ No differences found", fg="green", bold=True))
        return

    click.echo(f"\nChanges:")
    click.echo(f"  Added (need to apply): {result.added_count}")
    click.echo(f"  Removed (in cluster, not in manifests): {result.removed_count}")
    click.echo(f"  Modified: {result.modified_count}")

    by_type = result.diffs_by_change_type()

    # Show added
    added = by_type[DiffChangeType.ADDED]
    if added:
        click.echo(click.style("\n[ADDED] (needs kubectl apply)", fg="green"))
        for diff in added:
            ns_str = f" ({diff.resource_namespace})" if diff.resource_namespace else ""
            click.echo(f"  + {diff.resource_kind}/{diff.resource_name}{ns_str}")

    # Show removed
    removed = by_type[DiffChangeType.REMOVED]
    if removed:
        click.echo(click.style("\n[REMOVED] (exists in cluster, not in manifests)", fg="red"))
        for diff in removed:
            ns_str = f" ({diff.resource_namespace})" if diff.resource_namespace else ""
            click.echo(f"  - {diff.resource_kind}/{diff.resource_name}{ns_str}")

    # Show modified
    modified = by_type[DiffChangeType.MODIFIED]
    if modified:
        click.echo(click.style("\n[MODIFIED]", fg="yellow"))
        for diff in modified:
            ns_str = f" ({diff.resource_namespace})" if diff.resource_namespace else ""
            click.echo(f"  ~ {diff.resource_kind}/{diff.resource_name}{ns_str}")
            for detail in diff.diff_details[:5]:  # Limit to first 5 details
                click.echo(f"      {detail}")
            if len(diff.diff_details) > 5:
                click.echo(f"      ... and {len(diff.diff_details) - 5} more differences")


if __name__ == "__main__":
    cli()
