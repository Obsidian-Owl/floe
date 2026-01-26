"""Network diff command implementation.

Task ID: T074
Phase: 7 - Network and Pod Security CLI Commands
User Story: US5 - Network and Pod Security CLI Commands
Requirements: FR-083

This module implements the `floe network diff` command which:
- Compares expected vs deployed NetworkPolicies
- Shows added, removed, and modified policies
- Supports JSON and text output formats

Example:
    $ floe network diff --manifest-dir deploy/network/
    $ floe network diff --manifest-dir deploy/network/ --namespace floe-jobs
    $ floe network diff --manifest-dir deploy/network/ --output-format json
    $ floe network diff --manifest-dir deploy/network/ --kubeconfig ~/.kube/config
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

# =============================================================================
# Extracted Helper Functions
# =============================================================================


def _validate_manifest_dir(manifest_dir: Path | None) -> Path:
    """Validate and return manifest directory.

    Args:
        manifest_dir: Directory containing expected NetworkPolicy manifests.

    Returns:
        Validated manifest directory path.

    Raises:
        SystemExit: If manifest_dir is None or invalid.
    """
    if manifest_dir is None:
        error_exit(
            "Missing --manifest-dir option. Provide path to manifest directory.",
            exit_code=ExitCode.USAGE_ERROR,
        )
    # Type narrowing - error_exit calls sys.exit so we never reach here if None
    return manifest_dir


def _load_kubeconfig(kubeconfig: Path | None, context: str | None) -> None:
    """Load Kubernetes configuration.

    Args:
        kubeconfig: Optional path to kubeconfig file.
        context: Optional Kubernetes context to use.

    Raises:
        SystemExit: If kubernetes package not installed or config fails.
    """
    try:
        from kubernetes import config as k8s_config
    except ImportError:
        error_exit(
            "kubernetes package not installed. Install with: pip install kubernetes",
            exit_code=ExitCode.GENERAL_ERROR,
        )

    if kubeconfig:
        k8s_config.load_kube_config(config_file=str(kubeconfig), context=context)
    else:
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config(context=context)


def _parse_manifest_file(file_path: Path) -> list[dict[str, Any]]:
    """Parse a single YAML manifest file into resource dictionaries.

    Args:
        file_path: Path to the YAML manifest file.

    Returns:
        List of non-empty resource dictionaries from the file.

    Raises:
        ValueError: If manifest contains invalid K8s resource structure.
    """
    import yaml

    if not file_path.exists():
        return []

    content = file_path.read_text()
    if not content.strip():
        return []

    docs = list(yaml.safe_load_all(content))
    validated_docs = []
    for doc in docs:
        if doc is not None:
            # Validate required K8s manifest structure
            if not isinstance(doc, dict):
                raise ValueError(
                    f"Invalid manifest in {file_path}: expected dict, got {type(doc).__name__}"
                )
            if "apiVersion" not in doc:
                raise ValueError(f"Missing apiVersion in {file_path}")
            if "kind" not in doc:
                raise ValueError(f"Missing kind in {file_path}")
            validated_docs.append(doc)
    return validated_docs


def _load_expected_policies(manifest_dir: Path) -> dict[str, dict[str, Any]]:
    """Load expected NetworkPolicy resources from manifest files.

    Args:
        manifest_dir: Directory containing NetworkPolicy manifest files.

    Returns:
        Dictionary mapping policy identifiers to policy dictionaries.
    """
    policies: dict[str, dict[str, Any]] = {}

    # Find all YAML files in manifest directory
    for yaml_file in manifest_dir.glob("*.yaml"):
        resources = _parse_manifest_file(yaml_file)
        for resource in resources:
            if resource.get("kind") == "NetworkPolicy":
                namespace = resource.get("metadata", {}).get("namespace", "default")
                name = resource.get("metadata", {}).get("name", "unknown")
                policy_id = f"{namespace}/{name}"
                policies[policy_id] = resource

    return policies


def _get_deployed_policies(
    namespaces: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch deployed NetworkPolicy resources from the cluster.

    Args:
        namespaces: List of Kubernetes namespaces to fetch from.

    Returns:
        Dictionary mapping policy identifiers to policy dictionaries.
    """
    from kubernetes import client
    from kubernetes.client import ApiException

    policies: dict[str, dict[str, Any]] = {}

    try:
        networking_api = client.NetworkingV1Api()

        for namespace in namespaces:
            try:
                response = networking_api.list_namespaced_network_policy(namespace)
                for policy in response.items:
                    policy_dict = _k8s_network_policy_to_dict(policy)
                    policy_id = f"{namespace}/{policy.metadata.name}"
                    policies[policy_id] = policy_dict
            except ApiException as e:
                if e.status == 404:
                    info(f"Namespace {namespace} not found or has no NetworkPolicies")
                else:
                    raise

    except ApiException as e:
        error_exit(
            f"Failed to fetch NetworkPolicies from cluster: {sanitize_k8s_api_error(e)}",
            exit_code=ExitCode.NETWORK_ERROR,
        )

    return policies


def _k8s_network_policy_to_dict(policy: Any) -> dict[str, Any]:
    """Convert a Kubernetes NetworkPolicy API object to a dictionary.

    Args:
        policy: Kubernetes NetworkPolicy API object.

    Returns:
        Dictionary representation of the NetworkPolicy.
    """
    result: dict[str, Any] = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": policy.metadata.name,
            "namespace": policy.metadata.namespace,
        },
    }

    # Add spec if present
    if policy.spec:
        spec: dict[str, Any] = {}

        # Pod selector
        if policy.spec.pod_selector:
            spec["podSelector"] = _selector_to_dict(policy.spec.pod_selector)
        else:
            spec["podSelector"] = {}

        # Policy types
        if policy.spec.policy_types:
            spec["policyTypes"] = policy.spec.policy_types

        # Ingress rules
        if policy.spec.ingress:
            spec["ingress"] = [_ingress_rule_to_dict(rule) for rule in policy.spec.ingress]

        # Egress rules
        if policy.spec.egress:
            spec["egress"] = [_egress_rule_to_dict(rule) for rule in policy.spec.egress]

        result["spec"] = spec

    return result


def _selector_to_dict(selector: Any) -> dict[str, Any]:
    """Convert a label selector to a dictionary.

    Args:
        selector: Kubernetes label selector object.

    Returns:
        Dictionary representation of the selector.
    """
    result: dict[str, Any] = {}

    if selector.match_labels:
        result["matchLabels"] = selector.match_labels

    if selector.match_expressions:
        result["matchExpressions"] = [
            _match_expression_to_dict(expr) for expr in selector.match_expressions
        ]

    return result


def _match_expression_to_dict(expr: Any) -> dict[str, Any]:
    """Convert a match expression to a dictionary.

    Args:
        expr: Kubernetes match expression object.

    Returns:
        Dictionary representation of the match expression.
    """
    return {
        "key": expr.key,
        "operator": expr.operator,
        "values": expr.values or [],
    }


def _ingress_rule_to_dict(rule: Any) -> dict[str, Any]:
    """Convert an ingress rule to a dictionary.

    Args:
        rule: Kubernetes ingress rule object.

    Returns:
        Dictionary representation of the ingress rule.
    """
    result: dict[str, Any] = {}

    if rule.from_:
        result["from"] = [_peer_to_dict(peer) for peer in rule.from_]

    if rule.ports:
        result["ports"] = [_port_to_dict(port) for port in rule.ports]

    return result


def _egress_rule_to_dict(rule: Any) -> dict[str, Any]:
    """Convert an egress rule to a dictionary.

    Args:
        rule: Kubernetes egress rule object.

    Returns:
        Dictionary representation of the egress rule.
    """
    result: dict[str, Any] = {}

    if rule.to:
        result["to"] = [_peer_to_dict(peer) for peer in rule.to]

    if rule.ports:
        result["ports"] = [_port_to_dict(port) for port in rule.ports]

    return result


def _peer_to_dict(peer: Any) -> dict[str, Any]:
    """Convert a network policy peer to a dictionary.

    Args:
        peer: Kubernetes network policy peer object.

    Returns:
        Dictionary representation of the peer.
    """
    result: dict[str, Any] = {}

    if peer.pod_selector:
        result["podSelector"] = _selector_to_dict(peer.pod_selector)

    if peer.namespace_selector:
        result["namespaceSelector"] = _selector_to_dict(peer.namespace_selector)

    if peer.ip_block:
        result["ipBlock"] = {
            "cidr": peer.ip_block.cidr,
            "except": peer.ip_block.except_ or [],
        }

    return result


def _port_to_dict(port: Any) -> dict[str, Any]:
    """Convert a port specification to a dictionary.

    Args:
        port: Kubernetes port specification object.

    Returns:
        Dictionary representation of the port.
    """
    result: dict[str, Any] = {}

    if port.protocol:
        result["protocol"] = port.protocol

    if port.port:
        result["port"] = port.port

    return result


def _compute_diff(
    expected: dict[str, dict[str, Any]],
    deployed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute differences between expected and deployed policies.

    Args:
        expected: Dictionary of expected policies.
        deployed: Dictionary of deployed policies.

    Returns:
        Dictionary with missing, extra, and modified policies.
    """
    missing_list: list[dict[str, Any]] = []
    extra_list: list[dict[str, Any]] = []
    modified_list: list[dict[str, Any]] = []

    # Find missing and modified
    for policy_id, expected_policy in expected.items():
        if policy_id not in deployed:
            missing_list.append(
                {
                    "id": policy_id,
                    "policy": expected_policy,
                }
            )
        else:
            deployed_policy = deployed[policy_id]
            if expected_policy != deployed_policy:
                modified_list.append(
                    {
                        "id": policy_id,
                        "expected": expected_policy,
                        "deployed": deployed_policy,
                    }
                )

    # Find extra
    for policy_id, deployed_policy in deployed.items():
        if policy_id not in expected:
            extra_list.append(
                {
                    "id": policy_id,
                    "policy": deployed_policy,
                }
            )

    result: dict[str, Any] = {
        "missing": missing_list,
        "extra": extra_list,
        "modified": modified_list,
        "missing_count": len(missing_list),
        "extra_count": len(extra_list),
        "modified_count": len(modified_list),
    }

    return result


def _output_diff_as_text(diff_result: dict[str, Any]) -> None:
    """Output diff result in text format.

    Args:
        diff_result: The computed diff result.
    """
    total_changes = (
        diff_result["missing_count"] + diff_result["extra_count"] + diff_result["modified_count"]
    )

    if total_changes == 0:
        success("No differences found. Cluster matches expected manifests.")
        return

    warning(f"Found {total_changes} difference(s):")

    if diff_result["missing"]:
        click.echo("\nTo be created (in manifest but not deployed):")
        for item in diff_result["missing"]:
            click.echo(f"  + {item['id']}")

    if diff_result["extra"]:
        click.echo("\nTo be removed (deployed but not in manifest):")
        for item in diff_result["extra"]:
            click.echo(f"  - {item['id']}")

    if diff_result["modified"]:
        click.echo("\nTo be modified:")
        for item in diff_result["modified"]:
            click.echo(f"  ~ {item['id']}")


# =============================================================================
# Main Command
# =============================================================================


@click.command(
    name="diff",
    help="Compare expected vs deployed NetworkPolicies (FR-083).",
    epilog="""
Compares the manifests in the target directory with the actual
NetworkPolicy configuration in the cluster.

Examples:
    $ floe network diff --manifest-dir deploy/network/
    $ floe network diff --manifest-dir deploy/network/ --namespace floe-jobs
    $ floe network diff --manifest-dir deploy/network/ --output-format json
    $ floe network diff --manifest-dir deploy/network/ --kubeconfig ~/.kube/config
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--manifest-dir",
    "-m",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    required=True,
    help="Directory containing expected NetworkPolicy manifests.",
    metavar="PATH",
)
@click.option(
    "--namespace",
    "-n",
    type=str,
    default=None,
    help="Namespace to compare (can be specified multiple times).",
    metavar="TEXT",
    multiple=True,
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
    "--output-format",
    "-o",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json).",
    metavar="TEXT",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    hidden=True,
    help="Show verbose error messages with tracebacks.",
)
def diff_command(
    manifest_dir: Path,
    namespace: tuple[str, ...],
    kubeconfig: Path | None,
    context: str | None,
    output_format: str,
    debug: bool,
) -> None:
    """Compare expected vs deployed NetworkPolicies.

    Compares the manifests in the target directory with the actual
    NetworkPolicy configuration in the cluster.

    Args:
        manifest_dir: Directory containing expected NetworkPolicy manifests.
        namespace: Namespaces to compare (can be specified multiple times).
        kubeconfig: Path to kubeconfig file.
        context: Kubernetes context to use.
        output_format: Output format (text or json).
    """
    # Validate manifest directory
    validated_manifest_dir = _validate_manifest_dir(manifest_dir)

    # Determine namespaces to compare
    namespaces_to_compare: list[str] = list(namespace) if namespace else ["default"]

    info(f"Comparing manifests in: {sanitize_path_for_log(validated_manifest_dir)}")
    info(f"Against namespaces: {', '.join(namespaces_to_compare)}")

    if kubeconfig:
        info(f"Using kubeconfig: {sanitize_path_for_log(kubeconfig)}")

    if context:
        info(f"Using context: {context}")

    try:
        # Load kubeconfig
        _load_kubeconfig(kubeconfig, context)

        # Load expected policies
        expected_policies = _load_expected_policies(validated_manifest_dir)
        info(f"Loaded {len(expected_policies)} expected policies")

        # Fetch deployed policies
        deployed_policies = _get_deployed_policies(namespaces_to_compare)
        info(f"Fetched {len(deployed_policies)} deployed policies")

        # Compute diff
        diff_result = _compute_diff(expected_policies, deployed_policies)

        # Output results
        if output_format.lower() == "json":
            import json

            click.echo(json.dumps(diff_result, indent=2))
        else:
            _output_diff_as_text(diff_result)

    except FileNotFoundError as e:
        if debug:
            import traceback

            traceback.print_exc()
        error_exit(
            f"Manifest file not found: {e.filename}",
            exit_code=ExitCode.FILE_NOT_FOUND,
        )
    except Exception as e:
        if debug:
            import traceback

            traceback.print_exc()
        error_exit(
            f"Network diff failed: {type(e).__name__}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


__all__: list[str] = ["diff_command"]
