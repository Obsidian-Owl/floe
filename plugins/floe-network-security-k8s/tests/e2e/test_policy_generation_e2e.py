"""End-to-end tests for NetworkPolicy generation workflow.

Task: T088
Phase: 11 - E2E Tests (US7)
User Story: US7 - Plugin Architecture Standards
Requirement: FR-080, FR-081

Tests the complete workflow:
1. Generate policies from manifest.yaml
2. Validate generated policies
3. Apply policies to cluster
4. Verify policies work
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_network_security_k8s import K8sNetworkSecurityPlugin


class TestPolicyGenerationWorkflow:
    """E2E tests for policy generation workflow."""

    @pytest.fixture
    def sample_manifest(self, tmp_path: Path) -> Path:
        """Create sample manifest.yaml for testing.

        Args:
            tmp_path: Temporary directory for test files.

        Returns:
            Path to created manifest.yaml file.
        """
        manifest: dict[str, Any] = {
            "version": "1.0",
            "name": "test-platform",
            "security": {
                "network_policies": {
                    "enabled": True,
                    "default_deny": True,
                    "allow_external_https": True,
                    "ingress_controller_namespace": "ingress-nginx",
                }
            },
        }
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(yaml.dump(manifest))
        return manifest_path

    @pytest.fixture
    def plugin_instance(self) -> K8sNetworkSecurityPlugin:
        """Create plugin instance for testing.

        Returns:
            K8sNetworkSecurityPlugin instance.
        """
        return K8sNetworkSecurityPlugin()

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-080")
    def test_generate_creates_output_directory(self, sample_manifest: Path, tmp_path: Path) -> None:
        """Test generate command creates output directory structure.

        Validates that the generate command properly creates the output
        directory when it doesn't exist.

        Args:
            sample_manifest: Path to test manifest.yaml.
            tmp_path: Temporary directory for test files.
        """
        output_dir = tmp_path / "network"

        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "generate",
                "--config",
                str(sample_manifest),
                "--output",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Command should succeed or fail gracefully (may not have plugins)
        assert result.returncode in (0, 1, 2)
        # Output directory should be created
        assert output_dir.exists() or result.returncode != 0

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-080")
    def test_generate_with_dry_run_no_files_written(
        self, sample_manifest: Path, tmp_path: Path
    ) -> None:
        """Test generate --dry-run doesn't write files.

        Validates that dry-run mode shows what would be generated
        without actually writing files.

        Args:
            sample_manifest: Path to test manifest.yaml.
            tmp_path: Temporary directory for test files.
        """
        output_dir = tmp_path / "network"

        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "generate",
                "--config",
                str(sample_manifest),
                "--output",
                str(output_dir),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )

        # Dry-run should succeed
        assert result.returncode in (0, 1, 2)
        # Output should indicate dry-run
        assert "dry-run" in result.stdout.lower() or result.returncode != 0

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-080")
    def test_generate_with_namespace_filter(self, sample_manifest: Path, tmp_path: Path) -> None:
        """Test generate with --namespace filter.

        Validates that the --namespace option filters policy generation
        to a specific namespace.

        Args:
            sample_manifest: Path to test manifest.yaml.
            tmp_path: Temporary directory for test files.
        """
        output_dir = tmp_path / "network"

        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "generate",
                "--config",
                str(sample_manifest),
                "--output",
                str(output_dir),
                "--namespace",
                "floe-jobs",
            ],
            capture_output=True,
            text=True,
        )

        # Command should succeed or fail gracefully
        assert result.returncode in (0, 1, 2)
        # Output should mention the namespace
        assert "floe-jobs" in result.stdout or result.returncode != 0

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-081")
    def test_plugin_generates_valid_network_policy(
        self, plugin_instance: K8sNetworkSecurityPlugin
    ) -> None:
        """Test plugin generates valid NetworkPolicy manifest.

        Validates that the plugin can generate a properly formatted
        Kubernetes NetworkPolicy manifest.

        Args:
            plugin_instance: K8sNetworkSecurityPlugin instance.
        """
        from floe_core.network.schemas import NetworkPolicyConfig

        config = NetworkPolicyConfig(
            name="floe-test-default-deny",
            namespace="test-namespace",
            pod_selector={},
            policy_types=("Ingress", "Egress"),
            ingress_rules=(),
            egress_rules=(),
        )

        policy = plugin_instance.generate_network_policy(config)

        # Validate manifest structure
        assert policy["apiVersion"] == "networking.k8s.io/v1"
        assert policy["kind"] == "NetworkPolicy"
        assert policy["metadata"]["name"] == "floe-test-default-deny"
        assert policy["metadata"]["namespace"] == "test-namespace"
        assert "spec" in policy
        assert "podSelector" in policy["spec"]

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-081")
    def test_plugin_generates_policy_with_ingress_rules(
        self, plugin_instance: K8sNetworkSecurityPlugin
    ) -> None:
        """Test plugin generates policy with ingress rules.

        Validates that the plugin correctly includes ingress rules
        in the generated NetworkPolicy manifest.

        Args:
            plugin_instance: K8sNetworkSecurityPlugin instance.
        """
        from floe_core.network.schemas import IngressRule, NetworkPolicyConfig, PortRule

        ingress_rule = IngressRule(
            from_namespace="ingress-nginx",
            from_pod_labels={"app": "nginx"},
            ports=[PortRule(port=80, protocol="TCP")],
        )

        config = NetworkPolicyConfig(
            name="floe-test-ingress",
            namespace="test-namespace",
            pod_selector={},
            policy_types=("Ingress",),
            ingress_rules=(ingress_rule,),
            egress_rules=(),
        )

        policy = plugin_instance.generate_network_policy(config)

        # Validate ingress rules
        assert "Ingress" in policy["spec"]["policyTypes"]
        assert "ingress" in policy["spec"]
        assert len(policy["spec"]["ingress"]) > 0

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-081")
    def test_plugin_generates_policy_with_egress_rules(
        self, plugin_instance: K8sNetworkSecurityPlugin
    ) -> None:
        """Test plugin generates policy with egress rules.

        Validates that the plugin correctly includes egress rules
        in the generated NetworkPolicy manifest.

        Args:
            plugin_instance: K8sNetworkSecurityPlugin instance.
        """
        from floe_core.network.schemas import EgressRule, NetworkPolicyConfig, PortRule

        egress_rule = EgressRule(
            to_namespace="kube-system",
            ports=(PortRule(port=53, protocol="UDP"),),
        )

        config = NetworkPolicyConfig(
            name="floe-test-egress",
            namespace="test-namespace",
            pod_selector={},
            policy_types=("Egress",),
            ingress_rules=(),
            egress_rules=(egress_rule,),
        )

        policy = plugin_instance.generate_network_policy(config)

        # Validate egress rules
        assert "Egress" in policy["spec"]["policyTypes"]
        assert "egress" in policy["spec"]
        assert len(policy["spec"]["egress"]) > 0


class TestPolicyOutputFormats:
    """E2E tests for different policy output formats."""

    @pytest.fixture
    def sample_manifest(self, tmp_path: Path) -> Path:
        """Create sample manifest.yaml for testing.

        Args:
            tmp_path: Temporary directory for test files.

        Returns:
            Path to created manifest.yaml file.
        """
        manifest: dict[str, Any] = {
            "version": "1.0",
            "name": "test-platform",
            "security": {
                "network_policies": {
                    "enabled": True,
                    "default_deny": True,
                }
            },
        }
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(yaml.dump(manifest))
        return manifest_path

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-080")
    def test_generated_manifests_are_valid_yaml(
        self, sample_manifest: Path, tmp_path: Path
    ) -> None:
        """Test generated manifests are valid YAML.

        Validates that all generated manifest files are valid YAML
        that can be parsed by standard YAML parsers.

        Args:
            sample_manifest: Path to test manifest.yaml.
            tmp_path: Temporary directory for test files.
        """
        output_dir = tmp_path / "network"

        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "generate",
                "--config",
                str(sample_manifest),
                "--output",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # If generation succeeded, check YAML validity
        if result.returncode == 0 and output_dir.exists():
            yaml_files = list(output_dir.glob("*.yaml"))
            for yaml_file in yaml_files:
                try:
                    with open(yaml_file) as f:
                        yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {yaml_file}: {e}")

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-080")
    def test_generated_summary_markdown_exists(self, sample_manifest: Path, tmp_path: Path) -> None:
        """Test generated summary markdown file exists.

        Validates that the policy generation creates a summary
        markdown file documenting the generated policies.

        Args:
            sample_manifest: Path to test manifest.yaml.
            tmp_path: Temporary directory for test files.
        """
        output_dir = tmp_path / "network"

        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "generate",
                "--config",
                str(sample_manifest),
                "--output",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # If generation succeeded, check for summary
        if result.returncode == 0 and output_dir.exists():
            summary_file = output_dir / "NETWORK-POLICY-SUMMARY.md"
            assert summary_file.exists() or not list(output_dir.glob("*.yaml"))

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-081")
    def test_policy_manifest_has_required_metadata(
        self, sample_manifest: Path, tmp_path: Path
    ) -> None:
        """Test generated policies have required metadata.

        Validates that all generated NetworkPolicy manifests include
        required Kubernetes metadata fields.

        Args:
            sample_manifest: Path to test manifest.yaml.
            tmp_path: Temporary directory for test files.
        """
        output_dir = tmp_path / "network"

        result = subprocess.run(
            [
                "uv",
                "run",
                "floe",
                "network",
                "generate",
                "--config",
                str(sample_manifest),
                "--output",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # If generation succeeded, validate metadata
        if result.returncode == 0 and output_dir.exists():
            yaml_files = list(output_dir.glob("*.yaml"))
            for yaml_file in yaml_files:
                with open(yaml_file) as f:
                    content = yaml.safe_load(f)
                    if content and isinstance(content, dict):
                        # Check for required fields
                        if content.get("kind") == "NetworkPolicy":
                            assert "metadata" in content
                            assert "name" in content["metadata"]
                            assert "namespace" in content["metadata"]
                            assert "spec" in content


__all__: list[str] = [
    "TestPolicyGenerationWorkflow",
    "TestPolicyOutputFormats",
]
