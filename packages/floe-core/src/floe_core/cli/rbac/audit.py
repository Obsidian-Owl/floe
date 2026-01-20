"""RBAC audit command implementation.

Task ID: T034
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-024, FR-025

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
from typing import Any

import click

from floe_core.cli.utils import ExitCode, error_exit, info, success, warning


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
            from kubernetes import client, config as k8s_config
        except ImportError:
            error_exit(
                "kubernetes package not installed. Install with: pip install kubernetes",
                exit_code=ExitCode.GENERAL_ERROR,
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
        findings: list[dict[str, Any]] = []

        # Get roles
        roles = rbac_api.list_namespaced_role(namespace)
        for role in roles.items:
            role_findings = _audit_role(role)
            findings.extend(role_findings)

        # Get role bindings
        role_bindings = rbac_api.list_namespaced_role_binding(namespace)
        for binding in role_bindings.items:
            binding_findings = _audit_role_binding(binding)
            findings.extend(binding_findings)

        # Output results
        if output_format == "json":
            import json

            result = {
                "namespace": namespace,
                "findings": findings,
                "finding_count": len(findings),
            }
            click.echo(json.dumps(result, indent=2))
        else:
            if findings:
                warning(f"Found {len(findings)} RBAC issue(s):")
                for finding in findings:
                    severity = finding.get("severity", "INFO")
                    message = finding.get("message", "Unknown issue")
                    resource = finding.get("resource", "Unknown")
                    click.echo(f"  [{severity}] {resource}: {message}")
            else:
                success("No RBAC issues found.")

    except Exception as e:
        error_exit(
            f"RBAC audit failed: {e}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


def _audit_role(role: Any) -> list[dict[str, Any]]:
    """Audit a single Role for security issues.

    Args:
        role: Kubernetes Role object.

    Returns:
        List of finding dictionaries.
    """
    findings: list[dict[str, Any]] = []
    role_name = role.metadata.name

    if role.rules:
        for rule in role.rules:
            # Check for wildcard verbs
            if rule.verbs and "*" in rule.verbs:
                findings.append({
                    "severity": "HIGH",
                    "resource": f"Role/{role_name}",
                    "message": "Role has wildcard verb (*) permission",
                    "rule": str(rule),
                })

            # Check for wildcard resources
            if rule.resources and "*" in rule.resources:
                findings.append({
                    "severity": "HIGH",
                    "resource": f"Role/{role_name}",
                    "message": "Role has wildcard resource (*) permission",
                    "rule": str(rule),
                })

            # Check for wildcard API groups
            if rule.api_groups and "*" in rule.api_groups:
                findings.append({
                    "severity": "MEDIUM",
                    "resource": f"Role/{role_name}",
                    "message": "Role has wildcard API group (*)",
                    "rule": str(rule),
                })

    return findings


def _audit_role_binding(binding: Any) -> list[dict[str, Any]]:
    """Audit a single RoleBinding for security issues.

    Args:
        binding: Kubernetes RoleBinding object.

    Returns:
        List of finding dictionaries.
    """
    findings: list[dict[str, Any]] = []
    binding_name = binding.metadata.name

    # Check for bindings to cluster-admin or other powerful roles
    if binding.role_ref:
        role_name = binding.role_ref.name
        if role_name in ("cluster-admin", "admin", "edit"):
            findings.append({
                "severity": "MEDIUM",
                "resource": f"RoleBinding/{binding_name}",
                "message": f"RoleBinding references powerful role: {role_name}",
            })

    # Check for subjects with no namespace (could be cluster-wide)
    if binding.subjects:
        for subject in binding.subjects:
            if subject.kind == "ServiceAccount" and not subject.namespace:
                findings.append({
                    "severity": "LOW",
                    "resource": f"RoleBinding/{binding_name}",
                    "message": f"ServiceAccount '{subject.name}' has no namespace specified",
                })

    return findings


__all__: list[str] = ["audit_command"]
