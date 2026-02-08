"""Integration tests for Dagster cross-namespace access.

Tests the cross-namespace RoleBinding pattern where Dagster in floe-platform
can create and manage jobs in floe-jobs namespace.

Task: T039
User Story: US3 - Cross-Namespace Access
Requirements: FR-012, FR-023
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_rbac_k8s.plugin import K8sRBACPlugin as K8sRBACPluginType


class TestDagsterCrossNamespaceAccess:
    """Integration tests for Dagster cross-namespace access pattern."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-023")
    def test_dagster_can_access_jobs_namespace(self, plugin: K8sRBACPluginType) -> None:
        """Test Dagster SA in floe-platform can access floe-jobs."""
        from floe_core.schemas.rbac import (
            RoleBindingConfig,
            RoleBindingSubject,
            RoleConfig,
            RoleRule,
            ServiceAccountConfig,
        )

        # Create Dagster ServiceAccount in floe-platform
        dagster_sa = ServiceAccountConfig(
            name="floe-dagster",
            namespace="floe-platform",
        )
        sa_manifest = plugin.generate_service_account(dagster_sa)

        # Create Role in floe-jobs for job management
        job_creator_role = RoleConfig(
            name="floe-job-creator-role",
            namespace="floe-jobs",
            rules=[
                RoleRule(
                    api_groups=["batch"],
                    resources=["jobs"],
                    verbs=["get", "list", "create", "delete", "watch"],
                ),
                RoleRule(
                    api_groups=[""],
                    resources=["pods", "pods/log"],
                    verbs=["get", "list", "watch"],
                ),
            ],
        )
        role_manifest = plugin.generate_role(job_creator_role)

        # Create RoleBinding granting Dagster access to floe-jobs
        dagster_binding = RoleBindingConfig(
            name="floe-dagster-job-creator-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
            allowed_subject_namespaces=["floe-platform"],
        )
        binding_manifest = plugin.generate_role_binding(dagster_binding)

        # Verify SA is in floe-platform
        assert sa_manifest["metadata"]["namespace"] == "floe-platform"
        assert sa_manifest["metadata"]["name"] == "floe-dagster"

        # Verify Role is in floe-jobs
        assert role_manifest["metadata"]["namespace"] == "floe-jobs"
        assert role_manifest["metadata"]["name"] == "floe-job-creator-role"

        # Verify Binding is in floe-jobs, grants access to floe-platform SA
        assert binding_manifest["metadata"]["namespace"] == "floe-jobs"
        assert binding_manifest["subjects"][0]["namespace"] == "floe-platform"
        assert binding_manifest["subjects"][0]["name"] == "floe-dagster"
        assert binding_manifest["roleRef"]["name"] == "floe-job-creator-role"

    @pytest.mark.requirement("FR-023")
    def test_cross_namespace_access_denied_to_other_namespaces(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Test cross-namespace access is denied to non-allowed namespaces."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject
        from pydantic import ValidationError

        # Attempt to grant access from unauthorized namespace
        with pytest.raises(ValidationError, match="not in allowed namespaces"):
            RoleBindingConfig(
                name="floe-rogue-binding",
                namespace="floe-jobs",
                subjects=[
                    RoleBindingSubject(
                        name="floe-rogue-sa", namespace="floe-sales-domain"
                    )
                ],
                role_name="floe-job-creator-role",
                allowed_subject_namespaces=["floe-platform"],
            )

    @pytest.mark.requirement("FR-012")
    def test_cross_namespace_subjects_all_have_namespace(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Test all cross-namespace subjects include their namespace."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        binding = RoleBindingConfig(
            name="floe-multi-sa-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform"),
                RoleBindingSubject(name="floe-scheduler", namespace="floe-system"),
                RoleBindingSubject(name="floe-runner", namespace="floe-jobs"),
            ],
            role_name="floe-job-viewer-role",
            allowed_subject_namespaces=["floe-platform", "floe-system", "floe-jobs"],
        )

        manifest = plugin.generate_role_binding(binding)

        # All subjects have namespace
        for subject in manifest["subjects"]:
            assert "namespace" in subject
            assert subject["namespace"] in [
                "floe-platform",
                "floe-system",
                "floe-jobs",
            ]


class TestCrossNamespaceManifestGeneration:
    """Integration tests for cross-namespace manifest generation."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-023")
    def test_full_dagster_rbac_stack(self, plugin: K8sRBACPluginType) -> None:
        """Test generating complete RBAC stack for Dagster cross-namespace access."""
        from floe_core.schemas.rbac import (
            NamespaceConfig,
            RoleBindingConfig,
            RoleBindingSubject,
            RoleConfig,
            RoleRule,
            ServiceAccountConfig,
        )

        # 1. Create namespaces
        platform_ns = NamespaceConfig(
            name="floe-platform",
            layer="3",
            pss_enforce="baseline",
        )
        jobs_ns = NamespaceConfig(
            name="floe-jobs",
            layer="4",
            pss_enforce="restricted",
        )

        # 2. Create Dagster SA in platform namespace
        dagster_sa = ServiceAccountConfig(
            name="floe-dagster",
            namespace="floe-platform",
            automount_token=True,  # Dagster needs K8s API access
        )

        # 3. Create Role in jobs namespace
        job_role = RoleConfig(
            name="floe-job-creator-role",
            namespace="floe-jobs",
            rules=[
                RoleRule(
                    api_groups=["batch"],
                    resources=["jobs"],
                    verbs=["get", "list", "create", "delete", "watch"],
                ),
                RoleRule(
                    api_groups=[""],
                    resources=["pods", "pods/log"],
                    verbs=["get", "list", "watch"],
                ),
            ],
        )

        # 4. Create cross-namespace RoleBinding
        dagster_binding = RoleBindingConfig(
            name="floe-dagster-job-creator-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
            allowed_subject_namespaces=["floe-platform"],
        )

        # Generate all manifests
        platform_manifest = plugin.generate_namespace(platform_ns)
        jobs_manifest = plugin.generate_namespace(jobs_ns)
        sa_manifest = plugin.generate_service_account(dagster_sa)
        role_manifest = plugin.generate_role(job_role)
        binding_manifest = plugin.generate_role_binding(dagster_binding)

        # Verify namespaces
        assert platform_manifest["metadata"]["name"] == "floe-platform"
        assert (
            platform_manifest["metadata"]["labels"][
                "pod-security.kubernetes.io/enforce"
            ]
            == "baseline"
        )
        assert jobs_manifest["metadata"]["name"] == "floe-jobs"
        assert (
            jobs_manifest["metadata"]["labels"]["pod-security.kubernetes.io/enforce"]
            == "restricted"
        )

        # Verify SA
        assert sa_manifest["metadata"]["namespace"] == "floe-platform"
        assert sa_manifest["automountServiceAccountToken"] is True

        # Verify Role in jobs namespace
        assert role_manifest["metadata"]["namespace"] == "floe-jobs"

        # Verify cross-namespace binding
        assert binding_manifest["metadata"]["namespace"] == "floe-jobs"
        assert binding_manifest["subjects"][0]["namespace"] == "floe-platform"

    @pytest.mark.requirement("FR-023")
    def test_yaml_serializable_cross_namespace_stack(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Test all cross-namespace manifests are YAML serializable."""
        import yaml
        from floe_core.schemas.rbac import (
            RoleBindingConfig,
            RoleBindingSubject,
            RoleConfig,
            RoleRule,
            ServiceAccountConfig,
        )

        # Create cross-namespace resources
        dagster_sa = ServiceAccountConfig(
            name="floe-dagster",
            namespace="floe-platform",
        )
        job_role = RoleConfig(
            name="floe-job-viewer-role",
            namespace="floe-jobs",
            rules=[RoleRule(resources=["pods"], verbs=["get", "list"])],
        )
        binding = RoleBindingConfig(
            name="floe-dagster-viewer-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-viewer-role",
            allowed_subject_namespaces=["floe-platform"],
        )

        # Generate manifests
        sa_manifest = plugin.generate_service_account(dagster_sa)
        role_manifest = plugin.generate_role(job_role)
        binding_manifest = plugin.generate_role_binding(binding)

        # All should serialize to YAML without error
        sa_yaml = yaml.dump(sa_manifest, default_flow_style=False)
        role_yaml = yaml.dump(role_manifest, default_flow_style=False)
        binding_yaml = yaml.dump(binding_manifest, default_flow_style=False)

        # Verify key elements in YAML
        assert "namespace: floe-platform" in sa_yaml
        assert "namespace: floe-jobs" in role_yaml
        assert "namespace: floe-platform" in binding_yaml  # Subject namespace
        assert "namespace: floe-jobs" in binding_yaml  # Binding namespace

    @pytest.mark.requirement("FR-023")
    def test_yaml_roundtrip_preserves_cross_namespace(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Test YAML roundtrip preserves cross-namespace structure."""
        import yaml
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        binding = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform"),
                RoleBindingSubject(name="floe-runner", namespace="floe-jobs"),
            ],
            role_name="floe-test-role",
            allowed_subject_namespaces=["floe-platform", "floe-jobs"],
        )

        manifest = plugin.generate_role_binding(binding)
        yaml_str = yaml.dump(manifest)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        # Verify structure preserved
        assert restored["metadata"]["namespace"] == "floe-jobs"
        assert len(restored["subjects"]) == 2
        assert restored["subjects"][0]["namespace"] == "floe-platform"
        assert restored["subjects"][1]["namespace"] == "floe-jobs"
