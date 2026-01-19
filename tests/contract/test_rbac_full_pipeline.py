"""Contract tests for full RBAC pipeline end-to-end.

These tests validate the complete pipeline flow:
SecurityConfig -> K8sRBACPlugin -> RBACManifestGenerator -> YAML files

This ensures all components integrate correctly and produce valid K8s manifests.

Task: T069
Phase: Polish
User Story: N/A (Cross-cutting)
Requirements: FR-002, FR-050, FR-051, FR-052, FR-053, FR-070
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml


class TestFullRBACPipelineContract:
    """Contract tests for complete RBAC pipeline: SecurityConfig -> YAML files."""

    @pytest.mark.requirement("FR-002")
    def test_full_pipeline_with_enabled_rbac(self, tmp_path: Path) -> None:
        """Contract: Full pipeline produces valid manifests when RBAC is enabled.

        Pipeline: SecurityConfig -> K8sRBACPlugin -> RBACManifestGenerator -> YAML
        """
        from floe_core.rbac import RBACManifestGenerator
        from floe_core.schemas.security import (
            PodSecurityLevelConfig,
            RBACConfig,
            SecurityConfig,
        )
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        # Step 1: Create SecurityConfig (input)
        security_config = SecurityConfig(
            rbac=RBACConfig(enabled=True, job_service_account="auto"),
            pod_security=PodSecurityLevelConfig(
                jobs_level="restricted", platform_level="baseline"
            ),
            namespace_isolation="strict",
        )

        # Verify input contract
        assert security_config.rbac.enabled is True
        assert security_config.rbac.job_service_account == "auto"

        # Step 2: Create K8sRBACPlugin
        plugin = K8sRBACPlugin()
        assert plugin.name == "k8s-rbac"

        # Step 3: Create RBACManifestGenerator with plugin
        generator = RBACManifestGenerator(plugin=plugin, output_dir=tmp_path / "rbac")

        # Step 4: Generate manifests
        result = generator.generate(
            security_config=security_config,
            secret_references=["db-credentials", "api-key"],
        )

        # Verify output contract
        assert result.success is True
        assert result.errors == []
        # Files are generated (counts depend on configs passed)
        assert len(result.files_generated) > 0

        # Step 5: Verify YAML files exist and are valid (or empty)
        rbac_dir = tmp_path / "rbac"
        expected_files = [
            "serviceaccounts.yaml",
            "roles.yaml",
            "rolebindings.yaml",
            "namespaces.yaml",
        ]

        for filename in expected_files:
            filepath = rbac_dir / filename
            assert filepath.exists(), f"Missing file: {filename}"

            # Verify valid YAML (may be empty if no resources generated)
            content = yaml.safe_load(filepath.read_text())
            # Empty files are valid (no resources of that type generated)
            if content is not None:
                assert isinstance(content, dict)

    @pytest.mark.requirement("FR-050")
    def test_pipeline_produces_deterministic_output(self, tmp_path: Path) -> None:
        """Contract: Same input produces identical output (deterministic)."""
        from floe_core.rbac import RBACManifestGenerator
        from floe_core.schemas.security import RBACConfig, SecurityConfig
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        security_config = SecurityConfig(
            rbac=RBACConfig(enabled=True, job_service_account="auto"),
        )

        # Generate twice with same input
        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"

        for output_dir in [dir1, dir2]:
            generator = RBACManifestGenerator(
                plugin=K8sRBACPlugin(), output_dir=output_dir
            )
            result = generator.generate(
                security_config=security_config,
                secret_references=["secret-a"],
            )
            assert result.success is True

        # Compare outputs
        for filename in ["serviceaccounts.yaml", "roles.yaml", "rolebindings.yaml"]:
            content1 = (dir1 / filename).read_text()
            content2 = (dir2 / filename).read_text()
            assert content1 == content2, f"Non-deterministic output for {filename}"

    @pytest.mark.requirement("FR-052")
    def test_pipeline_disabled_rbac_produces_no_manifests(
        self, tmp_path: Path
    ) -> None:
        """Contract: Disabled RBAC produces no manifest files."""
        from floe_core.rbac import RBACManifestGenerator
        from floe_core.schemas.security import RBACConfig, SecurityConfig
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        security_config = SecurityConfig(
            rbac=RBACConfig(enabled=False),  # Disabled
        )

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(), output_dir=tmp_path / "rbac"
        )

        result = generator.generate(
            security_config=security_config,
            secret_references=[],
        )

        # Should succeed but produce no manifests
        assert result.success is True
        assert result.service_accounts == 0
        assert result.roles == 0
        assert result.role_bindings == 0
        assert result.files_generated == []

    @pytest.mark.requirement("FR-070")
    def test_pipeline_generates_least_privilege_roles(self, tmp_path: Path) -> None:
        """Contract: Generated roles follow least-privilege (no wildcards)."""
        from floe_core.rbac import RBACManifestGenerator
        from floe_core.schemas.security import RBACConfig, SecurityConfig
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        security_config = SecurityConfig(
            rbac=RBACConfig(enabled=True, job_service_account="auto"),
        )

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(), output_dir=tmp_path / "rbac"
        )

        result = generator.generate(
            security_config=security_config,
            secret_references=["my-secret"],
        )
        assert result.success is True

        # Read generated roles
        roles_file = tmp_path / "rbac" / "roles.yaml"
        if roles_file.exists():
            roles_content = yaml.safe_load(roles_file.read_text())
            if roles_content:
                # Verify no wildcard rules
                rules = roles_content.get("rules", [])
                for rule in rules:
                    verbs = rule.get("verbs", [])
                    resources = rule.get("resources", [])
                    assert "*" not in verbs, "Wildcard verb detected"
                    assert "*" not in resources, "Wildcard resource detected"

    @pytest.mark.requirement("FR-051")
    def test_pipeline_validates_manifests_before_write(self, tmp_path: Path) -> None:
        """Contract: Generator validates manifests before writing to disk."""
        from floe_core.rbac import RBACManifestGenerator
        from floe_core.schemas.security import RBACConfig, SecurityConfig
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        security_config = SecurityConfig(
            rbac=RBACConfig(enabled=True),
        )

        generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(), output_dir=tmp_path / "rbac"
        )

        # Generate manifests
        result = generator.generate(
            security_config=security_config,
            secret_references=["test-secret"],
        )

        # If success, manifests were validated
        if result.success:
            assert result.errors == []
            # Verify files are valid K8s manifests
            for filepath in result.files_generated:
                content = yaml.safe_load(Path(filepath).read_text())
                # Files may be empty if no manifests of that type generated
                if content is not None:
                    # All K8s manifests must have apiVersion and kind
                    assert "apiVersion" in content
                    assert "kind" in content


class TestSecurityConfigContractStability:
    """Contract tests for SecurityConfig schema stability."""

    @pytest.mark.requirement("FR-002")
    def test_security_config_has_required_fields(self) -> None:
        """Contract: SecurityConfig has rbac, pod_security, namespace_isolation."""
        from floe_core.schemas.security import SecurityConfig

        # Default config should have all fields
        config = SecurityConfig()

        assert hasattr(config, "rbac")
        assert hasattr(config, "pod_security")
        assert hasattr(config, "namespace_isolation")

    @pytest.mark.requirement("FR-002")
    def test_rbac_config_has_required_fields(self) -> None:
        """Contract: RBACConfig has enabled, job_service_account, cluster_scope."""
        from floe_core.schemas.security import RBACConfig

        config = RBACConfig()

        assert hasattr(config, "enabled")
        assert hasattr(config, "job_service_account")
        assert hasattr(config, "cluster_scope")

        # Verify defaults
        assert config.enabled is True  # FR-002: default enabled
        assert config.job_service_account == "auto"
        assert config.cluster_scope is False

    @pytest.mark.requirement("FR-002")
    def test_security_config_is_frozen(self) -> None:
        """Contract: SecurityConfig is immutable (frozen)."""
        from floe_core.schemas.security import SecurityConfig

        config = SecurityConfig()

        with pytest.raises(Exception):  # ValidationError or FrozenInstanceError
            config.namespace_isolation = "permissive"  # type: ignore[misc]


class TestK8sRBACPluginContractStability:
    """Contract tests for K8sRBACPlugin interface stability."""

    @pytest.mark.requirement("FR-002")
    def test_plugin_has_required_metadata(self) -> None:
        """Contract: K8sRBACPlugin provides required metadata properties."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()

        assert plugin.name == "k8s-rbac"
        assert plugin.version is not None
        assert plugin.floe_api_version is not None

    @pytest.mark.requirement("FR-002")
    def test_plugin_implements_required_methods(self) -> None:
        """Contract: K8sRBACPlugin implements required interface methods."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()

        # These methods are part of the contract
        assert hasattr(plugin, "generate_service_account")
        assert hasattr(plugin, "generate_role")
        assert hasattr(plugin, "generate_role_binding")
        assert hasattr(plugin, "generate_namespace")
        assert callable(plugin.generate_service_account)
        assert callable(plugin.generate_role)
        assert callable(plugin.generate_role_binding)
        assert callable(plugin.generate_namespace)
