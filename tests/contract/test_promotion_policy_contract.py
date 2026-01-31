"""Contract tests for PolicyEnforcer integration with PromotionController.

These tests verify the contract between PromotionController and PolicyEnforcer,
ensuring that promotion operations can correctly invoke and interpret policy
enforcement results.

Task: T014a
Requirements: FR-010 (Policy compliance gate integration)
"""

from __future__ import annotations

import pytest


class TestPolicyEnforcerPromotionContract:
    """Contract tests for PolicyEnforcer integration with PromotionController.

    These tests define the expected interface that PromotionController relies
    on when invoking PolicyEnforcer for the policy_compliance gate.
    """

    @pytest.mark.requirement("8C-FR-010")
    def test_policy_enforcer_can_be_instantiated_from_governance_config(self) -> None:
        """Contract: PolicyEnforcer MUST be instantiable from GovernanceConfig.

        PromotionController receives GovernanceConfig from manifest.yaml and
        must be able to create a PolicyEnforcer instance for gate validation.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        # Create a GovernanceConfig as it would come from manifest.yaml
        governance = GovernanceConfig()

        # PolicyEnforcer MUST accept governance_config parameter
        enforcer = PolicyEnforcer(governance_config=governance)

        assert enforcer is not None
        assert hasattr(enforcer, "enforce")

    @pytest.mark.requirement("8C-FR-010")
    def test_enforcement_result_passed_is_boolean(self) -> None:
        """Contract: EnforcementResult.passed MUST be a boolean.

        PromotionController checks result.passed to determine gate success/failure.
        This must be a boolean to enable correct gate status determination.
        """
        from datetime import datetime, timezone

        from floe_core.enforcement import EnforcementResult, EnforcementSummary

        # Create result with passed=True
        result_pass = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert isinstance(result_pass.passed, bool)
        assert result_pass.passed is True

        # Create result with passed=False
        result_fail = EnforcementResult(
            passed=False,
            violations=[],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert isinstance(result_fail.passed, bool)
        assert result_fail.passed is False

    @pytest.mark.requirement("8C-FR-010")
    def test_enforcement_result_violations_is_iterable(self) -> None:
        """Contract: EnforcementResult.violations MUST be iterable.

        PromotionController iterates over violations to construct gate result
        details. The violations field must support iteration.
        """
        from datetime import datetime, timezone

        from floe_core.enforcement import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="test_model",
            message="Model name violates naming convention",
            expected="medallion pattern",
            actual="test_model",
            suggestion="Rename to bronze_test_model",
            documentation_url="https://floe.dev/docs/naming",
        )

        result = EnforcementResult(
            passed=False,
            violations=[violation],
            summary=EnforcementSummary(
                total_models=1,
                models_validated=1,
                naming_violations=1,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        # Violations MUST be iterable
        assert hasattr(result.violations, "__iter__")
        violations_list = list(result.violations)
        assert len(violations_list) == 1
        assert violations_list[0].error_code == "FLOE-E201"

    @pytest.mark.requirement("8C-FR-010")
    def test_enforcement_result_violations_empty_list_is_valid(self) -> None:
        """Contract: EnforcementResult.violations MUST accept empty list.

        When no policy violations occur, violations should be an empty list.
        """
        from datetime import datetime, timezone

        from floe_core.enforcement import EnforcementResult, EnforcementSummary

        result = EnforcementResult(
            passed=True,
            violations=[],  # Empty list is valid
            summary=EnforcementSummary(total_models=5, models_validated=5),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        assert result.violations == []
        assert len(result.violations) == 0

    @pytest.mark.requirement("8C-FR-010")
    def test_violation_has_required_fields_for_gate_result(self) -> None:
        """Contract: Violation MUST have fields needed for GateResult.details.

        PromotionController constructs GateResult.details from violations.
        Required fields: error_code, severity, message, model_name.
        """
        from floe_core.enforcement import Violation

        violation = Violation(
            error_code="FLOE-E210",
            severity="error",
            policy_type="coverage",
            model_name="orders",
            message="Test coverage below threshold",
            expected="80%",
            actual="50%",
            suggestion="Add column tests",
            documentation_url="https://floe.dev/docs/coverage",
        )

        # Fields required for GateResult.details construction
        assert hasattr(violation, "error_code")
        assert hasattr(violation, "severity")
        assert hasattr(violation, "message")
        assert hasattr(violation, "model_name")

        assert violation.error_code == "FLOE-E210"
        assert violation.severity == "error"
        assert "coverage" in violation.message.lower()
        assert violation.model_name == "orders"

    @pytest.mark.requirement("8C-FR-010")
    def test_promotion_controller_accepts_policy_enforcer(self) -> None:
        """Contract: PromotionController MUST accept PolicyEnforcer parameter.

        PromotionController should be constructable with an optional PolicyEnforcer
        instance for the policy_compliance gate.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()
        governance = GovernanceConfig()
        policy_enforcer = PolicyEnforcer(governance_config=governance)

        # PromotionController MUST accept policy_enforcer parameter
        controller = PromotionController(
            client=oci_client,
            promotion=promotion,
            policy_enforcer=policy_enforcer,
        )

        assert controller.policy_enforcer is policy_enforcer

    @pytest.mark.requirement("8C-FR-010")
    def test_promotion_controller_policy_enforcer_is_optional(self) -> None:
        """Contract: PromotionController MUST work without PolicyEnforcer.

        PolicyEnforcer is optional - controller should work without it,
        treating policy_compliance gate as always-pass when not configured.
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        # PromotionController MUST work without policy_enforcer
        controller = PromotionController(
            client=oci_client,
            promotion=promotion,
            # No policy_enforcer provided
        )

        assert controller.policy_enforcer is None


class TestEnforcementResultGateIntegration:
    """Contract tests for EnforcementResult to GateResult conversion.

    These tests verify that EnforcementResult provides sufficient data
    for PromotionController to construct meaningful GateResult objects.
    """

    @pytest.mark.requirement("8C-FR-010")
    def test_enforcement_result_provides_error_count(self) -> None:
        """Contract: EnforcementResult MUST provide error_count property.

        PromotionController uses error_count to determine gate failure severity.
        """
        from datetime import datetime, timezone

        from floe_core.enforcement import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="test1",
                    message="Error 1",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E202",
                    severity="error",
                    policy_type="naming",
                    model_name="test2",
                    message="Error 2",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(
                total_models=2,
                models_validated=2,
                naming_violations=2,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        assert hasattr(result, "error_count")
        assert result.error_count == 2

    @pytest.mark.requirement("8C-FR-010")
    def test_enforcement_result_provides_warning_count(self) -> None:
        """Contract: EnforcementResult MUST provide warning_count property.

        PromotionController uses warning_count for gate result details.
        """
        from datetime import datetime, timezone

        from floe_core.enforcement import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        result = EnforcementResult(
            passed=True,
            violations=[
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test1",
                    message="Warning 1",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(
                total_models=1,
                models_validated=1,
                documentation_violations=1,
            ),
            enforcement_level="warn",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        assert hasattr(result, "warning_count")
        assert result.warning_count == 1

    @pytest.mark.requirement("8C-FR-010")
    def test_enforcement_result_summary_provides_duration(self) -> None:
        """Contract: EnforcementSummary MUST provide duration_ms.

        PromotionController records gate execution time in GateResult.duration_ms.
        """
        from floe_core.enforcement import EnforcementSummary

        summary = EnforcementSummary(
            total_models=10,
            models_validated=10,
            duration_ms=1234.56,
        )

        assert hasattr(summary, "duration_ms")
        assert summary.duration_ms == pytest.approx(1234.56)
