"""Contract tests for NamespaceConfig.to_k8s_manifest().

Tests the K8s Namespace manifest generation including PSS labels,
layer labels, and managed-by labels.

Task: T027
User Story: US2 - Namespace Isolation
Requirements: FR-030, FR-031, FR-032, FR-033, FR-034
"""

from __future__ import annotations

from typing import Any

import pytest


class TestNamespaceConfigSchemaContract:
    """Contract tests for NamespaceConfig schema stability."""

    @pytest.mark.requirement("FR-030")
    def test_namespace_config_has_required_fields(self) -> None:
        """Verify NamespaceConfig has all required fields."""
        from floe_core.schemas.rbac import NamespaceConfig

        schema = NamespaceConfig.model_json_schema()
        required = schema.get("required", [])

        assert "name" in required
        assert "layer" in required

    @pytest.mark.requirement("FR-030")
    def test_namespace_config_name_pattern(self) -> None:
        """Verify NamespaceConfig name follows floe-{purpose} pattern."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import NamespaceConfig

        # Valid names
        NamespaceConfig(name="floe-jobs", layer="4")
        NamespaceConfig(name="floe-platform", layer="3")
        NamespaceConfig(name="floe-test-namespace", layer="4")

        # Invalid - doesn't start with floe-
        with pytest.raises(ValidationError, match="name"):
            NamespaceConfig(name="jobs", layer="4")

    @pytest.mark.requirement("FR-030")
    def test_namespace_config_layer_values(self) -> None:
        """Verify NamespaceConfig layer accepts only valid values."""
        from pydantic import ValidationError

        from floe_core.schemas.rbac import NamespaceConfig

        # Valid layers
        NamespaceConfig(name="floe-platform", layer="3")
        NamespaceConfig(name="floe-jobs", layer="4")

        # Invalid layer
        with pytest.raises(ValidationError, match="layer"):
            NamespaceConfig(name="floe-invalid", layer="5")

    @pytest.mark.requirement("FR-031")
    def test_namespace_config_pss_defaults(self) -> None:
        """Verify NamespaceConfig has correct PSS defaults."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")

        assert config.pss_enforce == "restricted"
        assert config.pss_audit == "restricted"
        assert config.pss_warn == "restricted"

    @pytest.mark.requirement("FR-031")
    def test_namespace_config_pss_valid_values(self) -> None:
        """Verify NamespaceConfig PSS fields accept valid values."""
        from floe_core.schemas.rbac import NamespaceConfig

        # All valid PSS levels
        for level in ["privileged", "baseline", "restricted"]:
            config = NamespaceConfig(
                name="floe-test",
                layer="4",
                pss_enforce=level,
                pss_audit=level,
                pss_warn=level,
            )
            assert config.pss_enforce == level

    @pytest.mark.requirement("FR-030")
    def test_namespace_config_frozen(self) -> None:
        """Verify NamespaceConfig is immutable."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test", layer="4")

        with pytest.raises(Exception):  # ValidationError for frozen model
            config.name = "floe-other"


class TestNamespaceManifestContract:
    """Contract tests for NamespaceConfig.to_k8s_manifest()."""

    @pytest.mark.requirement("FR-030")
    def test_manifest_has_api_version(self) -> None:
        """Verify Namespace manifest has apiVersion: v1."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test", layer="4")
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "v1"

    @pytest.mark.requirement("FR-030")
    def test_manifest_has_kind(self) -> None:
        """Verify Namespace manifest has kind: Namespace."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test", layer="4")
        manifest = config.to_k8s_manifest()

        assert manifest["kind"] == "Namespace"

    @pytest.mark.requirement("FR-030")
    def test_manifest_has_metadata_name(self) -> None:
        """Verify Namespace manifest has metadata.name."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["name"] == "floe-jobs"

    @pytest.mark.requirement("FR-031")
    def test_manifest_has_pss_enforce_label(self) -> None:
        """Verify Namespace manifest has PSS enforce label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4", pss_enforce="restricted")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

    @pytest.mark.requirement("FR-031")
    def test_manifest_has_pss_audit_label(self) -> None:
        """Verify Namespace manifest has PSS audit label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4", pss_audit="restricted")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/audit"] == "restricted"

    @pytest.mark.requirement("FR-031")
    def test_manifest_has_pss_warn_label(self) -> None:
        """Verify Namespace manifest has PSS warn label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4", pss_warn="restricted")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/warn"] == "restricted"

    @pytest.mark.requirement("FR-034")
    def test_manifest_has_layer_label(self) -> None:
        """Verify Namespace manifest has floe.dev/layer label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["floe.dev/layer"] == "4"

    @pytest.mark.requirement("FR-034")
    def test_manifest_has_managed_by_label(self) -> None:
        """Verify Namespace manifest has managed-by label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-034")
    def test_manifest_has_part_of_label(self) -> None:
        """Verify Namespace manifest has part-of label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["app.kubernetes.io/part-of"] == "floe"


class TestNamespacePSSEnforcementLevels:
    """Contract tests for PSS enforcement level requirements."""

    @pytest.mark.requirement("FR-032")
    def test_jobs_namespace_restricted_by_default(self) -> None:
        """Verify jobs namespace (layer 4) defaults to restricted PSS."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

    @pytest.mark.requirement("FR-033")
    def test_platform_namespace_can_use_baseline(self) -> None:
        """Verify platform namespace (layer 3) can use baseline PSS."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(
            name="floe-platform",
            layer="3",
            pss_enforce="baseline",
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "baseline"

    @pytest.mark.requirement("FR-031")
    def test_all_pss_levels_supported(self) -> None:
        """Verify all three PSS levels can be configured."""
        from floe_core.schemas.rbac import NamespaceConfig

        for level in ["privileged", "baseline", "restricted"]:
            config = NamespaceConfig(
                name="floe-test",
                layer="4",
                pss_enforce=level,
            )
            manifest = config.to_k8s_manifest()
            labels = manifest["metadata"]["labels"]
            assert labels["pod-security.kubernetes.io/enforce"] == level


class TestNamespaceCustomLabels:
    """Contract tests for custom label handling."""

    @pytest.mark.requirement("FR-030")
    def test_custom_labels_included(self) -> None:
        """Verify custom labels are included in manifest."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(
            name="floe-test",
            layer="4",
            labels={"environment": "production", "team": "data-platform"},
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["environment"] == "production"
        assert labels["team"] == "data-platform"

    @pytest.mark.requirement("FR-030")
    def test_custom_labels_merged_with_required(self) -> None:
        """Verify custom labels are merged with required labels."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(
            name="floe-test",
            layer="4",
            labels={"custom": "value"},
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        # Required labels present
        assert "app.kubernetes.io/managed-by" in labels
        assert "pod-security.kubernetes.io/enforce" in labels
        assert "floe.dev/layer" in labels
        # Custom label present
        assert labels["custom"] == "value"


class TestNamespaceYAMLCompatibility:
    """Contract tests for YAML serialization compatibility."""

    @pytest.mark.requirement("FR-030")
    def test_manifest_yaml_serializable(self) -> None:
        """Verify Namespace manifest can be serialized to YAML."""
        import yaml

        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = config.to_k8s_manifest()

        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: v1" in yaml_str
        assert "kind: Namespace" in yaml_str

    @pytest.mark.requirement("FR-030")
    def test_manifest_yaml_roundtrip(self) -> None:
        """Verify Namespace manifest survives YAML roundtrip."""
        import yaml

        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
            pss_enforce="restricted",
        )
        manifest = config.to_k8s_manifest()

        yaml_str = yaml.dump(manifest)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        assert restored["apiVersion"] == manifest["apiVersion"]
        assert restored["kind"] == manifest["kind"]
        assert restored["metadata"]["name"] == manifest["metadata"]["name"]
        assert (
            restored["metadata"]["labels"]["pod-security.kubernetes.io/enforce"]
            == manifest["metadata"]["labels"]["pod-security.kubernetes.io/enforce"]
        )
