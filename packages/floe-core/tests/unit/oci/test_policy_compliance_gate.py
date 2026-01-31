"""Unit tests for policy compliance gate execution (T018).

Tests PromotionController._run_policy_compliance_gate() behavior.

Requirements tested:
    FR-010: Policy compliance gate integration
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestPolicyComplianceGate:
    """Tests for policy compliance gate execution."""

    @pytest.fixture
    def controller_with_enforcer(self) -> MagicMock:
        """Create a PromotionController with mocked PolicyEnforcer."""
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

        # Create real PolicyEnforcer with minimal config
        governance = GovernanceConfig()
        policy_enforcer = PolicyEnforcer(governance_config=governance)

        return PromotionController(
            client=oci_client,
            promotion=promotion,
            policy_enforcer=policy_enforcer,
        )

    @pytest.fixture
    def controller_without_enforcer(self) -> MagicMock:
        """Create a PromotionController without PolicyEnforcer."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-010")
    def test_policy_compliance_gate_passes_when_enforcer_passes(
        self, controller_with_enforcer: MagicMock
    ) -> None:
        """Test policy compliance gate returns PASSED when PolicyEnforcer passes."""
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        # Mock the PolicyEnforcer.enforce method to return passing result
        mock_result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=5, models_validated=5),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        with patch.object(
            controller_with_enforcer.policy_enforcer, "enforce", return_value=mock_result
        ):
            result = controller_with_enforcer._run_policy_compliance_gate(
                manifest={"nodes": {}},
                dry_run=False,
            )

            assert result.status == GateStatus.PASSED
            assert result.gate == PromotionGate.POLICY_COMPLIANCE
            assert result.error is None
            assert result.duration_ms >= 0

    @pytest.mark.requirement("8C-FR-010")
    def test_policy_compliance_gate_fails_when_enforcer_has_violations(
        self, controller_with_enforcer: MagicMock
    ) -> None:
        """Test policy compliance gate returns FAILED when PolicyEnforcer has violations."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        # Create a violation
        violation = Violation(
            error_code="FLOE-E001",
            severity="error",
            policy_type="naming",
            model_name="bad_model",
            message="Model naming violation",
            expected="stg_*",
            actual="bad_model",
            suggestion="Rename to follow naming convention",
            documentation_url="https://floe.dev/docs/errors/FLOE-E001",
        )

        mock_result = EnforcementResult(
            passed=False,
            violations=[violation],
            summary=EnforcementSummary(total_models=5, models_validated=5, naming_violations=1),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        with patch.object(
            controller_with_enforcer.policy_enforcer, "enforce", return_value=mock_result
        ):
            result = controller_with_enforcer._run_policy_compliance_gate(
                manifest={"nodes": {}},
                dry_run=False,
            )

            assert result.status == GateStatus.FAILED
            assert result.gate == PromotionGate.POLICY_COMPLIANCE
            assert result.error is not None
            assert "violation" in result.error.lower() or "policy" in result.error.lower()

    @pytest.mark.requirement("8C-FR-010")
    def test_policy_compliance_gate_skipped_when_no_enforcer(
        self, controller_without_enforcer: MagicMock
    ) -> None:
        """Test policy compliance gate returns SKIPPED when no PolicyEnforcer configured."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        result = controller_without_enforcer._run_policy_compliance_gate(
            manifest={"nodes": {}},
            dry_run=False,
        )

        assert result.status == GateStatus.SKIPPED
        assert result.gate == PromotionGate.POLICY_COMPLIANCE
        assert result.error is None

    @pytest.mark.requirement("8C-FR-010")
    def test_policy_compliance_gate_passes_dry_run_to_enforcer(
        self, controller_with_enforcer: MagicMock
    ) -> None:
        """Test that dry_run parameter is passed to PolicyEnforcer.enforce()."""
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        mock_result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=5, models_validated=5),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        with patch.object(
            controller_with_enforcer.policy_enforcer, "enforce", return_value=mock_result
        ) as mock_enforce:
            controller_with_enforcer._run_policy_compliance_gate(
                manifest={"nodes": {}},
                dry_run=True,
            )

            # Verify dry_run was passed
            mock_enforce.assert_called_once()
            call_kwargs = mock_enforce.call_args.kwargs
            assert call_kwargs.get("dry_run") is True

    @pytest.mark.requirement("8C-FR-010")
    def test_policy_compliance_gate_handles_enforcer_exception(
        self, controller_with_enforcer: MagicMock
    ) -> None:
        """Test policy compliance gate handles PolicyEnforcer exceptions gracefully."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        with patch.object(
            controller_with_enforcer.policy_enforcer,
            "enforce",
            side_effect=Exception("PolicyEnforcer internal error"),
        ):
            result = controller_with_enforcer._run_policy_compliance_gate(
                manifest={"nodes": {}},
                dry_run=False,
            )

            assert result.status == GateStatus.FAILED
            assert result.gate == PromotionGate.POLICY_COMPLIANCE
            assert result.error is not None
            assert "error" in result.error.lower()

    @pytest.mark.requirement("8C-FR-010")
    def test_policy_compliance_gate_records_duration(
        self, controller_with_enforcer: MagicMock
    ) -> None:
        """Test policy compliance gate records duration_ms."""
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        mock_result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=5, models_validated=5),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        with patch.object(
            controller_with_enforcer.policy_enforcer, "enforce", return_value=mock_result
        ):
            result = controller_with_enforcer._run_policy_compliance_gate(
                manifest={"nodes": {}},
                dry_run=False,
            )

            assert result.duration_ms >= 0
