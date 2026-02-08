"""Golden artifact tests for RBAC manifest backwards compatibility.

These tests ensure that the current RBAC manifest generation code can still
produce manifests that are structurally compatible with previous versions.
This prevents unintentional breaking changes to the manifest format.

Golden artifacts are stored in tests/contract/fixtures/rbac/v{N}/ directories.
When schema changes are made:
- MINOR changes: Existing golden artifacts should still parse
- MAJOR changes: Create new v{N+1} directory with updated artifacts

Task: Test Quality Improvement (P2)
Requirements: Contract stability, backwards compatibility
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from floe_core.schemas.rbac import (
    NamespaceConfig,
    RoleBindingConfig,
    RoleBindingSubject,
    RoleConfig,
    RoleRule,
    ServiceAccountConfig,
)
from floe_rbac_k8s.plugin import K8sRBACPlugin

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "rbac"


def load_golden_artifact(version: str, filename: str) -> dict[str, Any]:
    """Load a golden artifact YAML file.

    Args:
        version: Version directory (e.g., "v1")
        filename: YAML filename (e.g., "service_account.yaml")

    Returns:
        Parsed YAML content as dictionary.
    """
    filepath = FIXTURES_DIR / version / filename
    with filepath.open() as f:
        return yaml.safe_load(f)


class TestGoldenArtifactServiceAccount:
    """Golden artifact tests for ServiceAccount manifests."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPlugin:
        """Return K8sRBACPlugin instance."""
        return K8sRBACPlugin()

    @pytest.fixture
    def golden_v1(self) -> dict[str, Any]:
        """Load v1 golden ServiceAccount artifact."""
        return load_golden_artifact("v1", "service_account.yaml")

    @pytest.mark.requirement("FR-010")
    @pytest.mark.contract
    def test_current_matches_v1_structure(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test current ServiceAccount generation matches v1 golden artifact structure."""
        # Generate with same config as golden artifact
        config = ServiceAccountConfig(
            name="floe-job-runner",
            namespace="floe-jobs",
        )
        generated = plugin.generate_service_account(config)

        # Verify structural compatibility
        assert generated["apiVersion"] == golden_v1["apiVersion"]
        assert generated["kind"] == golden_v1["kind"]
        assert "metadata" in generated
        assert "name" in generated["metadata"]
        assert "namespace" in generated["metadata"]
        assert "labels" in generated["metadata"]
        assert "automountServiceAccountToken" in generated

    @pytest.mark.requirement("FR-011")
    @pytest.mark.contract
    def test_automount_token_default_matches_v1(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test automountServiceAccountToken default matches v1 (false)."""
        config = ServiceAccountConfig(
            name="floe-test-runner",
            namespace="floe-test",
        )
        generated = plugin.generate_service_account(config)

        # v1 contract: automountServiceAccountToken defaults to false
        assert (
            generated["automountServiceAccountToken"]
            == golden_v1["automountServiceAccountToken"]
        )
        assert generated["automountServiceAccountToken"] is False


class TestGoldenArtifactRole:
    """Golden artifact tests for Role manifests."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPlugin:
        """Return K8sRBACPlugin instance."""
        return K8sRBACPlugin()

    @pytest.fixture
    def golden_v1(self) -> dict[str, Any]:
        """Load v1 golden Role artifact."""
        return load_golden_artifact("v1", "role.yaml")

    @pytest.mark.requirement("FR-020")
    @pytest.mark.contract
    def test_current_matches_v1_structure(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test current Role generation matches v1 golden artifact structure."""
        # Generate with same config as golden artifact
        config = RoleConfig(
            name="floe-secret-reader-role",
            namespace="floe-jobs",
            rules=[
                RoleRule(
                    resources=["secrets"],
                    verbs=["get"],
                    resource_names=["snowflake-creds"],
                )
            ],
        )
        generated = plugin.generate_role(config)

        # Verify structural compatibility
        assert generated["apiVersion"] == golden_v1["apiVersion"]
        assert generated["kind"] == golden_v1["kind"]
        assert "metadata" in generated
        assert "rules" in generated
        assert isinstance(generated["rules"], list)

    @pytest.mark.requirement("FR-021")
    @pytest.mark.contract
    def test_resource_names_structure_matches_v1(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test resourceNames field structure matches v1 contract."""
        config = RoleConfig(
            name="floe-test-secrets-role",
            namespace="floe-test",
            rules=[
                RoleRule(
                    resources=["secrets"],
                    verbs=["get"],
                    resource_names=["my-secret"],
                )
            ],
        )
        generated = plugin.generate_role(config)

        # v1 contract: resourceNames is a list within rules
        rule = generated["rules"][0]
        golden_rule = golden_v1["rules"][0]

        assert "resourceNames" in rule
        assert isinstance(rule["resourceNames"], list)
        assert "resourceNames" in golden_rule


class TestGoldenArtifactRoleBinding:
    """Golden artifact tests for RoleBinding manifests."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPlugin:
        """Return K8sRBACPlugin instance."""
        return K8sRBACPlugin()

    @pytest.fixture
    def golden_v1(self) -> dict[str, Any]:
        """Load v1 golden RoleBinding artifact."""
        return load_golden_artifact("v1", "role_binding.yaml")

    @pytest.fixture
    def golden_cross_namespace_v1(self) -> dict[str, Any]:
        """Load v1 golden cross-namespace RoleBinding artifact."""
        return load_golden_artifact("v1", "cross_namespace_role_binding.yaml")

    @pytest.mark.requirement("FR-022")
    @pytest.mark.contract
    def test_current_matches_v1_structure(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test current RoleBinding generation matches v1 golden artifact structure."""
        config = RoleBindingConfig(
            name="floe-job-runner-secret-reader-binding",
            namespace="floe-jobs",
            role_name="floe-secret-reader-role",
            subjects=[
                RoleBindingSubject(
                    name="floe-job-runner",
                    namespace="floe-jobs",
                )
            ],
        )
        generated = plugin.generate_role_binding(config)

        # Verify structural compatibility
        assert generated["apiVersion"] == golden_v1["apiVersion"]
        assert generated["kind"] == golden_v1["kind"]
        assert "roleRef" in generated
        assert "subjects" in generated
        assert isinstance(generated["subjects"], list)

    @pytest.mark.requirement("FR-023")
    @pytest.mark.contract
    def test_cross_namespace_subject_matches_v1(
        self,
        plugin: K8sRBACPlugin,
        golden_cross_namespace_v1: dict[str, Any],
    ) -> None:
        """Test cross-namespace subject structure matches v1 contract."""
        config = RoleBindingConfig(
            name="floe-dagster-jobs-access-binding",
            namespace="floe-jobs",
            role_name="floe-dagster-job-manager-role",
            subjects=[
                RoleBindingSubject(
                    name="floe-dagster-webserver",
                    namespace="floe-platform",  # Different namespace
                )
            ],
        )
        generated = plugin.generate_role_binding(config)

        # v1 contract: subjects can have different namespace than binding
        subject = generated["subjects"][0]
        golden_subject = golden_cross_namespace_v1["subjects"][0]

        assert subject["namespace"] != generated["metadata"]["namespace"]
        assert "namespace" in golden_subject


class TestGoldenArtifactNamespace:
    """Golden artifact tests for Namespace manifests."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPlugin:
        """Return K8sRBACPlugin instance."""
        return K8sRBACPlugin()

    @pytest.fixture
    def golden_v1(self) -> dict[str, Any]:
        """Load v1 golden Namespace artifact."""
        return load_golden_artifact("v1", "namespace.yaml")

    @pytest.mark.requirement("FR-030")
    @pytest.mark.contract
    def test_current_matches_v1_structure(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test current Namespace generation matches v1 golden artifact structure."""
        config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
            pss_enforce="restricted",
        )
        generated = plugin.generate_namespace(config)

        # Verify structural compatibility
        assert generated["apiVersion"] == golden_v1["apiVersion"]
        assert generated["kind"] == golden_v1["kind"]
        assert "metadata" in generated
        assert "labels" in generated["metadata"]

    @pytest.mark.requirement("FR-031")
    @pytest.mark.contract
    def test_pss_labels_match_v1_contract(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test PSS labels structure matches v1 contract."""
        config = NamespaceConfig(
            name="floe-test-workloads",
            layer="4",
            pss_enforce="restricted",
        )
        generated = plugin.generate_namespace(config)
        labels = generated["metadata"]["labels"]
        golden_labels = golden_v1["metadata"]["labels"]

        # v1 contract: PSS labels must be present
        # Note: version labels are optional per PSS spec, floe uses latest by default
        pss_label_keys = [
            "pod-security.kubernetes.io/enforce",
            "pod-security.kubernetes.io/audit",
            "pod-security.kubernetes.io/warn",
        ]

        for key in pss_label_keys:
            assert key in labels, f"Missing PSS label: {key}"
            assert key in golden_labels, f"Golden artifact missing: {key}"

    @pytest.mark.requirement("FR-034")
    @pytest.mark.contract
    def test_layer_label_matches_v1_contract(
        self,
        plugin: K8sRBACPlugin,
        golden_v1: dict[str, Any],
    ) -> None:
        """Test layer label structure matches v1 contract."""
        config = NamespaceConfig(
            name="floe-test-workloads",
            layer="4",
        )
        generated = plugin.generate_namespace(config)
        labels = generated["metadata"]["labels"]
        golden_labels = golden_v1["metadata"]["labels"]

        # v1 contract: floe.dev/layer label must be present
        assert "floe.dev/layer" in labels
        assert "floe.dev/layer" in golden_labels


class TestGoldenArtifactVersioning:
    """Tests for golden artifact versioning and migration."""

    @pytest.mark.requirement("FR-035")
    @pytest.mark.contract
    def test_v1_fixtures_exist(self) -> None:
        """Test v1 fixture directory exists with required files."""
        v1_dir = FIXTURES_DIR / "v1"
        assert v1_dir.exists(), "v1 fixtures directory missing"

        required_files = [
            "service_account.yaml",
            "role.yaml",
            "role_binding.yaml",
            "namespace.yaml",
            "cross_namespace_role_binding.yaml",
        ]

        for filename in required_files:
            filepath = v1_dir / filename
            assert filepath.exists(), f"Missing v1 fixture: {filename}"

    @pytest.mark.requirement("FR-035")
    @pytest.mark.contract
    def test_v1_fixtures_are_valid_yaml(self) -> None:
        """Test all v1 fixtures are valid YAML."""
        v1_dir = FIXTURES_DIR / "v1"

        for filepath in v1_dir.glob("*.yaml"):
            with filepath.open() as f:
                content = yaml.safe_load(f)
                assert content is not None, f"Empty fixture: {filepath.name}"
                assert isinstance(content, dict), f"Invalid YAML: {filepath.name}"

    @pytest.mark.requirement("FR-035")
    @pytest.mark.contract
    def test_v1_fixtures_have_required_k8s_fields(self) -> None:
        """Test all v1 fixtures have apiVersion and kind."""
        v1_dir = FIXTURES_DIR / "v1"

        for filepath in v1_dir.glob("*.yaml"):
            content = load_golden_artifact("v1", filepath.name)

            assert "apiVersion" in content, f"Missing apiVersion: {filepath.name}"
            assert "kind" in content, f"Missing kind: {filepath.name}"
            assert "metadata" in content, f"Missing metadata: {filepath.name}"
