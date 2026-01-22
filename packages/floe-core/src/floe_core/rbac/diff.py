"""RBAC Diff Functions.

This module provides functions for computing differences between
expected and actual RBAC configurations.

Task: T058
User Story: US6 - RBAC Audit and Validation
Requirements: FR-063

Example:
    >>> from floe_core.rbac.diff import compute_rbac_diff
    >>> expected = [{"kind": "ServiceAccount", "metadata": {"name": "sa1"}}]
    >>> actual = []
    >>> result = compute_rbac_diff(expected, actual, "file.yaml", "cluster:test")
    >>> result.has_differences()
    True
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floe_core.schemas.rbac_diff import RBACDiffResult, ResourceDiff


# Maximum number of resources that can be diffed in a single call.
# This prevents memory exhaustion from unbounded resource lists.
# 10,000 resources is generous for typical RBAC configurations.
MAX_RESOURCES_PER_DIFF = 10_000


# Metadata fields to ignore when comparing resources
_IGNORED_METADATA_FIELDS = frozenset(
    {
        "uid",
        "resourceVersion",
        "creationTimestamp",
        "generation",
        "managedFields",
        "selfLink",
    }
)


def _normalize_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Normalize a resource by removing non-essential metadata.

    Args:
        resource: K8s resource dictionary.

    Returns:
        Normalized resource dictionary for comparison.
    """
    result = dict(resource)

    # Normalize metadata
    if "metadata" in result:
        metadata = dict(result["metadata"])
        for field in _IGNORED_METADATA_FIELDS:
            metadata.pop(field, None)
        # Also remove annotations that are cluster-specific
        if "annotations" in metadata:
            annotations = dict(metadata["annotations"])
            annotations.pop("kubectl.kubernetes.io/last-applied-configuration", None)
            metadata["annotations"] = annotations if annotations else None
            if not metadata["annotations"]:
                del metadata["annotations"]
        result["metadata"] = metadata

    return result


def _compare_values(
    expected: Any,
    actual: Any,
    path: str = "",
) -> list[str]:
    """Recursively compare two values and return differences.

    Args:
        expected: Expected value.
        actual: Actual value.
        path: Current path in the structure.

    Returns:
        List of difference descriptions.
    """
    differences: list[str] = []

    if type(expected) != type(actual):  # noqa: E721
        differences.append(
            f"{path}: type mismatch (expected {type(expected).__name__}, "
            f"got {type(actual).__name__})"
        )
        return differences

    if isinstance(expected, dict):
        all_keys = set(expected.keys()) | set(actual.keys())
        for key in all_keys:
            new_path = f"{path}.{key}" if path else key
            if key not in expected:
                differences.append(f"{new_path}: unexpected field")
            elif key not in actual:
                differences.append(f"{new_path}: missing field")
            else:
                differences.extend(_compare_values(expected[key], actual[key], new_path))
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            differences.append(
                f"{path}: list length mismatch (expected {len(expected)}, got {len(actual)})"
            )
        else:
            for i, (exp_item, act_item) in enumerate(zip(expected, actual, strict=True)):
                differences.extend(_compare_values(exp_item, act_item, f"{path}[{i}]"))
    elif expected != actual:
        differences.append(f"{path}: expected {expected!r}, got {actual!r}")

    return differences


def compute_resource_diff(
    expected: dict[str, Any] | None,
    actual: dict[str, Any] | None,
    resource_kind: str,
) -> ResourceDiff:
    """Compute the diff between expected and actual resource.

    Args:
        expected: Expected resource specification (None if added).
        actual: Actual resource specification (None if removed).
        resource_kind: K8s resource kind.

    Returns:
        ResourceDiff describing the change.

    Example:
        >>> expected = {"metadata": {"name": "sa1"}}
        >>> actual = {"metadata": {"name": "sa1"}}
        >>> diff = compute_resource_diff(expected, actual, "ServiceAccount")
        >>> diff.change_type.value
        'unchanged'
    """
    from floe_core.schemas.rbac_diff import DiffChangeType, ResourceDiff

    # Handle added resource (expected but not actual)
    if expected is not None and actual is None:
        metadata = expected.get("metadata", {})
        return ResourceDiff(
            change_type=DiffChangeType.ADDED,
            resource_kind=resource_kind,
            resource_name=metadata.get("name", "unknown"),
            resource_namespace=metadata.get("namespace"),
            expected_value=expected,
            actual_value=None,
            diff_details=["Resource needs to be created"],
        )

    # Handle removed resource (actual but not expected)
    if expected is None and actual is not None:
        metadata = actual.get("metadata", {})
        return ResourceDiff(
            change_type=DiffChangeType.REMOVED,
            resource_kind=resource_kind,
            resource_name=metadata.get("name", "unknown"),
            resource_namespace=metadata.get("namespace"),
            expected_value=None,
            actual_value=actual,
            diff_details=["Resource should be removed"],
        )

    # Both exist - compare them
    if expected is None or actual is None:
        msg = "Both expected and actual cannot be None"
        raise ValueError(msg)

    metadata = expected.get("metadata", {})
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace")

    # Normalize for comparison
    norm_expected = _normalize_resource(expected)
    norm_actual = _normalize_resource(actual)

    # Compare
    differences = _compare_values(norm_expected, norm_actual)

    if not differences:
        return ResourceDiff(
            change_type=DiffChangeType.UNCHANGED,
            resource_kind=resource_kind,
            resource_name=name,
            resource_namespace=namespace,
            expected_value=expected,
            actual_value=actual,
            diff_details=[],
        )

    return ResourceDiff(
        change_type=DiffChangeType.MODIFIED,
        resource_kind=resource_kind,
        resource_name=name,
        resource_namespace=namespace,
        expected_value=expected,
        actual_value=actual,
        diff_details=differences,
    )


def compute_rbac_diff(
    expected_resources: list[dict[str, Any]],
    actual_resources: list[dict[str, Any]],
    expected_source: str,
    actual_source: str,
    *,
    max_resources: int = MAX_RESOURCES_PER_DIFF,
) -> RBACDiffResult:
    """Compute diff between expected and actual RBAC resources.

    Args:
        expected_resources: List of expected K8s resources.
        actual_resources: List of actual K8s resources from cluster.
        expected_source: Description of expected resources source.
        actual_source: Description of actual resources source.
        max_resources: Maximum total resources allowed (default: 10,000).
            Set to 0 to disable limit (not recommended for untrusted input).

    Returns:
        RBACDiffResult with all differences.

    Raises:
        ValueError: If total resources exceed max_resources limit.

    Example:
        >>> expected = [{"kind": "ServiceAccount", "metadata": {"name": "sa1"}}]
        >>> actual = []
        >>> result = compute_rbac_diff(expected, actual, "file.yaml", "cluster:test")
        >>> result.has_differences()
        True
    """
    from floe_core.schemas.rbac_diff import DiffChangeType, RBACDiffResult

    # Validate resource count to prevent memory exhaustion
    total_resources = len(expected_resources) + len(actual_resources)
    if max_resources > 0 and total_resources > max_resources:
        msg = (
            f"Resource count {total_resources} exceeds maximum allowed "
            f"{max_resources}. Split into smaller batches or increase limit."
        )
        raise ValueError(msg)

    diffs: list[ResourceDiff] = []
    added_count = 0
    removed_count = 0
    modified_count = 0

    # Build lookup maps keyed by (kind, namespace, name)
    def resource_key(r: dict[str, Any]) -> tuple[str, str | None, str]:
        kind = r.get("kind", "Unknown")
        metadata = r.get("metadata", {})
        name = metadata.get("name", "unknown")
        namespace = metadata.get("namespace")
        return (kind, namespace, name)

    expected_map = {resource_key(r): r for r in expected_resources}
    actual_map = {resource_key(r): r for r in actual_resources}

    all_keys = set(expected_map.keys()) | set(actual_map.keys())

    for key in sorted(all_keys):
        kind, _namespace, _name = key
        expected_res = expected_map.get(key)
        actual_res = actual_map.get(key)

        diff = compute_resource_diff(expected_res, actual_res, kind)
        diffs.append(diff)

        if diff.change_type == DiffChangeType.ADDED:
            added_count += 1
        elif diff.change_type == DiffChangeType.REMOVED:
            removed_count += 1
        elif diff.change_type == DiffChangeType.MODIFIED:
            modified_count += 1

    return RBACDiffResult(
        expected_source=expected_source,
        actual_source=actual_source,
        diffs=diffs,
        added_count=added_count,
        removed_count=removed_count,
        modified_count=modified_count,
    )
