"""Contract tests for NetworkPolicyManifestGenerator.

Task: T048
Phase: 7 - Manifest Generator (US5)
User Story: US5 - NetworkPolicy Manifest Generation
Requirement: FR-070, FR-071, FR-072, FR-073

This contract test defines the interface contract for NetworkPolicyManifestGenerator.
The generator MUST:
1. Accept a NetworkSecurityPlugin and generate policies for configured namespaces
2. Output valid K8s NetworkPolicy YAML files
3. Generate a NETWORK-POLICY-SUMMARY.md documentation file
4. Support write_manifests() to output to target directory
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml


class TestNetworkPolicyManifestGeneratorContract:
    """Contract tests for NetworkPolicyManifestGenerator interface.

    These tests define the expected behavior of the generator class.
    Implementation MUST satisfy these contracts.
    """

    @pytest.mark.requirement("FR-070")
    def test_generator_class_exists(self) -> None:
        """Test that NetworkPolicyManifestGenerator class exists and is importable."""
        from floe_core.network import NetworkPolicyManifestGenerator

        assert NetworkPolicyManifestGenerator is not None

    @pytest.mark.requirement("FR-070")
    def test_generator_accepts_plugin(self) -> None:
        """Test that generator constructor accepts a NetworkSecurityPlugin."""
        from floe_core.network import NetworkPolicyManifestGenerator
        from floe_core.plugins import NetworkSecurityPlugin

        # Create a mock plugin
        mock_plugin = MagicMock(spec=NetworkSecurityPlugin)
        mock_plugin.name = "mock-network-security"
        mock_plugin.version = "0.1.0"

        # Should not raise
        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        assert generator is not None

    @pytest.mark.requirement("FR-070")
    def test_generator_has_generate_method(self) -> None:
        """Test that generator has generate() method."""
        from floe_core.network import NetworkPolicyManifestGenerator
        from floe_core.plugins import NetworkSecurityPlugin

        mock_plugin = MagicMock(spec=NetworkSecurityPlugin)
        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)

        assert hasattr(generator, "generate")
        assert callable(generator.generate)

    @pytest.mark.requirement("FR-071")
    def test_generator_has_write_manifests_method(self) -> None:
        """Test that generator has write_manifests() method."""
        from floe_core.network import NetworkPolicyManifestGenerator
        from floe_core.plugins import NetworkSecurityPlugin

        mock_plugin = MagicMock(spec=NetworkSecurityPlugin)
        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)

        assert hasattr(generator, "write_manifests")
        assert callable(generator.write_manifests)


class TestNetworkPolicyGeneratorOutputContract:
    """Contract tests for generator output format."""

    @pytest.fixture
    def mock_plugin(self) -> MagicMock:
        """Create a mock NetworkSecurityPlugin with expected behavior."""
        mock = MagicMock()
        mock.name = "k8s-network-security"
        mock.version = "0.1.0"

        mock.generate_default_deny_policies.return_value = [
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {
                    "name": "default-deny-all",
                    "namespace": "floe-jobs",
                    "labels": {"app.kubernetes.io/managed-by": "floe"},
                },
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [],
                    "egress": [],
                },
            }
        ]

        mock.generate_dns_egress_rule.return_value = {
            "to": [
                {
                    "namespaceSelector": {
                        "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                    }
                }
            ],
            "ports": [{"port": 53, "protocol": "UDP"}, {"port": 53, "protocol": "TCP"}],
        }

        return mock

    @pytest.mark.requirement("FR-070")
    def test_generate_returns_result_object(self, mock_plugin: MagicMock) -> None:
        """Test that generate() returns a NetworkPolicyGenerationResult."""
        from floe_core.network import (
            NetworkPolicyGenerationResult,
            NetworkPolicyManifestGenerator,
        )

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        assert isinstance(result, NetworkPolicyGenerationResult)
        assert hasattr(result, "generated_policies")
        assert isinstance(result.generated_policies, list)

    @pytest.mark.requirement("FR-071")
    def test_write_manifests_creates_yaml_files(self, mock_plugin: MagicMock) -> None:
        """Test that write_manifests() creates YAML files in target directory."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "network"
            generator.write_manifests(result, output_path)

            # Should create at least one YAML file
            yaml_files = list(output_path.glob("*.yaml"))
            assert len(yaml_files) >= 1, "Expected at least one YAML file"

    @pytest.mark.requirement("FR-072")
    def test_write_manifests_creates_summary_markdown(
        self, mock_plugin: MagicMock
    ) -> None:
        """Test that write_manifests() creates NETWORK-POLICY-SUMMARY.md."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "network"
            generator.write_manifests(result, output_path)

            summary_file = output_path / "NETWORK-POLICY-SUMMARY.md"
            assert (
                summary_file.exists()
            ), "NETWORK-POLICY-SUMMARY.md should be generated"

    @pytest.mark.requirement("FR-070")
    def test_generated_yaml_is_valid_k8s_resource(self, mock_plugin: MagicMock) -> None:
        """Test that generated YAML is a valid K8s NetworkPolicy resource."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "network"
            generator.write_manifests(result, output_path)

            yaml_files = list(output_path.glob("*.yaml"))
            for yaml_file in yaml_files:
                content = yaml.safe_load(yaml_file.read_text())

                # Must be a K8s resource
                assert "apiVersion" in content
                assert "kind" in content
                assert "metadata" in content
                assert "spec" in content

                # Must be a NetworkPolicy
                assert content["kind"] == "NetworkPolicy"
                assert content["apiVersion"] == "networking.k8s.io/v1"

    @pytest.mark.requirement("FR-073")
    def test_generated_yaml_has_managed_by_label(self, mock_plugin: MagicMock) -> None:
        """Test that generated policies have floe managed-by label."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "network"
            generator.write_manifests(result, output_path)

            yaml_files = list(output_path.glob("*.yaml"))
            for yaml_file in yaml_files:
                content = yaml.safe_load(yaml_file.read_text())
                labels = content.get("metadata", {}).get("labels", {})
                assert labels.get("app.kubernetes.io/managed-by") == "floe"


class TestNetworkPolicyGenerationResultContract:
    """Contract tests for NetworkPolicyGenerationResult dataclass."""

    @pytest.mark.requirement("FR-070")
    def test_result_class_exists(self) -> None:
        """Test that NetworkPolicyGenerationResult exists."""
        from floe_core.network import NetworkPolicyGenerationResult

        assert NetworkPolicyGenerationResult is not None

    @pytest.mark.requirement("FR-070")
    def test_result_has_generated_policies_field(self) -> None:
        """Test that result has generated_policies field."""
        from floe_core.network import NetworkPolicyGenerationResult

        # Create a minimal result
        result = NetworkPolicyGenerationResult(generated_policies=[])
        assert hasattr(result, "generated_policies")
        assert isinstance(result.generated_policies, list)

    @pytest.mark.requirement("FR-070")
    def test_result_has_summary_method(self) -> None:
        """Test that result has summary() method for reporting."""
        from floe_core.network import NetworkPolicyGenerationResult

        result = NetworkPolicyGenerationResult(
            generated_policies=[],
            policies_count=0,
        )
        assert hasattr(result, "summary")
        assert callable(result.summary)
        summary = result.summary()
        assert isinstance(summary, dict)


class TestGeneratorDNSAlwaysIncludedContract:
    """Contract tests verifying DNS egress is always included."""

    @pytest.fixture
    def mock_plugin(self) -> MagicMock:
        """Create mock plugin."""
        from floe_core.plugins import NetworkSecurityPlugin

        mock = MagicMock(spec=NetworkSecurityPlugin)
        mock.name = "k8s-network-security"
        mock.version = "0.1.0"

        mock.generate_default_deny_policies.return_value = [
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": "default-deny-all", "namespace": "floe-jobs"},
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [],
                    "egress": [],
                },
            }
        ]

        mock.generate_dns_egress_rule.return_value = {
            "to": [
                {
                    "namespaceSelector": {
                        "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                    }
                }
            ],
            "ports": [{"port": 53, "protocol": "UDP"}],
        }

        return mock

    @pytest.mark.requirement("FR-012")
    def test_dns_egress_always_included(self, mock_plugin: MagicMock) -> None:
        """Test that DNS egress rule is always included in generated policies."""
        from floe_core.network import NetworkPolicyManifestGenerator

        generator = NetworkPolicyManifestGenerator(plugin=mock_plugin)
        result = generator.generate(namespaces=["floe-jobs"])

        mock_plugin.generate_dns_egress_rule.assert_called()

        has_dns = False
        for policy in result.generated_policies:
            egress = policy.get("spec", {}).get("egress", [])
            for rule in egress:
                ports = rule.get("ports", [])
                for port_rule in ports:
                    if port_rule.get("port") == 53:
                        has_dns = True
                        break

        assert has_dns, "Generated policies should include DNS egress rule"
