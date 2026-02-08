"""Unit tests for NetworkPolicyManifestGenerator.

Tests the NetworkPolicyManifestGenerator class including:
- Policy generation from plugin
- YAML file output per namespace
- NETWORK-POLICY-SUMMARY.md generation
- DNS egress rule injection
- Plugin discovery and wiring (T055)

Task: T049, T051, T053, T055
Phase: 7 - Manifest Generator (US5)
Requirements: FR-070, FR-071, FR-072, FR-073
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml


@pytest.fixture
def mock_plugin() -> MagicMock:
    """Create a mock NetworkSecurityPlugin for testing."""
    plugin = MagicMock()
    plugin.generate_dns_egress_rule.return_value = {
        "to": [
            {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}
        ],
        "ports": [{"protocol": "UDP", "port": 53}],
    }
    plugin.generate_default_deny_policies.return_value = [
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "default-deny-all",
                "namespace": "floe-jobs",
                "labels": {"floe.dev/managed-by": "floe"},
            },
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [],
                "egress": [],
            },
        }
    ]
    return plugin


@pytest.fixture
def mock_plugin_multi_namespace() -> MagicMock:
    """Create a mock plugin that returns policies for multiple namespaces."""
    plugin = MagicMock()
    plugin.generate_dns_egress_rule.return_value = {
        "to": [
            {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}
        ],
        "ports": [{"protocol": "UDP", "port": 53}],
    }

    def generate_policies(namespace: str) -> list[dict[str, Any]]:
        return [
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "default-deny-all",
                    "namespace": namespace,
                    "labels": {"floe.dev/managed-by": "floe"},
                },
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [],
                    "egress": [],
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "allow-platform-egress",
                    "namespace": namespace,
                    "labels": {"floe.dev/managed-by": "floe"},
                },
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Egress"],
                    "egress": [
                        {
                            "to": [
                                {"namespaceSelector": {"matchLabels": {"name": "floe-platform"}}}
                            ],
                            "ports": [{"protocol": "TCP", "port": 8181}],
                        }
                    ],
                },
            },
        ]

    plugin.generate_default_deny_policies.side_effect = generate_policies
    return plugin


class TestNetworkPolicyManifestGenerator:
    """Unit tests for NetworkPolicyManifestGenerator class (T049)."""

    @pytest.mark.requirement("FR-070")
    def test_generator_accepts_plugin(self, mock_plugin: MagicMock) -> None:
        """Test generator can be instantiated with a plugin."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)

        assert generator is not None
        assert generator._plugin is mock_plugin

    @pytest.mark.requirement("FR-070")
    def test_generate_returns_result(self, mock_plugin: MagicMock) -> None:
        """Test generate() returns NetworkPolicyGenerationResult."""
        from floe_core.network import (
            NetworkPolicyGenerationResult,
            NetworkPolicyManifestGenerator,
        )

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        assert isinstance(result, NetworkPolicyGenerationResult)

    @pytest.mark.requirement("FR-070")
    def test_generate_calls_plugin_methods(self, mock_plugin: MagicMock) -> None:
        """Test generate() calls plugin's policy generation methods."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        generator.generate(namespaces=["floe-jobs"])

        mock_plugin.generate_default_deny_policies.assert_called_once_with("floe-jobs")
        mock_plugin.generate_dns_egress_rule.assert_called_once()

    @pytest.mark.requirement("FR-070")
    def test_generate_multiple_namespaces(self, mock_plugin_multi_namespace: MagicMock) -> None:
        """Test generate() processes multiple namespaces."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin_multi_namespace)
        result = generator.generate(namespaces=["floe-jobs", "floe-platform"])

        # 2 policies per namespace × 2 namespaces = 4 policies
        assert result.policies_count == 4
        assert result.namespaces_count == 2

    @pytest.mark.requirement("FR-071")
    def test_generate_injects_dns_egress(self, mock_plugin: MagicMock) -> None:
        """Test DNS egress rule is injected into all policies."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        # Verify DNS rule was injected
        policy = result.generated_policies[0]
        egress_rules = policy["spec"]["egress"]
        assert len(egress_rules) >= 1

        # Find the DNS rule
        dns_rule = next(
            (r for r in egress_rules if r.get("ports", [{}])[0].get("port") == 53),
            None,
        )
        assert dns_rule is not None

    @pytest.mark.requirement("FR-072")
    def test_result_summary_statistics(self, mock_plugin_multi_namespace: MagicMock) -> None:
        """Test result includes correct summary statistics."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin_multi_namespace)
        result = generator.generate(namespaces=["floe-jobs", "floe-platform"])

        summary = result.summary()
        assert summary["policies_count"] == 4
        assert summary["namespaces_count"] == 2
        assert "egress_rules_count" in summary
        assert "ingress_rules_count" in summary


class TestNetworkPolicyFileOutput:
    """Unit tests for YAML file output per namespace (T051)."""

    @pytest.mark.requirement("FR-071")
    def test_write_manifests_creates_directory(
        self, mock_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """Test write_manifests creates output directory if missing."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        output_dir = tmp_path / "network"
        assert not output_dir.exists()

        generator.write_manifests(result, output_dir)

        assert output_dir.exists()
        assert output_dir.is_dir()

    @pytest.mark.requirement("FR-071")
    def test_write_manifests_creates_yaml_files(
        self, mock_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """Test write_manifests creates YAML files for each policy."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        yaml_files = list(output_dir.glob("*.yaml"))
        assert len(yaml_files) == 1
        assert yaml_files[0].name == "floe-jobs-default-deny-all.yaml"

    @pytest.mark.requirement("FR-071")
    def test_write_manifests_separate_files_per_namespace(
        self, mock_plugin_multi_namespace: MagicMock, tmp_path: Path
    ) -> None:
        """Test each namespace gets separate YAML files."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin_multi_namespace)
        result = generator.generate(namespaces=["floe-jobs", "floe-platform"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        yaml_files = list(output_dir.glob("*.yaml"))
        assert len(yaml_files) == 4  # 2 policies × 2 namespaces

        # Check filenames include namespace prefix
        filenames = {f.name for f in yaml_files}
        assert "floe-jobs-default-deny-all.yaml" in filenames
        assert "floe-jobs-allow-platform-egress.yaml" in filenames
        assert "floe-platform-default-deny-all.yaml" in filenames
        assert "floe-platform-allow-platform-egress.yaml" in filenames

    @pytest.mark.requirement("FR-071")
    def test_yaml_files_are_valid_k8s_manifests(
        self, mock_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """Test generated YAML files contain valid K8s NetworkPolicy manifests."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        yaml_file = output_dir / "floe-jobs-default-deny-all.yaml"
        with yaml_file.open() as f:
            manifest = yaml.safe_load(f)

        assert manifest["apiVersion"] == "networking.k8s.io/v1"
        assert manifest["kind"] == "NetworkPolicy"
        assert manifest["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-073")
    def test_yaml_files_have_managed_by_label(self, mock_plugin: MagicMock, tmp_path: Path) -> None:
        """Test generated YAML files include floe.dev/managed-by label."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        yaml_file = output_dir / "floe-jobs-default-deny-all.yaml"
        with yaml_file.open() as f:
            manifest = yaml.safe_load(f)

        assert manifest["metadata"]["labels"]["floe.dev/managed-by"] == "floe"


class TestNetworkPolicySummaryGeneration:
    """Unit tests for NETWORK-POLICY-SUMMARY.md generation (T053)."""

    @pytest.mark.requirement("FR-072")
    def test_write_manifests_creates_summary_file(
        self, mock_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """Test write_manifests creates NETWORK-POLICY-SUMMARY.md file."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        summary_file = output_dir / "NETWORK-POLICY-SUMMARY.md"
        assert summary_file.exists()

    @pytest.mark.requirement("FR-072")
    def test_summary_includes_statistics(
        self, mock_plugin_multi_namespace: MagicMock, tmp_path: Path
    ) -> None:
        """Test summary markdown includes policy statistics."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin_multi_namespace)
        result = generator.generate(namespaces=["floe-jobs", "floe-platform"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        summary_file = output_dir / "NETWORK-POLICY-SUMMARY.md"
        content = summary_file.read_text()

        assert "Total Policies" in content
        assert "Namespaces" in content
        assert "Egress Rules" in content
        assert "Ingress Rules" in content

    @pytest.mark.requirement("FR-072")
    def test_summary_lists_policies_by_namespace(
        self, mock_plugin_multi_namespace: MagicMock, tmp_path: Path
    ) -> None:
        """Test summary lists policies organized by namespace."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin_multi_namespace)
        result = generator.generate(namespaces=["floe-jobs", "floe-platform"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        summary_file = output_dir / "NETWORK-POLICY-SUMMARY.md"
        content = summary_file.read_text()

        # Check namespace headers
        assert "### floe-jobs" in content
        assert "### floe-platform" in content

        # Check policy names listed
        assert "`default-deny-all`" in content
        assert "`allow-platform-egress`" in content

    @pytest.mark.requirement("FR-071")
    def test_summary_documents_dns_auto_inclusion(
        self, mock_plugin: MagicMock, tmp_path: Path
    ) -> None:
        """Test summary documents that DNS egress is always included."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        summary_file = output_dir / "NETWORK-POLICY-SUMMARY.md"
        content = summary_file.read_text()

        assert "DNS" in content
        assert "always included" in content.lower()


class TestGeneratorEmptyInput:
    """Unit tests for edge cases with empty or missing input."""

    @pytest.mark.requirement("FR-070")
    def test_generate_empty_namespaces(self, mock_plugin: MagicMock) -> None:
        """Test generate() handles empty namespace list."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=[])

        assert result.policies_count == 0
        assert result.namespaces_count == 0
        assert len(result.generated_policies) == 0

    @pytest.mark.requirement("FR-071")
    def test_write_manifests_empty_result(self, mock_plugin: MagicMock, tmp_path: Path) -> None:
        """Test write_manifests handles empty result."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=[])

        output_dir = tmp_path / "network"
        generator.write_manifests(result, output_dir)

        summary_file = output_dir / "NETWORK-POLICY-SUMMARY.md"
        assert summary_file.exists()

        yaml_files = list(output_dir.glob("*.yaml"))
        assert len(yaml_files) == 0


class TestPluginDiscovery:
    """Unit tests for plugin discovery and wiring (T055)."""

    @pytest.mark.requirement("FR-070")
    def test_discover_network_security_plugins_returns_dict(self) -> None:
        """Test discover_network_security_plugins returns dictionary."""
        from floe_core.network import discover_network_security_plugins

        result = discover_network_security_plugins()

        assert isinstance(result, dict)

    @pytest.mark.requirement("FR-070")
    def test_discover_network_security_plugins_finds_k8s_plugin(self) -> None:
        """Test k8s plugin is discovered from entry points."""
        from unittest.mock import patch

        from floe_core.network import discover_network_security_plugins
        from floe_core.plugins import NetworkSecurityPlugin

        mock_k8s_cls = type(
            "K8sPlugin",
            (NetworkSecurityPlugin,),
            {
                "name": property(lambda self: "k8s"),
                "version": property(lambda self: "0.1.0"),
                "floe_api_version": property(lambda self: "1.0"),
                "generate_default_deny_policies": lambda self, ns: [],
                "generate_dns_egress_rule": lambda self: {},
                "generate_network_policy": lambda self, config: {},
                "generate_pod_security_context": lambda self, config=None: {},
                "generate_container_security_context": lambda self, config=None: {},
                "generate_writable_volumes": lambda self, paths: ([], []),
                "get_config_schema": lambda self: None,
            },
        )

        mock_ep = MagicMock()
        mock_ep.name = "k8s"
        mock_ep.load.return_value = mock_k8s_cls

        with patch("floe_core.network.generator.entry_points", return_value=[mock_ep]):
            plugins = discover_network_security_plugins()

        assert "k8s" in plugins

    @pytest.mark.requirement("FR-070")
    def test_get_network_security_plugin_returns_instance(self) -> None:
        """Test get_network_security_plugin returns plugin instance."""
        from unittest.mock import patch

        from floe_core.network import get_network_security_plugin
        from floe_core.plugins import NetworkSecurityPlugin

        mock_k8s_cls = type(
            "K8sPlugin",
            (NetworkSecurityPlugin,),
            {
                "name": property(lambda self: "k8s"),
                "version": property(lambda self: "0.1.0"),
                "floe_api_version": property(lambda self: "1.0"),
                "generate_default_deny_policies": lambda self, ns: [],
                "generate_dns_egress_rule": lambda self: {},
                "generate_network_policy": lambda self, config: {},
                "generate_pod_security_context": lambda self, config=None: {},
                "generate_container_security_context": lambda self, config=None: {},
                "generate_writable_volumes": lambda self, paths: ([], []),
                "get_config_schema": lambda self: None,
            },
        )

        mock_ep = MagicMock()
        mock_ep.name = "k8s"
        mock_ep.load.return_value = mock_k8s_cls

        with patch("floe_core.network.generator.entry_points", return_value=[mock_ep]):
            plugin = get_network_security_plugin("k8s")

        assert isinstance(plugin, NetworkSecurityPlugin)

    @pytest.mark.requirement("FR-070")
    def test_get_network_security_plugin_auto_selects_single_plugin(self) -> None:
        """Test auto-selection when only one plugin available."""
        from unittest.mock import patch

        from floe_core.network import get_network_security_plugin
        from floe_core.plugins import NetworkSecurityPlugin

        mock_k8s_cls = type(
            "K8sPlugin",
            (NetworkSecurityPlugin,),
            {
                "name": property(lambda self: "k8s"),
                "version": property(lambda self: "0.1.0"),
                "floe_api_version": property(lambda self: "1.0"),
                "generate_default_deny_policies": lambda self, ns: [],
                "generate_dns_egress_rule": lambda self: {},
                "generate_network_policy": lambda self, config: {},
                "generate_pod_security_context": lambda self, config=None: {},
                "generate_container_security_context": lambda self, config=None: {},
                "generate_writable_volumes": lambda self, paths: ([], []),
                "get_config_schema": lambda self: None,
            },
        )

        mock_ep = MagicMock()
        mock_ep.name = "k8s"
        mock_ep.load.return_value = mock_k8s_cls

        with patch("floe_core.network.generator.entry_points", return_value=[mock_ep]):
            plugin = get_network_security_plugin()

        assert isinstance(plugin, NetworkSecurityPlugin)

    @pytest.mark.requirement("FR-070")
    def test_get_network_security_plugin_raises_for_unknown(self) -> None:
        """Test raises error for unknown plugin name."""
        from floe_core.network import (
            NetworkSecurityPluginNotFoundError,
            get_network_security_plugin,
        )

        with pytest.raises(NetworkSecurityPluginNotFoundError):
            get_network_security_plugin("nonexistent")

    @pytest.mark.requirement("FR-070")
    def test_from_entry_point_creates_generator(self) -> None:
        """Test from_entry_point factory creates generator."""
        from unittest.mock import patch

        from floe_core.network import NetworkPolicyManifestGenerator
        from floe_core.plugins import NetworkSecurityPlugin

        mock_k8s_cls = type(
            "K8sPlugin",
            (NetworkSecurityPlugin,),
            {
                "name": property(lambda self: "k8s"),
                "version": property(lambda self: "0.1.0"),
                "floe_api_version": property(lambda self: "1.0"),
                "generate_default_deny_policies": lambda self, ns: [],
                "generate_dns_egress_rule": lambda self: {},
                "generate_network_policy": lambda self, config: {},
                "generate_pod_security_context": lambda self, config=None: {},
                "generate_container_security_context": lambda self, config=None: {},
                "generate_writable_volumes": lambda self, paths: ([], []),
                "get_config_schema": lambda self: None,
            },
        )

        mock_ep = MagicMock()
        mock_ep.name = "k8s"
        mock_ep.load.return_value = mock_k8s_cls

        with patch("floe_core.network.generator.entry_points", return_value=[mock_ep]):
            generator = NetworkPolicyManifestGenerator.from_entry_point("k8s")

        assert isinstance(generator, NetworkPolicyManifestGenerator)

    @pytest.mark.requirement("FR-070")
    def test_from_entry_point_generator_can_generate(self) -> None:
        """Test generator from entry point can generate policies."""
        from unittest.mock import patch

        from floe_core.network import NetworkPolicyManifestGenerator
        from floe_core.plugins import NetworkSecurityPlugin

        mock_k8s_cls = type(
            "K8sPlugin",
            (NetworkSecurityPlugin,),
            {
                "name": property(lambda self: "k8s"),
                "version": property(lambda self: "0.1.0"),
                "floe_api_version": property(lambda self: "1.0"),
                "generate_default_deny_policies": lambda self, namespace: [
                    {
                        "apiVersion": "networking.k8s.io/v1",
                        "kind": "NetworkPolicy",
                        "metadata": {"name": "default-deny", "namespace": namespace},
                        "spec": {"egress": [], "ingress": []},
                    }
                ],
                "generate_dns_egress_rule": lambda self: {
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                            }
                        }
                    ],
                    "ports": [
                        {"protocol": "UDP", "port": 53},
                        {"protocol": "TCP", "port": 53},
                    ],
                },
                "generate_network_policy": lambda self, config: {},
                "generate_pod_security_context": lambda self, config=None: {},
                "generate_container_security_context": lambda self, config=None: {},
                "generate_writable_volumes": lambda self, paths: ([], []),
                "get_config_schema": lambda self: None,
            },
        )

        mock_ep = MagicMock()
        mock_ep.name = "k8s"
        mock_ep.load.return_value = mock_k8s_cls

        with patch("floe_core.network.generator.entry_points", return_value=[mock_ep]):
            generator = NetworkPolicyManifestGenerator.from_entry_point("k8s")
            result = generator.generate(namespaces=["floe-jobs"])

        assert result.policies_count >= 1
        assert result.namespaces_count == 1

    @pytest.mark.requirement("FR-070")
    def test_network_security_plugin_not_found_error_exported(self) -> None:
        """Test NetworkSecurityPluginNotFoundError is properly exported."""
        from floe_core.network import NetworkSecurityPluginNotFoundError

        assert issubclass(NetworkSecurityPluginNotFoundError, Exception)
