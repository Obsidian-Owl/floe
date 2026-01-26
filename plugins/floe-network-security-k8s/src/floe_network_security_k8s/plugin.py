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

        from_entries: list[dict[str, Any]] = []
        if rule.from_namespace:
            from_entries.append(
                {
                    "namespaceSelector": {
                        "matchLabels": {"kubernetes.io/metadata.name": rule.from_namespace}
                    }
                }
            )
        if rule.from_pod_labels:
            from_entries.append({"podSelector": {"matchLabels": rule.from_pod_labels}})
        if from_entries:
            k8s_rule["from"] = from_entries

        if rule.ports:
            k8s_rule["ports"] = [{"port": p.port, "protocol": p.protocol} for p in rule.ports]

        return k8s_rule

    def _convert_egress_rule(self, rule: Any) -> dict[str, Any]:
        """Convert an EgressRule to K8s manifest format."""
        k8s_rule: dict[str, Any] = {}

        to_entries: list[dict[str, Any]] = []
        if rule.to_namespace:
            to_entries.append(
                {
                    "namespaceSelector": {
                        "matchLabels": {"kubernetes.io/metadata.name": rule.to_namespace}
                    }
                }
            )
        if rule.to_cidr:
            to_entries.append({"ipBlock": {"cidr": rule.to_cidr}})
        if to_entries:
            k8s_rule["to"] = to_entries

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

    # =========================================================================
    # Platform Ingress Rules (US2 - Platform Namespace Policies)
    # =========================================================================

    def generate_ingress_controller_rule(self, namespace: str = "ingress-nginx") -> dict[str, Any]:
        """Generate ingress rule from ingress controller namespace.

        Platform services need to receive traffic from the ingress controller
        for external access.

        Args:
            namespace: Ingress controller namespace (default: ingress-nginx).

        Returns:
            Ingress rule allowing traffic from ingress controller.
        """
        return {
            "from": [
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": namespace,
                        },
                    },
                },
            ],
            "ports": [
                {"port": 80, "protocol": "TCP"},
                {"port": 443, "protocol": "TCP"},
                {"port": 8080, "protocol": "TCP"},
            ],
        }

    def generate_jobs_ingress_rule(self) -> dict[str, Any]:
        """Generate ingress rule from floe-jobs namespace.

        Platform services need to receive traffic from job pods:
        - Polaris catalog queries
        - OTel telemetry
        - MinIO storage access

        Returns:
            Ingress rule allowing traffic from floe-jobs.
        """
        return {
            "from": [
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": "floe-jobs",
                        },
                    },
                },
            ],
            "ports": [
                {"port": 8181, "protocol": "TCP"},  # Polaris
                {"port": 4317, "protocol": "TCP"},  # OTel gRPC
                {"port": 4318, "protocol": "TCP"},  # OTel HTTP
                {"port": 9000, "protocol": "TCP"},  # MinIO
            ],
        }

    def generate_intra_namespace_rule(self, namespace: str) -> dict[str, Any]:
        """Generate intra-namespace communication rule.

        Allows pods within the same namespace to communicate with each other.
        Uses empty podSelector to match all pods in the namespace.

        Args:
            namespace: Target namespace (used for documentation only).

        Returns:
            Ingress rule allowing intra-namespace traffic.
        """
        return {
            "from": [
                {
                    "podSelector": {},  # Match all pods in same namespace
                },
            ],
        }

    def generate_k8s_api_egress_rule(self) -> dict[str, Any]:
        """Generate egress rule for Kubernetes API access.

        Platform services may need to communicate with the K8s API server
        for service discovery, leader election, etc.

        Returns:
            Egress rule allowing traffic to K8s API (port 443/6443).
        """
        return {
            "to": [
                {
                    # K8s API is typically exposed via a service in default namespace
                    # or directly to the API server IP
                    "ipBlock": {
                        "cidr": "0.0.0.0/0",  # K8s API endpoint (restrict in prod)
                    },
                },
            ],
            "ports": [
                {"port": 443, "protocol": "TCP"},
                {"port": 6443, "protocol": "TCP"},
            ],
        }

    def generate_external_https_egress_rule(self, enabled: bool = True) -> dict[str, Any] | None:
        """Generate egress rule for external HTTPS access.

        Platform services may need to access external APIs (e.g., cloud services).
        This is configurable and can be disabled for stricter environments.

        Args:
            enabled: Whether external HTTPS is allowed.

        Returns:
            Egress rule for external HTTPS, or None if disabled.
        """
        if not enabled:
            return None

        return {
            "to": [
                {
                    "ipBlock": {
                        "cidr": "0.0.0.0/0",
                        "except": [
                            "10.0.0.0/8",
                            "172.16.0.0/12",
                            "192.168.0.0/16",
                        ],
                    },
                },
            ],
            "ports": [
                {"port": 443, "protocol": "TCP"},
            ],
        }

    # =========================================================================
    # Custom Egress Rules (T033 - User-configurable egress)
    # =========================================================================

    def generate_custom_egress_rule(
        self,
        cidr: str | None = None,
        namespace: str | None = None,
        port: int = 443,
        protocol: str = "TCP",
    ) -> dict[str, Any]:
        """Generate a custom egress rule for platform configuration.

        Platform operators can define custom egress rules for:
        - External services via CIDR blocks
        - Other Kubernetes namespaces

        Args:
            cidr: CIDR block for IP-based egress (e.g., "10.0.0.0/8").
            namespace: Target namespace for namespace-based egress.
            port: Destination port (default: 443).
            protocol: Protocol, TCP or UDP (default: TCP).

        Returns:
            Egress rule dictionary for NetworkPolicy.

        Raises:
            ValueError: If neither cidr nor namespace is provided.
        """
        if cidr is None and namespace is None:
            raise ValueError("Either cidr or namespace must be provided")

        rule: dict[str, Any] = {
            "to": [],
            "ports": [{"port": port, "protocol": protocol}],
        }

        if cidr is not None:
            rule["to"].append({"ipBlock": {"cidr": cidr}})
        elif namespace is not None:
            rule["to"].append(
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": namespace,
                        },
                    },
                }
            )

        return rule

    def generate_custom_egress_rules(
        self,
        cidr: str | None = None,
        namespace: str | None = None,
        ports: list[int] | None = None,
        protocol: str = "TCP",
    ) -> dict[str, Any]:
        """Generate a custom egress rule with multiple ports.

        Convenience method for creating egress rules that allow multiple ports
        to the same destination.

        Args:
            cidr: CIDR block for IP-based egress (e.g., "10.0.0.0/8").
            namespace: Target namespace for namespace-based egress.
            ports: List of destination ports.
            protocol: Protocol, TCP or UDP (default: TCP).

        Returns:
            Egress rule dictionary with multiple ports.

        Raises:
            ValueError: If neither cidr nor namespace is provided.
        """
        if cidr is None and namespace is None:
            raise ValueError("Either cidr or namespace must be provided")

        if ports is None:
            ports = [443]

        rule: dict[str, Any] = {
            "to": [],
            "ports": [{"port": p, "protocol": protocol} for p in ports],
        }

        if cidr is not None:
            rule["to"].append({"ipBlock": {"cidr": cidr}})
        elif namespace is not None:
            rule["to"].append(
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": namespace,
                        },
                    },
                }
            )

        return rule

    # =========================================================================
    # Pod Security Standards (Phase 5 - US3)
    # =========================================================================

    # Default PSS levels per namespace
    _DEFAULT_PSS_LEVELS: dict[str, str] = {
        "floe-jobs": "restricted",
        "floe-platform": "baseline",
    }

    def generate_pss_labels(
        self,
        level: str = "restricted",
        audit_level: str | None = None,
        warn_level: str | None = None,
    ) -> dict[str, str]:
        """Generate Pod Security Standards namespace labels.

        PSS is enforced via namespace labels that the Pod Security Admission
        controller reads to determine which security profile to enforce.

        Args:
            level: Enforcement level (privileged, baseline, restricted).
            audit_level: Audit logging level (defaults to same as level).
            warn_level: Warning level (defaults to same as level).

        Returns:
            Dictionary of PSS labels for namespace metadata.
        """
        if audit_level is None:
            audit_level = level
        if warn_level is None:
            warn_level = level

        return {
            "pod-security.kubernetes.io/enforce": level,
            "pod-security.kubernetes.io/audit": audit_level,
            "pod-security.kubernetes.io/warn": warn_level,
        }

    def get_namespace_pss_level(
        self,
        namespace: str,
        override_levels: dict[str, str] | None = None,
    ) -> str:
        """Get the PSS level for a namespace.

        Returns the appropriate PSS level for a namespace, with support
        for configuration overrides.

        Args:
            namespace: Kubernetes namespace name.
            override_levels: Optional dict mapping namespace -> level overrides.

        Returns:
            PSS level string (privileged, baseline, restricted).
        """
        # Check for override first
        if override_levels and namespace in override_levels:
            return override_levels[namespace]

        # Return default level, or "restricted" as secure default
        return self._DEFAULT_PSS_LEVELS.get(namespace, "restricted")

    def generate_namespace_manifest(
        self,
        name: str,
        pss_level: str = "restricted",
        additional_labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Generate a Kubernetes Namespace manifest with PSS labels.

        Creates a complete Namespace manifest with Pod Security Standards
        labels for enforcement, audit, and warning modes.

        Args:
            name: Namespace name.
            pss_level: PSS enforcement level (privileged, baseline, restricted).
            additional_labels: Optional additional labels to include.

        Returns:
            Dictionary representing K8s Namespace YAML.
        """
        # Start with PSS labels
        labels = self.generate_pss_labels(level=pss_level)

        # Add managed-by label
        labels["app.kubernetes.io/managed-by"] = "floe"

        # Merge additional labels
        if additional_labels:
            labels.update(additional_labels)

        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": name,
                "labels": labels,
            },
        }

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
