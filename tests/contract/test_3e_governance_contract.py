"""TDD Contract tests for Epic 3E Governance Integration (RBAC, Secrets, Network Policies).

These tests define the expected contract for schema extensions that will be
implemented in T007-T013. Some tests will FAIL until those schema changes
are made — that's correct TDD behavior.

Task Coverage:
    - T004: Contract test GovernanceConfig backward compat (FR-031, FR-032)
    - T005: Contract test Violation.policy_type extension (FR-032)
    - T006: Contract test EnforcementResultSummary extension (FR-005, FR-032)

Requirements:
    - 3E-FR-005: Contract Monitor Integration
    - 3E-FR-031: RBAC Configuration Schema
    - 3E-FR-032: Governance Contract Versioning (0.7.0)

Contract Guarantees:
1. Existing GovernanceConfig fields remain backward compatible
2. New 3E fields (rbac, secret_scanning, network_policies) are optional (default None)
3. Violation.policy_type extends to include new types (rbac, secret_scanning, network_policy)
4. VALID_POLICY_TYPES frozenset includes all 9 types (6 existing + 3 new)
5. EnforcementResultSummary extends with new fields (rbac_principal, secrets_scanned)
6. EnforcementSummary extends with new violation counters
7. COMPILED_ARTIFACTS_VERSION bumps to 0.7.0 for Epic 3E

TDD Expectations:
    - T004.test_existing_configs_without_3e_fields_still_parse: PASS NOW
    - T004 other tests: FAIL until T010 adds schema fields
    - T005.test_existing_policy_types_still_valid: PASS NOW
    - T005.test_invalid_policy_type_rejected: PASS NOW
    - T005 other tests: FAIL until T007-T008
    - T006.test_existing_summaries_still_parse: PASS NOW
    - T006 other tests: FAIL until T009-T012
"""

from __future__ import annotations

from typing import Any

import pytest


def _make_violation(policy_type: str) -> Any:
    """Create a minimal valid Violation for contract testing.

    Args:
        policy_type: Policy type for the violation (e.g., "naming", "rbac").

    Returns:
        Valid Violation instance for testing.

    Example:
        >>> violation = _make_violation("naming")
        >>> violation.policy_type
        'naming'
    """
    from floe_core.enforcement.result import Violation

    return Violation(
        error_code="FLOE-E999",
        severity="error",
        policy_type=policy_type,  # type: ignore[arg-type]
        model_name="test_model",
        message="Test violation",
        expected="expected",
        actual="actual",
        suggestion="Fix it",
        documentation_url="https://floe.dev/docs/test",
    )


# ==============================================================================
# T004: Contract test GovernanceConfig backward compat (FR-031, FR-032)
# ==============================================================================


class TestGovernanceConfig3EBackwardCompat:
    """Contract tests for GovernanceConfig backward compatibility with Epic 3E.

    These tests verify that existing GovernanceConfig instances remain valid
    after Epic 3E adds RBAC, secret scanning, and network policy fields.

    Task: T004
    Requirements: FR-031 (RBAC Configuration Schema), FR-032 (Governance Contract Versioning)
    """

    @pytest.mark.requirement("3E-FR-031")
    @pytest.mark.requirement("3E-FR-032")
    def test_existing_configs_without_3e_fields_still_parse(self) -> None:
        """Contract: GovernanceConfig with only pre-3E fields still parses.

        Verifies backward compatibility by creating a GovernanceConfig using
        only fields from before Epic 3E (pii_encryption, audit_logging,
        policy_enforcement_level, data_retention_days, naming, quality_gates,
        custom_rules, policy_overrides, data_contracts).

        This test should PASS NOW since we haven't added 3E fields yet.
        """
        from floe_core.schemas.manifest import GovernanceConfig

        # Create config with only pre-3E fields
        config = GovernanceConfig(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
        )

        # All existing fields MUST still work
        assert config.pii_encryption == "required"
        assert config.audit_logging == "enabled"
        assert config.policy_enforcement_level == "strict"
        assert config.data_retention_days == 90

    @pytest.mark.requirement("3E-FR-031")
    @pytest.mark.requirement("3E-FR-032")
    def test_3e_fields_optional_default_none(self) -> None:
        """Contract: New 3E fields (rbac, secret_scanning, network_policies) default to None.

        Verifies that the new 3E fields are optional and default to None for
        backward compatibility with existing manifests.

        TDD: This will FAIL until T010 adds the fields.
        """
        from floe_core.schemas.manifest import GovernanceConfig

        # Config without 3E fields MUST work
        config = GovernanceConfig(pii_encryption="required")  # type: ignore[call-arg]

        # TDD: Will pass after T010 implements schema changes
        assert config.rbac is None  # type: ignore[attr-defined]
        assert config.secret_scanning is None  # type: ignore[attr-defined]
        assert config.network_policies is None  # type: ignore[attr-defined]

    @pytest.mark.requirement("3E-FR-031")
    @pytest.mark.requirement("3E-FR-032")
    def test_3e_fields_present_in_json_schema(self) -> None:
        """Contract: New 3E fields appear in JSON Schema output.

        Verifies that rbac, secret_scanning, and network_policies are present
        in the JSON Schema export for IDE autocomplete and external validation.

        TDD: This will FAIL until T010 adds the fields.
        """
        from floe_core.schemas.manifest import GovernanceConfig

        schema = GovernanceConfig.model_json_schema()
        properties = schema.get("properties", {})

        # TDD: Will pass after T010 implements schema changes
        assert "rbac" in properties, "rbac field missing from schema"
        assert "secret_scanning" in properties, "secret_scanning field missing from schema"
        assert "network_policies" in properties, "network_policies field missing from schema"

    @pytest.mark.requirement("3E-FR-031")
    def test_rbac_config_structure(self) -> None:
        """Contract: RBACConfig has expected structure.

        Verifies that RBACConfig has:
        - enabled: bool (default False)
        - required_role: str | None (default None)
        - allow_principal_fallback: bool (default True)

        TDD: This will FAIL until T010 adds RBACConfig.
        """
        from floe_core.schemas.governance import RBACConfig  # type: ignore[attr-defined]

        # TDD: Will pass after T010 implements schema changes
        config = RBACConfig()
        assert config.enabled is False
        assert config.required_role is None
        assert config.allow_principal_fallback is True

        # Test field override
        config_strict = RBACConfig(
            enabled=True,
            required_role="data_engineer",
            allow_principal_fallback=False,
        )
        assert config_strict.enabled is True
        assert config_strict.required_role == "data_engineer"
        assert config_strict.allow_principal_fallback is False

    @pytest.mark.requirement("3E-FR-031")
    def test_secret_scanning_config_structure(self) -> None:
        """Contract: SecretScanningConfig has expected structure.

        Verifies that SecretScanningConfig has:
        - enabled: bool (default False)
        - exclude_patterns: list[str] (default [])
        - custom_patterns: list[SecretPattern] | None (default None)
        - severity: Literal["error", "warning"] (default "error")

        TDD: This will FAIL until T010 adds SecretScanningConfig.
        """
        from floe_core.schemas.governance import SecretScanningConfig  # type: ignore[attr-defined]

        # TDD: Will pass after T010 implements schema changes
        config = SecretScanningConfig()
        assert config.enabled is False
        assert config.exclude_patterns == []
        assert config.custom_patterns is None
        assert config.severity == "error"

        # Test field override
        config_custom = SecretScanningConfig(
            enabled=True,
            exclude_patterns=["test_*.py", "mock_*.yaml"],
            severity="warning",
        )
        assert config_custom.enabled is True
        assert config_custom.exclude_patterns == ["test_*.py", "mock_*.yaml"]
        assert config_custom.severity == "warning"

    @pytest.mark.requirement("3E-FR-031")
    def test_network_policies_config_structure(self) -> None:
        """Contract: NetworkPoliciesConfig has expected structure.

        Verifies that NetworkPoliciesConfig has:
        - enabled: bool (default False)
        - default_deny: bool (default True)
        - custom_egress_rules: list[dict[str, Any]] (default [])

        TDD: This will FAIL until T010 adds NetworkPoliciesConfig.
        """
        from typing import Any  # noqa: F401

        from floe_core.schemas.governance import NetworkPoliciesConfig  # type: ignore[attr-defined]

        # TDD: Will pass after T010 implements schema changes
        config = NetworkPoliciesConfig()
        assert config.enabled is False
        assert config.default_deny is True
        assert config.custom_egress_rules == []

        # Test field override
        egress_rule: dict[str, Any] = {
            "to": [{"host": "api.example.com"}],
            "ports": [{"port": 443, "protocol": "TCP"}],
        }
        config_custom = NetworkPoliciesConfig(
            enabled=True,
            default_deny=False,
            custom_egress_rules=[egress_rule],
        )
        assert config_custom.enabled is True
        assert config_custom.default_deny is False
        assert len(config_custom.custom_egress_rules) == 1


# ==============================================================================
# T005: Contract test Violation.policy_type extension (FR-032)
# ==============================================================================


class TestViolationPolicyType3EExtension:
    """Contract tests for Violation.policy_type extension for Epic 3E.

    These tests verify that the policy_type Literal extends to include
    new types: rbac, secret_scanning, network_policy (in addition to the
    6 existing types: naming, coverage, documentation, semantic, custom,
    data_contract).

    Task: T005
    Requirements: FR-032 (Governance Contract Versioning)
    """

    @pytest.mark.requirement("3E-FR-032")
    def test_existing_policy_types_still_valid(self) -> None:
        """Contract: All 6 existing policy types still create valid Violations.

        Verifies that existing types (naming, coverage, documentation, semantic,
        custom, data_contract) remain valid after Epic 3E extensions.

        This test should PASS NOW since existing types are already valid.
        """
        existing_types = [
            "naming",
            "coverage",
            "documentation",
            "semantic",
            "custom",
            "data_contract",
        ]

        for policy_type in existing_types:
            violation = _make_violation(policy_type)
            assert violation.policy_type == policy_type

    @pytest.mark.requirement("3E-FR-032")
    def test_new_policy_types_accepted(self) -> None:
        """Contract: New 3E policy types (rbac, secret_scanning, network_policy) are valid.

        Verifies that the new policy types from Epic 3E are accepted by the
        Violation Pydantic model.

        TDD: This will FAIL until T007 updates the Violation.policy_type Literal.
        """
        new_types = [
            "rbac",
            "secret_scanning",
            "network_policy",
        ]

        # TDD: Will pass after T007 implements schema changes
        for policy_type in new_types:
            violation = _make_violation(policy_type)
            assert violation.policy_type == policy_type

    @pytest.mark.requirement("3E-FR-032")
    def test_invalid_policy_type_rejected(self) -> None:
        """Contract: Invalid policy types are rejected by Pydantic validation.

        Verifies that types not in the Literal are rejected.

        This test should PASS NOW since Pydantic validation already enforces
        the Literal constraint.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="policy_type"):
            _make_violation("unknown_type")

    @pytest.mark.requirement("3E-FR-032")
    def test_valid_policy_types_frozenset_extended(self) -> None:
        """Contract: VALID_POLICY_TYPES frozenset contains all 9 types.

        Verifies that the VALID_POLICY_TYPES constant in governance.py
        includes all 9 types: 6 existing + 3 new.

        TDD: This will FAIL until T008 updates VALID_POLICY_TYPES.
        """
        from floe_core.schemas.governance import VALID_POLICY_TYPES

        expected_types = frozenset(
            [
                # Existing (6)
                "naming",
                "coverage",
                "documentation",
                "semantic",
                "custom",
                "data_contract",
                # New in Epic 3E (3)
                "rbac",
                "secret_scanning",
                "network_policy",
            ]
        )

        # TDD: Will pass after T008 implements schema changes
        assert VALID_POLICY_TYPES == expected_types


# ==============================================================================
# T006: Contract test EnforcementResultSummary extension (FR-005, FR-032)
# ==============================================================================


class TestEnforcementResultSummary3EExtension:
    """Contract tests for EnforcementResultSummary extension for Epic 3E.

    These tests verify that EnforcementResultSummary extends with new fields
    for RBAC principal tracking (FR-005) and secrets scanned counter (FR-032).

    Task: T006
    Requirements: FR-005 (Contract Monitor Integration), FR-032 (Governance Contract Versioning)
    """

    @pytest.mark.requirement("3E-FR-005")
    @pytest.mark.requirement("3E-FR-032")
    def test_existing_summaries_still_parse(self) -> None:
        """Contract: EnforcementResultSummary with only pre-3E fields still parses.

        Verifies backward compatibility by creating an EnforcementResultSummary
        using only fields from before Epic 3E (passed, error_count, warning_count,
        policy_types_checked, models_validated, enforcement_level).

        This test should PASS NOW since we haven't added 3E fields yet.
        """
        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        summary = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=2,
            policy_types_checked=["naming", "coverage"],
            models_validated=25,
            enforcement_level="warn",
        )

        # All existing fields MUST still work
        assert summary.passed is True
        assert summary.error_count == 0
        assert summary.warning_count == 2
        assert summary.policy_types_checked == ["naming", "coverage"]
        assert summary.models_validated == 25
        assert summary.enforcement_level == "warn"

    @pytest.mark.requirement("3E-FR-005")
    @pytest.mark.requirement("3E-FR-032")
    def test_rbac_principal_field_optional(self) -> None:
        """Contract: rbac_principal field (str | None) defaults to None.

        Verifies that the new rbac_principal field is optional and defaults
        to None for backward compatibility.

        TDD: This will FAIL until T011 adds the field to EnforcementResultSummary.
        """
        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        # Summary without rbac_principal MUST work
        summary = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=0,
            policy_types_checked=[],
            models_validated=10,
            enforcement_level="off",
        )

        # TDD: Will pass after T011 implements schema changes
        assert summary.rbac_principal is None  # type: ignore[attr-defined]

        # Summary WITH rbac_principal
        summary_with_principal = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=0,
            policy_types_checked=["rbac"],
            models_validated=10,
            enforcement_level="strict",
            rbac_principal="user@example.com",  # type: ignore[call-arg]
        )
        assert summary_with_principal.rbac_principal == "user@example.com"  # type: ignore[attr-defined]

    @pytest.mark.requirement("3E-FR-005")
    @pytest.mark.requirement("3E-FR-032")
    def test_secrets_scanned_field_default_zero(self) -> None:
        """Contract: secrets_scanned field (int) defaults to 0.

        Verifies that the new secrets_scanned field is optional with default 0.

        TDD: This will FAIL until T011 adds the field to EnforcementResultSummary.
        """
        from floe_core.schemas.compiled_artifacts import EnforcementResultSummary

        # Summary without explicit secrets_scanned MUST default to 0
        summary = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=0,
            policy_types_checked=[],
            models_validated=10,
            enforcement_level="off",
        )

        # TDD: Will pass after T011 implements schema changes
        assert summary.secrets_scanned == 0  # type: ignore[attr-defined]

        # Summary WITH secrets_scanned
        summary_with_scan = EnforcementResultSummary(
            passed=True,
            error_count=0,
            warning_count=0,
            policy_types_checked=["secret_scanning"],
            models_validated=10,
            enforcement_level="strict",
            secrets_scanned=42,  # type: ignore[call-arg]
        )
        assert summary_with_scan.secrets_scanned == 42  # type: ignore[attr-defined]

    @pytest.mark.requirement("3E-FR-032")
    def test_enforcement_summary_new_violation_counters(self) -> None:
        """Contract: EnforcementSummary has new violation counters for 3E.

        Verifies that EnforcementSummary (from enforcement.result) has:
        - rbac_violations: int (default 0)
        - secret_violations: int (default 0)
        - network_policy_violations: int (default 0)

        TDD: This will FAIL until T009 adds the fields to EnforcementSummary.
        """
        from floe_core.enforcement.result import EnforcementSummary

        # Summary without 3E counters MUST default all to 0
        summary = EnforcementSummary(
            total_models=50,
            models_validated=50,
        )

        # TDD: Will pass after T009 implements schema changes
        assert summary.rbac_violations == 0  # type: ignore[attr-defined]
        assert summary.secret_violations == 0  # type: ignore[attr-defined]
        assert summary.network_policy_violations == 0  # type: ignore[attr-defined]

        # Summary WITH 3E counters
        # TDD: Will pass after T009 implements schema changes
        summary_with_3e = EnforcementSummary(  # type: ignore[call-arg]
            total_models=100,
            models_validated=100,
            rbac_violations=3,
            secret_violations=5,
            network_policy_violations=2,
        )
        assert summary_with_3e.rbac_violations == 3  # type: ignore[attr-defined]
        assert summary_with_3e.secret_violations == 5  # type: ignore[attr-defined]
        assert summary_with_3e.network_policy_violations == 2  # type: ignore[attr-defined]

    @pytest.mark.requirement("3E-FR-032")
    def test_version_bump_to_0_7_0(self) -> None:
        """Contract: COMPILED_ARTIFACTS_VERSION bumps to 0.7.0 for Epic 3E.

        Verifies that the CompiledArtifacts contract version is updated to 0.7.0
        to reflect the breaking changes from Epic 3E.

        TDD: This will FAIL until T012 updates COMPILED_ARTIFACTS_VERSION.
        """
        from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

        # TDD: Will pass after T012 implements version bump
        assert COMPILED_ARTIFACTS_VERSION == "0.7.0"
