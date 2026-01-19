"""Unit tests for dry-run mode in policy enforcement.

Tests the dry-run flag handling:
- Dry-run mode passes through compilation pipeline
- Dry-run mode generates violations without blocking
- Dry-run report format

Task: T077
Requirements: FR-002 (Pipeline integration), US7 (Dry-run mode)
"""

from __future__ import annotations

from typing import Any

import pytest


class TestDryRunFlagHandling:
    """Tests for dry-run flag handling.

    Task: T077
    Requirement: US7 (Dry-run mode)
    """

    @pytest.mark.requirement("US7")
    def test_dry_run_mode_always_passes(
        self,
    ) -> None:
        """Dry-run mode MUST always return passed=True regardless of violations.

        When dry_run=True is passed to PolicyEnforcer.enforce(),
        the result.passed should be True even with violations.
        """
        from floe_core.enforcement import PolicyEnforcer
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

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=True)

        # Dry-run always passes
        assert result.passed is True
        # But violations are still reported
        assert len(result.violations) > 0

    @pytest.mark.requirement("US7")
    def test_dry_run_mode_downgrades_severity_to_warning(
        self,
    ) -> None:
        """Dry-run mode MUST downgrade all violations to warning severity.

        When dry_run=True, error-severity violations should be
        converted to warnings for reporting purposes.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",  # Would normally create errors
            ),
        )

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

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=True)

        # All violations should be warnings in dry-run mode
        for violation in result.violations:
            assert violation.severity == "warning"

        # No errors
        assert result.error_count == 0
        # But warnings exist
        assert result.warning_count > 0

    @pytest.mark.requirement("US7")
    def test_dry_run_mode_false_reports_actual_severity(
        self,
    ) -> None:
        """When dry_run=False, violations have actual severity.

        Ensures that non-dry-run mode correctly reports error severity.
        """
        from floe_core.enforcement import PolicyEnforcer
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
                "model.my_project.bad_model_name": {
                    "name": "bad_model_name",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=False)

        # Non-dry-run reports actual severity
        assert result.passed is False
        assert result.error_count > 0

    @pytest.mark.requirement("US7")
    def test_dry_run_with_no_violations_still_passes(
        self,
    ) -> None:
        """Dry-run mode with no violations returns passed=True.

        Validates that dry-run works correctly when there are no violations.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
        )

        # Model that follows medallion naming
        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.bronze_orders": {
                    "name": "bronze_orders",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=True)

        assert result.passed is True
        assert len(result.violations) == 0


class TestDryRunReportFormat:
    """Tests for dry-run report output format.

    Task: T082
    Requirement: US7 (Dry-run mode)
    """

    @pytest.mark.requirement("US7")
    def test_dry_run_result_includes_all_violation_details(
        self,
    ) -> None:
        """Dry-run result MUST include full violation details for reporting.

        Each violation should include:
        - error_code
        - policy_type
        - model_name
        - message
        - suggestion
        - documentation_url
        """
        from floe_core.enforcement import PolicyEnforcer
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
                "model.my_project.bad_model_name": {
                    "name": "bad_model_name",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=True)

        assert len(result.violations) > 0
        violation = result.violations[0]

        # All report fields present
        assert violation.error_code is not None
        assert violation.policy_type == "naming"
        assert violation.model_name == "bad_model_name"
        assert violation.message is not None
        assert violation.suggestion is not None
        assert violation.documentation_url is not None

    @pytest.mark.requirement("US7")
    def test_dry_run_summary_counts_warnings(
        self,
    ) -> None:
        """Dry-run summary MUST correctly count warnings.

        Since dry-run downgrades all to warnings, the summary should reflect this.
        """
        from floe_core.enforcement import PolicyEnforcer
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

        # Model with naming AND documentation violations
        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.bad_model_name": {
                    "name": "bad_model_name",
                    "resource_type": "model",
                    "description": "",  # Missing
                    "columns": {},
                },
            },
        }

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=True)

        # Summary should have naming + documentation violations (as warnings)
        assert result.summary.naming_violations > 0
        assert result.summary.documentation_violations > 0
        # All are warnings in dry-run
        assert result.error_count == 0
        expected_warnings = (
            result.summary.naming_violations + result.summary.documentation_violations
        )
        assert result.warning_count == expected_warnings
