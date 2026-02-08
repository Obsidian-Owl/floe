"""Network audit command implementation.

Task ID: T075
Phase: 7C - Network and Pod Security
Requirements: FR-082 (Audit cluster NetworkPolicy state),
              FR-092 (Warn if namespace lacks default-deny policy)

This module implements the `floe network audit` command which:
- Audits current cluster NetworkPolicy state
- Reports findings (missing default-deny policies, overly permissive rules, etc.)
- Supports JSON and text output formats
- Validates namespace-level network security posture

Example:
    $ floe network audit --namespace floe-jobs
    $ floe network audit --all-namespaces
    $ floe network audit --namespace floe-jobs --output json
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from floe_core.cli.utils import (
    ExitCode,
    error_exit,
    info,
    sanitize_k8s_api_error,
    sanitize_path_for_log,
    success,
    warning,
)
from floe_core.network.schemas import _validate_namespace

if TYPE_CHECKING:
    pass


@click.command(
    name="audit",
    help="Audit cluster NetworkPolicy state (FR-082).",
    epilog="""
Analyzes NetworkPolicy configuration in the cluster and reports findings
such as missing default-deny policies, overly permissive rules, etc.

Examples:
    $ floe network audit --namespace floe-jobs
    $ floe network audit --all-namespaces
    $ floe network audit --namespace floe-jobs --output json
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--namespace",
    "-n",
    type=str,
    multiple=True,
    default=None,
    help="Namespaces to audit (can be repeated). Default: all namespaces.",
    metavar="TEXT",
)
@click.option(
    "--all-namespaces",
    is_flag=True,
    default=False,
    help="Audit all namespaces in the cluster.",
)
@click.option(
    "--output-format",
    "-o",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json).",
    metavar="TEXT",
)
@click.option(
    "--kubeconfig",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Path to kubeconfig file.",
    metavar="PATH",
)
@click.option(
    "--context",
    type=str,
    default=None,
    help="Kubernetes context to use.",
    metavar="TEXT",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    hidden=True,
    help="Show verbose error messages with tracebacks.",
)
def audit_command(
    namespace: tuple[str, ...],
    all_namespaces: bool,
    output_format: str,
    kubeconfig: Path | None,
    context: str | None,
    debug: bool,
) -> None:
    """Audit cluster NetworkPolicy state.

    Analyzes NetworkPolicy configuration in the cluster and reports security
    findings such as missing default-deny policies, overly permissive rules,
    and namespace-level network security posture.

    Args:
        namespace: Namespaces to audit (can be repeated).
        all_namespaces: Audit all namespaces in the cluster.
        output_format: Output format (text or json).
        kubeconfig: Path to kubeconfig file.
        context: Kubernetes context to use.
    """
    _validate_audit_inputs(namespace, all_namespaces)
    namespaces_to_audit = _resolve_namespaces(namespace, all_namespaces)

    info(f"Auditing NetworkPolicies in {len(namespaces_to_audit)} namespace(s)")
    if kubeconfig:
        info(f"Using kubeconfig: {sanitize_path_for_log(kubeconfig)}")
    if context:
        info(f"Using context: {context}")

    try:
        networking_api = _setup_kubernetes_client(kubeconfig, context)
        report = _perform_audit(networking_api, namespaces_to_audit)
        _output_report(report, output_format)
    except Exception as e:
        if debug:
            import traceback

            traceback.print_exc()
        error_exit(
            f"Network audit failed: {type(e).__name__}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


def _validate_audit_inputs(namespace: tuple[str, ...], all_namespaces: bool) -> None:
    """Validate audit command inputs.

    Args:
        namespace: Namespaces to audit.
        all_namespaces: Whether to audit all namespaces.

    Raises:
        SystemExit: If inputs are invalid.
    """
    if not all_namespaces and not namespace:
        error_exit(
            "Must specify --namespace or --all-namespaces",
            exit_code=ExitCode.USAGE_ERROR,
        )

    for ns in namespace:
        try:
            _validate_namespace(ns)
        except ValueError as e:
            error_exit(str(e), exit_code=ExitCode.USAGE_ERROR)


def _resolve_namespaces(
    namespace: tuple[str, ...],
    all_namespaces: bool,
) -> list[str]:
    """Resolve which namespaces to audit.

    Args:
        namespace: Explicitly specified namespaces.
        all_namespaces: Whether to audit all namespaces.

    Returns:
        List of namespace names to audit.
    """
    if all_namespaces:
        return ["*"]  # Special marker for all namespaces
    return list(namespace)


def _setup_kubernetes_client(
    kubeconfig: Path | None,
    context: str | None,
) -> Any:
    """Set up and return Kubernetes Networking API client.

    Args:
        kubeconfig: Path to kubeconfig file, or None for default.
        context: Kubernetes context to use, or None for current context.

    Returns:
        NetworkingV1Api client instance.

    Raises:
        SystemExit: If kubernetes package is not installed or config fails.
    """
    try:
        from kubernetes import client
        from kubernetes import config as k8s_config
    except ImportError:
        error_exit(
            "kubernetes package not installed. Install with: pip install kubernetes",
            exit_code=ExitCode.GENERAL_ERROR,
        )

    _load_kubeconfig(k8s_config, kubeconfig, context)
    return client.NetworkingV1Api()


def _load_kubeconfig(
    k8s_config: Any,
    kubeconfig: Path | None,
    context: str | None,
) -> None:
    """Load Kubernetes configuration.

    Args:
        k8s_config: Kubernetes config module.
        kubeconfig: Path to kubeconfig file, or None for default.
        context: Kubernetes context to use, or None for current context.

    Raises:
        SystemExit: If kubeconfig cannot be loaded.
    """
    try:
        if kubeconfig:
            k8s_config.load_kube_config(config_file=str(kubeconfig), context=context)
            return

        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config(context=context)
    except Exception as e:
        error_exit(
            f"Failed to load kubeconfig: {type(e).__name__}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


def _perform_audit(
    networking_api: Any,
    namespaces: list[str],
) -> dict[str, Any]:
    """Perform network audit and return report.

    Args:
        networking_api: Kubernetes Networking API client.
        namespaces: List of namespaces to audit (["*"] for all).

    Returns:
        Audit report dictionary with findings and statistics.
    """
    from kubernetes.client import ApiException

    findings: list[dict[str, Any]] = []
    policies: list[dict[str, Any]] = []
    audited_namespaces: list[str] = []

    # Resolve namespace list
    if namespaces == ["*"]:
        try:
            from kubernetes import client

            v1 = client.CoreV1Api()
            ns_list = v1.list_namespace()
            namespaces = [ns.metadata.name for ns in ns_list.items]
        except ApiException as e:
            error_exit(
                f"Failed to list namespaces: {sanitize_k8s_api_error(e)}",
                exit_code=ExitCode.NETWORK_ERROR,
            )

    # Audit each namespace
    for ns in namespaces:
        audited_namespaces.append(ns)
        try:
            ns_policies = networking_api.list_namespaced_network_policy(ns)
            ns_findings = _audit_namespace(ns, ns_policies)
            findings.extend(ns_findings)

            # Collect policy information
            for policy in ns_policies.items:
                policies.append(_policy_to_dict(policy, ns))

        except ApiException as e:
            if e.status == 404:
                # Namespace doesn't exist
                findings.append(
                    {
                        "severity": "error",
                        "type": "namespace_not_found",
                        "namespace": ns,
                        "message": f"Namespace '{ns}' not found",
                        "recommendation": "Verify namespace name is correct",
                    }
                )
            else:
                error_exit(
                    f"Failed to audit namespace {ns}: {sanitize_k8s_api_error(e)}",
                    exit_code=ExitCode.NETWORK_ERROR,
                )

    return {
        "namespaces": audited_namespaces,
        "policies": policies,
        "findings": findings,
        "summary": {
            "total_namespaces": len(audited_namespaces),
            "total_policies": len(policies),
            "total_findings": len(findings),
            "critical_findings": sum(
                1 for f in findings if f.get("severity") == "critical"
            ),
            "warning_findings": sum(
                1 for f in findings if f.get("severity") == "warning"
            ),
        },
    }


def _audit_namespace(
    namespace: str,
    policies: Any,
) -> list[dict[str, Any]]:
    """Audit a single namespace for network security issues.

    Args:
        namespace: Namespace name.
        policies: NetworkPolicyList from Kubernetes API.

    Returns:
        List of findings for this namespace.
    """
    findings: list[dict[str, Any]] = []

    # Check for default-deny policy (FR-092)
    has_default_deny = _check_default_deny_policy(policies)
    if not has_default_deny:
        findings.append(
            {
                "severity": "warning",
                "type": "missing_default_deny",
                "namespace": namespace,
                "message": f"Namespace '{namespace}' lacks default-deny NetworkPolicy",
                "recommendation": (
                    "Create a default-deny NetworkPolicy to restrict all traffic"
                ),
            }
        )

    # Check for overly permissive policies
    for policy in policies.items:
        policy_findings = _audit_policy(policy, namespace)
        findings.extend(policy_findings)

    return findings


def _check_default_deny_policy(policies: Any) -> bool:
    """Check if namespace has a default-deny NetworkPolicy.

    A default-deny policy is one that:
    - Has empty or no ingress rules (denies all ingress)
    - Has empty or no egress rules (denies all egress)
    - Or explicitly denies all traffic

    Args:
        policies: NetworkPolicyList from Kubernetes API.

    Returns:
        True if default-deny policy exists, False otherwise.
    """
    for policy in policies.items:
        policy_name = policy.metadata.name
        spec = policy.spec

        # Check for default-deny pattern: no rules or empty rules
        if spec.ingress_rules is None or len(spec.ingress_rules) == 0:
            if spec.egress_rules is None or len(spec.egress_rules) == 0:
                # This is a default-deny policy
                return True

        # Check for explicit default-deny naming
        if "default-deny" in policy_name.lower():
            return True

    return False


def _audit_policy(
    policy: Any,
    namespace: str,
) -> list[dict[str, Any]]:
    """Audit a single NetworkPolicy for security issues.

    Args:
        policy: Kubernetes NetworkPolicy object.
        namespace: Namespace of the policy.

    Returns:
        List of findings for this policy.
    """
    findings: list[dict[str, Any]] = []
    policy_name = policy.metadata.name
    spec = policy.spec

    # Check for overly permissive ingress rules
    if spec.ingress_rules:
        for idx, rule in enumerate(spec.ingress_rules):
            if _is_permissive_rule(rule):
                findings.append(
                    {
                        "severity": "warning",
                        "type": "overly_permissive_ingress",
                        "namespace": namespace,
                        "policy": policy_name,
                        "rule_index": idx,
                        "message": (
                            f"NetworkPolicy '{policy_name}' has overly permissive ingress rule"
                        ),
                        "recommendation": (
                            "Restrict ingress to specific sources and ports"
                        ),
                    }
                )

    # Check for overly permissive egress rules
    if spec.egress_rules:
        for idx, rule in enumerate(spec.egress_rules):
            if _is_permissive_rule(rule):
                findings.append(
                    {
                        "severity": "warning",
                        "type": "overly_permissive_egress",
                        "namespace": namespace,
                        "policy": policy_name,
                        "rule_index": idx,
                        "message": (
                            f"NetworkPolicy '{policy_name}' has overly permissive egress rule"
                        ),
                        "recommendation": (
                            "Restrict egress to specific destinations and ports"
                        ),
                    }
                )

    return findings


def _is_permissive_rule(rule: Any) -> bool:
    """Check if a rule is overly permissive.

    A rule is considered permissive if:
    - It has no from/to selectors (allows all sources/destinations)
    - It has no ports specified (allows all ports)

    Args:
        rule: Kubernetes NetworkPolicyIngressRule or EgressRule.

    Returns:
        True if rule is overly permissive, False otherwise.
    """
    # Check if rule has no selectors (allows all)
    has_from_selector = hasattr(rule, "from_") and rule.from_ and len(rule.from_) > 0
    has_to_selector = hasattr(rule, "to") and rule.to and len(rule.to) > 0

    # For ingress rules, check 'from'
    if hasattr(rule, "from_"):
        if not has_from_selector:
            return True

    # For egress rules, check 'to'
    if hasattr(rule, "to"):
        if not has_to_selector:
            return True

    # Check if no ports specified
    has_ports = hasattr(rule, "ports") and rule.ports and len(rule.ports) > 0
    if not has_ports:
        return True

    return False


def _policy_to_dict(policy: Any, namespace: str) -> dict[str, Any]:
    """Convert a NetworkPolicy object to a dictionary.

    Args:
        policy: Kubernetes NetworkPolicy object.
        namespace: Namespace of the policy.

    Returns:
        Dictionary representation of the policy.
    """
    spec = policy.spec
    return {
        "name": policy.metadata.name,
        "namespace": namespace,
        "pod_selector": _selector_to_dict(spec.pod_selector),
        "ingress_rules": len(spec.ingress_rules) if spec.ingress_rules else 0,
        "egress_rules": len(spec.egress_rules) if spec.egress_rules else 0,
        "policy_types": spec.policy_types or [],
    }


def _selector_to_dict(selector: Any) -> dict[str, Any]:
    """Convert a label selector to a dictionary.

    Args:
        selector: Kubernetes LabelSelector object.

    Returns:
        Dictionary representation of the selector.
    """
    if selector is None:
        return {}

    result: dict[str, Any] = {}
    if selector.match_labels:
        result["match_labels"] = selector.match_labels
    if selector.match_expressions:
        result["match_expressions"] = [
            {
                "key": expr.key,
                "operator": expr.operator,
                "values": expr.values or [],
            }
            for expr in selector.match_expressions
        ]

    return result


def _output_report(report: dict[str, Any], output_format: str) -> None:
    """Output the audit report in the specified format.

    Args:
        report: The audit report dictionary.
        output_format: Output format ('json' or 'text').
    """
    if output_format == "json":
        import json

        click.echo(json.dumps(report, indent=2))
        return

    _output_report_as_text(report)


def _output_report_as_text(report: dict[str, Any]) -> None:
    """Output the audit report as text.

    Args:
        report: The audit report dictionary.
    """
    summary = report.get("summary", {})
    findings = report.get("findings", [])

    click.echo("Network Audit Report")
    click.echo("=" * 20)
    click.echo(f"Namespaces audited: {summary.get('total_namespaces', 0)}")
    click.echo(f"Total policies: {summary.get('total_policies', 0)}")
    click.echo(f"Total findings: {summary.get('total_findings', 0)}")

    if not findings:
        success("No network security issues found.")
        return

    critical_count = summary.get("critical_findings", 0)
    warning_count = summary.get("warning_findings", 0)

    if critical_count > 0:
        error_exit(
            f"Found {len(findings)} network security issue(s) including {critical_count} CRITICAL",
            exit_code=ExitCode.VALIDATION_ERROR,
        )

    if warning_count > 0:
        warning(f"Found {len(findings)} network security issue(s):")
        for finding in findings:
            severity = finding.get("severity", "unknown").upper()
            namespace = finding.get("namespace", "unknown")
            policy = finding.get("policy", "")
            message = finding.get("message", "")

            if policy:
                click.echo(f"  [{severity}] {namespace}/{policy}: {message}")
            else:
                click.echo(f"  [{severity}] {namespace}: {message}")


__all__: list[str] = ["audit_command"]
