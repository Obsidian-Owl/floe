"""Golden tests for diff_command() behavior preservation.

This test file captures the exact output of diff-related functions to enable
safe refactoring. If behavior changes after refactoring, these tests will fail.

Task: T019
User Story: US3 - Reduce Code Complexity
Requirements: FR-010

Usage:
    # Run tests normally
    pytest packages/floe-core/tests/unit/cli/rbac/test_diff_golden.py -v

    # Update golden fixtures (after intentional behavior changes)
    UPDATE_GOLDEN=1 pytest packages/floe-core/tests/unit/cli/rbac/test_diff_golden.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# Determine if we should update fixtures
UPDATE_GOLDEN = os.environ.get("UPDATE_GOLDEN", "0") == "1"

# Golden fixtures directory
# Path: tests/unit/cli/rbac/test_diff_golden.py
# Need: packages/floe-core/tests/unit/cli/rbac -> floe (7 parents)
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent.parent.parent
    / "testing"
    / "fixtures"
    / "golden"
    / "cli_rbac"
)


def _save_golden_fixture(
    fixture_path: Path, name: str, output: Any, function_name: str = ""
) -> None:
    """Save output as a golden fixture."""
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    output_json = json.dumps(output, sort_keys=True, default=str)
    checksum = hashlib.sha256(output_json.encode()).hexdigest()[:16]

    data = {
        "name": name,
        "function_name": function_name,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "checksum": checksum,
        "output": output,
    }
    fixture_path.write_text(json.dumps(data, indent=2, default=str))


def _normalize_for_comparison(data: Any) -> Any:
    """Remove timestamp fields that change between runs and sort lists of strings."""
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            # Skip timestamp fields
            if k in ("generated_at", "captured_at", "timestamp"):
                continue
            result[k] = _normalize_for_comparison(v)
        return result
    elif isinstance(data, list):
        normalized = [_normalize_for_comparison(item) for item in data]
        # Sort if all items are strings (order may not be deterministic)
        if all(isinstance(item, str) for item in normalized):
            return sorted(normalized)
        return normalized
    return data


def _assert_golden_match(
    actual: Any, fixture_path: Path, *, update: bool = False
) -> None:
    """Assert that actual output matches the golden fixture."""
    if update:
        _save_golden_fixture(fixture_path, fixture_path.stem, actual)
        return

    if not fixture_path.exists():
        pytest.fail(
            f"Golden fixture not found: {fixture_path}\nRun with UPDATE_GOLDEN=1 to create it."
        )

    data = json.loads(fixture_path.read_text())
    expected = data["output"]

    # Normalize both for comparison (remove timestamps)
    actual_normalized = _normalize_for_comparison(actual)
    expected_normalized = _normalize_for_comparison(expected)

    if actual_normalized != expected_normalized:
        actual_json = json.dumps(
            actual_normalized, indent=2, sort_keys=True, default=str
        )
        expected_json = json.dumps(
            expected_normalized, indent=2, sort_keys=True, default=str
        )

        pytest.fail(
            f"Golden test failed: output does not match fixture\n"
            f"Fixture: {fixture_path}\n"
            f"\nExpected:\n{expected_json}\n\nActual:\n{actual_json}"
        )


# Test data fixtures
SAMPLE_SERVICE_ACCOUNT: dict[str, Any] = {
    "kind": "ServiceAccount",
    "apiVersion": "v1",
    "metadata": {"name": "floe-worker", "namespace": "floe"},
}

SAMPLE_ROLE: dict[str, Any] = {
    "kind": "Role",
    "apiVersion": "rbac.authorization.k8s.io/v1",
    "metadata": {"name": "floe-secret-reader", "namespace": "floe"},
    "rules": [
        {
            "apiGroups": [""],
            "resources": ["secrets"],
            "verbs": ["get"],
            "resourceNames": ["db-creds"],
        }
    ],
}

SAMPLE_ROLE_BINDING: dict[str, Any] = {
    "kind": "RoleBinding",
    "apiVersion": "rbac.authorization.k8s.io/v1",
    "metadata": {"name": "floe-worker-secret-binding", "namespace": "floe"},
    "roleRef": {
        "apiGroup": "rbac.authorization.k8s.io",
        "kind": "Role",
        "name": "floe-secret-reader",
    },
    "subjects": [
        {"kind": "ServiceAccount", "name": "floe-worker", "namespace": "floe"}
    ],
}


class TestDiffCommandGolden:
    """Golden tests for RBAC diff functions.

    These tests capture the exact behavior of diff functions before refactoring.
    After refactoring, run these tests to verify behavior is preserved.
    """

    @pytest.mark.requirement("FR-010")
    def test_compute_resource_diff_added(self) -> None:
        """Golden test: compute_resource_diff when resource is added (expected only)."""
        from floe_core.rbac.diff import compute_resource_diff

        result = compute_resource_diff(
            expected=SAMPLE_SERVICE_ACCOUNT,
            actual=None,
            resource_kind="ServiceAccount",
        )

        # Convert to dict for comparison
        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "resource_diff_added.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compute_resource_diff_removed(self) -> None:
        """Golden test: compute_resource_diff when resource is removed (actual only)."""
        from floe_core.rbac.diff import compute_resource_diff

        result = compute_resource_diff(
            expected=None,
            actual=SAMPLE_SERVICE_ACCOUNT,
            resource_kind="ServiceAccount",
        )

        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "resource_diff_removed.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compute_resource_diff_unchanged(self) -> None:
        """Golden test: compute_resource_diff when resource is unchanged."""
        from floe_core.rbac.diff import compute_resource_diff

        result = compute_resource_diff(
            expected=SAMPLE_ROLE,
            actual=SAMPLE_ROLE,
            resource_kind="Role",
        )

        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "resource_diff_unchanged.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compute_resource_diff_modified(self) -> None:
        """Golden test: compute_resource_diff when resource is modified."""
        from floe_core.rbac.diff import compute_resource_diff

        modified_role = dict(SAMPLE_ROLE)
        modified_role["rules"] = [
            {
                "apiGroups": [""],
                "resources": ["secrets"],
                "verbs": ["get", "list"],  # Added 'list'
                "resourceNames": ["db-creds", "api-key"],  # Added 'api-key'
            }
        ]

        result = compute_resource_diff(
            expected=SAMPLE_ROLE,
            actual=modified_role,
            resource_kind="Role",
        )

        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "resource_diff_modified.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compute_rbac_diff_full_scenario(self) -> None:
        """Golden test: compute_rbac_diff with mixed changes (add/remove/modify/unchanged)."""
        from floe_core.rbac.diff import compute_rbac_diff

        # Expected: SA + Role (with original rules) + new RoleBinding
        expected_resources: list[dict[str, Any]] = [
            SAMPLE_SERVICE_ACCOUNT,
            SAMPLE_ROLE,
            {
                "kind": "RoleBinding",
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "metadata": {"name": "new-binding", "namespace": "floe"},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": "floe-secret-reader",
                },
                "subjects": [
                    {"kind": "ServiceAccount", "name": "new-sa", "namespace": "floe"}
                ],
            },
        ]

        # Actual: SA unchanged + Role modified + extra ClusterRole
        modified_role = dict(SAMPLE_ROLE)
        modified_role["rules"] = [
            {
                "apiGroups": [""],
                "resources": ["secrets"],
                "verbs": ["get", "list"],
                "resourceNames": ["db-creds"],
            }
        ]

        actual_resources: list[dict[str, Any]] = [
            SAMPLE_SERVICE_ACCOUNT,  # Unchanged
            modified_role,  # Modified
            {  # Extra resource to be removed
                "kind": "Role",
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "metadata": {"name": "orphan-role", "namespace": "floe"},
                "rules": [],
            },
        ]

        result = compute_rbac_diff(
            expected_resources=expected_resources,
            actual_resources=actual_resources,
            expected_source="test/manifests",
            actual_source="cluster:floe",
        )

        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "rbac_diff_full_scenario.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compute_rbac_diff_empty_expected(self) -> None:
        """Golden test: compute_rbac_diff with empty expected (all to be removed)."""
        from floe_core.rbac.diff import compute_rbac_diff

        result = compute_rbac_diff(
            expected_resources=[],
            actual_resources=[SAMPLE_SERVICE_ACCOUNT, SAMPLE_ROLE],
            expected_source="test/empty",
            actual_source="cluster:floe",
        )

        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "rbac_diff_empty_expected.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compute_rbac_diff_empty_actual(self) -> None:
        """Golden test: compute_rbac_diff with empty actual (all to be created)."""
        from floe_core.rbac.diff import compute_rbac_diff

        result = compute_rbac_diff(
            expected_resources=[
                SAMPLE_SERVICE_ACCOUNT,
                SAMPLE_ROLE,
                SAMPLE_ROLE_BINDING,
            ],
            actual_resources=[],
            expected_source="test/manifests",
            actual_source="cluster:empty",
        )

        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "rbac_diff_empty_actual.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compute_rbac_diff_no_differences(self) -> None:
        """Golden test: compute_rbac_diff when expected equals actual."""
        from floe_core.rbac.diff import compute_rbac_diff

        resources: list[dict[str, Any]] = [
            SAMPLE_SERVICE_ACCOUNT,
            SAMPLE_ROLE,
            SAMPLE_ROLE_BINDING,
        ]

        result = compute_rbac_diff(
            expected_resources=resources,
            actual_resources=resources,
            expected_source="test/manifests",
            actual_source="cluster:floe",
        )

        result_dict = result.model_dump()

        fixture_path = FIXTURES_DIR / "rbac_diff_no_differences.json"
        _assert_golden_match(result_dict, fixture_path, update=UPDATE_GOLDEN)


class TestDiffHelperGolden:
    """Golden tests for diff helper functions."""

    @pytest.mark.requirement("FR-010")
    def test_normalize_resource(self) -> None:
        """Golden test: _normalize_resource removes cluster-specific metadata."""
        from floe_core.rbac.diff import _normalize_resource

        resource_with_metadata = {
            "kind": "ServiceAccount",
            "apiVersion": "v1",
            "metadata": {
                "name": "test-sa",
                "namespace": "default",
                "uid": "abc123",
                "resourceVersion": "12345",
                "creationTimestamp": "2026-01-22T00:00:00Z",
                "generation": 1,
                "annotations": {
                    "kubectl.kubernetes.io/last-applied-configuration": "{}",
                    "custom-annotation": "value",
                },
            },
        }

        result = _normalize_resource(resource_with_metadata)

        fixture_path = FIXTURES_DIR / "normalize_resource.json"
        _assert_golden_match(result, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compare_values_identical(self) -> None:
        """Golden test: _compare_values with identical values."""
        from floe_core.rbac.diff import _compare_values

        result = _compare_values(
            expected={"a": 1, "b": [1, 2, 3]},
            actual={"a": 1, "b": [1, 2, 3]},
        )

        fixture_path = FIXTURES_DIR / "compare_values_identical.json"
        _assert_golden_match(result, fixture_path, update=UPDATE_GOLDEN)

    @pytest.mark.requirement("FR-010")
    def test_compare_values_different(self) -> None:
        """Golden test: _compare_values with different values."""
        from floe_core.rbac.diff import _compare_values

        result = _compare_values(
            expected={"a": 1, "b": [1, 2, 3], "c": "original"},
            actual={"a": 2, "b": [1, 2, 4], "d": "extra"},
        )

        fixture_path = FIXTURES_DIR / "compare_values_different.json"
        _assert_golden_match(result, fixture_path, update=UPDATE_GOLDEN)


__all__: list[str] = ["TestDiffCommandGolden", "TestDiffHelperGolden"]
