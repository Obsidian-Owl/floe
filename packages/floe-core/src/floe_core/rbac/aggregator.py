"""RBACPermissionAggregator for cached permission aggregation.

This module provides the RBACPermissionAggregator class that aggregates
permissions with LRU caching to avoid redundant permission computations.

Task: T017
User Story: US2 - Fix N+1 Performance Issues
Requirements: FR-009

Example:
    >>> from floe_core.rbac.aggregator import RBACPermissionAggregator
    >>> aggregator = RBACPermissionAggregator()
    >>> permissions = aggregator.aggregate_permissions("admin", "secret/db-creds")
    >>> Permission.READ in permissions
    True
"""

from __future__ import annotations

from enum import Enum, auto
from functools import lru_cache
from typing import Any


class Permission(Enum):
    """Permission types for RBAC resources.

    Represents the standard Kubernetes RBAC verbs as permission types.
    """

    READ = auto()
    WRITE = auto()
    DELETE = auto()
    LIST = auto()
    WATCH = auto()


# Cache size for permission aggregation (FR-009)
_DEFAULT_CACHE_SIZE: int = 256


class RBACPermissionAggregator:
    """Aggregates permissions with LRU caching for performance.

    Provides cached permission lookups to avoid redundant computations
    when the same principal-resource combination is queried multiple times.

    The caching significantly improves performance when processing
    multiple data products that may reference the same secrets or
    principals.

    Attributes:
        _permission_rules: Internal mapping of permission rules.

    Contract:
        - MUST use LRU caching for aggregate_permissions() (FR-009)
        - MUST return consistent results for same inputs
        - MUST support cache invalidation via clear_cache()
        - MUST provide cache statistics via cache_info()

    Example:
        >>> aggregator = RBACPermissionAggregator()
        >>> perms1 = aggregator.aggregate_permissions("admin", "secret/db")
        >>> perms2 = aggregator.aggregate_permissions("admin", "secret/db")
        >>> # Second call uses cached result
        >>> aggregator.cache_info().hits
        1
    """

    def __init__(self, cache_size: int = _DEFAULT_CACHE_SIZE) -> None:
        """Initialize the aggregator with specified cache size.

        Args:
            cache_size: Maximum number of permission results to cache.
                Defaults to 256.
        """
        self._cache_size = cache_size
        self._permission_rules: dict[str, dict[str, set[Permission]]] = {}

        # Create cached method with specified size
        # Using closure to bind cache_size at initialization
        self._cached_aggregate = lru_cache(maxsize=cache_size)(self._aggregate_permissions_impl)

    def add_permission_rule(
        self,
        principal: str,
        resource: str,
        permissions: set[Permission],
    ) -> None:
        """Add a permission rule for a principal-resource combination.

        Args:
            principal: The principal (user, service account, etc.).
            resource: The resource path (e.g., "secret/db-creds").
            permissions: Set of permissions to grant.

        Contract:
            - MUST merge with existing permissions (additive)
            - MUST clear cache when rules change
        """
        if principal not in self._permission_rules:
            self._permission_rules[principal] = {}

        if resource not in self._permission_rules[principal]:
            self._permission_rules[principal][resource] = set()

        self._permission_rules[principal][resource].update(permissions)

        # Clear cache when rules change
        self.clear_cache()

    def aggregate_permissions(
        self,
        principal: str,
        resource: str,
    ) -> frozenset[Permission]:
        """Aggregate permissions for a principal-resource combination.

        Uses LRU caching to avoid redundant lookups. The cache key is
        the (principal, resource) tuple.

        Args:
            principal: The principal to check permissions for.
            resource: The resource to check access to.

        Returns:
            Frozenset of Permission values granted to the principal
            for the resource. Returns empty frozenset if no permissions.

        Contract:
            - MUST use LRU caching for repeated lookups (FR-009)
            - MUST return frozenset (hashable for caching)
            - MUST return empty frozenset for unknown principals/resources

        Example:
            >>> aggregator = RBACPermissionAggregator()
            >>> aggregator.add_permission_rule(
            ...     "admin", "secret/db", {Permission.READ, Permission.WRITE}
            ... )
            >>> perms = aggregator.aggregate_permissions("admin", "secret/db")
            >>> Permission.READ in perms
            True
        """
        return self._cached_aggregate(principal, resource)

    def _aggregate_permissions_impl(
        self,
        principal: str,
        resource: str,
    ) -> frozenset[Permission]:
        """Implementation of permission aggregation (called by cached wrapper).

        Args:
            principal: The principal to check permissions for.
            resource: The resource to check access to.

        Returns:
            Frozenset of Permission values.
        """
        principal_rules = self._permission_rules.get(principal)
        if principal_rules is None:
            return frozenset()

        permissions = principal_rules.get(resource)
        if permissions is None:
            return frozenset()

        return frozenset(permissions)

    def clear_cache(self) -> None:
        """Clear the permission cache.

        Should be called when permission rules are modified to ensure
        subsequent lookups reflect the changes.

        Contract:
            - MUST clear all cached permission results
            - MUST be called automatically when rules change
        """
        self._cached_aggregate.cache_clear()

    def cache_info(self) -> Any:
        """Get cache statistics.

        Returns:
            Named tuple with hits, misses, maxsize, currsize.

        Example:
            >>> info = aggregator.cache_info()
            >>> info.hits
            10
            >>> info.misses
            5
        """
        return self._cached_aggregate.cache_info()
