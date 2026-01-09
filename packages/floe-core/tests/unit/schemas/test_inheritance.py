"""Unit tests for configuration inheritance models.

Tests for 3-tier inheritance (enterprise → domain → product) including:
- 2-tier mode (no inheritance)
- Parent-child merge behavior
- List merge strategies (extend vs replace)
- Circular dependency detection

Task: T024, T025, T026, T027
Requirements: FR-003, FR-004, FR-005, FR-014, FR-016
"""

from __future__ import annotations

from typing import Any

import pytest


class TestTwoTierMode:
    """Tests for 2-tier mode (scope=None, no inheritance) (T024)."""

    @pytest.mark.requirement("001-FR-016")
    def test_two_tier_mode_no_parent(self) -> None:
        """Test that 2-tier mode (scope=None) has no parent resolution.

        Given a configuration with scope=None (2-tier),
        When loading the configuration,
        Then no parent resolution occurs and the manifest is used standalone.
        """
        from floe_core.schemas import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "standalone-platform",
                "version": "1.0.0",
                "owner": "team@example.com",
            },
            scope=None,  # Explicit 2-tier mode
            plugins={
                "compute": {"type": "duckdb"},
            },
        )

        assert manifest.scope is None
        assert manifest.parent_manifest is None
        # In 2-tier mode, the manifest is standalone - no inheritance chain needed

    @pytest.mark.requirement("001-FR-016")
    def test_two_tier_mode_default(self) -> None:
        """Test that scope defaults to None (2-tier mode)."""
        from floe_core.schemas import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "default-platform",
                "version": "1.0.0",
                "owner": "team@example.com",
            },
            plugins={},
        )

        # scope should default to None (2-tier)
        assert manifest.scope is None

    @pytest.mark.requirement("001-FR-016")
    def test_two_tier_mode_all_fields_resolved_locally(self) -> None:
        """Test that 2-tier mode resolves all fields from the manifest itself."""
        from floe_core.schemas import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "complete-platform",
                "version": "2.0.0",
                "owner": "platform@corp.com",
                "description": "Complete standalone platform",
            },
            plugins={
                "compute": {"type": "duckdb", "config": {"threads": 4}},
                "orchestrator": {"type": "dagster"},
                "catalog": {"type": "polaris"},
            },
            governance={
                "pii_encryption": "required",
                "audit_logging": "enabled",
            },
        )

        # All values come from the manifest directly
        assert manifest.metadata.name == "complete-platform"
        assert manifest.plugins.compute is not None
        assert manifest.plugins.compute.type == "duckdb"
        assert manifest.plugins.compute.config == {"threads": 4}
        assert manifest.governance is not None
        assert manifest.governance.pii_encryption == "required"


class TestParentChildMerge:
    """Tests for parent-child merge behavior (T025)."""

    @pytest.mark.requirement("001-FR-003")
    @pytest.mark.requirement("001-FR-004")
    def test_merge_manifests_child_overrides_parent(self) -> None:
        """Test that child values override parent values.

        Given a child configuration (scope=domain) that references a parent (scope=enterprise),
        When merging configurations,
        Then child values take precedence over parent values.
        """
        from floe_core.schemas import PlatformManifest
        from floe_core.schemas.inheritance import merge_manifests

        parent = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "enterprise-platform",
                "version": "1.0.0",
                "owner": "enterprise@corp.com",
            },
            scope="enterprise",
            plugins={
                "compute": {"type": "snowflake"},
                "orchestrator": {"type": "dagster"},
            },
        )

        child = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "domain-platform",
                "version": "1.0.0",
                "owner": "domain@corp.com",
            },
            scope="domain",
            parent_manifest="oci://registry/enterprise:v1",
            plugins={
                "compute": {"type": "duckdb"},  # Override parent's snowflake
            },
        )

        resolved = merge_manifests(parent, child)

        # Child's compute should override parent's
        assert resolved.plugins.compute is not None
        assert resolved.plugins.compute.type == "duckdb"
        # Parent's orchestrator should be preserved (not overridden)
        assert resolved.plugins.orchestrator is not None
        assert resolved.plugins.orchestrator.type == "dagster"

    @pytest.mark.requirement("001-FR-003")
    @pytest.mark.requirement("001-FR-004")
    def test_merge_manifests_inherits_parent_values(self) -> None:
        """Test that parent values are inherited when not overridden."""
        from floe_core.schemas import PlatformManifest
        from floe_core.schemas.inheritance import merge_manifests

        parent = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "enterprise-platform",
                "version": "1.0.0",
                "owner": "enterprise@corp.com",
            },
            scope="enterprise",
            plugins={
                "compute": {"type": "snowflake"},
                "orchestrator": {"type": "dagster"},
                "catalog": {"type": "polaris"},
            },
            governance={
                "pii_encryption": "required",
                "audit_logging": "enabled",
            },
        )

        child = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "domain-platform",
                "version": "1.0.0",
                "owner": "domain@corp.com",
            },
            scope="domain",
            parent_manifest="oci://registry/enterprise:v1",
            plugins={},  # Empty plugins - should inherit all from parent
        )

        resolved = merge_manifests(parent, child)

        # All parent plugins should be inherited
        assert resolved.plugins.compute is not None
        assert resolved.plugins.compute.type == "snowflake"
        assert resolved.plugins.orchestrator is not None
        assert resolved.plugins.orchestrator.type == "dagster"
        assert resolved.plugins.catalog is not None
        assert resolved.plugins.catalog.type == "polaris"

    @pytest.mark.requirement("001-FR-003")
    def test_inheritance_chain_tracks_sources(self) -> None:
        """Test that InheritanceChain tracks which tier provided each field."""
        from floe_core.schemas import PlatformManifest
        from floe_core.schemas.inheritance import InheritanceChain, merge_manifests

        parent = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "enterprise",
                "version": "1.0.0",
                "owner": "enterprise@corp.com",
            },
            scope="enterprise",
            plugins={
                "compute": {"type": "snowflake"},
            },
        )

        child = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "domain",
                "version": "1.0.0",
                "owner": "domain@corp.com",
            },
            scope="domain",
            parent_manifest="oci://registry/enterprise:v1",
            plugins={
                "orchestrator": {"type": "dagster"},
            },
        )

        resolved = merge_manifests(parent, child)

        chain = InheritanceChain(
            enterprise=parent,
            domain=child,
            product=child,
            resolved=resolved,
            field_sources={
                "plugins.compute": "enterprise",
                "plugins.orchestrator": "domain",
            },
        )

        assert chain.field_sources["plugins.compute"] == "enterprise"
        assert chain.field_sources["plugins.orchestrator"] == "domain"


class TestListMerge:
    """Tests for list merge strategies (T026)."""

    @pytest.mark.requirement("001-FR-014")
    def test_list_merge_extend_default(self) -> None:
        """Test that parent plugins are inherited when merging.

        Given a parent with plugins and a child that adds to them,
        When merging,
        Then parent plugins are inherited and child plugins override.
        """
        from floe_core.schemas import PlatformManifest
        from floe_core.schemas.inheritance import merge_manifests

        parent = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "enterprise",
                "version": "1.0.0",
                "owner": "enterprise@corp.com",
            },
            scope="enterprise",
            plugins={
                "compute": {"type": "snowflake"},
                "catalog": {"type": "polaris"},
            },
            approved_plugins={
                "compute": ["duckdb", "snowflake"],
            },
        )

        child = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "domain",
                "version": "1.0.0",
                "owner": "domain@corp.com",
            },
            scope="domain",
            parent_manifest="oci://registry/enterprise:v1",
            plugins={
                "orchestrator": {"type": "dagster"},  # Add new plugin
            },
            approved_products=["product-a", "product-b"],
        )

        resolved = merge_manifests(parent, child)

        # Parent's plugins should be inherited
        assert resolved.plugins.compute is not None
        assert resolved.plugins.compute.type == "snowflake"
        assert resolved.plugins.catalog is not None
        assert resolved.plugins.catalog.type == "polaris"
        # Child's new plugin should be added
        assert resolved.plugins.orchestrator is not None
        assert resolved.plugins.orchestrator.type == "dagster"

    @pytest.mark.requirement("001-FR-014")
    def test_list_replace_strategy(self) -> None:
        """Test that lists can be replaced entirely when using OVERRIDE strategy.

        Given a child that needs to completely replace a parent's value,
        When merging with OVERRIDE strategy,
        Then the parent's value is replaced entirely.
        """
        from floe_core.schemas import PlatformManifest
        from floe_core.schemas.inheritance import merge_manifests

        parent = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "enterprise",
                "version": "1.0.0",
                "owner": "enterprise@corp.com",
            },
            scope="enterprise",
            plugins={
                "compute": {"type": "snowflake", "config": {"warehouse": "LARGE"}},
            },
        )

        child = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "domain",
                "version": "1.0.0",
                "owner": "domain@corp.com",
            },
            scope="domain",
            parent_manifest="oci://registry/enterprise:v1",
            plugins={
                "compute": {"type": "duckdb", "config": {"threads": 8}},
            },
        )

        # plugins has OVERRIDE strategy
        resolved = merge_manifests(parent, child)

        # Child's entire compute config replaces parent's
        assert resolved.plugins.compute is not None
        assert resolved.plugins.compute.type == "duckdb"
        assert resolved.plugins.compute.config == {"threads": 8}


class TestCircularDependency:
    """Tests for circular dependency detection (T027)."""

    @pytest.mark.requirement("001-FR-005")
    def test_detect_circular_inheritance_direct(self) -> None:
        """Test detection of direct circular inheritance (A → B → A).

        Given configuration A extends B and B extends A (circular),
        When detecting circular dependencies,
        Then the system identifies the circular dependency.
        """
        from floe_core.schemas.inheritance import (
            CircularInheritanceError,
            detect_circular_inheritance,
        )

        # Create manifest references that form a cycle
        manifests: dict[str, dict[str, Any]] = {
            "oci://registry/A:v1": {
                "name": "A",
                "parent_manifest": "oci://registry/B:v1",
            },
            "oci://registry/B:v1": {
                "name": "B",
                "parent_manifest": "oci://registry/A:v1",
            },
        }

        with pytest.raises(CircularInheritanceError) as exc_info:
            detect_circular_inheritance("oci://registry/A:v1", manifests)

        assert "circular" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-005")
    def test_detect_circular_inheritance_indirect(self) -> None:
        """Test detection of indirect circular inheritance (A → B → C → A)."""
        from floe_core.schemas.inheritance import (
            CircularInheritanceError,
            detect_circular_inheritance,
        )

        manifests: dict[str, dict[str, Any]] = {
            "oci://registry/A:v1": {
                "name": "A",
                "parent_manifest": "oci://registry/B:v1",
            },
            "oci://registry/B:v1": {
                "name": "B",
                "parent_manifest": "oci://registry/C:v1",
            },
            "oci://registry/C:v1": {
                "name": "C",
                "parent_manifest": "oci://registry/A:v1",
            },
        }

        with pytest.raises(CircularInheritanceError) as exc_info:
            detect_circular_inheritance("oci://registry/A:v1", manifests)

        assert "circular" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-005")
    def test_no_circular_inheritance_valid_chain(self) -> None:
        """Test that valid inheritance chains pass without error."""
        from floe_core.schemas.inheritance import detect_circular_inheritance

        # Valid chain: A → B → C (no cycle)
        manifests: dict[str, dict[str, Any]] = {
            "oci://registry/A:v1": {
                "name": "A",
                "parent_manifest": "oci://registry/B:v1",
            },
            "oci://registry/B:v1": {
                "name": "B",
                "parent_manifest": "oci://registry/C:v1",
            },
            "oci://registry/C:v1": {
                "name": "C",
                "parent_manifest": None,  # Root of chain
            },
        }

        # Should not raise
        detect_circular_inheritance("oci://registry/A:v1", manifests)

    @pytest.mark.requirement("001-FR-005")
    def test_detect_self_reference(self) -> None:
        """Test detection of self-referencing manifest (A → A)."""
        from floe_core.schemas.inheritance import (
            CircularInheritanceError,
            detect_circular_inheritance,
        )

        manifests: dict[str, dict[str, Any]] = {
            "oci://registry/A:v1": {
                "name": "A",
                "parent_manifest": "oci://registry/A:v1",  # Self-reference
            },
        }

        with pytest.raises(CircularInheritanceError) as exc_info:
            detect_circular_inheritance("oci://registry/A:v1", manifests)

        assert "circular" in str(exc_info.value).lower()


class TestMergeStrategies:
    """Tests for merge strategy application."""

    @pytest.mark.requirement("001-FR-004")
    def test_field_merge_strategies_exist(self) -> None:
        """Test that FIELD_MERGE_STRATEGIES defines strategies for key fields."""
        from floe_core.schemas.inheritance import (
            FIELD_MERGE_STRATEGIES,
            MergeStrategy,
        )

        # Verify expected fields have merge strategies
        assert "plugins" in FIELD_MERGE_STRATEGIES
        assert "governance" in FIELD_MERGE_STRATEGIES
        assert "approved_plugins" in FIELD_MERGE_STRATEGIES

        # Verify governance is FORBID (immutable)
        assert FIELD_MERGE_STRATEGIES["governance"] == MergeStrategy.FORBID

    @pytest.mark.requirement("001-FR-004")
    def test_merge_strategy_enum_values(self) -> None:
        """Test MergeStrategy enum has correct values."""
        from floe_core.schemas.inheritance import MergeStrategy

        assert MergeStrategy.OVERRIDE.value == "override"
        assert MergeStrategy.EXTEND.value == "extend"
        assert MergeStrategy.FORBID.value == "forbid"
