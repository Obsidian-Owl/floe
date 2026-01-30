"""Unit tests for gate orchestration (T019).

Tests PromotionController._run_all_gates() behavior.

Requirements tested:
    FR-002: Gate validation before promotion
    FR-010: Policy compliance gate integration
    FR-012: Gate timeout configuration
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestRunAllGates:
    """Tests for gate orchestration."""

    @pytest.fixture
    def controller_with_gates(self) -> MagicMock:
        """Create a PromotionController with custom environment gates."""
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)

        # Custom environments with different gates
        envs = [
            EnvironmentConfig(
                name="dev",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
            EnvironmentConfig(
                name="staging",
                gates={
                    PromotionGate.POLICY_COMPLIANCE: True,
                    PromotionGate.TESTS: True,
                },
            ),
            EnvironmentConfig(
                name="prod",
                gates={
                    PromotionGate.POLICY_COMPLIANCE: True,
                    PromotionGate.TESTS: True,
                    PromotionGate.SECURITY_SCAN: True,
                },
            ),
        ]
        promotion = PromotionConfig(
            environments=envs,
            gate_commands={
                "tests": "pytest --collect-only",
                "security_scan": "trivy image ${ARTIFACT_REF}",
            },
        )

        governance = GovernanceConfig()
        policy_enforcer = PolicyEnforcer(governance_config=governance)

        return PromotionController(
            client=oci_client,
            promotion=promotion,
            policy_enforcer=policy_enforcer,
        )

    @pytest.mark.requirement("8C-FR-002")
    def test_run_all_gates_returns_list_of_gate_results(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test _run_all_gates returns list of GateResult objects."""
        from floe_core.schemas.promotion import GateResult

        # Mock the individual gate methods
        with patch.object(
            controller_with_gates, "_run_policy_compliance_gate"
        ) as mock_policy, patch.object(
            controller_with_gates, "_run_gate"
        ) as mock_gate:
            from floe_core.schemas.promotion import GateStatus, PromotionGate

            mock_policy.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=100,
            )
            mock_gate.return_value = GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=200,
            )

            results = controller_with_gates._run_all_gates(
                to_env="staging",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=False,
            )

            assert isinstance(results, list)
            assert len(results) > 0
            assert all(isinstance(r, GateResult) for r in results)

    @pytest.mark.requirement("8C-FR-010")
    def test_run_all_gates_always_runs_policy_compliance(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test that policy_compliance gate is always executed."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        with patch.object(
            controller_with_gates, "_run_policy_compliance_gate"
        ) as mock_policy:
            mock_policy.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=100,
            )

            results = controller_with_gates._run_all_gates(
                to_env="dev",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=False,
            )

            mock_policy.assert_called_once()
            # Verify policy_compliance gate is in results
            policy_results = [r for r in results if r.gate == PromotionGate.POLICY_COMPLIANCE]
            assert len(policy_results) == 1

    @pytest.mark.requirement("8C-FR-002")
    def test_run_all_gates_runs_enabled_gates_only(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test that only enabled gates for the environment are run."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        with patch.object(
            controller_with_gates, "_run_policy_compliance_gate"
        ) as mock_policy, patch.object(
            controller_with_gates, "_run_gate"
        ) as mock_gate:
            mock_policy.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=100,
            )
            mock_gate.return_value = GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=200,
            )

            # dev only has policy_compliance enabled
            results = controller_with_gates._run_all_gates(
                to_env="dev",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=False,
            )

            # Only policy_compliance should be called
            mock_policy.assert_called_once()
            mock_gate.assert_not_called()
            assert len(results) == 1

    @pytest.mark.requirement("8C-FR-002")
    def test_run_all_gates_runs_tests_gate_when_enabled(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test that tests gate is run when enabled for environment."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        with patch.object(
            controller_with_gates, "_run_policy_compliance_gate"
        ) as mock_policy, patch.object(
            controller_with_gates, "_run_gate"
        ) as mock_gate:
            mock_policy.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=100,
            )
            mock_gate.return_value = GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=200,
            )

            # staging has policy_compliance and tests enabled
            results = controller_with_gates._run_all_gates(
                to_env="staging",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=False,
            )

            mock_policy.assert_called_once()
            mock_gate.assert_called_once()
            assert len(results) == 2

    @pytest.mark.requirement("8C-FR-002")
    def test_run_all_gates_stops_on_failure_unless_dry_run(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test that gate execution stops on first failure (not dry_run)."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        with patch.object(
            controller_with_gates, "_run_policy_compliance_gate"
        ) as mock_policy, patch.object(
            controller_with_gates, "_run_gate"
        ) as mock_gate:
            # Policy compliance fails
            mock_policy.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.FAILED,
                duration_ms=100,
                error="Policy violations found",
            )
            mock_gate.return_value = GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=200,
            )

            # prod has 3 gates, but should stop after first failure
            results = controller_with_gates._run_all_gates(
                to_env="prod",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=False,
            )

            # Should stop after policy_compliance failure
            mock_policy.assert_called_once()
            mock_gate.assert_not_called()

            # Should contain the failed gate result
            assert len(results) == 1
            assert results[0].status == GateStatus.FAILED

    @pytest.mark.requirement("8C-FR-002")
    def test_run_all_gates_continues_on_failure_in_dry_run(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test that dry_run continues all gates even after failure."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        with patch.object(
            controller_with_gates, "_run_policy_compliance_gate"
        ) as mock_policy, patch.object(
            controller_with_gates, "_run_gate"
        ) as mock_gate:
            # Policy compliance fails
            mock_policy.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.FAILED,
                duration_ms=100,
                error="Policy violations found",
            )
            mock_gate.return_value = GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=200,
            )

            # staging has 2 gates, dry_run should continue all
            results = controller_with_gates._run_all_gates(
                to_env="staging",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=True,
            )

            # Should continue after policy_compliance failure
            mock_policy.assert_called_once()
            mock_gate.assert_called_once()

            # Should contain both gate results
            assert len(results) == 2

    @pytest.mark.requirement("8C-FR-012")
    def test_run_all_gates_uses_environment_timeout(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test that gate execution uses environment's timeout configuration."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        with patch.object(
            controller_with_gates, "_run_policy_compliance_gate"
        ) as mock_policy, patch.object(
            controller_with_gates, "_run_gate"
        ) as mock_gate:
            mock_policy.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=100,
            )
            mock_gate.return_value = GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=200,
            )

            controller_with_gates._run_all_gates(
                to_env="staging",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=False,
            )

            # Verify _run_gate was called with timeout
            mock_gate.assert_called_once()
            call_kwargs = mock_gate.call_args.kwargs
            assert "timeout_seconds" in call_kwargs
            # Default timeout is 300 seconds
            assert call_kwargs["timeout_seconds"] == 300

    @pytest.mark.requirement("8C-FR-002")
    def test_run_all_gates_raises_for_unknown_environment(
        self, controller_with_gates: MagicMock
    ) -> None:
        """Test that _run_all_gates raises ValueError for unknown environment."""
        with pytest.raises(ValueError, match="not found"):
            controller_with_gates._run_all_gates(
                to_env="unknown",
                manifest={"nodes": {}},
                artifact_ref="harbor.example.com/floe:v1.0.0",
                dry_run=False,
            )
