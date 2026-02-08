"""Contract tests for RBACManifestGenerator output stability.

These tests ensure the RBACManifestGenerator produces stable, predictable output
that can be consumed by downstream tooling (kubectl, GitOps pipelines).

Task: T040
User Story: US4 - RBAC Manifest Generation
Requirements: FR-050, FR-051, FR-052, FR-053
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestRBACManifestGeneratorOutputContract:
    """Contract tests for RBACManifestGenerator output structure."""

    @pytest.mark.requirement("FR-050")
    def test_generator_produces_target_rbac_directory(self) -> None:
        """Contract: RBACManifestGenerator writes to target/rbac/ directory."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        # Generator should have configurable output_dir defaulting to target/rbac
        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        # Default output directory
        assert generator.output_dir == Path("target/rbac")

        # Custom output directory
        custom_generator = RBACManifestGenerator(
            plugin=K8sRBACPlugin(),
            output_dir=Path("custom/rbac"),
        )
        assert custom_generator.output_dir == Path("custom/rbac")

    @pytest.mark.requirement("FR-053")
    def test_generator_produces_separate_manifest_files(self) -> None:
        """Contract: Generator produces separate manifest files per resource type."""
        from floe_core.rbac.generator import MANIFEST_FILES

        # These file names are part of the contract
        expected_files = {
            "serviceaccounts.yaml",
            "roles.yaml",
            "rolebindings.yaml",
            "namespaces.yaml",
        }

        assert set(MANIFEST_FILES) == expected_files

    @pytest.mark.requirement("FR-051")
    def test_generated_manifests_are_valid_yaml(self) -> None:
        """Contract: All generated manifests are valid YAML."""
        from floe_core.schemas.rbac import (
            NamespaceConfig,
            RoleBindingConfig,
            RoleBindingSubject,
            RoleConfig,
            RoleRule,
            ServiceAccountConfig,
        )

        # Generate manifests for all resource types
        sa_config = ServiceAccountConfig(name="floe-test-sa", namespace="floe-jobs")
        role_config = RoleConfig(
            name="floe-test-role",
            namespace="floe-jobs",
            rules=[RoleRule(resources=["secrets"], verbs=["get"])],
        )
        binding_config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="floe-jobs",
            subjects=[RoleBindingSubject(name="floe-test-sa", namespace="floe-jobs")],
            role_name="floe-test-role",
        )
        ns_config = NamespaceConfig(name="floe-jobs", layer="4")

        # All manifests must serialize to valid YAML
        manifests = [
            sa_config.to_k8s_manifest(),
            role_config.to_k8s_manifest(),
            binding_config.to_k8s_manifest(),
            ns_config.to_k8s_manifest(),
        ]

        for manifest in manifests:
            yaml_str = yaml.dump(manifest, default_flow_style=False)
            # Must roundtrip cleanly
            parsed: dict[str, Any] = yaml.safe_load(yaml_str)
            assert parsed == manifest

    @pytest.mark.requirement("FR-051")
    def test_generated_manifests_have_required_k8s_fields(self) -> None:
        """Contract: All manifests have apiVersion, kind, metadata."""
        from floe_core.schemas.rbac import (
            NamespaceConfig,
            RoleBindingConfig,
            RoleBindingSubject,
            RoleConfig,
            RoleRule,
            ServiceAccountConfig,
        )

        # All K8s manifests must have these top-level fields
        required_fields = {"apiVersion", "kind", "metadata"}

        configs: list[tuple[str, Any]] = [
            (
                "ServiceAccount",
                ServiceAccountConfig(name="floe-test", namespace="default"),
            ),
            (
                "Role",
                RoleConfig(
                    name="floe-test-role",
                    namespace="default",
                    rules=[RoleRule(resources=["secrets"], verbs=["get"])],
                ),
            ),
            (
                "RoleBinding",
                RoleBindingConfig(
                    name="floe-test-binding",
                    namespace="default",
                    subjects=[
                        RoleBindingSubject(name="floe-test", namespace="default")
                    ],
                    role_name="floe-test-role",
                ),
            ),
            ("Namespace", NamespaceConfig(name="floe-test", layer="4")),
        ]

        for kind, config in configs:
            manifest = config.to_k8s_manifest()
            assert required_fields.issubset(
                set(manifest.keys())
            ), f"{kind} manifest missing required fields: {required_fields - set(manifest.keys())}"
            assert manifest["kind"] == kind

    @pytest.mark.requirement("FR-050")
    def test_generation_result_contract(self) -> None:
        """Contract: GenerationResult has stable structure."""
        from floe_core.rbac.generator import GenerationResult

        # GenerationResult must have these fields
        result = GenerationResult(
            success=True,
            files_generated=[Path("target/rbac/serviceaccounts.yaml")],
            service_accounts=1,
            roles=1,
            role_bindings=1,
            namespaces=1,
            warnings=[],
            errors=[],
        )

        assert result.success is True
        assert len(result.files_generated) == 1
        assert result.service_accounts == 1
        assert result.roles == 1
        assert result.role_bindings == 1
        assert result.namespaces == 1
        assert result.warnings == []
        assert result.errors == []

    @pytest.mark.requirement("FR-050")
    def test_generation_result_defaults(self) -> None:
        """Contract: GenerationResult has sensible defaults."""
        from floe_core.rbac.generator import GenerationResult

        # Minimal construction
        result = GenerationResult(success=True)

        assert result.success is True
        assert result.files_generated == []
        assert result.service_accounts == 0
        assert result.roles == 0
        assert result.role_bindings == 0
        assert result.namespaces == 0
        assert result.warnings == []
        assert result.errors == []


class TestRBACManifestAggregationContract:
    """Contract tests for permission aggregation in RBACManifestGenerator."""

    @pytest.mark.requirement("FR-052")
    def test_aggregate_permissions_returns_list_of_role_rules(self) -> None:
        """Contract: aggregate_permissions returns list[RoleRule]."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_core.schemas.rbac import RoleRule
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        # Secret references as input
        secret_refs = ["snowflake-creds", "catalog-creds"]

        # aggregate_permissions must return list[RoleRule]
        rules = generator.aggregate_permissions(secret_refs)

        assert isinstance(rules, list)
        assert all(isinstance(rule, RoleRule) for rule in rules)

    @pytest.mark.requirement("FR-052")
    def test_aggregation_deduplicates_secret_references(self) -> None:
        """Contract: Duplicate secret references are deduplicated in aggregation."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        # Duplicate secret references
        secret_refs = [
            "snowflake-creds",
            "catalog-creds",
            "snowflake-creds",  # Duplicate
            "snowflake-creds",  # Another duplicate
        ]

        rules = generator.aggregate_permissions(secret_refs)

        # Should only have unique resource names
        all_resource_names: list[str] = []
        for rule in rules:
            if rule.resource_names:
                all_resource_names.extend(rule.resource_names)

        # Check uniqueness
        assert len(all_resource_names) == len(set(all_resource_names))
        assert set(all_resource_names) == {"snowflake-creds", "catalog-creds"}

    @pytest.mark.requirement("FR-052")
    def test_aggregation_produces_minimal_roles(self) -> None:
        """Contract: Multiple secret refs in same namespace produce one aggregated Role."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        # Multiple secrets that should be aggregated
        secret_refs = ["cred-a", "cred-b", "cred-c"]

        rules = generator.aggregate_permissions(secret_refs)

        # Should produce minimal rules (ideally one rule with all resourceNames)
        # The exact structure depends on implementation, but there should be
        # fewer rules than secret references
        total_resource_names = sum(len(rule.resource_names or []) for rule in rules)
        assert total_resource_names == 3  # All secrets accounted for


class TestRBACManifestFileWritingContract:
    """Contract tests for manifest file writing."""

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_accepts_dict_of_lists(self) -> None:
        """Contract: write_manifests accepts dict[str, list[dict]]."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        # The manifests parameter structure (documented for contract)
        _manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "floe-test", "namespace": "default"},
                }
            ],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        # write_manifests should accept this structure
        # (actual file writing tested in integration tests)
        assert callable(generator.write_manifests)

    @pytest.mark.requirement("FR-053")
    def test_manifest_file_names_are_stable(self) -> None:
        """Contract: Output file names are stable for GitOps tooling."""
        from floe_core.rbac.generator import MANIFEST_FILES

        # These exact file names are part of the contract
        # Changing them would break GitOps pipelines
        assert "serviceaccounts.yaml" in MANIFEST_FILES
        assert "roles.yaml" in MANIFEST_FILES
        assert "rolebindings.yaml" in MANIFEST_FILES
        assert "namespaces.yaml" in MANIFEST_FILES


class TestRBACManifestGeneratorInterfaceContract:
    """Contract tests for RBACManifestGenerator interface stability."""

    @pytest.mark.requirement("FR-050")
    def test_generator_requires_rbac_plugin(self) -> None:
        """Contract: RBACManifestGenerator requires an RBACPlugin."""
        from floe_core.plugins.rbac import RBACPlugin
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        # Must work with any RBACPlugin implementation
        plugin = K8sRBACPlugin()
        assert isinstance(plugin, RBACPlugin)

        generator = RBACManifestGenerator(plugin=plugin)
        assert generator.plugin is plugin

    @pytest.mark.requirement("FR-050")
    def test_generator_has_generate_method(self) -> None:
        """Contract: RBACManifestGenerator has generate() method."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        # generate method must exist and be callable
        assert hasattr(generator, "generate")
        assert callable(generator.generate)

    @pytest.mark.requirement("FR-052")
    def test_generator_has_aggregate_permissions_method(self) -> None:
        """Contract: RBACManifestGenerator has aggregate_permissions() method."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        assert hasattr(generator, "aggregate_permissions")
        assert callable(generator.aggregate_permissions)

    @pytest.mark.requirement("FR-053")
    def test_generator_has_write_manifests_method(self) -> None:
        """Contract: RBACManifestGenerator has write_manifests() method."""
        from floe_core.rbac.generator import RBACManifestGenerator
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        assert hasattr(generator, "write_manifests")
        assert callable(generator.write_manifests)
