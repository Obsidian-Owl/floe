"""Integration tests for dry-run mode in the compilation pipeline.

Tests the end-to-end dry-run behavior through run_enforce_stage:
- Dry-run flag passthrough from pipeline
- Report output format with all violation details
- Summary statistics in dry-run mode

Task: T078
Requirements: FR-002 (Pipeline integration), US7 (Dry-run mode)
"""

from __future__ import annotations

from typing import Any

import pytest


class TestDryRunPipelineIntegration:
    """Tests for dry-run mode integration with compilation pipeline.

    Task: T078
    Requirement: US7 (Dry-run mode)
    """

    @pytest.mark.requirement("US7")
    def test_dry_run_passes_through_run_enforce_stage(
        self,
    ) -> None:
        """Dry-run flag MUST pass through run_enforce_stage correctly.

        When run_enforce_stage is called with dry_run=True, it should
        delegate to PolicyEnforcer with the same flag.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
        )

        # Model that violates medallion naming
        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.bad_model_name": {
                    "name": "bad_model_name",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        # Dry-run mode - should NOT raise even with strict enforcement
        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=True,
        )

        # Should pass despite violations
        assert result.passed is True
        # Violations should still be reported
        assert len(result.violations) > 0

    @pytest.mark.requirement("US7")
    def test_dry_run_returns_complete_violation_details(
        self,
    ) -> None:
        """Dry-run result MUST include complete violation details for reporting.

        Each violation in dry-run mode should have all required fields
        for a complete audit report.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

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
                "model.my_project.invalid_model": {
                    "name": "invalid_model",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=True,
        )

        assert len(result.violations) > 0
        violation = result.violations[0]

        # All required report fields must be present
        assert violation.error_code is not None
        assert violation.policy_type == "naming"
        assert violation.model_name == "invalid_model"
        assert violation.message is not None
        assert violation.suggestion is not None
        assert violation.documentation_url is not None
        # Dry-run downgrades to warning
        assert violation.severity == "warning"

    @pytest.mark.requirement("US7")
    def test_dry_run_summary_contains_all_statistics(
        self,
    ) -> None:
        """Dry-run summary MUST contain complete statistics.

        The EnforcementResult summary should include all model and
        violation counts for reporting purposes.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
            quality_gates=QualityGatesConfig(
                require_descriptions=True,
            ),
        )

        # Model with multiple violations
        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.bad_name": {
                    "name": "bad_name",
                    "resource_type": "model",
                    "description": "",  # Documentation violation
                    "columns": {},
                },
                "model.my_project.another_bad": {
                    "name": "another_bad",
                    "resource_type": "model",
                    "description": "",
                    "columns": {},
                },
            },
        }

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=True,
        )

        # Summary should have complete statistics
        assert result.summary.total_models == 2
        assert result.summary.models_validated == 2
        assert result.summary.naming_violations > 0
        assert result.summary.documentation_violations > 0
        assert result.summary.duration_ms >= 0.0

    @pytest.mark.requirement("US7")
    def test_dry_run_does_not_raise_in_strict_mode(
        self,
    ) -> None:
        """Dry-run MUST NOT raise PolicyEnforcementError even in strict mode.

        This is the critical integration behavior: strict mode would normally
        raise, but dry-run bypasses the raise.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.errors import PolicyEnforcementError
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

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
                "model.my_project.bad_model": {
                    "name": "bad_model",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        # First verify strict mode DOES raise when not dry-run
        with pytest.raises(PolicyEnforcementError):
            run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
                dry_run=False,
            )

        # Now verify dry-run does NOT raise
        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=True,
        )

        assert result.passed is True
        assert result.error_count == 0  # Downgraded to warnings
        assert result.warning_count > 0

    @pytest.mark.requirement("US7")
    def test_dry_run_with_multiple_validator_types(
        self,
    ) -> None:
        """Dry-run MUST report violations from all validator types.

        When multiple validators find violations, all should be included
        in the dry-run report, all as warnings.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
            quality_gates=QualityGatesConfig(
                require_descriptions=True,
                minimum_test_coverage=100,  # High threshold
            ),
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.invalid": {
                    "name": "invalid",  # Naming violation
                    "resource_type": "model",
                    "description": "",  # Documentation violation
                    "columns": {
                        "id": {
                            "name": "id",
                            "description": "",  # Column documentation violation
                        },
                    },
                },
            },
        }

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=True,
        )

        # Multiple violation types present
        policy_types = {v.policy_type for v in result.violations}
        assert "naming" in policy_types
        assert "documentation" in policy_types

        # All should be warnings in dry-run mode
        for violation in result.violations:
            assert violation.severity == "warning"

        # Result should pass despite violations
        assert result.passed is True
