"""NetworkPolicy manifest generator for Kubernetes.

Task: T050, T055
Phase: 7 - Manifest Generator (US5)
Requirement: FR-070, FR-071, FR-072, FR-073
"""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

from floe_core.network.result import NetworkPolicyGenerationResult

if TYPE_CHECKING:
    from floe_core.plugins import NetworkSecurityPlugin

logger = structlog.get_logger(__name__)

NETWORK_SECURITY_ENTRY_POINT_GROUP = "floe.network_security"


class NetworkSecurityPluginNotFoundError(Exception):
    """Raised when no network security plugin is found or specified plugin not available."""

    pass


def discover_network_security_plugins() -> dict[str, type["NetworkSecurityPlugin"]]:
    """Discover all network security plugins from entry points.

    Scans the floe.network_security entry point group and loads all discovered
    plugin classes.

    Returns:
        Dict mapping plugin name to plugin class.

    Example:
        >>> plugins = discover_network_security_plugins()
        >>> print(plugins.keys())
        dict_keys(['k8s'])
    """
    discovered: dict[str, type[NetworkSecurityPlugin]] = {}

    try:
        eps = entry_points(group=NETWORK_SECURITY_ENTRY_POINT_GROUP)
    except Exception as e:
        logger.error(
            "discover_plugins.failed",
            group=NETWORK_SECURITY_ENTRY_POINT_GROUP,
            error=str(e),
        )
        return discovered

    for ep in eps:
        try:
            plugin_class = ep.load()
            discovered[ep.name] = plugin_class
            logger.debug(
                "discover_plugins.found",
                name=ep.name,
                plugin_class=plugin_class.__name__,
            )
        except Exception as e:
            logger.warning(
                "discover_plugins.load_failed",
                name=ep.name,
                error=str(e),
            )

    logger.info(
        "discover_plugins.completed",
        count=len(discovered),
        plugins=list(discovered.keys()),
    )

    return discovered


def get_network_security_plugin(name: str | None = None) -> "NetworkSecurityPlugin":
    """Get a network security plugin instance by name.

    If no name is specified and only one plugin is available, returns that plugin.
    If multiple plugins are available and no name is specified, raises an error.

    Args:
        name: Optional plugin name. If None, uses the only available plugin
              or raises if multiple are available.

    Returns:
        Instantiated NetworkSecurityPlugin.

    Raises:
        NetworkSecurityPluginNotFoundError: If no plugins found or specified
            plugin not available.

    Example:
        >>> plugin = get_network_security_plugin("k8s")
        >>> policies = plugin.generate_default_deny_policies("floe-jobs")
    """
    plugins = discover_network_security_plugins()

    if not plugins:
        msg = (
            f"No network security plugins found. "
            f"Ensure a plugin is installed with entry point group '{NETWORK_SECURITY_ENTRY_POINT_GROUP}'"
        )
        raise NetworkSecurityPluginNotFoundError(msg)

    if name is None:
        if len(plugins) == 1:
            name = next(iter(plugins.keys()))
            logger.debug("get_plugin.auto_selected", name=name)
        else:
            msg = (
                f"Multiple network security plugins available: {list(plugins.keys())}. "
                f"Specify which plugin to use."
            )
            raise NetworkSecurityPluginNotFoundError(msg)

    if name not in plugins:
        msg = f"Network security plugin '{name}' not found. Available: {list(plugins.keys())}"
        raise NetworkSecurityPluginNotFoundError(msg)

    plugin_class = plugins[name]
    plugin_instance = plugin_class()

    logger.info("get_plugin.instantiated", name=name, plugin_class=plugin_class.__name__)

    return plugin_instance


class NetworkPolicyManifestGenerator:
    """Generate Kubernetes NetworkPolicy manifests from floe configuration.

    Uses a NetworkSecurityPlugin to generate policies for specified namespaces,
    then writes them to YAML files in the target directory.
    """

    def __init__(self, plugin: NetworkSecurityPlugin) -> None:
        self._plugin = plugin

    @classmethod
    def from_entry_point(cls, plugin_name: str | None = None) -> "NetworkPolicyManifestGenerator":
        """Create generator with plugin discovered from entry points.

        Args:
            plugin_name: Optional plugin name. If None, auto-selects if only one available.

        Returns:
            Configured NetworkPolicyManifestGenerator instance.

        Raises:
            NetworkSecurityPluginNotFoundError: If no plugins found.
        """
        plugin = get_network_security_plugin(plugin_name)
        return cls(plugin=plugin)

    def generate(self, namespaces: list[str]) -> NetworkPolicyGenerationResult:
        """Generate NetworkPolicy manifests for the given namespaces.

        Args:
            namespaces: List of namespace names to generate policies for.

        Returns:
            NetworkPolicyGenerationResult with all generated policies.
        """
        generated_policies: list[dict[str, Any]] = []
        warnings: list[str] = []
        egress_count = 0
        ingress_count = 0
        default_deny_count = 0

        dns_rule = self._plugin.generate_dns_egress_rule()

        for namespace in namespaces:
            default_deny_policies = self._plugin.generate_default_deny_policies(namespace)

            for policy in default_deny_policies:
                egress_rules = list(policy.get("spec", {}).get("egress", []))
                egress_rules.append(dns_rule)
                policy["spec"]["egress"] = egress_rules
                egress_count += len(egress_rules)

                ingress_rules = policy.get("spec", {}).get("ingress", [])
                ingress_count += len(ingress_rules)

                default_deny_count += 1
                generated_policies.append(policy)

        return NetworkPolicyGenerationResult(
            generated_policies=generated_policies,
            warnings=warnings,
            policies_count=len(generated_policies),
            namespaces_count=len(namespaces),
            default_deny_count=default_deny_count,
            egress_rules_count=egress_count,
            ingress_rules_count=ingress_count,
        )

    def write_manifests(
        self,
        result: NetworkPolicyGenerationResult,
        output_dir: Path,
    ) -> None:
        """Write generated policies to YAML files in the output directory.

        Args:
            result: Generation result containing policies.
            output_dir: Directory to write YAML files to.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        policies_by_namespace: dict[str, list[dict[str, Any]]] = {}
        for policy in result.generated_policies:
            namespace = policy.get("metadata", {}).get("namespace", "unknown")
            if namespace not in policies_by_namespace:
                policies_by_namespace[namespace] = []
            policies_by_namespace[namespace].append(policy)

        for namespace, policies in policies_by_namespace.items():
            for i, policy in enumerate(policies):
                policy_name = policy.get("metadata", {}).get("name", f"policy-{i}")
                filename = f"{namespace}-{policy_name}.yaml"
                filepath = output_dir / filename

                with filepath.open("w") as f:
                    yaml.dump(policy, f, default_flow_style=False, sort_keys=False)

        self._write_summary(result, output_dir)

    def _write_summary(
        self,
        result: NetworkPolicyGenerationResult,
        output_dir: Path,
    ) -> None:
        """Write NETWORK-POLICY-SUMMARY.md documentation file."""
        summary_path = output_dir / "NETWORK-POLICY-SUMMARY.md"
        stats = result.summary()

        content = f"""# Network Policy Summary

Generated by floe NetworkPolicyManifestGenerator.

## Statistics

| Metric | Value |
|--------|-------|
| Total Policies | {stats["policies_count"]} |
| Namespaces | {stats["namespaces_count"]} |
| Default-Deny Policies | {stats["default_deny_count"]} |
| Egress Rules | {stats["egress_rules_count"]} |
| Ingress Rules | {stats["ingress_rules_count"]} |
| Warnings | {stats["warnings_count"]} |

## DNS Egress

DNS egress (UDP/TCP port 53 to kube-system) is **always included** in all policies.
This cannot be disabled as it is required for Kubernetes service discovery.

## Policies by Namespace

"""
        policies_by_ns: dict[str, list[str]] = {}
        for policy in result.generated_policies:
            ns = policy.get("metadata", {}).get("namespace", "unknown")
            name = policy.get("metadata", {}).get("name", "unnamed")
            if ns not in policies_by_ns:
                policies_by_ns[ns] = []
            policies_by_ns[ns].append(name)

        for ns, names in sorted(policies_by_ns.items()):
            content += f"### {ns}\n\n"
            for name in names:
                content += f"- `{name}`\n"
            content += "\n"

        summary_path.write_text(content)
