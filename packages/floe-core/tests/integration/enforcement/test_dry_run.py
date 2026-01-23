"""Integration tests for dry-run mode in the compilation pipeline.

Tests the end-to-end dry-run behavior through run_enforce_stage:
- Dry-run flag passthrough from pipeline
- Report output format with all violation details
- Summary statistics in dry-run mode

Task: T078, T080
Phase: 10 - US8 (Test Duplication Reduction)
Requirements: FR-002 (Pipeline integration), US7 (Dry-run mode)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.schemas.manifest import GovernanceConfig


class TestDryRunPipelineIntegration:
    """Tests for dry-run mode integration with compilation pipeline.

    Task: T078, T080
    Requirement: US7 (Dry-run mode)
    """

    @pytest.mark.requirement("US7")
    @pytest.mark.parametrize(
        ("dry_run", "expect_pass", "expect_severity"),
        [
            pytest.param(True, True, "warning", id="dry_run_passes_with_warnings"),
            pytest.param(False, False, "error", id="normal_fails_with_errors"),
        ],
    )
    def test_dry_run_pipeline_behavior(
        self,
        strict_naming_governance_config: GovernanceConfig,
        dbt_manifest_with_naming_violation: dict[str, Any],
        dry_run: bool,
        expect_pass: bool,
        expect_severity: str,
    ) -> None:
        """Test dry-run vs normal mode behavior through run_enforce_stage.

        When dry_run=True: result.passed=True, violations are warnings
        When dry_run=False: result.passed=False, violations are errors
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.errors import PolicyEnforcementError

        if not dry_run:
            # Normal mode should raise with strict enforcement
            with pytest.raises(PolicyEnforcementError):
                run_enforce_stage(
                    governance_config=strict_naming_governance_config,
                    dbt_manifest=dbt_manifest_with_naming_violation,
                    dry_run=dry_run,
                )
        else:
            result = run_enforce_stage(
                governance_config=strict_naming_governance_config,
                dbt_manifest=dbt_manifest_with_naming_violation,
                dry_run=dry_run,
            )

            assert result.passed is expect_pass
            assert len(result.violations) > 0
            for violation in result.violations:
                assert violation.severity == expect_severity

    @pytest.mark.requirement("US7")
    def test_dry_run_returns_complete_violation_details(
        self,
        strict_naming_governance_config: GovernanceConfig,
        dbt_manifest_with_naming_violation: dict[str, Any],
    ) -> None:
        """Dry-run result MUST include complete violation details for reporting."""
        from floe_core.compilation.stages import run_enforce_stage

        result = run_enforce_stage(
            governance_config=strict_naming_governance_config,
            dbt_manifest=dbt_manifest_with_naming_violation,
            dry_run=True,
        )

        assert len(result.violations) > 0
        violation = result.violations[0]

        # All required report fields must be present
        assert violation.error_code is not None
        assert violation.policy_type == "naming"
        assert violation.model_name == "bad_model_name"
        assert violation.message is not None
        assert violation.suggestion is not None
        assert violation.documentation_url is not None
        # Dry-run downgrades to warning
        assert violation.severity == "warning"

    @pytest.mark.requirement("US7")
    def test_dry_run_summary_contains_all_statistics(
        self,
        strict_multi_policy_governance_config: GovernanceConfig,
        dbt_manifest_with_multiple_models: dict[str, Any],
    ) -> None:
        """Dry-run summary MUST contain complete statistics."""
        from floe_core.compilation.stages import run_enforce_stage

        result = run_enforce_stage(
            governance_config=strict_multi_policy_governance_config,
            dbt_manifest=dbt_manifest_with_multiple_models,
            dry_run=True,
        )

        # Summary should have complete statistics
        assert result.summary.total_models == 2
        assert result.summary.models_validated == 2
        assert result.summary.naming_violations > 0
        assert result.summary.documentation_violations > 0
        assert result.summary.duration_ms >= 0.0

    @pytest.mark.requirement("US7")
    def test_dry_run_with_multiple_validator_types(
        self,
        strict_multi_policy_governance_config: GovernanceConfig,
    ) -> None:
        """Dry-run MUST report violations from all validator types as warnings."""
        from floe_core.compilation.stages import run_enforce_stage

        # Model with multiple violation types
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
            governance_config=strict_multi_policy_governance_config,
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
