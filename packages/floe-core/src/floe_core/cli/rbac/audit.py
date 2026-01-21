"""RBAC audit command implementation.

Task ID: T034
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-024, FR-025, FR-062, FR-070

This module implements the `floe rbac audit` command which:
- Audits current cluster RBAC state
- Reports security findings (wildcard permissions, etc.)
- Supports JSON and text output formats

Example:
    $ floe rbac audit
    $ floe rbac audit --namespace floe-jobs
    $ floe rbac audit --output json
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success, warning

if TYPE_CHECKING:
    from floe_core.schemas.rbac_audit import AuditFinding


@click.command(
    name="audit",
    help="Audit current cluster RBAC state (FR-062).",
    epilog="""
Analyzes RBAC configuration in the cluster and reports findings
such as wildcard permissions, missing resource constraints, etc.

Examples:
    $ floe rbac audit
    $ floe rbac audit --namespace floe-jobs
    $ floe rbac audit --output json
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--namespace",
    "-n",
    type=str,
    default=None,
    help="Namespaces to audit (default: all floe-managed).",
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
def audit_command(
    namespace: str | None,
    output: str | None,
    kubeconfig: Path | None,
) -> None:
    """Audit current cluster RBAC state.

    Analyzes RBAC configuration in the cluster and reports security
    findings such as wildcard permissions, missing resource constraints,
    and overly permissive role bindings.

    Args:
        namespace: Namespace to audit (default: all floe-managed).
        output: Output format (text or json).
        kubeconfig: Path to kubeconfig file.
    """
    # Validate required namespace
    if namespace is None:
        error_exit(
            "Missing --namespace option. Provide namespace to audit.",
            exit_code=ExitCode.USAGE_ERROR,
        )

    # Default values
    output_format = output if output is not None else "text"

    info(f"Auditing RBAC in namespace: {namespace}")

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

        # Import type-safe models
        from floe_core.rbac.audit import (
            check_missing_resource_names,
            detect_wildcard_permissions,
        )
        from floe_core.schemas.rbac_audit import (
            RBACAuditReport,
        )

        # Load kubeconfig
        if kubeconfig:
            k8s_config.load_kube_config(config_file=str(kubeconfig))
        else:
            try:
                k8s_config.load_incluster_config()
            except k8s_config.ConfigException:
                k8s_config.load_kube_config()

        # Get RBAC API
        rbac_api = client.RbacAuthorizationV1Api()

        # Audit roles and role bindings in namespace
        findings: list[AuditFinding] = []
        total_roles = 0
        total_role_bindings = 0

        # Get roles and use type-safe detection functions
        roles = rbac_api.list_namespaced_role(namespace)
        for role in roles.items:
            total_roles += 1
            role_name = role.metadata.name
            if role.rules:
                # Convert K8s rules to dict format for detection functions
                rules_dicts = [
                    {
                        "apiGroups": rule.api_groups or [],
                        "resources": rule.resources or [],
                        "verbs": rule.verbs or [],
                        "resourceNames": rule.resource_names or [],
                    }
                    for rule in role.rules
                ]
                # Use type-safe detection functions
                findings.extend(detect_wildcard_permissions(rules_dicts, role_name, namespace))
                findings.extend(check_missing_resource_names(rules_dicts, role_name, namespace))
            # Also check for legacy dict-based findings
            role_findings = _audit_role(role, namespace)
            findings.extend(role_findings)

        # Get role bindings
        role_bindings = rbac_api.list_namespaced_role_binding(namespace)
        for binding in role_bindings.items:
            total_role_bindings += 1
            binding_findings = _audit_role_binding(binding, namespace)
            findings.extend(binding_findings)

        # Build type-safe report
        report = RBACAuditReport(
            cluster_name="current-context",
            findings=findings,
            total_roles=total_roles,
            total_role_bindings=total_role_bindings,
        )

        # Output results using type-safe models
        if output_format == "json":
            click.echo(report.model_dump_json(indent=2))
        else:
            if report.findings:
                if report.has_critical_findings():
                    error_exit(
                        f"Found {len(report.findings)} RBAC issue(s) including CRITICAL:",
                        exit_code=ExitCode.VALIDATION_ERROR,
                    )
                warning(f"Found {len(report.findings)} RBAC issue(s):")
                for finding in report.findings:
                    severity = finding.severity.value.upper()
                    resource = f"{finding.resource_kind}/{finding.resource_name}"
                    click.echo(f"  [{severity}] {resource}: {finding.message}")
            else:
                success("No RBAC issues found.")

    except Exception as e:
        error_exit(
            f"RBAC audit failed: {e}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


def _audit_role(role: Any, namespace: str | None) -> list[AuditFinding]:
    """Audit a single Role for additional security issues.

    This function handles checks not covered by detect_wildcard_permissions.

    Args:
        role: Kubernetes Role object.
        namespace: Namespace of the role.

    Returns:
        List of AuditFinding objects.
    """

    findings: list[AuditFinding] = []
    # Additional checks can be added here in the future
    # Primary wildcard detection is now handled by detect_wildcard_permissions
    return findings


def _audit_role_binding(binding: Any, namespace: str | None) -> list[AuditFinding]:
    """Audit a single RoleBinding for security issues.

    Args:
        binding: Kubernetes RoleBinding object.
        namespace: Namespace of the role binding.

    Returns:
        List of AuditFinding objects.
    """
    from floe_core.schemas.rbac_audit import (
        AuditFinding,
        AuditFindingType,
        AuditSeverity,
    )

    findings: list[AuditFinding] = []
    binding_name = binding.metadata.name

    # Check for bindings to cluster-admin or other powerful roles
    if binding.role_ref:
        role_name = binding.role_ref.name
        if role_name in ("cluster-admin", "admin", "edit"):
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.WARNING,
                    finding_type=AuditFindingType.EXCESSIVE_PERMISSIONS,
                    resource_kind="RoleBinding",
                    resource_name=binding_name,
                    resource_namespace=namespace,
                    message=f"RoleBinding references powerful role: {role_name}",
                    recommendation=f"Review if {role_name} permissions are required",
                )
            )

    # Check for subjects with no namespace (could be cluster-wide)
    if binding.subjects:
        for subject in binding.subjects:
            if subject.kind == "ServiceAccount" and not subject.namespace:
                findings.append(
                    AuditFinding(
                        severity=AuditSeverity.INFO,
                        finding_type=AuditFindingType.CROSS_NAMESPACE_ACCESS,
                        resource_kind="RoleBinding",
                        resource_name=binding_name,
                        resource_namespace=namespace,
                        message=f"ServiceAccount '{subject.name}' has no namespace specified",
                        recommendation="Specify namespace for ServiceAccount subject",
                    )
                )

    return findings


__all__: list[str] = ["audit_command"]
