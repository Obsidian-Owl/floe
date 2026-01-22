"""Unit tests for RBACPermissionAggregator.

Task: T017
User Story: US2 - Fix N+1 Performance Issues
Requirements: FR-009
"""

from __future__ import annotations

import pytest

from floe_core.rbac.aggregator import (
    Permission,
    RBACPermissionAggregator,
    _DEFAULT_CACHE_SIZE,
)


class TestRBACPermissionAggregator:
    """Tests for RBACPermissionAggregator class."""

    @pytest.mark.requirement("FR-009")
    def test_init_with_default_cache_size(self) -> None:
        """Test aggregator initializes with default cache size."""
        aggregator = RBACPermissionAggregator()
        info = aggregator.cache_info()
        assert info.maxsize == _DEFAULT_CACHE_SIZE

    @pytest.mark.requirement("FR-009")
    def test_init_with_custom_cache_size(self) -> None:
        """Test aggregator initializes with custom cache size."""
        custom_size = 100
        aggregator = RBACPermissionAggregator(cache_size=custom_size)
        info = aggregator.cache_info()
        assert info.maxsize == custom_size

    @pytest.mark.requirement("FR-009")
    def test_aggregate_permissions_returns_empty_for_unknown_principal(
        self,
    ) -> None:
        """Test aggregate_permissions returns empty frozenset for unknown principal."""
        aggregator = RBACPermissionAggregator()
        result = aggregator.aggregate_permissions("unknown", "resource")
        assert result == frozenset()

    @pytest.mark.requirement("FR-009")
    def test_aggregate_permissions_returns_empty_for_unknown_resource(
        self,
    ) -> None:
        """Test aggregate_permissions returns empty frozenset for unknown resource."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule(
            "admin", "known-resource", {Permission.READ}
        )
        result = aggregator.aggregate_permissions("admin", "unknown-resource")
        assert result == frozenset()

    @pytest.mark.requirement("FR-009")
    def test_add_permission_rule_and_aggregate(self) -> None:
        """Test adding permission rules and aggregating them."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule(
            "admin", "secret/db", {Permission.READ, Permission.WRITE}
        )

        result = aggregator.aggregate_permissions("admin", "secret/db")
        assert Permission.READ in result
        assert Permission.WRITE in result
        assert len(result) == 2

    @pytest.mark.requirement("FR-009")
    def test_add_permission_rule_is_additive(self) -> None:
        """Test adding multiple permission rules is additive."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule("admin", "secret/db", {Permission.READ})
        aggregator.add_permission_rule("admin", "secret/db", {Permission.WRITE})

        result = aggregator.aggregate_permissions("admin", "secret/db")
        assert Permission.READ in result
        assert Permission.WRITE in result

    @pytest.mark.requirement("FR-009")
    def test_aggregate_permissions_uses_caching(self) -> None:
        """Test aggregate_permissions uses LRU caching."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule("admin", "secret/db", {Permission.READ})

        # First call - cache miss
        aggregator.aggregate_permissions("admin", "secret/db")
        info1 = aggregator.cache_info()
        assert info1.misses == 1
        assert info1.hits == 0

        # Second call - cache hit
        aggregator.aggregate_permissions("admin", "secret/db")
        info2 = aggregator.cache_info()
        assert info2.misses == 1
        assert info2.hits == 1

    @pytest.mark.requirement("FR-009")
    def test_clear_cache_resets_cache_stats(self) -> None:
        """Test clear_cache resets the cache."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule("admin", "secret/db", {Permission.READ})

        # Build up some cache
        aggregator.aggregate_permissions("admin", "secret/db")
        aggregator.aggregate_permissions("admin", "secret/db")

        info_before = aggregator.cache_info()
        assert info_before.hits == 1

        # Clear and verify
        aggregator.clear_cache()
        info_after = aggregator.cache_info()
        assert info_after.hits == 0
        assert info_after.misses == 0
        assert info_after.currsize == 0

    @pytest.mark.requirement("FR-009")
    def test_add_permission_rule_clears_cache(self) -> None:
        """Test adding a permission rule clears the cache."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule("admin", "secret/db", {Permission.READ})

        # Build cache
        aggregator.aggregate_permissions("admin", "secret/db")
        info1 = aggregator.cache_info()
        assert info1.currsize == 1

        # Add new rule - should clear cache
        aggregator.add_permission_rule("admin", "secret/other", {Permission.WRITE})
        info2 = aggregator.cache_info()
        assert info2.currsize == 0

    @pytest.mark.requirement("FR-009")
    def test_aggregate_permissions_returns_frozenset(self) -> None:
        """Test aggregate_permissions returns a frozenset (hashable)."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule("admin", "secret/db", {Permission.READ})

        result = aggregator.aggregate_permissions("admin", "secret/db")
        assert isinstance(result, frozenset)
        # Frozensets are hashable
        hash(result)

    @pytest.mark.requirement("FR-009")
    def test_multiple_principals_and_resources(self) -> None:
        """Test handling multiple principals and resources."""
        aggregator = RBACPermissionAggregator()
        aggregator.add_permission_rule("admin", "secret/db", {Permission.READ, Permission.WRITE})
        aggregator.add_permission_rule("reader", "secret/db", {Permission.READ})
        aggregator.add_permission_rule("admin", "secret/api", {Permission.READ})

        # Admin has READ + WRITE on db
        admin_db = aggregator.aggregate_permissions("admin", "secret/db")
        assert Permission.READ in admin_db
        assert Permission.WRITE in admin_db

        # Reader has only READ on db
        reader_db = aggregator.aggregate_permissions("reader", "secret/db")
        assert Permission.READ in reader_db
        assert Permission.WRITE not in reader_db

        # Admin has only READ on api
        admin_api = aggregator.aggregate_permissions("admin", "secret/api")
        assert Permission.READ in admin_api
        assert Permission.WRITE not in admin_api

    @pytest.mark.requirement("FR-009")
    def test_cache_info_returns_expected_attributes(self) -> None:
        """Test cache_info returns expected named tuple attributes."""
        aggregator = RBACPermissionAggregator()
        info = aggregator.cache_info()

        # Standard lru_cache info attributes
        assert hasattr(info, "hits")
        assert hasattr(info, "misses")
        assert hasattr(info, "maxsize")
        assert hasattr(info, "currsize")

    @pytest.mark.requirement("FR-009")
    def test_all_permission_types(self) -> None:
        """Test all Permission enum values can be used."""
        aggregator = RBACPermissionAggregator()
        all_permissions = {
            Permission.READ,
            Permission.WRITE,
            Permission.DELETE,
            Permission.LIST,
            Permission.WATCH,
        }
        aggregator.add_permission_rule("superuser", "resource", all_permissions)

        result = aggregator.aggregate_permissions("superuser", "resource")
        assert result == frozenset(all_permissions)


class TestPermissionEnum:
    """Tests for Permission enum."""

    def test_permission_enum_values(self) -> None:
        """Test Permission enum has expected values."""
        assert Permission.READ is not None
        assert Permission.WRITE is not None
        assert Permission.DELETE is not None
        assert Permission.LIST is not None
        assert Permission.WATCH is not None

    def test_permission_enum_count(self) -> None:
        """Test Permission enum has 5 values."""
        assert len(Permission) == 5
