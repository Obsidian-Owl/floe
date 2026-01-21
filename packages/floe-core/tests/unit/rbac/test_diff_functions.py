"""Unit tests for RBAC diff functions.

Tests the compute_resource_diff and compute_rbac_diff functions
migrated from floe-cli.

Task: T063, Epic 11
User Story: US6 - RBAC Audit and Validation
Requirements: FR-063
"""

from __future__ import annotations

from typing import Any

import pytest


class TestComputeResourceDiff:
    """Unit tests for compute_resource_diff function."""

    @pytest.mark.requirement("FR-063")
    def test_detect_added_resource(self) -> None:
        """Test detection of added resource (expected but not actual)."""
        from floe_core.rbac.diff import compute_resource_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected: dict[str, Any] = {
            "kind": "ServiceAccount",
            "metadata": {"name": "new-sa", "namespace": "default"},
        }
        actual = None

        diff = compute_resource_diff(expected, actual, "ServiceAccount")

        assert diff.change_type == DiffChangeType.ADDED
        assert diff.resource_name == "new-sa"
        assert diff.resource_namespace == "default"
        assert "created" in diff.diff_details[0].lower()

    @pytest.mark.requirement("FR-063")
    def test_detect_removed_resource(self) -> None:
        """Test detection of removed resource (actual but not expected)."""
        from floe_core.rbac.diff import compute_resource_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected = None
        actual: dict[str, Any] = {
            "kind": "ServiceAccount",
            "metadata": {"name": "old-sa", "namespace": "floe-jobs"},
        }

        diff = compute_resource_diff(expected, actual, "ServiceAccount")

        assert diff.change_type == DiffChangeType.REMOVED
        assert diff.resource_name == "old-sa"
        assert diff.resource_namespace == "floe-jobs"
        assert "removed" in diff.diff_details[0].lower()

    @pytest.mark.requirement("FR-063")
    def test_detect_unchanged_resource(self) -> None:
        """Test detection of unchanged resource."""
        from floe_core.rbac.diff import compute_resource_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        resource: dict[str, Any] = {
            "kind": "ServiceAccount",
            "metadata": {"name": "my-sa", "namespace": "default"},
        }

        diff = compute_resource_diff(resource, resource.copy(), "ServiceAccount")

        assert diff.change_type == DiffChangeType.UNCHANGED
        assert len(diff.diff_details) == 0

    @pytest.mark.requirement("FR-063")
    def test_detect_modified_resource(self) -> None:
        """Test detection of modified resource."""
        from floe_core.rbac.diff import compute_resource_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected: dict[str, Any] = {
            "kind": "Role",
            "metadata": {"name": "my-role", "namespace": "default"},
            "rules": [{"verbs": ["get"]}],
        }
        actual: dict[str, Any] = {
            "kind": "Role",
            "metadata": {"name": "my-role", "namespace": "default"},
            "rules": [{"verbs": ["get", "list"]}],
        }

        diff = compute_resource_diff(expected, actual, "Role")

        assert diff.change_type == DiffChangeType.MODIFIED
        assert len(diff.diff_details) > 0

    @pytest.mark.requirement("FR-063")
    def test_ignores_metadata_fields(self) -> None:
        """Test that non-essential metadata fields are ignored."""
        from floe_core.rbac.diff import compute_resource_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected: dict[str, Any] = {
            "kind": "ServiceAccount",
            "metadata": {"name": "my-sa", "namespace": "default"},
        }
        actual: dict[str, Any] = {
            "kind": "ServiceAccount",
            "metadata": {
                "name": "my-sa",
                "namespace": "default",
                "uid": "abc123",
                "resourceVersion": "456",
                "creationTimestamp": "2024-01-01T00:00:00Z",
            },
        }

        diff = compute_resource_diff(expected, actual, "ServiceAccount")

        assert diff.change_type == DiffChangeType.UNCHANGED

    @pytest.mark.requirement("FR-063")
    def test_both_none_raises_error(self) -> None:
        """Test that both expected and actual being None raises error."""
        from floe_core.rbac.diff import compute_resource_diff

        with pytest.raises(ValueError, match="cannot be None"):
            compute_resource_diff(None, None, "ServiceAccount")

    @pytest.mark.requirement("FR-063")
    def test_diff_details_show_path(self) -> None:
        """Test diff details show the path to changed value."""
        from floe_core.rbac.diff import compute_resource_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected: dict[str, Any] = {
            "kind": "Role",
            "metadata": {"name": "my-role", "namespace": "default"},
            "rules": [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["get"]}],
        }
        actual: dict[str, Any] = {
            "kind": "Role",
            "metadata": {"name": "my-role", "namespace": "default"},
            "rules": [{"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]}],
        }

        diff = compute_resource_diff(expected, actual, "Role")

        assert diff.change_type == DiffChangeType.MODIFIED
        # Should show the path where the difference is
        detail_text = " ".join(diff.diff_details)
        assert "rules" in detail_text or "resources" in detail_text


class TestComputeRbacDiff:
    """Unit tests for compute_rbac_diff function."""

    @pytest.mark.requirement("FR-063")
    def test_diff_empty_lists(self) -> None:
        """Test diff with empty resource lists."""
        from floe_core.rbac.diff import compute_rbac_diff

        result = compute_rbac_diff([], [], "expected.yaml", "cluster:test")

        assert not result.has_differences()
        assert result.added_count == 0
        assert result.removed_count == 0
        assert result.modified_count == 0

    @pytest.mark.requirement("FR-063")
    def test_diff_added_resources(self) -> None:
        """Test diff detects added resources."""
        from floe_core.rbac.diff import compute_rbac_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected = [
            {
                "kind": "ServiceAccount",
                "metadata": {"name": "sa1", "namespace": "default"},
            },
        ]
        actual: list[dict[str, Any]] = []

        result = compute_rbac_diff(expected, actual, "expected.yaml", "cluster:test")

        assert result.has_differences()
        assert result.added_count == 1
        by_type = result.diffs_by_change_type()
        assert len(by_type[DiffChangeType.ADDED]) == 1

    @pytest.mark.requirement("FR-063")
    def test_diff_removed_resources(self) -> None:
        """Test diff detects removed resources."""
        from floe_core.rbac.diff import compute_rbac_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected: list[dict[str, Any]] = []
        actual = [
            {
                "kind": "Role",
                "metadata": {"name": "old-role", "namespace": "default"},
            },
        ]

        result = compute_rbac_diff(expected, actual, "expected.yaml", "cluster:test")

        assert result.has_differences()
        assert result.removed_count == 1
        by_type = result.diffs_by_change_type()
        assert len(by_type[DiffChangeType.REMOVED]) == 1

    @pytest.mark.requirement("FR-063")
    def test_diff_modified_resources(self) -> None:
        """Test diff detects modified resources."""
        from floe_core.rbac.diff import compute_rbac_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected = [
            {
                "kind": "Role",
                "metadata": {"name": "my-role", "namespace": "default"},
                "rules": [{"verbs": ["get"]}],
            },
        ]
        actual = [
            {
                "kind": "Role",
                "metadata": {"name": "my-role", "namespace": "default"},
                "rules": [{"verbs": ["get", "list"]}],
            },
        ]

        result = compute_rbac_diff(expected, actual, "expected.yaml", "cluster:test")

        assert result.has_differences()
        assert result.modified_count == 1
        by_type = result.diffs_by_change_type()
        assert len(by_type[DiffChangeType.MODIFIED]) == 1

    @pytest.mark.requirement("FR-063")
    def test_diff_mixed_changes(self) -> None:
        """Test diff with added, removed, and modified resources."""
        from floe_core.rbac.diff import compute_rbac_diff
        from floe_core.schemas.rbac_diff import DiffChangeType

        expected = [
            {
                "kind": "ServiceAccount",
                "metadata": {"name": "new-sa", "namespace": "default"},
            },
            {
                "kind": "Role",
                "metadata": {"name": "modified-role", "namespace": "default"},
                "rules": [{"verbs": ["get"]}],
            },
        ]
        actual = [
            {
                "kind": "ServiceAccount",
                "metadata": {"name": "old-sa", "namespace": "default"},
            },
            {
                "kind": "Role",
                "metadata": {"name": "modified-role", "namespace": "default"},
                "rules": [{"verbs": ["*"]}],
            },
        ]

        result = compute_rbac_diff(expected, actual, "expected.yaml", "cluster:test")

        assert result.has_differences()
        assert result.added_count == 1  # new-sa
        assert result.removed_count == 1  # old-sa
        assert result.modified_count == 1  # modified-role

    @pytest.mark.requirement("FR-063")
    def test_diff_result_sources(self) -> None:
        """Test diff result includes source information."""
        from floe_core.rbac.diff import compute_rbac_diff

        result = compute_rbac_diff(
            [], [], "deploy/rbac/manifests.yaml", "cluster:production"
        )

        assert result.expected_source == "deploy/rbac/manifests.yaml"
        assert result.actual_source == "cluster:production"

    @pytest.mark.requirement("FR-063")
    def test_diff_by_resource_kind(self) -> None:
        """Test diffs can be grouped by resource kind."""
        from floe_core.rbac.diff import compute_rbac_diff

        expected = [
            {"kind": "ServiceAccount", "metadata": {"name": "sa1", "namespace": "ns"}},
            {"kind": "Role", "metadata": {"name": "role1", "namespace": "ns"}},
            {"kind": "ServiceAccount", "metadata": {"name": "sa2", "namespace": "ns"}},
        ]
        actual: list[dict[str, Any]] = []

        result = compute_rbac_diff(expected, actual, "manifest.yaml", "cluster")

        by_kind = result.diffs_by_resource_kind()

        assert len(by_kind["ServiceAccount"]) == 2
        assert len(by_kind["Role"]) == 1

    @pytest.mark.requirement("FR-063")
    def test_diff_result_serializable(self) -> None:
        """Test diff result is JSON serializable."""
        import json

        from floe_core.rbac.diff import compute_rbac_diff

        expected = [
            {"kind": "ServiceAccount", "metadata": {"name": "sa1", "namespace": "ns"}},
        ]
        actual: list[dict[str, Any]] = []

        result = compute_rbac_diff(expected, actual, "manifest.yaml", "cluster")

        # Should not raise
        json_str = result.model_dump_json()
        data = json.loads(json_str)

        assert data["expected_source"] == "manifest.yaml"
        assert data["actual_source"] == "cluster"
        assert data["added_count"] == 1

    @pytest.mark.requirement("FR-063")
    def test_has_differences_unchanged_only_false(self) -> None:
        """Test has_differences returns False when all unchanged."""
        from floe_core.rbac.diff import compute_rbac_diff

        resources = [
            {"kind": "ServiceAccount", "metadata": {"name": "sa1", "namespace": "ns"}},
        ]

        result = compute_rbac_diff(resources, resources.copy(), "expected.yaml", "cluster")

        assert not result.has_differences()


class TestCompareValues:
    """Unit tests for _compare_values helper function."""

    @pytest.mark.requirement("FR-063")
    def test_compare_identical_dicts(self) -> None:
        """Test comparing identical dictionaries."""
        from floe_core.rbac.diff import _compare_values

        a = {"key": "value", "nested": {"inner": 1}}
        b = {"key": "value", "nested": {"inner": 1}}

        diffs = _compare_values(a, b)

        assert len(diffs) == 0

    @pytest.mark.requirement("FR-063")
    def test_compare_different_values(self) -> None:
        """Test comparing dictionaries with different values."""
        from floe_core.rbac.diff import _compare_values

        a = {"key": "value1"}
        b = {"key": "value2"}

        diffs = _compare_values(a, b)

        assert len(diffs) == 1
        assert "key" in diffs[0]
        assert "value1" in diffs[0]
        assert "value2" in diffs[0]

    @pytest.mark.requirement("FR-063")
    def test_compare_missing_field(self) -> None:
        """Test comparing dictionaries with missing field."""
        from floe_core.rbac.diff import _compare_values

        a = {"key1": "value", "key2": "value"}
        b = {"key1": "value"}

        diffs = _compare_values(a, b)

        assert len(diffs) == 1
        assert "key2" in diffs[0]
        assert "missing" in diffs[0].lower()

    @pytest.mark.requirement("FR-063")
    def test_compare_unexpected_field(self) -> None:
        """Test comparing dictionaries with unexpected field."""
        from floe_core.rbac.diff import _compare_values

        a = {"key1": "value"}
        b = {"key1": "value", "key2": "unexpected"}

        diffs = _compare_values(a, b)

        assert len(diffs) == 1
        assert "key2" in diffs[0]
        assert "unexpected" in diffs[0].lower()

    @pytest.mark.requirement("FR-063")
    def test_compare_list_length_mismatch(self) -> None:
        """Test comparing lists with different lengths."""
        from floe_core.rbac.diff import _compare_values

        a = [1, 2, 3]
        b = [1, 2]

        diffs = _compare_values(a, b)

        assert len(diffs) == 1
        assert "length" in diffs[0].lower()

    @pytest.mark.requirement("FR-063")
    def test_compare_type_mismatch(self) -> None:
        """Test comparing values with different types."""
        from floe_core.rbac.diff import _compare_values

        a = {"key": "string"}
        b = {"key": 123}

        diffs = _compare_values(a, b)

        assert len(diffs) == 1
        assert "type" in diffs[0].lower()

