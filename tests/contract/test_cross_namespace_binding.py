"""Contract tests for cross-namespace RoleBinding.

Tests that RoleBindingConfig supports subjects from different namespaces
than the RoleBinding itself, enabling cross-namespace access patterns.

Task: T034
User Story: US3 - Cross-Namespace Access
Requirements: FR-012, FR-023
"""

from __future__ import annotations

from typing import Any

import pytest


class TestCrossNamespaceRoleBindingContract:
    """Contract tests for cross-namespace RoleBinding support."""

    @pytest.mark.requirement("FR-023")
    def test_rolebinding_supports_cross_namespace_subjects(self) -> None:
        """Verify RoleBindingConfig allows subjects from different namespaces."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        # RoleBinding in floe-jobs, subject in floe-platform
        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
        )

        manifest = config.to_k8s_manifest()

        # Binding namespace differs from subject namespace
        assert manifest["metadata"]["namespace"] == "floe-jobs"
        assert manifest["subjects"][0]["namespace"] == "floe-platform"

    @pytest.mark.requirement("FR-023")
    def test_rolebinding_multiple_cross_namespace_subjects(self) -> None:
        """Verify RoleBindingConfig allows multiple subjects from different namespaces."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-multi-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform"),
                RoleBindingSubject(name="floe-scheduler", namespace="floe-system"),
                RoleBindingSubject(name="floe-runner", namespace="floe-jobs"),
            ],
            role_name="floe-job-creator-role",
        )

        manifest = config.to_k8s_manifest()

        assert len(manifest["subjects"]) == 3
        assert manifest["subjects"][0]["namespace"] == "floe-platform"
        assert manifest["subjects"][1]["namespace"] == "floe-system"
        assert manifest["subjects"][2]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-012")
    def test_rolebinding_subject_has_service_account_kind(self) -> None:
        """Verify RoleBinding subjects are ServiceAccounts."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
        )

        manifest = config.to_k8s_manifest()

        assert manifest["subjects"][0]["kind"] == "ServiceAccount"

    @pytest.mark.requirement("FR-023")
    def test_rolebinding_role_ref_is_local(self) -> None:
        """Verify RoleBinding references a Role in the binding's namespace."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
        )

        manifest = config.to_k8s_manifest()

        # roleRef points to Role (not ClusterRole)
        assert manifest["roleRef"]["kind"] == "Role"
        assert manifest["roleRef"]["name"] == "floe-job-creator-role"
        assert manifest["roleRef"]["apiGroup"] == "rbac.authorization.k8s.io"


class TestCrossNamespaceAccessPattern:
    """Contract tests for the Dagster cross-namespace access pattern."""

    @pytest.mark.requirement("FR-023")
    def test_dagster_can_create_jobs_in_floe_jobs(self) -> None:
        """Verify Dagster pattern: platform SA can access jobs namespace."""
        from floe_core.schemas.rbac import (
            RoleBindingConfig,
            RoleBindingSubject,
            RoleConfig,
            RoleRule,
        )

        # Role in floe-jobs that allows job creation
        role_config = RoleConfig(
            name="floe-job-creator-role",
            namespace="floe-jobs",
            rules=[
                RoleRule(
                    api_groups=["batch"],
                    resources=["jobs"],
                    verbs=["get", "list", "create", "delete"],
                ),
                RoleRule(
                    api_groups=[""],
                    resources=["pods"],
                    verbs=["get", "list", "watch"],
                ),
            ],
        )

        # RoleBinding granting Dagster SA (in floe-platform) access
        binding_config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
        )

        role_manifest = role_config.to_k8s_manifest()
        binding_manifest = binding_config.to_k8s_manifest()

        # Role is in floe-jobs
        assert role_manifest["metadata"]["namespace"] == "floe-jobs"

        # Binding is in floe-jobs, grants access to SA in floe-platform
        assert binding_manifest["metadata"]["namespace"] == "floe-jobs"
        assert binding_manifest["subjects"][0]["namespace"] == "floe-platform"

        # Binding references the role
        assert binding_manifest["roleRef"]["name"] == "floe-job-creator-role"


class TestCrossNamespaceSchemaStability:
    """Contract tests for cross-namespace schema stability."""

    @pytest.mark.requirement("FR-012")
    def test_rolebinding_subject_schema_fields(self) -> None:
        """Verify RoleBindingSubject has required fields."""
        from floe_core.schemas.rbac import RoleBindingSubject

        schema = RoleBindingSubject.model_json_schema()
        props = schema.get("properties", {})

        assert "kind" in props
        assert "name" in props
        assert "namespace" in props

    @pytest.mark.requirement("FR-012")
    def test_rolebinding_subject_kind_default(self) -> None:
        """Verify RoleBindingSubject kind defaults to ServiceAccount."""
        from floe_core.schemas.rbac import RoleBindingSubject

        subject = RoleBindingSubject(name="floe-test", namespace="default")
        assert subject.kind == "ServiceAccount"

    @pytest.mark.requirement("FR-023")
    def test_rolebinding_config_subject_namespace_required(self) -> None:
        """Verify RoleBindingSubject requires namespace."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import RoleBindingSubject

        # Subject without namespace should fail
        with pytest.raises(ValidationError, match="namespace"):
            RoleBindingSubject(name="floe-test")  # type: ignore[call-arg]


class TestCrossNamespaceYAMLCompatibility:
    """Contract tests for YAML serialization of cross-namespace bindings."""

    @pytest.mark.requirement("FR-023")
    def test_cross_namespace_binding_yaml_serializable(self) -> None:
        """Verify cross-namespace RoleBinding can be serialized to YAML."""
        import yaml

        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
        )

        manifest = config.to_k8s_manifest()
        yaml_str = yaml.dump(manifest, default_flow_style=False)

        assert "apiVersion: rbac.authorization.k8s.io/v1" in yaml_str
        assert "kind: RoleBinding" in yaml_str
        assert "namespace: floe-jobs" in yaml_str
        assert "namespace: floe-platform" in yaml_str

    @pytest.mark.requirement("FR-023")
    def test_cross_namespace_binding_yaml_roundtrip(self) -> None:
        """Verify cross-namespace RoleBinding survives YAML roundtrip."""
        import yaml

        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
        )

        manifest = config.to_k8s_manifest()
        yaml_str = yaml.dump(manifest)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        assert restored["metadata"]["namespace"] == manifest["metadata"]["namespace"]
        assert restored["subjects"][0]["namespace"] == manifest["subjects"][0]["namespace"]
        assert restored["subjects"][0]["name"] == manifest["subjects"][0]["name"]
        assert restored["roleRef"]["name"] == manifest["roleRef"]["name"]
