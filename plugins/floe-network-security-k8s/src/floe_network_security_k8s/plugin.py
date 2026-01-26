"""Kubernetes Network Security plugin implementation.

This module provides the K8sNetworkSecurityPlugin class that implements
the NetworkSecurityPlugin ABC from floe-core.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from floe_core.plugins import NetworkSecurityPlugin

if TYPE_CHECKING:
    from floe_core.network.schemas import NetworkPolicyConfig


class K8sNetworkSecurityPlugin(NetworkSecurityPlugin):
    """Kubernetes Network Security plugin.

    Implements the NetworkSecurityPlugin ABC to generate:
    - NetworkPolicy manifests (default-deny, egress allowlists)
    - Pod Security Standards namespace labels
    - Container securityContext configurations

    Attributes:
        name: Plugin identifier.
        version: Plugin version (semver).
        floe_api_version: Minimum floe API version required.
    """

    @property
    def name(self) -> str:
        """Plugin identifier."""
        return "k8s-network-security"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Minimum floe API version required."""
        return "1.0"

    def generate_network_policy(self, config: NetworkPolicyConfig) -> dict[str, Any]:
        """Generate a single K8s NetworkPolicy manifest.

        Args:
            config: NetworkPolicy configuration.

        Returns:
            Dictionary representing K8s NetworkPolicy YAML.
        """
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": config.name,
                "namespace": config.namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "floe",
                },
            },
            "spec": {
                "podSelector": config.pod_selector or {},
                "policyTypes": [],
            },
        }

        # Add ingress rules if present
        if config.ingress_rules:
            manifest["spec"]["policyTypes"].append("Ingress")
            manifest["spec"]["ingress"] = [
                self._convert_ingress_rule(rule) for rule in config.ingress_rules
            ]

        # Add egress rules if present
        if config.egress_rules:
            manifest["spec"]["policyTypes"].append("Egress")
            manifest["spec"]["egress"] = [
                self._convert_egress_rule(rule) for rule in config.egress_rules
            ]

        return manifest

    def _convert_ingress_rule(self, rule: Any) -> dict[str, Any]:
        """Convert an IngressRule to K8s manifest format."""
        k8s_rule: dict[str, Any] = {}

        if rule.from_sources:
            k8s_rule["from"] = rule.from_sources

        if rule.ports:
            k8s_rule["ports"] = [{"port": p.port, "protocol": p.protocol} for p in rule.ports]

        return k8s_rule

    def _convert_egress_rule(self, rule: Any) -> dict[str, Any]:
        """Convert an EgressRule to K8s manifest format."""
        k8s_rule: dict[str, Any] = {}

        if rule.to_destinations:
            k8s_rule["to"] = rule.to_destinations

        if rule.ports:
            k8s_rule["ports"] = [{"port": p.port, "protocol": p.protocol} for p in rule.ports]

        return k8s_rule

    def generate_default_deny_policies(self, namespace: str) -> list[dict[str, Any]]:
        """Generate default-deny ingress and egress policies.

        Args:
            namespace: Target namespace.

        Returns:
            List of NetworkPolicy manifests (ingress-deny, egress-deny).
        """
        return [
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "default-deny-all",
                    "namespace": namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "floe",
                    },
                },
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [],
                    "egress": [],
                },
            }
        ]

    def generate_dns_egress_rule(self) -> dict[str, Any]:
        """Generate DNS egress rule (always required).

        Returns:
            Egress rule allowing UDP 53 to kube-system.
        """
        return {
            "to": [
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": "kube-system",
                        },
                    },
                },
            ],
            "ports": [
                {"port": 53, "protocol": "UDP"},
                {"port": 53, "protocol": "TCP"},
            ],
        }

    def generate_platform_egress_rules(self) -> list[dict[str, Any]]:
        """Generate platform service egress rules (built-in).

        Jobs need to communicate with platform services:
        - Polaris catalog: TCP 8181
        - OTel Collector: TCP 4317 (gRPC), 4318 (HTTP)
        - MinIO storage: TCP 9000

        Returns:
            List of egress rules for platform services.
        """
        platform_namespace_selector = {
            "namespaceSelector": {
                "matchLabels": {
                    "kubernetes.io/metadata.name": "floe-platform",
                },
            },
        }

        return [
            # Polaris catalog (REST API)
            {
                "to": [platform_namespace_selector],
                "ports": [{"port": 8181, "protocol": "TCP"}],
            },
            # OTel Collector (gRPC for traces/metrics)
            {
                "to": [platform_namespace_selector],
                "ports": [{"port": 4317, "protocol": "TCP"}],
            },
            # OTel Collector (HTTP for traces/metrics)
            {
                "to": [platform_namespace_selector],
                "ports": [{"port": 4318, "protocol": "TCP"}],
            },
            # MinIO storage (S3-compatible API)
            {
                "to": [platform_namespace_selector],
                "ports": [{"port": 9000, "protocol": "TCP"}],
            },
        ]

    def generate_pod_security_context(self, config: Any) -> dict[str, Any]:
        """Generate pod-level securityContext.

        Args:
            config: Pod security context configuration.

        Returns:
            Dictionary representing K8s pod securityContext.
        """
        return {
            "runAsNonRoot": True,
            "runAsUser": 1000,
            "runAsGroup": 1000,
            "fsGroup": 1000,
            "seccompProfile": {
                "type": "RuntimeDefault",
            },
        }

    def generate_container_security_context(self, config: Any) -> dict[str, Any]:
        """Generate container-level securityContext.

        Args:
            config: Pod security context configuration.

        Returns:
            Dictionary representing K8s container securityContext.
        """
        return {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {
                "drop": ["ALL"],
            },
        }

    def generate_writable_volumes(
        self, writable_paths: list[str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Generate emptyDir volumes for writable paths.

        Args:
            writable_paths: Paths needing write access (e.g., ["/tmp", "/home/floe"]).

        Returns:
            Tuple of (volumes, volumeMounts).
        """
        volumes: list[dict[str, Any]] = []
        volume_mounts: list[dict[str, Any]] = []

        for path in writable_paths:
            # Generate a safe volume name from the path
            volume_name = self._path_to_volume_name(path)

            volumes.append(
                {
                    "name": volume_name,
                    "emptyDir": {},
                }
            )

            volume_mounts.append(
                {
                    "name": volume_name,
                    "mountPath": path,
                }
            )

        return volumes, volume_mounts

    def _path_to_volume_name(self, path: str) -> str:
        """Convert a path to a valid K8s volume name.

        K8s volume names must be lowercase alphanumeric with dashes.

        Args:
            path: File system path (e.g., "/tmp", "/home/floe").

        Returns:
            Valid K8s volume name (e.g., "writable-tmp", "writable-home-floe").
        """
        # Remove leading slash and replace slashes with dashes
        clean_path = path.lstrip("/").replace("/", "-")
        # Convert to lowercase and remove invalid characters
        clean_path = re.sub(r"[^a-z0-9-]", "-", clean_path.lower())
        # Remove consecutive dashes and trim
        clean_path = re.sub(r"-+", "-", clean_path).strip("-")
        # Prefix with 'writable-' for clarity
        return f"writable-{clean_path}" if clean_path else "writable-root"
