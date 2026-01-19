"""Unit tests for RoleBindingConfig with cross-namespace subjects.

Tests the cross-namespace subject functionality in RoleBindingConfig,
ensuring subjects can be from different namespaces than the RoleBinding.

Task: T035
User Story: US3 - Cross-Namespace Access
Requirements: FR-012, FR-023
"""

from __future__ import annotations

from typing import Any

import pytest


class TestCrossNamespaceSubjectValidation:
    """Unit tests for cross-namespace subject validation."""

    @pytest.mark.requirement("FR-023")
    def test_subject_namespace_different_from_binding(self) -> None:
        """Test subject can have different namespace than binding."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        subject = RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
        config = RoleBindingConfig(
            name="floe-cross-binding",
            namespace="floe-jobs",
            subjects=[subject],
            role_name="floe-test-role",
        )

        assert config.namespace == "floe-jobs"
        assert config.subjects[0].namespace == "floe-platform"

    @pytest.mark.requirement("FR-023")
    def test_subject_namespace_same_as_binding(self) -> None:
        """Test subject can have same namespace as binding."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        subject = RoleBindingSubject(name="floe-runner", namespace="floe-jobs")
        config = RoleBindingConfig(
            name="floe-same-ns-binding",
            namespace="floe-jobs",
            subjects=[subject],
            role_name="floe-test-role",
        )

        assert config.namespace == "floe-jobs"
        assert config.subjects[0].namespace == "floe-jobs"

    @pytest.mark.requirement("FR-012")
    def test_subject_requires_namespace(self) -> None:
        """Test that subject namespace is required."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import RoleBindingSubject

        with pytest.raises(ValidationError):
            RoleBindingSubject(name="floe-test")  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-012")
    def test_subject_requires_name(self) -> None:
        """Test that subject name is required."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import RoleBindingSubject

        with pytest.raises(ValidationError):
            RoleBindingSubject(namespace="floe-jobs")  # type: ignore[call-arg]


class TestCrossNamespaceManifestGeneration:
    """Unit tests for cross-namespace manifest generation."""

    @pytest.mark.requirement("FR-023")
    def test_manifest_preserves_cross_namespace_subjects(self) -> None:
        """Test manifest includes correct namespace for cross-namespace subjects."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-cross-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-test-role",
        )

        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["namespace"] == "floe-jobs"
        assert manifest["subjects"][0]["namespace"] == "floe-platform"
        assert manifest["subjects"][0]["name"] == "floe-dagster"

    @pytest.mark.requirement("FR-023")
    def test_manifest_multiple_namespaces(self) -> None:
        """Test manifest with subjects from multiple different namespaces."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-multi-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform"),
                RoleBindingSubject(name="floe-scheduler", namespace="floe-system"),
                RoleBindingSubject(name="floe-monitor", namespace="floe-monitoring"),
            ],
            role_name="floe-test-role",
        )

        manifest = config.to_k8s_manifest()

        assert len(manifest["subjects"]) == 3

        # Each subject has correct namespace
        namespaces = [s["namespace"] for s in manifest["subjects"]]
        assert "floe-platform" in namespaces
        assert "floe-system" in namespaces
        assert "floe-monitoring" in namespaces

    @pytest.mark.requirement("FR-012")
    def test_manifest_subjects_have_kind(self) -> None:
        """Test manifest subjects include kind: ServiceAccount."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-cross-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-test-role",
        )

        manifest = config.to_k8s_manifest()

        for subject in manifest["subjects"]:
            assert subject["kind"] == "ServiceAccount"


class TestCrossNamespaceSubjectProperties:
    """Unit tests for RoleBindingSubject properties."""

    @pytest.mark.requirement("FR-012")
    def test_subject_kind_default_service_account(self) -> None:
        """Test subject kind defaults to ServiceAccount."""
        from floe_core.schemas.rbac import RoleBindingSubject

        subject = RoleBindingSubject(name="floe-test", namespace="floe-jobs")
        assert subject.kind == "ServiceAccount"

    @pytest.mark.requirement("FR-012")
    def test_subject_kind_literal_type(self) -> None:
        """Test subject kind is a Literal type."""
        from floe_core.schemas.rbac import RoleBindingSubject

        # Only ServiceAccount is allowed by the Literal type
        subject = RoleBindingSubject(
            kind="ServiceAccount", name="floe-test", namespace="floe-jobs"
        )
        assert subject.kind == "ServiceAccount"

    @pytest.mark.requirement("FR-023")
    def test_subject_is_frozen(self) -> None:
        """Test subject is immutable."""
        from floe_core.schemas.rbac import RoleBindingSubject

        subject = RoleBindingSubject(name="floe-test", namespace="floe-jobs")

        with pytest.raises(Exception):  # ValidationError for frozen model
            subject.namespace = "floe-other"


class TestCrossNamespaceRoleRefBehavior:
    """Unit tests for roleRef behavior with cross-namespace subjects."""

    @pytest.mark.requirement("FR-023")
    def test_role_ref_references_local_role(self) -> None:
        """Test roleRef references Role in binding's namespace."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-cross-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-job-creator-role",
        )

        manifest = config.to_k8s_manifest()

        # roleRef is for Role (namespaced), not ClusterRole
        assert manifest["roleRef"]["kind"] == "Role"
        assert manifest["roleRef"]["name"] == "floe-job-creator-role"
        assert manifest["roleRef"]["apiGroup"] == "rbac.authorization.k8s.io"

    @pytest.mark.requirement("FR-023")
    def test_role_ref_api_group_correct(self) -> None:
        """Test roleRef has correct API group."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-cross-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-test-role",
        )

        manifest = config.to_k8s_manifest()

        assert manifest["roleRef"]["apiGroup"] == "rbac.authorization.k8s.io"


class TestCrossNamespaceAllowedNamespaces:
    """Unit tests for allowed_subject_namespaces validation."""

    @pytest.mark.requirement("FR-023")
    def test_allowed_namespaces_accepts_valid(self) -> None:
        """Test subjects from allowed namespaces are accepted."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-test-role",
            allowed_subject_namespaces=["floe-platform", "floe-jobs"],
        )

        assert config.subjects[0].namespace == "floe-platform"

    @pytest.mark.requirement("FR-023")
    def test_allowed_namespaces_rejects_invalid(self) -> None:
        """Test subjects from disallowed namespaces are rejected."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        with pytest.raises(ValidationError, match="not in allowed namespaces"):
            RoleBindingConfig(
                name="floe-dagster-binding",
                namespace="floe-jobs",
                subjects=[
                    RoleBindingSubject(name="floe-dagster", namespace="floe-sales-domain")
                ],
                role_name="floe-test-role",
                allowed_subject_namespaces=["floe-platform", "floe-jobs"],
            )

    @pytest.mark.requirement("FR-023")
    def test_allowed_namespaces_none_permits_all(self) -> None:
        """Test None allowed_subject_namespaces permits all namespaces."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        # Should not raise - no restrictions when allowed_subject_namespaces is None
        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-any-namespace")
            ],
            role_name="floe-test-role",
            allowed_subject_namespaces=None,
        )

        assert config.subjects[0].namespace == "floe-any-namespace"

    @pytest.mark.requirement("FR-023")
    def test_allowed_namespaces_multiple_subjects(self) -> None:
        """Test validation works with multiple subjects."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        # One valid, one invalid subject
        with pytest.raises(ValidationError, match="floe-bad-namespace"):
            RoleBindingConfig(
                name="floe-multi-binding",
                namespace="floe-jobs",
                subjects=[
                    RoleBindingSubject(name="floe-dagster", namespace="floe-platform"),
                    RoleBindingSubject(name="floe-rogue", namespace="floe-bad-namespace"),
                ],
                role_name="floe-test-role",
                allowed_subject_namespaces=["floe-platform", "floe-jobs"],
            )

    @pytest.mark.requirement("FR-023")
    def test_allowed_namespaces_empty_list_rejects_all(self) -> None:
        """Test empty allowed list rejects all cross-namespace subjects."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        with pytest.raises(ValidationError, match="not in allowed namespaces"):
            RoleBindingConfig(
                name="floe-dagster-binding",
                namespace="floe-jobs",
                subjects=[
                    RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
                ],
                role_name="floe-test-role",
                allowed_subject_namespaces=[],  # Empty = reject all
            )


class TestCrossNamespaceYAMLOutput:
    """Unit tests for YAML output of cross-namespace bindings."""

    @pytest.mark.requirement("FR-023")
    def test_yaml_includes_all_namespaces(self) -> None:
        """Test YAML output includes all namespaces correctly."""
        import yaml

        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-cross-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform")
            ],
            role_name="floe-test-role",
        )

        manifest = config.to_k8s_manifest()
        yaml_str = yaml.dump(manifest, default_flow_style=False)

        # Both namespaces appear in YAML
        assert "namespace: floe-jobs" in yaml_str
        assert "namespace: floe-platform" in yaml_str

    @pytest.mark.requirement("FR-023")
    def test_yaml_roundtrip_preserves_cross_namespace(self) -> None:
        """Test YAML roundtrip preserves cross-namespace structure."""
        import yaml

        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-cross-binding",
            namespace="floe-jobs",
            subjects=[
                RoleBindingSubject(name="floe-dagster", namespace="floe-platform"),
                RoleBindingSubject(name="floe-runner", namespace="floe-jobs"),
            ],
            role_name="floe-test-role",
        )

        manifest = config.to_k8s_manifest()
        yaml_str = yaml.dump(manifest)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        # Verify structure preserved
        assert restored["metadata"]["namespace"] == "floe-jobs"
        assert len(restored["subjects"]) == 2
        assert restored["subjects"][0]["namespace"] == "floe-platform"
        assert restored["subjects"][1]["namespace"] == "floe-jobs"
