"""Unit tests for RoleConfig.to_k8s_manifest() method.

Tests the K8s Role manifest generation including rules structure,
resource names, and label handling.

Task: T019
User Story: US1 - Service Account Generation
Requirements: FR-020, FR-021, FR-022, FR-024, FR-070
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.schemas.rbac import RoleConfig, RoleRule


class TestRoleManifestBasicStructure:
    """Unit tests for basic manifest structure."""

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_api_version(self) -> None:
        """Test manifest includes apiVersion: rbac.authorization.k8s.io/v1."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "apiVersion" in manifest
        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_kind(self) -> None:
        """Test manifest includes kind: Role."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "kind" in manifest
        assert manifest["kind"] == "Role"

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_metadata(self) -> None:
        """Test manifest includes metadata section."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "metadata" in manifest
        assert isinstance(manifest["metadata"], dict)

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_rules(self) -> None:
        """Test manifest includes rules section."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "rules" in manifest
        assert isinstance(manifest["rules"], list)


class TestRoleManifestMetadata:
    """Unit tests for manifest metadata section."""

    @pytest.mark.requirement("FR-020")
    def test_metadata_has_name(self) -> None:
        """Test metadata includes name matching config."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-reader-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["name"] == "floe-reader-role"

    @pytest.mark.requirement("FR-020")
    def test_metadata_has_namespace(self) -> None:
        """Test metadata includes namespace matching config."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="floe-jobs", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-021")
    def test_metadata_has_managed_by_label(self) -> None:
        """Test metadata labels include managed-by: floe."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert "app.kubernetes.io/managed-by" in labels
        assert labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-020")
    def test_metadata_includes_custom_labels(self) -> None:
        """Test metadata includes custom labels from config."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(
            name="floe-test-role",
            namespace="default",
            rules=[rule],
            labels={
                "app.kubernetes.io/managed-by": "floe",
                "custom-label": "custom-value",
            },
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["custom-label"] == "custom-value"


class TestRoleManifestRules:
    """Unit tests for manifest rules section."""

    @pytest.mark.requirement("FR-024")
    def test_rules_has_api_groups(self) -> None:
        """Test rules include apiGroups."""
        rule = RoleRule(api_groups=["batch"], resources=["jobs"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["rules"][0]["apiGroups"] == ["batch"]

    @pytest.mark.requirement("FR-024")
    def test_rules_has_resources(self) -> None:
        """Test rules include resources."""
        rule = RoleRule(resources=["pods", "services"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["rules"][0]["resources"] == ["pods", "services"]

    @pytest.mark.requirement("FR-024")
    def test_rules_has_verbs(self) -> None:
        """Test rules include verbs."""
        rule = RoleRule(resources=["pods"], verbs=["get", "list", "watch"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["rules"][0]["verbs"] == ["get", "list", "watch"]

    @pytest.mark.requirement("FR-024")
    def test_rules_default_api_groups(self) -> None:
        """Test rules default apiGroups to core API group."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["rules"][0]["apiGroups"] == [""]

    @pytest.mark.requirement("FR-024")
    def test_rules_include_resource_names_when_specified(self) -> None:
        """Test rules include resourceNames when specified."""
        rule = RoleRule(
            resources=["secrets"],
            verbs=["get"],
            resource_names=["db-password", "api-key"],
        )
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "resourceNames" in manifest["rules"][0]
        assert manifest["rules"][0]["resourceNames"] == ["db-password", "api-key"]

    @pytest.mark.requirement("FR-024")
    def test_rules_exclude_resource_names_when_not_specified(self) -> None:
        """Test rules exclude resourceNames when not specified."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "resourceNames" not in manifest["rules"][0]

    @pytest.mark.requirement("FR-024")
    def test_multiple_rules(self) -> None:
        """Test manifest with multiple rules."""
        rules = [
            RoleRule(resources=["pods"], verbs=["get", "list"]),
            RoleRule(api_groups=["batch"], resources=["jobs"], verbs=["get", "create"]),
            RoleRule(resources=["secrets"], verbs=["get"], resource_names=["my-secret"]),
        ]
        config = RoleConfig(name="floe-test-role", namespace="default", rules=rules)
        manifest = config.to_k8s_manifest()

        assert len(manifest["rules"]) == 3

        # First rule
        assert manifest["rules"][0]["resources"] == ["pods"]
        assert manifest["rules"][0]["verbs"] == ["get", "list"]

        # Second rule
        assert manifest["rules"][1]["apiGroups"] == ["batch"]
        assert manifest["rules"][1]["resources"] == ["jobs"]

        # Third rule
        assert manifest["rules"][2]["resourceNames"] == ["my-secret"]


class TestRoleManifestFieldTypes:
    """Unit tests for manifest field types."""

    @pytest.mark.requirement("FR-022")
    def test_api_version_is_string(self) -> None:
        """Test apiVersion is a string."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["apiVersion"], str)

    @pytest.mark.requirement("FR-022")
    def test_kind_is_string(self) -> None:
        """Test kind is a string."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["kind"], str)

    @pytest.mark.requirement("FR-024")
    def test_rules_is_list(self) -> None:
        """Test rules is a list."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["rules"], list)

    @pytest.mark.requirement("FR-024")
    def test_each_rule_is_dict(self) -> None:
        """Test each rule is a dictionary."""
        rules = [
            RoleRule(resources=["pods"], verbs=["get"]),
            RoleRule(resources=["secrets"], verbs=["get"]),
        ]
        config = RoleConfig(name="floe-test-role", namespace="default", rules=rules)
        manifest = config.to_k8s_manifest()

        for rule in manifest["rules"]:
            assert isinstance(rule, dict)


class TestRoleManifestVariousConfigs:
    """Unit tests for manifest generation with various configurations."""

    @pytest.mark.requirement("FR-020")
    def test_minimal_rule(self) -> None:
        """Test manifest generation with minimal rule."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-minimal-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"
        assert manifest["kind"] == "Role"
        assert manifest["metadata"]["name"] == "floe-minimal-role"
        assert len(manifest["rules"]) == 1

    @pytest.mark.requirement("FR-024")
    def test_complex_rules(self) -> None:
        """Test manifest generation with complex rules."""
        rules = [
            RoleRule(
                api_groups=[""],
                resources=["pods", "pods/log", "pods/exec"],
                verbs=["get", "list", "create"],
            ),
            RoleRule(
                api_groups=["batch"],
                resources=["jobs"],
                verbs=["get", "list", "create", "delete"],
            ),
            RoleRule(
                api_groups=[""],
                resources=["secrets"],
                verbs=["get"],
                resource_names=["db-creds", "api-key"],
            ),
        ]
        config = RoleConfig(name="floe-complex-role", namespace="floe-jobs", rules=rules)
        manifest = config.to_k8s_manifest()

        assert len(manifest["rules"]) == 3
        assert manifest["rules"][0]["resources"] == ["pods", "pods/log", "pods/exec"]
        assert manifest["rules"][2]["resourceNames"] == ["db-creds", "api-key"]


class TestRoleManifestYamlCompatibility:
    """Unit tests ensuring manifest is YAML-serializable."""

    @pytest.mark.requirement("FR-022")
    def test_manifest_can_be_yaml_serialized(self) -> None:
        """Test manifest can be serialized to YAML."""
        import yaml

        rule = RoleRule(resources=["pods"], verbs=["get", "list"])
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        # Should not raise
        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: rbac.authorization.k8s.io/v1" in yaml_str
        assert "kind: Role" in yaml_str

    @pytest.mark.requirement("FR-022")
    def test_manifest_yaml_roundtrip(self) -> None:
        """Test manifest survives YAML roundtrip."""
        import yaml

        rule = RoleRule(
            api_groups=["batch"],
            resources=["jobs"],
            verbs=["get"],
            resource_names=["my-job"],
        )
        config = RoleConfig(name="floe-test-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        yaml_str = yaml.dump(manifest)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        assert restored["apiVersion"] == manifest["apiVersion"]
        assert restored["kind"] == manifest["kind"]
        assert restored["rules"][0]["resourceNames"] == manifest["rules"][0]["resourceNames"]
