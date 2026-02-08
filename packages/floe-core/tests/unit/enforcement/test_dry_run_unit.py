"""Unit tests for dry-run mode in policy enforcement.

Tests the dry-run flag handling:
- Dry-run mode passes through compilation pipeline
- Dry-run mode generates violations without blocking
- Dry-run report format

Task: T077, T080
Phase: 10 - US8 (Test Duplication Reduction)
Requirements: FR-002 (Pipeline integration), US7 (Dry-run mode)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.schemas.manifest import GovernanceConfig


class TestDryRunFlagHandling:
    """Tests for dry-run flag handling.

    Task: T077, T080
    Requirement: US7 (Dry-run mode)
    """

    @pytest.mark.requirement("US7")
    @pytest.mark.parametrize(
        ("dry_run", "expected_passed", "expected_severity"),
        [
            pytest.param(True, True, "warning", id="dry_run_passes_with_warnings"),
            pytest.param(False, False, "error", id="normal_fails_with_errors"),
        ],
    )
    def test_dry_run_mode_behavior(
        self,
        strict_naming_governance_config: GovernanceConfig,
        dbt_manifest_with_naming_violation: dict[str, Any],
        dry_run: bool,
        expected_passed: bool,
        expected_severity: str,
    ) -> None:
        """Test dry-run vs normal mode behavior with violations.

        When dry_run=True: result.passed=True, violations are warnings
        When dry_run=False: result.passed=False, violations are errors
        """
        from floe_core.enforcement import PolicyEnforcer

        enforcer = PolicyEnforcer(governance_config=strict_naming_governance_config)
        result = enforcer.enforce(dbt_manifest_with_naming_violation, dry_run=dry_run)

        assert result.passed is expected_passed
        assert len(result.violations) > 0

        # Check severity matches mode
        for violation in result.violations:
            assert violation.severity == expected_severity

    @pytest.mark.requirement("US7")
    @pytest.mark.parametrize(
        ("dry_run", "expected_error_count_positive"),
        [
            pytest.param(True, False, id="dry_run_no_errors"),
            pytest.param(False, True, id="normal_has_errors"),
        ],
    )
    def test_dry_run_error_count(
        self,
        strict_naming_governance_config: GovernanceConfig,
        dbt_manifest_with_naming_violation: dict[str, Any],
        dry_run: bool,
        expected_error_count_positive: bool,
    ) -> None:
        """Test error count is zero in dry-run, positive in normal mode."""
        from floe_core.enforcement import PolicyEnforcer

        enforcer = PolicyEnforcer(governance_config=strict_naming_governance_config)
        result = enforcer.enforce(dbt_manifest_with_naming_violation, dry_run=dry_run)

        if expected_error_count_positive:
            assert result.error_count > 0
        else:
            assert result.error_count == 0
            assert result.warning_count > 0  # Dry-run has warnings instead

    @pytest.mark.requirement("US7")
    def test_dry_run_with_no_violations_still_passes(
        self,
        strict_naming_governance_config: GovernanceConfig,
        dbt_manifest_compliant: dict[str, Any],
    ) -> None:
        """Dry-run mode with no violations returns passed=True."""
        from floe_core.enforcement import PolicyEnforcer

        enforcer = PolicyEnforcer(governance_config=strict_naming_governance_config)
        result = enforcer.enforce(dbt_manifest_compliant, dry_run=True)

        assert result.passed is True
        assert len(result.violations) == 0


class TestDryRunReportFormat:
    """Tests for dry-run report output format.

    Task: T082, T080
    Requirement: US7 (Dry-run mode)
    """

    @pytest.mark.requirement("US7")
    def test_dry_run_result_includes_all_violation_details(
        self,
        strict_naming_governance_config: GovernanceConfig,
        dbt_manifest_with_naming_violation: dict[str, Any],
    ) -> None:
        """Dry-run result MUST include full violation details for reporting."""
        from floe_core.enforcement import PolicyEnforcer

        enforcer = PolicyEnforcer(governance_config=strict_naming_governance_config)
        result = enforcer.enforce(dbt_manifest_with_naming_violation, dry_run=True)

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
        strict_multi_policy_governance_config: GovernanceConfig,
        dbt_manifest_with_multi_violations: dict[str, Any],
    ) -> None:
        """Dry-run summary MUST correctly count warnings from all violation types."""
        from floe_core.enforcement import PolicyEnforcer

        enforcer = PolicyEnforcer(governance_config=strict_multi_policy_governance_config)
        result = enforcer.enforce(dbt_manifest_with_multi_violations, dry_run=True)

        # Summary should have naming + documentation violations (as warnings)
        assert result.summary.naming_violations > 0
        assert result.summary.documentation_violations > 0

        # All are warnings in dry-run
        assert result.error_count == 0
        expected_warnings = (
            result.summary.naming_violations + result.summary.documentation_violations
        )
        assert result.warning_count == expected_warnings
