"""Network CNI plugin verification command.

Task ID: FR-084
Phase: Network and Pod Security
Requirements: FR-084 - Verify CNI plugin supports NetworkPolicies

This module implements the `floe network check-cni` command which:
- Detects the CNI plugin running in the cluster
- Verifies NetworkPolicy support
- Reports compatibility status

Supported CNI plugins:
- Calico: Full support
- Cilium: Full support with extensions
- Weave: Full support
- AWS VPC CNI: Support on EKS 1.25+
- Azure CNI: Support with Network Policy Manager
- GCE: Support on GKE (must be enabled)
- Flannel: NOT supported (needs Calico overlay)
- KindNet: NOT supported

Example:
    $ floe network check-cni
    $ floe network check-cni --kubeconfig ~/.kube/config
    $ floe network check-cni --context prod-cluster --verbose
    $ floe network check-cni --output-format json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from floe_core.cli.utils import (
    ExitCode,
    error,
    error_exit,
    info,
    success,
)

if TYPE_CHECKING:
    from kubernetes.client import AppsV1Api, CoreV1Api

logger = logging.getLogger(__name__)


# CNI support matrix
CNI_SUPPORT: dict[str, dict[str, Any]] = {
    "calico": {
        "supported": True,
        "notes": "Full NetworkPolicy support",
        "min_version": "3.0",
    },
    "cilium": {
        "supported": True,
        "notes": "Full support with extensions",
        "min_version": "1.0",
    },
    "weave": {
        "supported": True,
        "notes": "Full NetworkPolicy support",
        "min_version": "2.0",
    },
    "aws-node": {
        "supported": True,
        "notes": "Support on EKS 1.25+",
        "min_version": "1.25",
    },
    "azure-cni": {
        "supported": True,
        "notes": "Support with Network Policy Manager",
        "min_version": "1.0",
    },
    "gce": {
        "supported": True,
        "notes": "Support on GKE (must be enabled)",
        "min_version": "1.0",
    },
    "flannel": {
        "supported": False,
        "notes": "NOT supported - needs Calico overlay",
        "min_version": None,
    },
    "kindnet": {
        "supported": False,
        "notes": "NOT supported",
        "min_version": None,
    },
}


def _load_kubernetes_client(
    kubeconfig: Path | None, context: str | None
) -> tuple[CoreV1Api, AppsV1Api]:
    """Load and configure Kubernetes client.

    Args:
        kubeconfig: Path to kubeconfig file.
        context: Kubernetes context to use.

    Returns:
        Tuple of (CoreV1Api, AppsV1Api) clients.

    Raises:
        SystemExit: If unable to connect to cluster.
    """
    try:
        from kubernetes import client
        from kubernetes import config as k8s_config

        if kubeconfig:
            k8s_config.load_kube_config(
                config_file=str(kubeconfig),
                context=context,
            )
        else:
            try:
                k8s_config.load_incluster_config()
            except k8s_config.ConfigException:
                k8s_config.load_kube_config(context=context)

        core_api: CoreV1Api = client.CoreV1Api()
        apps_api: AppsV1Api = client.AppsV1Api()
        return core_api, apps_api

    except Exception as e:
        error_exit(
            f"Failed to connect to Kubernetes cluster: {type(e).__name__}",
            exit_code=ExitCode.NETWORK_ERROR,
        )


def _detect_cni(
    core_api: CoreV1Api, apps_api: AppsV1Api, verbose: bool = False
) -> dict[str, Any]:
    """Detect CNI plugin by checking DaemonSets and ConfigMaps.

    Args:
        core_api: Kubernetes CoreV1Api client.
        apps_api: Kubernetes AppsV1Api client.
        verbose: Show detailed detection info.

    Returns:
        Dictionary with detection results:
        {
            "detected": "calico" | None,
            "supported": bool,
            "notes": str,
            "daemonsets": list[str],
            "configmaps": list[str],
        }
    """
    result: dict[str, Any] = {
        "detected": None,
        "supported": False,
        "notes": "",
        "daemonsets": [],
        "configmaps": [],
    }

    try:
        # Check DaemonSets in kube-system namespace
        daemonsets = apps_api.list_namespaced_daemon_set(namespace="kube-system")
        ds_names = [ds.metadata.name for ds in daemonsets.items]
        result["daemonsets"] = ds_names

        if verbose:
            info(f"Found DaemonSets: {', '.join(ds_names) if ds_names else 'none'}")

        # Map DaemonSet names to CNI plugins
        cni_daemonsets = {
            "calico-node": "calico",
            "cilium": "cilium",
            "weave-net": "weave",
            "aws-node": "aws-node",
            "azure-cni": "azure-cni",
            "gke-metadata-server": "gce",
            "flannel": "flannel",
            "kindnet": "kindnet",
        }

        detected_cni = None
        for ds_name, cni_name in cni_daemonsets.items():
            if any(ds_name in name for name in ds_names):
                detected_cni = cni_name
                break

        if detected_cni:
            result["detected"] = detected_cni
            support_info = CNI_SUPPORT.get(detected_cni, {})
            result["supported"] = support_info.get("supported", False)
            result["notes"] = support_info.get("notes", "")

            if verbose:
                info(f"Detected CNI: {detected_cni}")

        # Also check ConfigMaps for CNI configuration
        try:
            configmaps = core_api.list_namespaced_config_map(namespace="kube-system")
            cm_names = [cm.metadata.name for cm in configmaps.items]
            result["configmaps"] = cm_names

            if verbose:
                info(f"Found ConfigMaps: {', '.join(cm_names) if cm_names else 'none'}")
        except Exception as e:
            if verbose:
                error(f"Could not list ConfigMaps: {type(e).__name__}")

    except Exception as e:
        error(f"Error detecting CNI: {type(e).__name__}")

    return result


def _format_text_output(result: dict[str, Any]) -> None:
    """Format and print text output.

    Args:
        result: Detection result dictionary.
    """
    if result["detected"]:
        detected = result["detected"].upper()
        supported = result["supported"]
        notes = result["notes"]

        if supported:
            success(f"✓ CNI Plugin: {detected}")
            success("  Status: SUPPORTED")
            success(f"  Notes: {notes}")
        else:
            error(f"✗ CNI Plugin: {detected}")
            error("  Status: NOT SUPPORTED")
            error(f"  Notes: {notes}")
    else:
        error("✗ Could not detect CNI plugin")
        error("  Checked for: Calico, Cilium, Weave, AWS VPC CNI, Azure CNI, GCE")


def _format_json_output(result: dict[str, Any]) -> None:
    """Format and print JSON output.

    Args:
        result: Detection result dictionary.
    """
    output = {
        "cni": result["detected"],
        "supported": result["supported"],
        "notes": result["notes"],
        "detected_daemonsets": result["daemonsets"],
        "detected_configmaps": result["configmaps"],
    }
    click.echo(json.dumps(output, indent=2))


@click.command(
    name="check-cni",
    help="Verify CNI plugin supports NetworkPolicies (FR-084).",
    epilog="""
Detects the CNI plugin running in the cluster and verifies
NetworkPolicy support. Checks DaemonSets and ConfigMaps in
the kube-system namespace.

Supported CNI plugins:
  ✓ Calico, Cilium, Weave, AWS VPC CNI, Azure CNI, GCE
  ✗ Flannel (needs Calico overlay), KindNet

Examples:
    $ floe network check-cni
    $ floe network check-cni --kubeconfig ~/.kube/config
    $ floe network check-cni --context prod-cluster --verbose
    $ floe network check-cni --output-format json
""",
    context_settings={"help_option_names": ["-h", "--help"]},
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
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed CNI detection info.",
)
@click.option(
    "--output-format",
    "-o",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format.",
    metavar="TEXT",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    hidden=True,
    help="Show verbose error messages with tracebacks.",
)
def check_cni_command(
    kubeconfig: Path | None,
    context: str | None,
    verbose: bool,
    output_format: str,
    debug: bool,
) -> None:
    """Verify CNI plugin supports NetworkPolicies.

    Detects the CNI plugin running in the cluster and checks
    if it supports Kubernetes NetworkPolicies.

    Args:
        kubeconfig: Path to kubeconfig file.
        context: Kubernetes context to use.
        verbose: Show detailed detection info.
        output_format: Output format (text or json).
    """
    try:
        if verbose:
            info("Connecting to Kubernetes cluster...")

        # Load Kubernetes clients
        core_api, apps_api = _load_kubernetes_client(kubeconfig, context)

        if verbose:
            info("Connected successfully")
            info("Detecting CNI plugin...")

        # Detect CNI
        result = _detect_cni(core_api, apps_api, verbose=verbose)

        # Format and output results
        if output_format.lower() == "json":
            _format_json_output(result)
        else:
            _format_text_output(result)

        # Exit with appropriate code
        if result["detected"] and result["supported"]:
            exit_code = ExitCode.SUCCESS
        elif result["detected"]:
            exit_code = ExitCode.VALIDATION_ERROR
        else:
            exit_code = ExitCode.GENERAL_ERROR

        if exit_code != ExitCode.SUCCESS:
            raise SystemExit(exit_code)

    except SystemExit:
        raise
    except Exception as e:
        if debug:
            import traceback

            traceback.print_exc()
        error_exit(
            f"CNI check failed: {type(e).__name__}",
            exit_code=ExitCode.GENERAL_ERROR,
        )


__all__: list[str] = ["check_cni_command"]
