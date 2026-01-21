"""Unit tests for enhanced violation context (US4).

Tests for downstream_impact population and violations_by_model grouping:
- downstream_impact from manifest child_map (FR-016)
- violations_by_model grouping property (FR-019)
- include_context parameter for lazy computation (FR-016)

Task: T045, T046
Requirements: FR-016 (Enhanced Context), FR-019 (By-Model Grouping)

TDD Pattern: These tests are written FIRST and should FAIL until
T047-T049 implements the downstream impact computation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def manifest_with_child_map() -> dict[str, Any]:
    """Create a manifest with child_map for downstream impact testing.

    Dependency graph:
        bronze_orders -> silver_orders -> gold_orders
        bronze_orders -> silver_order_items
        silver_order_items -> gold_order_summary
        bronze_customers -> (no children)

    Returns:
        Manifest dictionary with nodes and child_map.
    """
    return {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.project.bronze_orders": {
                "resource_type": "model",
                "name": "bronze_orders",
                "unique_id": "model.project.bronze_orders",
            },
            "model.project.silver_orders": {
                "resource_type": "model",
                "name": "silver_orders",
                "unique_id": "model.project.silver_orders",
            },
            "model.project.silver_order_items": {
                "resource_type": "model",
                "name": "silver_order_items",
                "unique_id": "model.project.silver_order_items",
            },
            "model.project.gold_orders": {
                "resource_type": "model",
                "name": "gold_orders",
                "unique_id": "model.project.gold_orders",
            },
            "model.project.gold_order_summary": {
                "resource_type": "model",
                "name": "gold_order_summary",
                "unique_id": "model.project.gold_order_summary",
            },
            "model.project.bronze_customers": {
                "resource_type": "model",
                "name": "bronze_customers",
                "unique_id": "model.project.bronze_customers",
            },
        },
        "child_map": {
            "model.project.bronze_orders": [
                "model.project.silver_orders",
                "model.project.silver_order_items",
            ],
            "model.project.silver_orders": ["model.project.gold_orders"],
            "model.project.silver_order_items": ["model.project.gold_order_summary"],
            "model.project.gold_orders": [],
            "model.project.gold_order_summary": [],
            "model.project.bronze_customers": [],
        },
    }


@pytest.fixture
def sample_violation_bronze_orders() -> Violation:
    """Create a sample violation for bronze_orders model."""
    return Violation(
        error_code="FLOE-E201",
        severity="error",
        policy_type="naming",
        model_name="bronze_orders",
        message="Model 'bronze_orders' violates naming convention",
        expected="Pattern: bronze_*, silver_*, gold_*",
        actual="bronze_orders",
        suggestion="Model name is valid for medallion pattern",
        documentation_url="https://floe.dev/docs/enforcement/naming",
    )


@pytest.fixture
def sample_violation_bronze_customers() -> Violation:
    """Create a sample violation for bronze_customers model."""
    return Violation(
        error_code="FLOE-E210",
        severity="error",
        policy_type="coverage",
        model_name="bronze_customers",
        message="Model 'bronze_customers' has insufficient test coverage",
        expected="Test coverage >= 80%",
        actual="Test coverage is 50%",
        suggestion="Add more tests to model columns",
        documentation_url="https://floe.dev/docs/enforcement/coverage",
    )


@pytest.fixture
def sample_violation_silver_orders() -> Violation:
    """Create a sample violation for silver_orders model."""
    return Violation(
        error_code="FLOE-E220",
        severity="error",
        policy_type="documentation",
        model_name="silver_orders",
        message="Model 'silver_orders' is missing description",
        expected="Model should have a description",
        actual="No description provided",
        suggestion="Add a description to the model",
        documentation_url="https://floe.dev/docs/enforcement/documentation",
    )


# ==============================================================================
# T045: Tests for downstream_impact Population (FR-016)
# ==============================================================================


class TestDownstreamImpactPopulation:
    """Tests for downstream_impact field population from manifest child_map.

    FR-016: System MUST populate Violation.downstream_impact with list of
    affected downstream models computed from manifest child_map.
    """

    @pytest.mark.requirement("003b-FR-016")
    def test_downstream_impact_populated_from_child_map(
        self,
        manifest_with_child_map: dict[str, Any],
        sample_violation_bronze_orders: Violation,
    ) -> None:
        """Test that downstream_impact is populated from manifest child_map.

        Given: Violation for bronze_orders which has 2 direct children
        When: compute_downstream_impact is called
        Then: downstream_impact contains the child model names
        """
        from floe_core.enforcement.result import compute_downstream_impact

        child_map = manifest_with_child_map["child_map"]
        impact = compute_downstream_impact(
            model_name="bronze_orders",
            child_map=child_map,
        )

        # bronze_orders has silver_orders and silver_order_items as children
        assert "silver_orders" in impact
        assert "silver_order_items" in impact

    @pytest.mark.requirement("003b-FR-016")
    def test_downstream_impact_includes_transitive_dependencies(
        self,
        manifest_with_child_map: dict[str, Any],
    ) -> None:
        """Test that downstream_impact includes transitive (indirect) children.

        Given: bronze_orders -> silver_orders -> gold_orders
        When: compute_downstream_impact is called with recursive=True
        Then: downstream_impact includes both direct and indirect children
        """
        from floe_core.enforcement.result import compute_downstream_impact

        child_map = manifest_with_child_map["child_map"]
        impact = compute_downstream_impact(
            model_name="bronze_orders",
            child_map=child_map,
            recursive=True,
        )

        # Should include direct children
        assert "silver_orders" in impact
        assert "silver_order_items" in impact
        # Should include transitive children
        assert "gold_orders" in impact
        assert "gold_order_summary" in impact

    @pytest.mark.requirement("003b-FR-016")
    def test_downstream_impact_empty_for_leaf_models(
        self,
        manifest_with_child_map: dict[str, Any],
    ) -> None:
        """Test that downstream_impact is empty for models with no children.

        Given: bronze_customers has no children in child_map
        When: compute_downstream_impact is called
        Then: downstream_impact is empty list
        """
        from floe_core.enforcement.result import compute_downstream_impact

        child_map = manifest_with_child_map["child_map"]
        impact = compute_downstream_impact(
            model_name="bronze_customers",
            child_map=child_map,
        )

        assert impact == []

    @pytest.mark.requirement("003b-FR-016")
    def test_downstream_impact_extracts_model_names_from_unique_ids(
        self,
        manifest_with_child_map: dict[str, Any],
    ) -> None:
        """Test that downstream_impact returns simple model names, not unique_ids.

        Given: child_map contains unique_ids like "model.project.silver_orders"
        When: compute_downstream_impact is called
        Then: downstream_impact contains simple names like "silver_orders"
        """
        from floe_core.enforcement.result import compute_downstream_impact

        child_map = manifest_with_child_map["child_map"]
        impact = compute_downstream_impact(
            model_name="bronze_orders",
            child_map=child_map,
        )

        # Should be simple names, not unique_ids
        for name in impact:
            assert not name.startswith("model.")
            assert "." not in name

    @pytest.mark.requirement("003b-FR-016")
    def test_downstream_impact_handles_missing_model_in_child_map(
        self,
        manifest_with_child_map: dict[str, Any],
    ) -> None:
        """Test that downstream_impact handles model not in child_map gracefully.

        Given: Model name not present in child_map
        When: compute_downstream_impact is called
        Then: Returns empty list (no error)
        """
        from floe_core.enforcement.result import compute_downstream_impact

        child_map = manifest_with_child_map["child_map"]
        impact = compute_downstream_impact(
            model_name="nonexistent_model",
            child_map=child_map,
        )

        assert impact == []


# ==============================================================================
# T046: Tests for violations_by_model Property (FR-019)
# ==============================================================================


class TestViolationsByModelGrouping:
    """Tests for violations_by_model grouping property.

    FR-019: System MUST provide violations_by_model property on
    EnforcementResult for easy model-centric reporting.
    """

    @pytest.mark.requirement("003b-FR-019")
    def test_violations_by_model_groups_correctly(
        self,
        sample_violation_bronze_orders: Violation,
        sample_violation_bronze_customers: Violation,
        sample_violation_silver_orders: Violation,
    ) -> None:
        """Test that violations_by_model groups violations by model name.

        Given: Multiple violations for different models
        When: violations_by_model property accessed
        Then: Dictionary groups violations by model_name
        """
        violations = [
            sample_violation_bronze_orders,
            sample_violation_bronze_customers,
            sample_violation_silver_orders,
        ]

        result = EnforcementResult(
            passed=False,
            violations=violations,
            summary=EnforcementSummary(
                total_models=3,
                models_validated=3,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        by_model = result.violations_by_model

        assert "bronze_orders" in by_model
        assert "bronze_customers" in by_model
        assert "silver_orders" in by_model
        assert len(by_model["bronze_orders"]) == 1
        assert len(by_model["bronze_customers"]) == 1
        assert len(by_model["silver_orders"]) == 1

    @pytest.mark.requirement("003b-FR-019")
    def test_violations_by_model_multiple_per_model(
        self,
    ) -> None:
        """Test that multiple violations for same model are grouped together.

        Given: Two violations for the same model
        When: violations_by_model property accessed
        Then: Both violations in same list
        """
        violation1 = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="bronze_orders",
            message="Naming violation",
            expected="expected",
            actual="actual",
            suggestion="suggestion",
            documentation_url="https://floe.dev/docs/naming",
        )
        violation2 = Violation(
            error_code="FLOE-E210",
            severity="error",
            policy_type="coverage",
            model_name="bronze_orders",
            message="Coverage violation",
            expected="expected",
            actual="actual",
            suggestion="suggestion",
            documentation_url="https://floe.dev/docs/coverage",
        )

        result = EnforcementResult(
            passed=False,
            violations=[violation1, violation2],
            summary=EnforcementSummary(
                total_models=1,
                models_validated=1,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        by_model = result.violations_by_model

        assert len(by_model) == 1
        assert "bronze_orders" in by_model
        assert len(by_model["bronze_orders"]) == 2

    @pytest.mark.requirement("003b-FR-019")
    def test_violations_by_model_empty_when_no_violations(
        self,
    ) -> None:
        """Test that violations_by_model is empty when no violations.

        Given: EnforcementResult with no violations
        When: violations_by_model property accessed
        Then: Empty dictionary returned
        """
        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=5,
                models_validated=5,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        assert result.violations_by_model == {}


# ==============================================================================
# Additional Context Tests
# ==============================================================================


class TestViolationContextEdgeCases:
    """Edge case tests for violation context features."""

    @pytest.mark.requirement("003b-FR-016")
    def test_downstream_impact_handles_circular_reference(
        self,
    ) -> None:
        """Test that downstream_impact handles circular references in child_map.

        Given: child_map with circular reference (A -> B -> A)
        When: compute_downstream_impact is called with recursive=True
        Then: No infinite loop, returns unique list
        """
        from floe_core.enforcement.result import compute_downstream_impact

        circular_child_map = {
            "model.project.model_a": ["model.project.model_b"],
            "model.project.model_b": ["model.project.model_a"],
        }

        # Should not hang or raise error
        impact = compute_downstream_impact(
            model_name="model_a",
            child_map=circular_child_map,
            recursive=True,
        )

        # Should include both but not infinite
        assert "model_b" in impact
        # model_a is included because it's a child of model_b
        # but we started from model_a so it shouldn't be in its own impact
        assert len(impact) <= 2

    @pytest.mark.requirement("003b-FR-016")
    def test_include_context_parameter_controls_computation(
        self,
        manifest_with_child_map: dict[str, Any],
    ) -> None:
        """Test that include_context parameter controls downstream_impact computation.

        FR-016: Support lazy computation via include_context parameter.

        Given: PolicyEnforcer.enforce() with include_context=False
        When: Violations are generated
        Then: downstream_impact is None (not computed)
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(pattern="custom", custom_patterns=["^invalid_.*$"]),
        )
        enforcer = PolicyEnforcer(governance_config=config)

        # enforce() should support include_context parameter
        result = enforcer.enforce(
            manifest_with_child_map,
            include_context=False,
        )

        # Violations should have downstream_impact=None when include_context=False
        for violation in result.violations:
            assert violation.downstream_impact is None

    @pytest.mark.requirement("003b-FR-016")
    def test_include_context_true_populates_downstream_impact(
        self,
        manifest_with_child_map: dict[str, Any],
    ) -> None:
        """Test that include_context=True populates downstream_impact.

        Given: PolicyEnforcer.enforce() with include_context=True
        When: Violations are generated
        Then: downstream_impact is populated from child_map
        """
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        # Use naming pattern that will generate violations for bronze_orders
        config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(pattern="custom", custom_patterns=["^invalid_.*$"]),
        )
        enforcer = PolicyEnforcer(governance_config=config)

        result = enforcer.enforce(
            manifest_with_child_map,
            include_context=True,
        )

        # Find violation for bronze_orders (if any)
        bronze_violations = [v for v in result.violations if v.model_name == "bronze_orders"]

        if bronze_violations:
            # downstream_impact should be populated
            violation = bronze_violations[0]
            assert violation.downstream_impact is not None
            # bronze_orders has children
            assert len(violation.downstream_impact) > 0
