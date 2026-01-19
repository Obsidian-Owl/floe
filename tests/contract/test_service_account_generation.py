"""Contract tests for ServiceAccount generation schema stability.

These tests ensure the ServiceAccountConfig, RoleConfig, and RoleBindingConfig
models remain stable and backward-compatible. They validate the contract between
configuration and K8s manifest generation.

Task: T017
User Story: US1 - Service Account Generation
Requirements: FR-010, FR-011, FR-012, FR-013, FR-014
"""

from __future__ import annotations

import pytest
from floe_core.plugins.rbac import RBACPlugin
from floe_core.schemas.rbac import (
    RoleBindingConfig,
    RoleBindingSubject,
    RoleConfig,
    RoleRule,
    ServiceAccountConfig,
)
from pydantic import ValidationError


class TestServiceAccountConfigSchemaContract:
    """Contract tests for ServiceAccountConfig schema stability.

    These tests ensure the schema structure remains stable for K8s ServiceAccount
    generation.
    """

    @pytest.mark.requirement("FR-010")
    def test_required_fields_are_name_and_namespace(self) -> None:
        """Contract: name and namespace are required fields."""
        # Should succeed with name and namespace
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        assert config.name == "floe-test"
        assert config.namespace == "default"

        # Should fail without name
        with pytest.raises(ValidationError, match="name"):
            ServiceAccountConfig(namespace="default")  # type: ignore[call-arg]

        # Should fail without namespace
        with pytest.raises(ValidationError, match="namespace"):
            ServiceAccountConfig(name="floe-test")  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-010")
    def test_name_must_start_with_floe(self) -> None:
        """Contract: ServiceAccount names must follow floe-{purpose} pattern.

        This ensures all generated ServiceAccounts are identifiable as floe-managed.
        """
        # Valid floe-prefixed names
        valid_names = [
            "floe-a",
            "floe-job-runner",
            "floe-pipeline-executor",
            "floe-123",
            "floe-dbt-runner",
        ]
        for name in valid_names:
            config = ServiceAccountConfig(name=name, namespace="default")
            assert config.name == name

        # Invalid names (not floe-prefixed)
        invalid_names = [
            "job-runner",
            "my-service-account",
            "default",
            "admin",
            "FLOE-test",  # Uppercase
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                ServiceAccountConfig(name=name, namespace="default")

    @pytest.mark.requirement("FR-011")
    def test_automount_token_defaults_to_false(self) -> None:
        """Contract: automount_token defaults to False for security.

        This ensures least-privilege by default - pods must explicitly request
        the service account token if needed.
        """
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        assert config.automount_token is False

    @pytest.mark.requirement("FR-013")
    def test_labels_include_managed_by_floe(self) -> None:
        """Contract: Default labels include app.kubernetes.io/managed-by: floe.

        This ensures all generated resources are identifiable as floe-managed.
        """
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        assert "app.kubernetes.io/managed-by" in config.labels
        assert config.labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-010")
    def test_model_is_immutable(self) -> None:
        """Contract: ServiceAccountConfig is immutable (frozen=True).

        This ensures configurations can be safely used in caches and mappings.
        """
        config = ServiceAccountConfig(name="floe-test", namespace="default")

        with pytest.raises(ValidationError):
            config.name = "floe-other"  # type: ignore[misc]


class TestServiceAccountManifestContract:
    """Contract tests for ServiceAccountConfig.to_k8s_manifest() output stability."""

    @pytest.mark.requirement("FR-012")
    def test_manifest_apiversion_is_v1(self) -> None:
        """Contract: Generated manifest has apiVersion: v1."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()
        assert manifest["apiVersion"] == "v1"

    @pytest.mark.requirement("FR-012")
    def test_manifest_kind_is_serviceaccount(self) -> None:
        """Contract: Generated manifest has kind: ServiceAccount."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()
        assert manifest["kind"] == "ServiceAccount"

    @pytest.mark.requirement("FR-012")
    def test_manifest_metadata_structure(self) -> None:
        """Contract: Manifest metadata contains name, namespace, labels."""
        config = ServiceAccountConfig(
            name="floe-runner",
            namespace="floe-jobs",
            labels={"app.kubernetes.io/managed-by": "floe", "custom": "label"},
        )
        manifest = config.to_k8s_manifest()

        assert "metadata" in manifest
        assert manifest["metadata"]["name"] == "floe-runner"
        assert manifest["metadata"]["namespace"] == "floe-jobs"
        assert manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"
        assert manifest["metadata"]["labels"]["custom"] == "label"

    @pytest.mark.requirement("FR-014")
    def test_manifest_includes_automount_token(self) -> None:
        """Contract: Manifest includes automountServiceAccountToken field."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            automount_token=True,
        )
        manifest = config.to_k8s_manifest()

        assert "automountServiceAccountToken" in manifest
        assert manifest["automountServiceAccountToken"] is True

    @pytest.mark.requirement("FR-012")
    def test_manifest_includes_annotations(self) -> None:
        """Contract: Manifest includes annotations when provided."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            annotations={"description": "Test service account"},
        )
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["annotations"]["description"] == "Test service account"


class TestRoleConfigSchemaContract:
    """Contract tests for RoleConfig schema stability."""

    @pytest.mark.requirement("FR-020")
    def test_required_fields_are_name_namespace_rules(self) -> None:
        """Contract: name, namespace, and rules are required fields."""
        rule = RoleRule(resources=["pods"], verbs=["get"])

        # Should succeed with all required fields
        config = RoleConfig(name="floe-reader-role", namespace="default", rules=[rule])
        assert config.name == "floe-reader-role"

        # Should fail without rules
        with pytest.raises(ValidationError, match="rules"):
            RoleConfig(name="floe-reader-role", namespace="default", rules=[])

    @pytest.mark.requirement("FR-020")
    def test_name_must_follow_role_pattern(self) -> None:
        """Contract: Role names must follow floe-{purpose}-role pattern."""
        rule = RoleRule(resources=["pods"], verbs=["get"])

        # Valid names
        valid_names = ["floe-reader-role", "floe-job-runner-role", "floe-a-role"]
        for name in valid_names:
            config = RoleConfig(name=name, namespace="default", rules=[rule])
            assert config.name == name

        # Invalid names
        invalid_names = ["reader-role", "floe-reader", "FLOE-reader-role"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                RoleConfig(name=name, namespace="default", rules=[rule])

    @pytest.mark.requirement("FR-070")
    def test_wildcard_in_resources_is_forbidden(self) -> None:
        """Contract: Wildcard (*) in resources is forbidden (FR-070).

        This ensures least-privilege by requiring explicit resource specification.
        """
        with pytest.raises(ValidationError, match="Wildcard"):
            RoleRule(resources=["*"], verbs=["get"])

    @pytest.mark.requirement("FR-070")
    def test_wildcard_in_verbs_is_forbidden(self) -> None:
        """Contract: Wildcard (*) in verbs is forbidden (FR-070).

        This ensures least-privilege by requiring explicit verb specification.
        """
        with pytest.raises(ValidationError, match="Wildcard"):
            RoleRule(resources=["pods"], verbs=["*"])

    @pytest.mark.requirement("FR-070")
    def test_wildcard_in_api_groups_is_forbidden(self) -> None:
        """Contract: Wildcard (*) in apiGroups is forbidden (FR-070).

        This ensures least-privilege by requiring explicit API group specification.
        """
        with pytest.raises(ValidationError, match="Wildcard"):
            RoleRule(api_groups=["*"], resources=["pods"], verbs=["get"])


class TestRoleManifestContract:
    """Contract tests for RoleConfig.to_k8s_manifest() output stability."""

    @pytest.mark.requirement("FR-022")
    def test_manifest_apiversion_is_rbac_v1(self) -> None:
        """Contract: Generated manifest has apiVersion: rbac.authorization.k8s.io/v1."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-reader-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-022")
    def test_manifest_kind_is_role(self) -> None:
        """Contract: Generated manifest has kind: Role."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-reader-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["kind"] == "Role"

    @pytest.mark.requirement("FR-024")
    def test_manifest_rules_structure(self) -> None:
        """Contract: Manifest rules have correct K8s RBAC structure."""
        rule = RoleRule(
            api_groups=["batch"],
            resources=["jobs"],
            verbs=["get", "list", "create"],
            resource_names=["my-job"],
        )
        config = RoleConfig(name="floe-job-role", namespace="default", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "rules" in manifest
        assert len(manifest["rules"]) == 1

        k8s_rule = manifest["rules"][0]
        assert k8s_rule["apiGroups"] == ["batch"]
        assert k8s_rule["resources"] == ["jobs"]
        assert k8s_rule["verbs"] == ["get", "list", "create"]
        assert k8s_rule["resourceNames"] == ["my-job"]


class TestRoleBindingConfigSchemaContract:
    """Contract tests for RoleBindingConfig schema stability."""

    @pytest.mark.requirement("FR-022")
    def test_required_fields(self) -> None:
        """Contract: name, namespace, subjects, role_name are required fields."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")

        config = RoleBindingConfig(
            name="floe-runner-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-runner-role",
        )
        assert config.name == "floe-runner-binding"
        assert config.role_name == "floe-runner-role"

    @pytest.mark.requirement("FR-022")
    def test_name_must_follow_binding_pattern(self) -> None:
        """Contract: RoleBinding names must follow floe-{purpose}-binding pattern."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")

        # Valid names
        valid_names = ["floe-runner-binding", "floe-job-binding", "floe-a-binding"]
        for name in valid_names:
            config = RoleBindingConfig(
                name=name,
                namespace="default",
                subjects=[subject],
                role_name="floe-test-role",
            )
            assert config.name == name

        # Invalid names
        invalid_names = ["runner-binding", "floe-runner", "FLOE-binding"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                RoleBindingConfig(
                    name=name,
                    namespace="default",
                    subjects=[subject],
                    role_name="floe-test-role",
                )


class TestRoleBindingManifestContract:
    """Contract tests for RoleBindingConfig.to_k8s_manifest() output stability."""

    @pytest.mark.requirement("FR-022")
    def test_manifest_apiversion_is_rbac_v1(self) -> None:
        """Contract: Generated manifest has apiVersion: rbac.authorization.k8s.io/v1."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-runner-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-runner-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-022")
    def test_manifest_kind_is_rolebinding(self) -> None:
        """Contract: Generated manifest has kind: RoleBinding."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-runner-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-runner-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["kind"] == "RoleBinding"

    @pytest.mark.requirement("FR-022")
    def test_manifest_subjects_structure(self) -> None:
        """Contract: Manifest subjects have correct K8s RBAC structure."""
        subject = RoleBindingSubject(name="floe-runner", namespace="floe-jobs")
        config = RoleBindingConfig(
            name="floe-runner-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-runner-role",
        )
        manifest = config.to_k8s_manifest()

        assert "subjects" in manifest
        assert len(manifest["subjects"]) == 1

        k8s_subject = manifest["subjects"][0]
        assert k8s_subject["kind"] == "ServiceAccount"
        assert k8s_subject["name"] == "floe-runner"
        assert k8s_subject["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-022")
    def test_manifest_roleref_structure(self) -> None:
        """Contract: Manifest roleRef has correct K8s RBAC structure."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-runner-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-runner-role",
        )
        manifest = config.to_k8s_manifest()

        assert "roleRef" in manifest
        assert manifest["roleRef"]["kind"] == "Role"
        assert manifest["roleRef"]["name"] == "floe-runner-role"
        assert manifest["roleRef"]["apiGroup"] == "rbac.authorization.k8s.io"


class TestRBACPluginInterfaceContract:
    """Contract tests for RBACPlugin abstract interface stability."""

    @pytest.mark.requirement("FR-003")
    def test_rbac_plugin_has_generate_service_account_method(self) -> None:
        """Contract: RBACPlugin ABC defines generate_service_account method."""
        assert hasattr(RBACPlugin, "generate_service_account")

    @pytest.mark.requirement("FR-003")
    def test_rbac_plugin_has_generate_role_method(self) -> None:
        """Contract: RBACPlugin ABC defines generate_role method."""
        assert hasattr(RBACPlugin, "generate_role")

    @pytest.mark.requirement("FR-003")
    def test_rbac_plugin_has_generate_role_binding_method(self) -> None:
        """Contract: RBACPlugin ABC defines generate_role_binding method."""
        assert hasattr(RBACPlugin, "generate_role_binding")

    @pytest.mark.requirement("FR-003")
    def test_rbac_plugin_cannot_be_instantiated(self) -> None:
        """Contract: RBACPlugin is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            RBACPlugin()  # type: ignore[abstract]


class TestServiceAccountJsonSerialization:
    """Contract tests for JSON serialization/deserialization stability."""

    @pytest.mark.requirement("FR-010")
    def test_json_roundtrip_is_lossless(self) -> None:
        """Contract: JSON serialization/deserialization is lossless."""
        original = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            automount_token=True,
            labels={"app.kubernetes.io/managed-by": "floe", "custom": "value"},
            annotations={"description": "test"},
        )

        json_str = original.model_dump_json()
        restored = ServiceAccountConfig.model_validate_json(json_str)

        assert restored == original
        assert restored.name == original.name
        assert restored.namespace == original.namespace
        assert restored.automount_token == original.automount_token
        assert restored.labels == original.labels
        assert restored.annotations == original.annotations

    @pytest.mark.requirement("FR-020")
    def test_role_config_json_roundtrip(self) -> None:
        """Contract: RoleConfig survives JSON roundtrip."""
        rule = RoleRule(
            api_groups=["batch"],
            resources=["jobs"],
            verbs=["get", "list"],
            resource_names=["my-job"],
        )
        original = RoleConfig(
            name="floe-test-role",
            namespace="default",
            rules=[rule],
        )

        json_str = original.model_dump_json()
        restored = RoleConfig.model_validate_json(json_str)

        assert restored == original
        assert len(restored.rules) == 1
        assert restored.rules[0].resource_names == ["my-job"]

    @pytest.mark.requirement("FR-022")
    def test_role_binding_config_json_roundtrip(self) -> None:
        """Contract: RoleBindingConfig survives JSON roundtrip."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        original = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )

        json_str = original.model_dump_json()
        restored = RoleBindingConfig.model_validate_json(json_str)

        assert restored == original
        assert len(restored.subjects) == 1
        assert restored.subjects[0].name == "floe-runner"
