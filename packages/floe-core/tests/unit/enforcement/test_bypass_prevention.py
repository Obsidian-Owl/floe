"""Unit tests for bypass prevention in policy enforcement.

Tests that strict mode cannot be circumvented by:
- Environment variables
- CLI flags (dry_run doesn't change enforcement level)
- Manifest configuration

Task: T094
Requirements: FR-009 (Bypass prevention), US1 (Policy Evaluation at Compile Time)
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from floe_core.enforcement import PolicyEnforcer
from floe_core.enforcement.errors import PolicyEnforcementError
from floe_core.schemas.governance import NamingConfig
from floe_core.schemas.manifest import GovernanceConfig


class TestBypassPrevention:
    """Tests for policy enforcement bypass prevention.

    Task: T094
    Requirement: FR-009, US1
    """

    @pytest.mark.requirement("FR-009")
    def test_strict_mode_not_overridden_by_env_var(self) -> None:
        """Strict mode MUST NOT be overridden by environment variables.

        The enforcement level is set in GovernanceConfig, not read from
        environment variables. This test verifies that even with env vars
        set to bypass enforcement, strict mode still enforces.
        """
        # Set environment variables that might attempt to bypass
        env_vars = {
            "FLOE_POLICY_ENFORCEMENT_LEVEL": "off",
            "FLOE_ENFORCEMENT_LEVEL": "warn",
            "POLICY_ENFORCEMENT": "disabled",
            "SKIP_POLICY_ENFORCEMENT": "true",
        }

        with patch.dict(os.environ, env_vars):
            # Configure strict mode
            governance_config = GovernanceConfig(
                policy_enforcement_level="strict",
                naming=NamingConfig(
                    pattern="medallion",
                    enforcement="strict",
                ),
            )

            # Model that violates naming convention
            dbt_manifest: dict[str, Any] = {
                "metadata": {"dbt_version": "1.8.0"},
                "nodes": {
                    "model.my_project.bad_model": {
                        "name": "bad_model",
                        "resource_type": "model",
                        "columns": {},
                    },
                },
            }

            enforcer = PolicyEnforcer(governance_config=governance_config)
            result = enforcer.enforce(dbt_manifest)

            # Strict mode MUST still produce error-severity violations
            assert len(result.violations) > 0
            assert result.enforcement_level == "strict"
            assert any(v.severity == "error" for v in result.violations)

    @pytest.mark.requirement("FR-009")
    def test_dry_run_does_not_change_enforcement_level(self) -> None:
        """Dry-run flag downgrades severity but does NOT change enforcement level.

        The dry_run flag only affects violation severity (error → warning),
        it does NOT change the configured enforcement level itself.
        """
        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.invalid_name": {
                    "name": "invalid_name",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=True)

        # Enforcement level should STILL be "strict"
        assert result.enforcement_level == "strict"

        # But severity should be downgraded to warning
        assert all(v.severity == "warning" for v in result.violations)

        # Result passes in dry-run mode
        assert result.passed is True

    @pytest.mark.requirement("FR-009")
    def test_strict_mode_cannot_be_downgraded_after_construction(self) -> None:
        """Once PolicyEnforcer is constructed, enforcement level cannot be changed.

        PolicyEnforcer receives its configuration at construction time and
        does not expose any method to downgrade the enforcement level.
        """
        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
        )

        enforcer = PolicyEnforcer(governance_config=governance_config)

        # Verify enforcement level is read-only (no setter)
        assert not hasattr(enforcer, "set_enforcement_level")
        assert not hasattr(enforcer, "enforcement_level")

        # The config is stored but should not be mutable for enforcement
        assert enforcer.governance_config.policy_enforcement_level == "strict"

    @pytest.mark.requirement("FR-009")
    def test_strict_mode_raises_on_errors_without_dry_run(self) -> None:
        """Strict mode MUST raise PolicyEnforcementError for error violations.

        When enforcement_level is "strict" and there are error-severity
        violations, run_enforce_stage should raise PolicyEnforcementError.
        This cannot be bypassed.
        """
        from floe_core.compilation.stages import run_enforce_stage

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.violating_model": {
                    "name": "violating_model",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        # MUST raise PolicyEnforcementError in strict mode
        with pytest.raises(PolicyEnforcementError) as exc_info:
            run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
                dry_run=False,
            )

        # Exception should contain the violations
        assert len(exc_info.value.violations) > 0

    @pytest.mark.requirement("FR-009")
    def test_warn_mode_does_not_raise_on_violations(self) -> None:
        """Warn mode should return result without raising, even with violations.

        This is expected behavior - warn mode reports but doesn't block.
        The key is that "strict" cannot be downgraded to "warn" at runtime.
        """
        from floe_core.compilation.stages import run_enforce_stage

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="warn",
            ),
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.bad_model": {
                    "name": "bad_model",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        # Should NOT raise even with violations
        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        # Violations are present but mode is warn
        assert len(result.violations) > 0
        assert result.enforcement_level == "warn"
        # Warn mode passes even with violations (violations are warnings)
        assert result.passed is True

    @pytest.mark.requirement("FR-009")
    def test_enforcement_level_immutable_via_config_frozen(self) -> None:
        """GovernanceConfig should be frozen (immutable) to prevent tampering.

        Once created, the config cannot be modified to bypass enforcement.
        """
        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
        )

        # Attempting to modify should raise an error
        # Pydantic v2 frozen models raise ValidationError on attribute assignment
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            governance_config.policy_enforcement_level = "off"  # type: ignore[misc]

    @pytest.mark.requirement("FR-009")
    def test_no_global_bypass_flag_exists(self) -> None:
        """Verify no global bypass mechanism exists in the module.

        There should be no module-level flag to disable enforcement.
        """
        import floe_core.enforcement as enforcement_module
        import floe_core.enforcement.policy_enforcer as enforcer_module

        # Check for common bypass patterns
        bypass_patterns = [
            "SKIP_ENFORCEMENT",
            "DISABLE_ENFORCEMENT",
            "BYPASS_POLICY",
            "ENFORCEMENT_DISABLED",
            "_skip_enforcement",
            "_bypass",
        ]

        for pattern in bypass_patterns:
            assert not hasattr(enforcement_module, pattern), f"Found potential bypass: {pattern}"
            assert not hasattr(enforcer_module, pattern), f"Found potential bypass: {pattern}"
