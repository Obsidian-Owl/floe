"""Unit tests for RBAC resource configuration schemas.

Tests the ServiceAccountConfig, RoleRule, RoleConfig, RoleBindingSubject,
RoleBindingConfig, NamespaceConfig, and PodSecurityConfig models.

Task: T015
Requirements: FR-010 to FR-014, FR-020 to FR-024, FR-030 to FR-034,
              FR-040 to FR-044, FR-070 (No wildcards)
Contract: specs/7b-k8s-rbac/data-model.md
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.schemas.rbac import (
    NamespaceConfig,
    PodSecurityConfig,
    RoleBindingConfig,
    RoleBindingSubject,
    RoleConfig,
    RoleRule,
    ServiceAccountConfig,
)


# =============================================================================
# ServiceAccountConfig Tests
# =============================================================================


class TestServiceAccountConfig:
    """Unit tests for ServiceAccountConfig model."""

    @pytest.mark.requirement("FR-010")
    def test_create_with_required_fields(self) -> None:
        """Test ServiceAccountConfig with only required fields."""
        config = ServiceAccountConfig(
            name="floe-job-runner",
            namespace="floe-jobs",
        )

        assert config.name == "floe-job-runner"
        assert config.namespace == "floe-jobs"
        assert config.automount_token is False
        assert "app.kubernetes.io/managed-by" in config.labels
        assert config.labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-010")
    def test_create_with_all_fields(self) -> None:
        """Test ServiceAccountConfig with all fields specified."""
        config = ServiceAccountConfig(
            name="floe-pipeline",
            namespace="floe-platform",
            automount_token=True,
            labels={"app.kubernetes.io/managed-by": "floe", "custom": "value"},
            annotations={"description": "test sa"},
        )

        assert config.name == "floe-pipeline"
        assert config.automount_token is True
        assert config.labels["custom"] == "value"
        assert config.annotations["description"] == "test sa"

    @pytest.mark.requirement("FR-010")
    def test_name_must_start_with_floe(self) -> None:
        """Test name must follow floe-{purpose} pattern."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            ServiceAccountConfig(name="invalid-name", namespace="ns")

    @pytest.mark.requirement("FR-010")
    def test_name_valid_patterns(self) -> None:
        """Test various valid floe-prefixed names."""
        valid_names = [
            "floe-a",
            "floe-job-runner",
            "floe-pipeline-executor",
            "floe-123",
            "floe-a-b-c",
        ]
        for name in valid_names:
            config = ServiceAccountConfig(name=name, namespace="ns")
            assert config.name == name

    @pytest.mark.requirement("FR-010")
    def test_name_invalid_uppercase(self) -> None:
        """Test name rejects uppercase characters."""
        with pytest.raises(ValidationError):
            ServiceAccountConfig(name="floe-InvalidName", namespace="ns")

    @pytest.mark.requirement("FR-010")
    def test_namespace_valid_patterns(self) -> None:
        """Test various valid namespace names."""
        valid_namespaces = [
            "a",
            "ns",
            "default",
            "floe-jobs",
            "my-namespace-123",
        ]
        for ns in valid_namespaces:
            config = ServiceAccountConfig(name="floe-test", namespace=ns)
            assert config.namespace == ns

    @pytest.mark.requirement("FR-010")
    def test_namespace_invalid_patterns(self) -> None:
        """Test namespace rejects invalid patterns."""
        invalid_namespaces = [
            "-invalid",  # starts with hyphen
            "invalid-",  # ends with hyphen
        ]
        for ns in invalid_namespaces:
            with pytest.raises(ValidationError):
                ServiceAccountConfig(name="floe-test", namespace=ns)

    @pytest.mark.requirement("FR-011")
    def test_automount_token_default_false(self) -> None:
        """Test automount_token defaults to False for security."""
        config = ServiceAccountConfig(name="floe-test", namespace="ns")
        assert config.automount_token is False

    @pytest.mark.requirement("FR-010")
    def test_model_is_frozen(self) -> None:
        """Test ServiceAccountConfig is immutable."""
        config = ServiceAccountConfig(name="floe-test", namespace="ns")

        with pytest.raises(ValidationError):
            config.name = "floe-other"  # type: ignore[misc]

    @pytest.mark.requirement("FR-010")
    def test_extra_fields_forbidden(self) -> None:
        """Test ServiceAccountConfig rejects extra fields."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ServiceAccountConfig(
                name="floe-test",
                namespace="ns",
                extra="field",  # type: ignore[call-arg]
            )


class TestServiceAccountConfigManifest:
    """Unit tests for ServiceAccountConfig.to_k8s_manifest()."""

    @pytest.mark.requirement("FR-012")
    def test_manifest_has_correct_api_version(self) -> None:
        """Test manifest includes apiVersion: v1."""
        config = ServiceAccountConfig(name="floe-test", namespace="ns")
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "v1"

    @pytest.mark.requirement("FR-012")
    def test_manifest_has_correct_kind(self) -> None:
        """Test manifest includes kind: ServiceAccount."""
        config = ServiceAccountConfig(name="floe-test", namespace="ns")
        manifest = config.to_k8s_manifest()

        assert manifest["kind"] == "ServiceAccount"

    @pytest.mark.requirement("FR-012")
    def test_manifest_has_metadata(self) -> None:
        """Test manifest includes metadata with name and namespace."""
        config = ServiceAccountConfig(name="floe-runner", namespace="floe-jobs")
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["name"] == "floe-runner"
        assert manifest["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-013")
    def test_manifest_has_managed_by_label(self) -> None:
        """Test manifest includes managed-by label."""
        config = ServiceAccountConfig(name="floe-test", namespace="ns")
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-014")
    def test_manifest_has_automount_token(self) -> None:
        """Test manifest includes automountServiceAccountToken."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="ns",
            automount_token=True,
        )
        manifest = config.to_k8s_manifest()

        assert manifest["automountServiceAccountToken"] is True

    @pytest.mark.requirement("FR-012")
    def test_manifest_includes_annotations(self) -> None:
        """Test manifest includes annotations when provided."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="ns",
            annotations={"key": "value"},
        )
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["annotations"]["key"] == "value"


# =============================================================================
# RoleRule Tests
# =============================================================================


class TestRoleRule:
    """Unit tests for RoleRule model."""

    @pytest.mark.requirement("FR-020")
    def test_create_with_required_fields(self) -> None:
        """Test RoleRule with required fields only."""
        rule = RoleRule(
            resources=["pods"],
            verbs=["get", "list"],
        )

        assert rule.resources == ["pods"]
        assert rule.verbs == ["get", "list"]
        assert rule.api_groups == [""]  # default
        assert rule.resource_names is None

    @pytest.mark.requirement("FR-020")
    def test_create_with_all_fields(self) -> None:
        """Test RoleRule with all fields specified."""
        rule = RoleRule(
            api_groups=["batch"],
            resources=["jobs"],
            verbs=["get", "create", "delete"],
            resource_names=["my-job"],
        )

        assert rule.api_groups == ["batch"]
        assert rule.resources == ["jobs"]
        assert rule.verbs == ["get", "create", "delete"]
        assert rule.resource_names == ["my-job"]

    @pytest.mark.requirement("FR-070")
    def test_wildcard_in_api_groups_forbidden(self) -> None:
        """Test wildcard (*) in api_groups is rejected (FR-070)."""
        with pytest.raises(ValidationError, match="Wildcard permissions"):
            RoleRule(
                api_groups=["*"],
                resources=["pods"],
                verbs=["get"],
            )

    @pytest.mark.requirement("FR-070")
    def test_wildcard_in_resources_forbidden(self) -> None:
        """Test wildcard (*) in resources is rejected (FR-070)."""
        with pytest.raises(ValidationError, match="Wildcard permissions"):
            RoleRule(
                resources=["*"],
                verbs=["get"],
            )

    @pytest.mark.requirement("FR-070")
    def test_wildcard_in_verbs_forbidden(self) -> None:
        """Test wildcard (*) in verbs is rejected (FR-070)."""
        with pytest.raises(ValidationError, match="Wildcard permissions"):
            RoleRule(
                resources=["pods"],
                verbs=["*"],
            )

    @pytest.mark.requirement("FR-070")
    def test_wildcard_mixed_with_other_values_forbidden(self) -> None:
        """Test wildcard mixed with other values is rejected."""
        with pytest.raises(ValidationError, match="Wildcard permissions"):
            RoleRule(
                resources=["pods", "*"],
                verbs=["get"],
            )

    @pytest.mark.requirement("FR-020")
    def test_resources_must_not_be_empty(self) -> None:
        """Test resources list must have at least one item."""
        with pytest.raises(ValidationError, match="at least 1"):
            RoleRule(resources=[], verbs=["get"])

    @pytest.mark.requirement("FR-020")
    def test_verbs_must_not_be_empty(self) -> None:
        """Test verbs list must have at least one item."""
        with pytest.raises(ValidationError, match="at least 1"):
            RoleRule(resources=["pods"], verbs=[])

    @pytest.mark.requirement("FR-020")
    def test_model_is_frozen(self) -> None:
        """Test RoleRule is immutable."""
        rule = RoleRule(resources=["pods"], verbs=["get"])

        with pytest.raises(ValidationError):
            rule.resources = ["secrets"]  # type: ignore[misc]


# =============================================================================
# RoleConfig Tests
# =============================================================================


class TestRoleConfig:
    """Unit tests for RoleConfig model."""

    @pytest.mark.requirement("FR-020")
    def test_create_with_required_fields(self) -> None:
        """Test RoleConfig with required fields."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(
            name="floe-reader-role",
            namespace="floe-jobs",
            rules=[rule],
        )

        assert config.name == "floe-reader-role"
        assert config.namespace == "floe-jobs"
        assert len(config.rules) == 1

    @pytest.mark.requirement("FR-020")
    def test_name_must_follow_pattern(self) -> None:
        """Test name must follow floe-{purpose}-role pattern."""
        rule = RoleRule(resources=["pods"], verbs=["get"])

        with pytest.raises(ValidationError, match="String should match pattern"):
            RoleConfig(name="invalid-role", namespace="ns", rules=[rule])

    @pytest.mark.requirement("FR-020")
    def test_name_valid_patterns(self) -> None:
        """Test various valid role names."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        valid_names = [
            "floe-a-role",
            "floe-reader-role",
            "floe-job-runner-role",
            "floe-123-role",
        ]
        for name in valid_names:
            config = RoleConfig(name=name, namespace="ns", rules=[rule])
            assert config.name == name

    @pytest.mark.requirement("FR-020")
    def test_rules_must_not_be_empty(self) -> None:
        """Test rules list must have at least one item."""
        with pytest.raises(ValidationError, match="at least 1"):
            RoleConfig(name="floe-test-role", namespace="ns", rules=[])

    @pytest.mark.requirement("FR-021")
    def test_default_labels_include_managed_by(self) -> None:
        """Test default labels include managed-by."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="ns", rules=[rule])

        assert config.labels["app.kubernetes.io/managed-by"] == "floe"


class TestRoleConfigManifest:
    """Unit tests for RoleConfig.to_k8s_manifest()."""

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_correct_api_version(self) -> None:
        """Test manifest includes correct apiVersion."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="ns", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_correct_kind(self) -> None:
        """Test manifest includes kind: Role."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="ns", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["kind"] == "Role"

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_rules(self) -> None:
        """Test manifest includes rules array."""
        rule = RoleRule(
            api_groups=[""],
            resources=["pods"],
            verbs=["get", "list"],
        )
        config = RoleConfig(name="floe-test-role", namespace="ns", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "rules" in manifest
        assert len(manifest["rules"]) == 1
        assert manifest["rules"][0]["apiGroups"] == [""]
        assert manifest["rules"][0]["resources"] == ["pods"]
        assert manifest["rules"][0]["verbs"] == ["get", "list"]

    @pytest.mark.requirement("FR-023")
    def test_manifest_includes_resource_names(self) -> None:
        """Test manifest includes resourceNames when specified."""
        rule = RoleRule(
            resources=["secrets"],
            verbs=["get"],
            resource_names=["my-secret"],
        )
        config = RoleConfig(name="floe-test-role", namespace="ns", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert manifest["rules"][0]["resourceNames"] == ["my-secret"]

    @pytest.mark.requirement("FR-022")
    def test_manifest_excludes_resource_names_when_none(self) -> None:
        """Test manifest excludes resourceNames when not specified."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="ns", rules=[rule])
        manifest = config.to_k8s_manifest()

        assert "resourceNames" not in manifest["rules"][0]


# =============================================================================
# RoleBindingSubject Tests
# =============================================================================


class TestRoleBindingSubject:
    """Unit tests for RoleBindingSubject model."""

    @pytest.mark.requirement("FR-030")
    def test_create_with_required_fields(self) -> None:
        """Test RoleBindingSubject with required fields."""
        subject = RoleBindingSubject(
            name="floe-runner",
            namespace="floe-jobs",
        )

        assert subject.kind == "ServiceAccount"
        assert subject.name == "floe-runner"
        assert subject.namespace == "floe-jobs"

    @pytest.mark.requirement("FR-030")
    def test_kind_defaults_to_service_account(self) -> None:
        """Test kind defaults to ServiceAccount."""
        subject = RoleBindingSubject(name="sa", namespace="ns")
        assert subject.kind == "ServiceAccount"

    @pytest.mark.requirement("FR-030")
    def test_model_is_frozen(self) -> None:
        """Test RoleBindingSubject is immutable."""
        subject = RoleBindingSubject(name="sa", namespace="ns")

        with pytest.raises(ValidationError):
            subject.name = "other"  # type: ignore[misc]


# =============================================================================
# RoleBindingConfig Tests
# =============================================================================


class TestRoleBindingConfig:
    """Unit tests for RoleBindingConfig model."""

    @pytest.mark.requirement("FR-030")
    def test_create_with_required_fields(self) -> None:
        """Test RoleBindingConfig with required fields."""
        subject = RoleBindingSubject(name="floe-runner", namespace="floe-jobs")
        config = RoleBindingConfig(
            name="floe-runner-binding",
            namespace="floe-jobs",
            subjects=[subject],
            role_name="floe-runner-role",
        )

        assert config.name == "floe-runner-binding"
        assert config.namespace == "floe-jobs"
        assert len(config.subjects) == 1
        assert config.role_name == "floe-runner-role"

    @pytest.mark.requirement("FR-030")
    def test_name_must_follow_pattern(self) -> None:
        """Test name must follow floe-{purpose}-binding pattern."""
        subject = RoleBindingSubject(name="sa", namespace="ns")

        with pytest.raises(ValidationError, match="String should match pattern"):
            RoleBindingConfig(
                name="invalid-binding",
                namespace="ns",
                subjects=[subject],
                role_name="role",
            )

    @pytest.mark.requirement("FR-030")
    def test_name_valid_patterns(self) -> None:
        """Test various valid binding names."""
        subject = RoleBindingSubject(name="sa", namespace="ns")
        valid_names = [
            "floe-a-binding",
            "floe-reader-binding",
            "floe-job-runner-binding",
        ]
        for name in valid_names:
            config = RoleBindingConfig(
                name=name,
                namespace="ns",
                subjects=[subject],
                role_name="role",
            )
            assert config.name == name

    @pytest.mark.requirement("FR-030")
    def test_subjects_must_not_be_empty(self) -> None:
        """Test subjects list must have at least one item."""
        with pytest.raises(ValidationError, match="at least 1"):
            RoleBindingConfig(
                name="floe-test-binding",
                namespace="ns",
                subjects=[],
                role_name="role",
            )


class TestRoleBindingConfigManifest:
    """Unit tests for RoleBindingConfig.to_k8s_manifest()."""

    @pytest.mark.requirement("FR-032")
    def test_manifest_has_correct_api_version(self) -> None:
        """Test manifest includes correct apiVersion."""
        subject = RoleBindingSubject(name="sa", namespace="ns")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="ns",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-032")
    def test_manifest_has_correct_kind(self) -> None:
        """Test manifest includes kind: RoleBinding."""
        subject = RoleBindingSubject(name="sa", namespace="ns")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="ns",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["kind"] == "RoleBinding"

    @pytest.mark.requirement("FR-032")
    def test_manifest_has_subjects(self) -> None:
        """Test manifest includes subjects array."""
        subject = RoleBindingSubject(name="floe-runner", namespace="floe-jobs")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="ns",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert "subjects" in manifest
        assert len(manifest["subjects"]) == 1
        assert manifest["subjects"][0]["kind"] == "ServiceAccount"
        assert manifest["subjects"][0]["name"] == "floe-runner"
        assert manifest["subjects"][0]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-033")
    def test_manifest_has_role_ref(self) -> None:
        """Test manifest includes roleRef."""
        subject = RoleBindingSubject(name="sa", namespace="ns")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="ns",
            subjects=[subject],
            role_name="floe-reader-role",
        )
        manifest = config.to_k8s_manifest()

        assert "roleRef" in manifest
        assert manifest["roleRef"]["kind"] == "Role"
        assert manifest["roleRef"]["name"] == "floe-reader-role"
        assert manifest["roleRef"]["apiGroup"] == "rbac.authorization.k8s.io"


# =============================================================================
# NamespaceConfig Tests
# =============================================================================


class TestNamespaceConfig:
    """Unit tests for NamespaceConfig model."""

    @pytest.mark.requirement("FR-040")
    def test_create_with_required_fields(self) -> None:
        """Test NamespaceConfig with required fields."""
        config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
        )

        assert config.name == "floe-jobs"
        assert config.layer == "4"
        assert config.pss_enforce == "restricted"
        assert config.pss_audit == "restricted"
        assert config.pss_warn == "restricted"

    @pytest.mark.requirement("FR-040")
    def test_create_with_all_fields(self) -> None:
        """Test NamespaceConfig with all fields specified."""
        config = NamespaceConfig(
            name="floe-platform",
            layer="3",
            pss_enforce="baseline",
            pss_audit="baseline",
            pss_warn="baseline",
            labels={"custom": "label"},
        )

        assert config.name == "floe-platform"
        assert config.layer == "3"
        assert config.pss_enforce == "baseline"
        assert config.labels["custom"] == "label"

    @pytest.mark.requirement("FR-040")
    def test_name_must_follow_pattern(self) -> None:
        """Test name must follow floe-{purpose} pattern."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            NamespaceConfig(name="invalid-ns", layer="4")

    @pytest.mark.requirement("FR-040")
    def test_layer_must_be_3_or_4(self) -> None:
        """Test layer must be '3' or '4'."""
        with pytest.raises(ValidationError, match="Input should be '3' or '4'"):
            NamespaceConfig(name="floe-test", layer="1")  # type: ignore[arg-type]

    @pytest.mark.requirement("FR-041")
    def test_pss_levels_valid_values(self) -> None:
        """Test PSS levels accept valid values."""
        for level in ["privileged", "baseline", "restricted"]:
            config = NamespaceConfig(
                name="floe-test",
                layer="4",
                pss_enforce=level,  # type: ignore[arg-type]
            )
            assert config.pss_enforce == level

    @pytest.mark.requirement("FR-041")
    def test_pss_level_invalid_value(self) -> None:
        """Test PSS levels reject invalid values."""
        with pytest.raises(ValidationError):
            NamespaceConfig(
                name="floe-test",
                layer="4",
                pss_enforce="invalid",  # type: ignore[arg-type]
            )


class TestNamespaceConfigManifest:
    """Unit tests for NamespaceConfig.to_k8s_manifest()."""

    @pytest.mark.requirement("FR-042")
    def test_manifest_has_correct_api_version(self) -> None:
        """Test manifest includes apiVersion: v1."""
        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "v1"

    @pytest.mark.requirement("FR-042")
    def test_manifest_has_correct_kind(self) -> None:
        """Test manifest includes kind: Namespace."""
        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        assert manifest["kind"] == "Namespace"

    @pytest.mark.requirement("FR-043")
    def test_manifest_has_pss_enforce_label(self) -> None:
        """Test manifest includes PSS enforce label."""
        config = NamespaceConfig(name="floe-jobs", layer="4", pss_enforce="restricted")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

    @pytest.mark.requirement("FR-043")
    def test_manifest_has_pss_audit_label(self) -> None:
        """Test manifest includes PSS audit label."""
        config = NamespaceConfig(name="floe-jobs", layer="4", pss_audit="baseline")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/audit"] == "baseline"

    @pytest.mark.requirement("FR-043")
    def test_manifest_has_pss_warn_label(self) -> None:
        """Test manifest includes PSS warn label."""
        config = NamespaceConfig(name="floe-jobs", layer="4", pss_warn="privileged")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/warn"] == "privileged"

    @pytest.mark.requirement("FR-044")
    def test_manifest_has_layer_label(self) -> None:
        """Test manifest includes floe.dev/layer label."""
        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["floe.dev/layer"] == "4"

    @pytest.mark.requirement("FR-042")
    def test_manifest_has_managed_by_label(self) -> None:
        """Test manifest includes managed-by label."""
        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-042")
    def test_manifest_includes_custom_labels(self) -> None:
        """Test manifest includes custom labels."""
        config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
            labels={"custom": "value"},
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["custom"] == "value"


# =============================================================================
# PodSecurityConfig Tests
# =============================================================================


class TestPodSecurityConfig:
    """Unit tests for PodSecurityConfig model."""

    @pytest.mark.requirement("FR-050")
    def test_create_with_defaults(self) -> None:
        """Test PodSecurityConfig uses secure defaults."""
        config = PodSecurityConfig()

        assert config.run_as_non_root is True
        assert config.run_as_user == 1000
        assert config.run_as_group == 1000
        assert config.fs_group == 1000
        assert config.read_only_root_filesystem is True
        assert config.allow_privilege_escalation is False
        assert config.seccomp_profile_type == "RuntimeDefault"

    @pytest.mark.requirement("FR-050")
    def test_create_with_custom_values(self) -> None:
        """Test PodSecurityConfig with custom values."""
        config = PodSecurityConfig(
            run_as_user=2000,
            run_as_group=2000,
            fs_group=3000,
            seccomp_profile_type="Localhost",
        )

        assert config.run_as_user == 2000
        assert config.run_as_group == 2000
        assert config.fs_group == 3000
        assert config.seccomp_profile_type == "Localhost"

    @pytest.mark.requirement("FR-050")
    def test_uid_gid_must_be_positive(self) -> None:
        """Test UID/GID must be >= 1."""
        with pytest.raises(ValidationError):
            PodSecurityConfig(run_as_user=0)

    @pytest.mark.requirement("FR-050")
    def test_seccomp_profile_valid_values(self) -> None:
        """Test seccomp profile accepts valid values."""
        for profile in ["RuntimeDefault", "Localhost", "Unconfined"]:
            config = PodSecurityConfig(seccomp_profile_type=profile)  # type: ignore[arg-type]
            assert config.seccomp_profile_type == profile

    @pytest.mark.requirement("FR-050")
    def test_seccomp_profile_invalid_value(self) -> None:
        """Test seccomp profile rejects invalid values."""
        with pytest.raises(ValidationError):
            PodSecurityConfig(seccomp_profile_type="Invalid")  # type: ignore[arg-type]


class TestPodSecurityConfigContext:
    """Unit tests for PodSecurityConfig context generation methods."""

    @pytest.mark.requirement("FR-051")
    def test_pod_security_context_has_run_as_non_root(self) -> None:
        """Test pod context includes runAsNonRoot."""
        config = PodSecurityConfig()
        context = config.to_pod_security_context()

        assert context["runAsNonRoot"] is True

    @pytest.mark.requirement("FR-051")
    def test_pod_security_context_has_run_as_user(self) -> None:
        """Test pod context includes runAsUser."""
        config = PodSecurityConfig(run_as_user=1000)
        context = config.to_pod_security_context()

        assert context["runAsUser"] == 1000

    @pytest.mark.requirement("FR-051")
    def test_pod_security_context_has_run_as_group(self) -> None:
        """Test pod context includes runAsGroup."""
        config = PodSecurityConfig(run_as_group=1000)
        context = config.to_pod_security_context()

        assert context["runAsGroup"] == 1000

    @pytest.mark.requirement("FR-051")
    def test_pod_security_context_has_fs_group(self) -> None:
        """Test pod context includes fsGroup."""
        config = PodSecurityConfig(fs_group=1000)
        context = config.to_pod_security_context()

        assert context["fsGroup"] == 1000

    @pytest.mark.requirement("FR-051")
    def test_pod_security_context_has_seccomp_profile(self) -> None:
        """Test pod context includes seccompProfile."""
        config = PodSecurityConfig(seccomp_profile_type="RuntimeDefault")
        context = config.to_pod_security_context()

        assert context["seccompProfile"]["type"] == "RuntimeDefault"

    @pytest.mark.requirement("FR-052")
    def test_container_security_context_has_allow_privilege_escalation(self) -> None:
        """Test container context includes allowPrivilegeEscalation."""
        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert context["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("FR-052")
    def test_container_security_context_has_read_only_root_filesystem(self) -> None:
        """Test container context includes readOnlyRootFilesystem."""
        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert context["readOnlyRootFilesystem"] is True

    @pytest.mark.requirement("FR-053")
    def test_container_security_context_drops_all_capabilities(self) -> None:
        """Test container context drops ALL capabilities."""
        config = PodSecurityConfig()
        context = config.to_container_security_context()

        assert context["capabilities"]["drop"] == ["ALL"]


# =============================================================================
# Edge Cases and Serialization Tests
# =============================================================================


class TestRBACSchemasSerialization:
    """Unit tests for model serialization."""

    @pytest.mark.requirement("FR-010")
    def test_service_account_config_to_dict(self) -> None:
        """Test ServiceAccountConfig can be serialized to dict."""
        config = ServiceAccountConfig(name="floe-test", namespace="ns")
        data: dict[str, Any] = config.model_dump()

        assert data["name"] == "floe-test"
        assert data["namespace"] == "ns"

    @pytest.mark.requirement("FR-020")
    def test_role_config_to_dict(self) -> None:
        """Test RoleConfig can be serialized to dict."""
        rule = RoleRule(resources=["pods"], verbs=["get"])
        config = RoleConfig(name="floe-test-role", namespace="ns", rules=[rule])
        data: dict[str, Any] = config.model_dump()

        assert data["name"] == "floe-test-role"
        assert len(data["rules"]) == 1

    @pytest.mark.requirement("FR-040")
    def test_namespace_config_to_dict(self) -> None:
        """Test NamespaceConfig can be serialized to dict."""
        config = NamespaceConfig(name="floe-jobs", layer="4")
        data: dict[str, Any] = config.model_dump()

        assert data["name"] == "floe-jobs"
        assert data["layer"] == "4"

    @pytest.mark.requirement("FR-010")
    def test_service_account_config_json_schema(self) -> None:
        """Test ServiceAccountConfig generates valid JSON schema."""
        schema = ServiceAccountConfig.model_json_schema()

        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "namespace" in schema["properties"]

    @pytest.mark.requirement("FR-020")
    def test_role_config_json_schema(self) -> None:
        """Test RoleConfig generates valid JSON schema."""
        schema = RoleConfig.model_json_schema()

        assert "properties" in schema
        assert "rules" in schema["properties"]

    @pytest.mark.requirement("FR-040")
    def test_namespace_config_json_schema(self) -> None:
        """Test NamespaceConfig generates valid JSON schema."""
        schema = NamespaceConfig.model_json_schema()

        assert "properties" in schema
        assert "pss_enforce" in schema["properties"]
