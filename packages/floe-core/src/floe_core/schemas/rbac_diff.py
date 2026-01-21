"""RBAC Diff Models.

This module provides Pydantic models for comparing expected vs actual
RBAC configurations, including change types and diff results.

Task: T058
User Story: US6 - RBAC Audit and Validation
Requirements: FR-063

Example:
    >>> from floe_core.schemas.rbac_diff import (
    ...     DiffChangeType,
    ...     ResourceDiff,
    ...     RBACDiffResult,
    ... )
    >>> diff = ResourceDiff(
    ...     change_type=DiffChangeType.MODIFIED,
    ...     resource_kind="Role",
    ...     resource_name="my-role",
    ...     resource_namespace="default",
    ...     diff_details=["rules[0].verbs: expected ['get'], got ['get', 'list']"],
    ... )
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiffChangeType(str, Enum):
    """Types of changes in a diff.

    Used to categorize how a resource differs between expected and actual.
    """

    ADDED = "added"
    """Resource needs to be created (expected but not actual)."""

    REMOVED = "removed"
    """Resource should be removed (actual but not expected)."""

    MODIFIED = "modified"
    """Resource exists but differs from expected."""

    UNCHANGED = "unchanged"
    """Resource matches expected state."""


class ResourceDiff(BaseModel):
    """A single resource difference between expected and actual state.

    Attributes:
        change_type: Type of change (added, removed, modified, unchanged).
        resource_kind: K8s resource kind (ServiceAccount, Role, etc.).
        resource_name: Name of the resource.
        resource_namespace: Namespace of the resource (None for cluster-scoped).
        expected_value: Expected resource specification.
        actual_value: Actual resource specification from cluster.
        diff_details: List of specific differences found.

    Example:
        >>> diff = ResourceDiff(
        ...     change_type=DiffChangeType.MODIFIED,
        ...     resource_kind="Role",
        ...     resource_name="my-role",
        ...     resource_namespace="default",
        ...     diff_details=["rules[0].verbs: expected ['get'], got ['get', 'list']"],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    change_type: DiffChangeType = Field(
        ...,
        description="Type of change",
    )
    resource_kind: str = Field(
        ...,
        description="K8s resource kind",
    )
    resource_name: str = Field(
        ...,
        description="Name of the resource",
    )
    resource_namespace: str | None = Field(
        default=None,
        description="Namespace of the resource",
    )
    expected_value: dict[str, Any] | None = Field(
        default=None,
        description="Expected resource specification",
    )
    actual_value: dict[str, Any] | None = Field(
        default=None,
        description="Actual resource specification",
    )
    diff_details: list[str] = Field(
        default_factory=list,
        description="Specific differences found",
    )


class RBACDiffResult(BaseModel):
    """Result of comparing expected vs actual RBAC configuration.

    Attributes:
        generated_at: Timestamp when diff was computed.
        expected_source: Source of expected resources (file path or description).
        actual_source: Source of actual resources (cluster name or file path).
        diffs: List of resource differences.
        added_count: Number of resources to be added.
        removed_count: Number of resources to be removed.
        modified_count: Number of resources that differ.

    Example:
        >>> result = RBACDiffResult(
        ...     expected_source="manifest.yaml",
        ...     actual_source="cluster:my-cluster",
        ...     diffs=[],
        ...     added_count=0,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Diff computation timestamp",
    )
    expected_source: str = Field(
        ...,
        description="Source of expected resources",
    )
    actual_source: str = Field(
        ...,
        description="Source of actual resources",
    )
    diffs: list[ResourceDiff] = Field(
        default_factory=list,
        description="List of resource differences",
    )
    added_count: int = Field(
        default=0,
        ge=0,
        description="Resources to be added",
    )
    removed_count: int = Field(
        default=0,
        ge=0,
        description="Resources to be removed",
    )
    modified_count: int = Field(
        default=0,
        ge=0,
        description="Resources that differ",
    )

    def has_differences(self) -> bool:
        """Check if there are any actual differences.

        Returns:
            True if any diff has a non-UNCHANGED change type.
        """
        return any(d.change_type != DiffChangeType.UNCHANGED for d in self.diffs)

    def diffs_by_change_type(self) -> dict[DiffChangeType, list[ResourceDiff]]:
        """Group diffs by change type.

        Returns:
            Dictionary mapping change types to lists of diffs.
        """
        result: dict[DiffChangeType, list[ResourceDiff]] = {
            change_type: [] for change_type in DiffChangeType
        }
        for diff in self.diffs:
            result[diff.change_type].append(diff)
        return result

    def diffs_by_resource_kind(self) -> dict[str, list[ResourceDiff]]:
        """Group diffs by resource kind.

        Returns:
            Dictionary mapping resource kinds to lists of diffs.
        """
        result: dict[str, list[ResourceDiff]] = {}
        for diff in self.diffs:
            if diff.resource_kind not in result:
                result[diff.resource_kind] = []
            result[diff.resource_kind].append(diff)
        return result
