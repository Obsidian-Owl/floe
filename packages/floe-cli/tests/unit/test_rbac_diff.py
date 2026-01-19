"""Unit tests for RBAC diff functionality.

Tests the RBACDiffResult model and diff utilities for comparing
expected vs deployed RBAC configurations.

Task: T058
User Story: US6 - RBAC Audit and Validation
Requirements: FR-063
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestDiffChangeType:
    """Unit tests for DiffChangeType enum."""

    @pytest.mark.requirement("FR-063")
    def test_all_change_types_exist(self) -> None:
        """Test all expected change types exist."""
        from floe_cli.commands.rbac import DiffChangeType

        expected_types = [
            "ADDED",
            "REMOVED",
            "MODIFIED",
            "UNCHANGED",
        ]

        for type_name in expected_types:
            assert hasattr(DiffChangeType, type_name), f"Missing {type_name}"


class TestResourceDiff:
    """Unit tests for ResourceDiff model."""

    @pytest.mark.requirement("FR-063")
    def test_resource_diff_creation(self) -> None:
        """Test ResourceDiff can be created with required fields."""
        from floe_cli.commands.rbac import DiffChangeType, ResourceDiff

        diff = ResourceDiff(
            change_type=DiffChangeType.ADDED,
            resource_kind="ServiceAccount",
            resource_name="new-sa",
            resource_namespace="floe-jobs",
        )

        assert diff.change_type == DiffChangeType.ADDED
        assert diff.resource_kind == "ServiceAccount"
        assert diff.resource_name == "new-sa"
        assert diff.resource_namespace == "floe-jobs"

    @pytest.mark.requirement("FR-063")
    def test_resource_diff_with_details(self) -> None:
        """Test ResourceDiff with expected and actual values."""
        from floe_cli.commands.rbac import DiffChangeType, ResourceDiff

        diff = ResourceDiff(
            change_type=DiffChangeType.MODIFIED,
            resource_kind="Role",
            resource_name="my-role",
            resource_namespace="default",
            expected_value={"rules": [{"verbs": ["get"]}]},
            actual_value={"rules": [{"verbs": ["get", "list"]}]},
            diff_details=["rules[0].verbs: expected ['get'], got ['get', 'list']"],
        )

        assert diff.expected_value == {"rules": [{"verbs": ["get"]}]}
        assert diff.actual_value == {"rules": [{"verbs": ["get", "list"]}]}
        assert len(diff.diff_details) == 1

    @pytest.mark.requirement("FR-063")
    def test_resource_diff_immutable(self) -> None:
        """Test ResourceDiff is immutable (frozen model)."""
        from floe_cli.commands.rbac import DiffChangeType, ResourceDiff

        diff = ResourceDiff(
            change_type=DiffChangeType.ADDED,
            resource_kind="ServiceAccount",
            resource_name="test-sa",
        )

        with pytest.raises(ValidationError):
            diff.resource_name = "other-sa"  # type: ignore[misc]

    @pytest.mark.requirement("FR-063")
    def test_resource_diff_cluster_scoped(self) -> None:
        """Test ResourceDiff for cluster-scoped resources."""
        from floe_cli.commands.rbac import DiffChangeType, ResourceDiff

        diff = ResourceDiff(
            change_type=DiffChangeType.REMOVED,
            resource_kind="ClusterRole",
            resource_name="cluster-admin",
            resource_namespace=None,  # Cluster-scoped
        )

        assert diff.resource_namespace is None
        assert diff.resource_kind == "ClusterRole"


class TestRBACDiffResult:
    """Unit tests for RBACDiffResult model."""

    @pytest.mark.requirement("FR-063")
    def test_diff_result_creation(self) -> None:
        """Test RBACDiffResult can be created with defaults."""
        from floe_cli.commands.rbac import RBACDiffResult

        result = RBACDiffResult(
            expected_source="manifest.yaml",
            actual_source="cluster:my-cluster",
        )

        assert result.expected_source == "manifest.yaml"
        assert result.actual_source == "cluster:my-cluster"
        assert result.diffs == []
        assert result.generated_at is not None

    @pytest.mark.requirement("FR-063")
    def test_diff_result_with_diffs(self) -> None:
        """Test RBACDiffResult with diff entries."""
        from floe_cli.commands.rbac import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        diffs = [
            ResourceDiff(
                change_type=DiffChangeType.ADDED,
                resource_kind="ServiceAccount",
                resource_name="sa1",
                resource_namespace="ns1",
            ),
            ResourceDiff(
                change_type=DiffChangeType.REMOVED,
                resource_kind="Role",
                resource_name="role1",
                resource_namespace="ns1",
            ),
        ]

        result = RBACDiffResult(
            expected_source="expected.yaml",
            actual_source="deployed.yaml",
            diffs=diffs,
        )

        assert len(result.diffs) == 2

    @pytest.mark.requirement("FR-063")
    def test_has_differences_true(self) -> None:
        """Test has_differences returns True when diffs exist."""
        from floe_cli.commands.rbac import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        diff = ResourceDiff(
            change_type=DiffChangeType.ADDED,
            resource_kind="ServiceAccount",
            resource_name="sa1",
        )

        result = RBACDiffResult(
            expected_source="expected.yaml",
            actual_source="deployed.yaml",
            diffs=[diff],
        )

        assert result.has_differences() is True

    @pytest.mark.requirement("FR-063")
    def test_has_differences_false(self) -> None:
        """Test has_differences returns False when no diffs."""
        from floe_cli.commands.rbac import RBACDiffResult

        result = RBACDiffResult(
            expected_source="expected.yaml",
            actual_source="deployed.yaml",
            diffs=[],
        )

        assert result.has_differences() is False

    @pytest.mark.requirement("FR-063")
    def test_has_differences_unchanged_only(self) -> None:
        """Test has_differences returns False with only UNCHANGED entries."""
        from floe_cli.commands.rbac import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        unchanged = ResourceDiff(
            change_type=DiffChangeType.UNCHANGED,
            resource_kind="ServiceAccount",
            resource_name="sa1",
        )

        result = RBACDiffResult(
            expected_source="expected.yaml",
            actual_source="deployed.yaml",
            diffs=[unchanged],
        )

        assert result.has_differences() is False

    @pytest.mark.requirement("FR-063")
    def test_diffs_by_change_type(self) -> None:
        """Test diffs can be grouped by change type."""
        from floe_cli.commands.rbac import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        diffs = [
            ResourceDiff(
                change_type=DiffChangeType.ADDED,
                resource_kind="ServiceAccount",
                resource_name="sa1",
            ),
            ResourceDiff(
                change_type=DiffChangeType.REMOVED,
                resource_kind="Role",
                resource_name="role1",
            ),
            ResourceDiff(
                change_type=DiffChangeType.ADDED,
                resource_kind="ServiceAccount",
                resource_name="sa2",
            ),
            ResourceDiff(
                change_type=DiffChangeType.MODIFIED,
                resource_kind="Role",
                resource_name="role2",
            ),
        ]

        result = RBACDiffResult(
            expected_source="expected.yaml",
            actual_source="deployed.yaml",
            diffs=diffs,
        )

        by_type = result.diffs_by_change_type()

        assert len(by_type[DiffChangeType.ADDED]) == 2
        assert len(by_type[DiffChangeType.REMOVED]) == 1
        assert len(by_type[DiffChangeType.MODIFIED]) == 1
        assert len(by_type[DiffChangeType.UNCHANGED]) == 0

    @pytest.mark.requirement("FR-063")
    def test_diffs_by_resource_kind(self) -> None:
        """Test diffs can be grouped by resource kind."""
        from floe_cli.commands.rbac import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        diffs = [
            ResourceDiff(
                change_type=DiffChangeType.ADDED,
                resource_kind="ServiceAccount",
                resource_name="sa1",
            ),
            ResourceDiff(
                change_type=DiffChangeType.ADDED,
                resource_kind="Role",
                resource_name="role1",
            ),
            ResourceDiff(
                change_type=DiffChangeType.ADDED,
                resource_kind="ServiceAccount",
                resource_name="sa2",
            ),
        ]

        result = RBACDiffResult(
            expected_source="expected.yaml",
            actual_source="deployed.yaml",
            diffs=diffs,
        )

        by_kind = result.diffs_by_resource_kind()

        assert len(by_kind["ServiceAccount"]) == 2
        assert len(by_kind["Role"]) == 1

    @pytest.mark.requirement("FR-063")
    def test_diff_result_serializable(self) -> None:
        """Test RBACDiffResult is JSON serializable."""
        import json

        from floe_cli.commands.rbac import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        diff = ResourceDiff(
            change_type=DiffChangeType.MODIFIED,
            resource_kind="Role",
            resource_name="my-role",
            resource_namespace="default",
            expected_value={"rules": []},
            actual_value={"rules": [{"verbs": ["*"]}]},
        )

        result = RBACDiffResult(
            expected_source="expected.yaml",
            actual_source="cluster:test-cluster",
            diffs=[diff],
            added_count=0,
            removed_count=0,
            modified_count=1,
        )

        # Should not raise
        json_str = result.model_dump_json()
        assert "my-role" in json_str
        assert "modified" in json_str.lower()

        # Can also use standard json.dumps
        data = result.model_dump(mode="json")
        json_str2 = json.dumps(data)
        assert "my-role" in json_str2


class TestComputeResourceDiff:
    """Unit tests for compute_resource_diff function."""

    @pytest.mark.requirement("FR-063")
    def test_compute_diff_identical(self) -> None:
        """Test diff of identical resources returns UNCHANGED."""
        from floe_cli.commands.rbac import DiffChangeType, compute_resource_diff

        expected = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "test-sa", "namespace": "default"},
        }
        actual = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "test-sa", "namespace": "default"},
        }

        diff = compute_resource_diff(expected, actual, "ServiceAccount")

        assert diff.change_type == DiffChangeType.UNCHANGED
        assert diff.resource_name == "test-sa"
        assert diff.resource_namespace == "default"

    @pytest.mark.requirement("FR-063")
    def test_compute_diff_added(self) -> None:
        """Test diff of added resource (no actual)."""
        from floe_cli.commands.rbac import DiffChangeType, compute_resource_diff

        expected = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "new-sa", "namespace": "floe-jobs"},
        }

        diff = compute_resource_diff(expected, None, "ServiceAccount")

        assert diff.change_type == DiffChangeType.ADDED
        assert diff.resource_name == "new-sa"
        assert diff.expected_value is not None
        assert diff.actual_value is None

    @pytest.mark.requirement("FR-063")
    def test_compute_diff_removed(self) -> None:
        """Test diff of removed resource (no expected)."""
        from floe_cli.commands.rbac import DiffChangeType, compute_resource_diff

        actual = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "old-sa", "namespace": "default"},
        }

        diff = compute_resource_diff(None, actual, "ServiceAccount")

        assert diff.change_type == DiffChangeType.REMOVED
        assert diff.resource_name == "old-sa"
        assert diff.expected_value is None
        assert diff.actual_value is not None

    @pytest.mark.requirement("FR-063")
    def test_compute_diff_modified(self) -> None:
        """Test diff of modified resource."""
        from floe_cli.commands.rbac import DiffChangeType, compute_resource_diff

        expected = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": "my-role", "namespace": "default"},
            "rules": [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["get"]}],
        }
        actual = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": "my-role", "namespace": "default"},
            "rules": [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["get", "list"]}],
        }

        diff = compute_resource_diff(expected, actual, "Role")

        assert diff.change_type == DiffChangeType.MODIFIED
        assert diff.resource_name == "my-role"
        assert diff.expected_value is not None
        assert diff.actual_value is not None
        assert len(diff.diff_details) > 0

    @pytest.mark.requirement("FR-063")
    def test_compute_diff_ignores_metadata_fields(self) -> None:
        """Test diff ignores non-essential metadata fields."""
        from floe_cli.commands.rbac import DiffChangeType, compute_resource_diff

        expected = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "test-sa", "namespace": "default"},
        }
        actual = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": "test-sa",
                "namespace": "default",
                "uid": "12345-abcde",
                "resourceVersion": "67890",
                "creationTimestamp": "2026-01-01T00:00:00Z",
            },
        }

        diff = compute_resource_diff(expected, actual, "ServiceAccount")

        # Should be UNCHANGED because uid, resourceVersion, creationTimestamp are ignored
        assert diff.change_type == DiffChangeType.UNCHANGED


class TestComputeRBACDiff:
    """Unit tests for compute_rbac_diff function."""

    @pytest.mark.requirement("FR-063")
    def test_compute_rbac_diff_no_changes(self) -> None:
        """Test diff computation when resources are identical."""
        from floe_cli.commands.rbac import compute_rbac_diff

        expected = [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
        ]
        actual = [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
        ]

        result = compute_rbac_diff(
            expected_resources=expected,
            actual_resources=actual,
            expected_source="expected.yaml",
            actual_source="cluster:test",
        )

        assert result.has_differences() is False
        assert result.added_count == 0
        assert result.removed_count == 0
        assert result.modified_count == 0

    @pytest.mark.requirement("FR-063")
    def test_compute_rbac_diff_with_additions(self) -> None:
        """Test diff computation with added resources."""
        from floe_cli.commands.rbac import compute_rbac_diff

        expected = [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa2", "namespace": "ns1"},
            },
        ]
        actual = [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
        ]

        result = compute_rbac_diff(
            expected_resources=expected,
            actual_resources=actual,
            expected_source="expected.yaml",
            actual_source="cluster:test",
        )

        assert result.has_differences() is True
        assert result.added_count == 1  # sa2 needs to be added to cluster

    @pytest.mark.requirement("FR-063")
    def test_compute_rbac_diff_with_removals(self) -> None:
        """Test diff computation with removed resources."""
        from floe_cli.commands.rbac import compute_rbac_diff

        expected = [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
        ]
        actual = [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa1", "namespace": "ns1"},
            },
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "old-sa", "namespace": "ns1"},
            },
        ]

        result = compute_rbac_diff(
            expected_resources=expected,
            actual_resources=actual,
            expected_source="expected.yaml",
            actual_source="cluster:test",
        )

        assert result.has_differences() is True
        assert result.removed_count == 1  # old-sa should be removed

    @pytest.mark.requirement("FR-063")
    def test_compute_rbac_diff_empty_lists(self) -> None:
        """Test diff computation with empty resource lists."""
        from floe_cli.commands.rbac import compute_rbac_diff

        result = compute_rbac_diff(
            expected_resources=[],
            actual_resources=[],
            expected_source="expected.yaml",
            actual_source="cluster:test",
        )

        assert result.has_differences() is False
        assert len(result.diffs) == 0
