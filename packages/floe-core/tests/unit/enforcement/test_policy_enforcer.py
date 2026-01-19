"""Unit tests for PolicyEnforcer orchestration.

Tests for PolicyEnforcer.enforce() method which coordinates all validators.
Following TDD: these tests are written FIRST and will FAIL until
the PolicyEnforcer is implemented in T029-T030.

Task: T023
Requirements: FR-001 (Compile-Time Enforcement), US1 (Compile-time Enforcement)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


def create_minimal_dbt_manifest() -> dict[str, Any]:
    """Create a minimal valid dbt manifest for testing.

    Returns:
        Minimal dbt manifest structure with required fields.
    """
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
            "dbt_version": "1.8.0",
            "generated_at": "2026-01-19T10:00:00Z",
            "invocation_id": "test-invocation-id",
            "project_name": "test_project",
        },
        "nodes": {},
        "sources": {},
        "exposures": {},
        "metrics": {},
        "selectors": {},
        "disabled": {},
        "parent_map": {},
        "child_map": {},
    }


def create_dbt_manifest_with_models(
    models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a dbt manifest with specified models.

    Args:
        models: List of model configurations with keys:
            - name: Model name
            - schema: Schema name (optional, defaults to "public")
            - columns: List of column dicts with name and optional tests
            - description: Model description (optional)

    Returns:
        dbt manifest with the specified models.
    """
    manifest = create_minimal_dbt_manifest()
    nodes: dict[str, Any] = {}

    for model in models:
        model_name = model["name"]
        unique_id = f"model.test_project.{model_name}"
        nodes[unique_id] = {
            "unique_id": unique_id,
            "name": model_name,
            "resource_type": "model",
            "schema": model.get("schema", "public"),
            "description": model.get("description", ""),
            "columns": {
                col["name"]: {
                    "name": col["name"],
                    "description": col.get("description", ""),
                    "data_tests": col.get("tests", []),
                }
                for col in model.get("columns", [])
            },
            "config": model.get("config", {}),
            "meta": model.get("meta", {}),
        }

    manifest["nodes"] = nodes
    return manifest


class TestPolicyEnforcerInit:
    """Tests for PolicyEnforcer initialization (T023)."""

    @pytest.mark.requirement("3A-US1-FR001")
    def test_policy_enforcer_init_with_governance_config(self) -> None:
        """Test PolicyEnforcer can be initialized with GovernanceConfig."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig(policy_enforcement_level="strict")
        enforcer = PolicyEnforcer(governance_config=config)

        assert enforcer.governance_config is config
        assert enforcer.governance_config.policy_enforcement_level == "strict"

    @pytest.mark.requirement("3A-US1-FR001")
    def test_policy_enforcer_init_with_naming_config(self) -> None:
        """Test PolicyEnforcer can be initialized with NamingConfig."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="strict", pattern="medallion")
        config = GovernanceConfig(naming=naming)
        enforcer = PolicyEnforcer(governance_config=config)

        assert enforcer.governance_config.naming is not None
        assert enforcer.governance_config.naming.enforcement == "strict"

    @pytest.mark.requirement("3A-US1-FR001")
    def test_policy_enforcer_init_with_quality_gates(self) -> None:
        """Test PolicyEnforcer can be initialized with QualityGatesConfig."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        quality = QualityGatesConfig(minimum_test_coverage=90)
        config = GovernanceConfig(quality_gates=quality)
        enforcer = PolicyEnforcer(governance_config=config)

        assert enforcer.governance_config.quality_gates is not None
        assert enforcer.governance_config.quality_gates.minimum_test_coverage == 90


class TestPolicyEnforcerEnforce:
    """Tests for PolicyEnforcer.enforce() orchestration (T023)."""

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_returns_enforcement_result(self) -> None:
        """Test enforce() returns EnforcementResult."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.enforcement.result import EnforcementResult
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        enforcer = PolicyEnforcer(governance_config=config)
        manifest = create_minimal_dbt_manifest()

        result = enforcer.enforce(manifest)

        assert isinstance(result, EnforcementResult)

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_passes_with_no_violations(self) -> None:
        """Test enforce() returns passed=True when no violations."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        enforcer = PolicyEnforcer(governance_config=config)
        manifest = create_minimal_dbt_manifest()

        result = enforcer.enforce(manifest)

        assert result.passed is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_fails_with_naming_violation(self) -> None:
        """Test enforce() returns passed=False when naming violation exists."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="strict", pattern="medallion")
        config = GovernanceConfig(naming=naming)
        enforcer = PolicyEnforcer(governance_config=config)

        # Model name doesn't follow medallion pattern
        manifest = create_dbt_manifest_with_models([
            {"name": "stg_customers", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest)

        assert result.passed is False
        assert len(result.violations) > 0
        # Should have naming violation
        assert any(v.policy_type == "naming" for v in result.violations)

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_off_mode_skips_validation(self) -> None:
        """Test enforce() skips validation when enforcement is 'off'."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="off", pattern="medallion")
        config = GovernanceConfig(naming=naming)
        enforcer = PolicyEnforcer(governance_config=config)

        # Model name doesn't follow medallion pattern, but enforcement is off
        manifest = create_dbt_manifest_with_models([
            {"name": "stg_customers", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest)

        # Should pass because enforcement is off
        assert result.passed is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_warn_mode_returns_warnings(self) -> None:
        """Test enforce() returns warnings (not errors) when enforcement is 'warn'."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="warn", pattern="medallion")
        config = GovernanceConfig(naming=naming)
        enforcer = PolicyEnforcer(governance_config=config)

        # Model name doesn't follow medallion pattern
        manifest = create_dbt_manifest_with_models([
            {"name": "stg_customers", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest)

        # Should still pass (warn mode), but have violations
        assert result.passed is True
        assert len(result.violations) > 0
        # All violations should be warnings
        assert all(v.severity == "warning" for v in result.violations)

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_strict_mode_returns_errors(self) -> None:
        """Test enforce() returns errors when enforcement is 'strict'."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="strict", pattern="medallion")
        config = GovernanceConfig(naming=naming)
        enforcer = PolicyEnforcer(governance_config=config)

        # Model name doesn't follow medallion pattern
        manifest = create_dbt_manifest_with_models([
            {"name": "stg_customers", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest)

        # Should fail (strict mode)
        assert result.passed is False
        # Should have error severity violations
        assert any(v.severity == "error" for v in result.violations)

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_includes_summary(self) -> None:
        """Test enforce() result includes summary statistics."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        enforcer = PolicyEnforcer(governance_config=config)
        manifest = create_dbt_manifest_with_models([
            {"name": "bronze_customers", "columns": [{"name": "id"}]},
            {"name": "silver_orders", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest)

        assert result.summary is not None
        assert result.summary.total_models == 2
        assert result.summary.models_validated == 2

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_includes_timestamp(self) -> None:
        """Test enforce() result includes timestamp."""
        from datetime import datetime, timezone

        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        enforcer = PolicyEnforcer(governance_config=config)
        manifest = create_minimal_dbt_manifest()

        before = datetime.now(timezone.utc)
        result = enforcer.enforce(manifest)
        after = datetime.now(timezone.utc)

        assert result.timestamp is not None
        assert before <= result.timestamp <= after

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_includes_enforcement_level(self) -> None:
        """Test enforce() result includes enforcement level."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig(policy_enforcement_level="strict")
        enforcer = PolicyEnforcer(governance_config=config)
        manifest = create_minimal_dbt_manifest()

        result = enforcer.enforce(manifest)

        assert result.enforcement_level == "strict"

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_with_dry_run_mode(self) -> None:
        """Test enforce() respects dry_run parameter."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="strict", pattern="medallion")
        config = GovernanceConfig(naming=naming)
        enforcer = PolicyEnforcer(governance_config=config)

        # Model name doesn't follow medallion pattern
        manifest = create_dbt_manifest_with_models([
            {"name": "stg_customers", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest, dry_run=True)

        # In dry-run mode, violations are reported but severity is downgraded
        assert len(result.violations) > 0
        # Violations should be warnings in dry-run mode
        assert all(v.severity == "warning" for v in result.violations)
        # Result should pass in dry-run mode
        assert result.passed is True


class TestPolicyEnforcerMultipleValidators:
    """Tests for PolicyEnforcer with multiple validators (T023)."""

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_runs_all_validators(self) -> None:
        """Test enforce() runs naming, coverage, and documentation validators."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="strict", pattern="medallion")
        quality = QualityGatesConfig(
            minimum_test_coverage=80,
            require_descriptions=True,
        )
        config = GovernanceConfig(naming=naming, quality_gates=quality)
        enforcer = PolicyEnforcer(governance_config=config)

        # Model with multiple violations:
        # - Name doesn't follow medallion
        # - No tests (coverage violation)
        # - No description (documentation violation)
        manifest = create_dbt_manifest_with_models([
            {"name": "stg_customers", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest)

        assert result.passed is False
        # Should have violations from multiple validators
        violation_types = {v.policy_type for v in result.violations}
        assert "naming" in violation_types
        # Coverage and documentation validators will also run

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_aggregates_violations_correctly(self) -> None:
        """Test enforce() correctly aggregates violations from all validators."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        naming = NamingConfig(enforcement="strict", pattern="medallion")
        config = GovernanceConfig(naming=naming)
        enforcer = PolicyEnforcer(governance_config=config)

        # Multiple models with naming violations
        manifest = create_dbt_manifest_with_models([
            {"name": "stg_customers", "columns": [{"name": "id"}]},
            {"name": "stg_orders", "columns": [{"name": "id"}]},
            {"name": "bronze_products", "columns": [{"name": "id"}]},  # Valid
        ])

        result = enforcer.enforce(manifest)

        # Should have 2 naming violations (stg_customers, stg_orders)
        naming_violations = [v for v in result.violations if v.policy_type == "naming"]
        assert len(naming_violations) == 2
        assert result.summary.naming_violations == 2


class TestPolicyEnforcerEdgeCases:
    """Tests for PolicyEnforcer edge cases (T023)."""

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_empty_manifest(self) -> None:
        """Test enforce() handles empty manifest (no models)."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        enforcer = PolicyEnforcer(governance_config=config)
        manifest = create_minimal_dbt_manifest()

        result = enforcer.enforce(manifest)

        assert result.passed is True
        assert result.summary.total_models == 0
        assert len(result.violations) == 0

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_no_governance_config_fields(self) -> None:
        """Test enforce() with GovernanceConfig that has no policy fields."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        # GovernanceConfig with no naming or quality_gates
        config = GovernanceConfig()
        enforcer = PolicyEnforcer(governance_config=config)

        manifest = create_dbt_manifest_with_models([
            {"name": "any_name_works", "columns": [{"name": "id"}]},
        ])

        result = enforcer.enforce(manifest)

        # Should pass - no policy checks configured
        assert result.passed is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3A-US1-FR001")
    def test_enforce_with_manifest_version(self) -> None:
        """Test enforce() captures manifest version in result."""
        from floe_core.enforcement.policy_enforcer import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        config = GovernanceConfig()
        enforcer = PolicyEnforcer(governance_config=config)
        manifest = create_minimal_dbt_manifest()

        result = enforcer.enforce(manifest)

        assert result.manifest_version == "1.8.0"
