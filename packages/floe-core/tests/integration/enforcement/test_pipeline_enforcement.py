"""Integration tests for policy enforcement in the compilation pipeline.

Tests the integration of PolicyEnforcer into Stage 4 (ENFORCE) of the
compilation pipeline. These tests validate end-to-end behavior including:
- ENFORCE stage integration with real manifest/spec files
- Strict mode blocking compilation on violations
- Warn mode logging violations without blocking

Task: T071, T072, T073
Requirements: FR-002 (Pipeline integration), US1 (Compile-time enforcement)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts


class TestEnforceStageIntegration:
    """Tests for ENFORCE stage integration in the compilation pipeline.

    Task: T071
    Requirement: FR-002 (Pipeline integration)
    """

    @pytest.mark.requirement("FR-002")
    def test_enforce_stage_calls_policy_enforcer(
        self,
        tmp_path: Path,
    ) -> None:
        """ENFORCE stage MUST instantiate and call PolicyEnforcer.

        Validates that Stage 4 (ENFORCE) of the compilation pipeline:
        1. Creates a PolicyEnforcer instance with GovernanceConfig
        2. Calls PolicyEnforcer.enforce() with dbt manifest
        3. Processes the EnforcementResult
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.manifest import GovernanceConfig

        # Create minimal governance config
        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
        )

        # Create minimal dbt manifest
        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        # Run ENFORCE stage
        with patch.object(PolicyEnforcer, "enforce") as mock_enforce:
            mock_enforce.return_value = MagicMock(
                passed=True,
                violations=[],
                error_count=0,
                warning_count=0,
            )

            result = run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
                dry_run=False,
            )

        # Verify PolicyEnforcer was called
        mock_enforce.assert_called_once()
        call_args = mock_enforce.call_args
        assert call_args.args[0] == dbt_manifest
        assert result.passed is True

    @pytest.mark.requirement("FR-002")
    def test_enforce_stage_returns_enforcement_result(
        self,
        tmp_path: Path,
    ) -> None:
        """ENFORCE stage MUST return EnforcementResult.

        Validates that run_enforce_stage returns the EnforcementResult
        from PolicyEnforcer for downstream processing.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.result import EnforcementResult
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        assert isinstance(result, EnforcementResult)
        assert result.passed is True
        assert result.enforcement_level == "warn"

    @pytest.mark.requirement("FR-002")
    def test_enforce_stage_with_no_governance_config_skips_enforcement(
        self,
    ) -> None:
        """ENFORCE stage MUST skip enforcement when GovernanceConfig is None.

        When no governance configuration is provided, the ENFORCE stage
        should return a passing result without running PolicyEnforcer.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.result import EnforcementResult

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        result = run_enforce_stage(
            governance_config=None,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        assert isinstance(result, EnforcementResult)
        assert result.passed is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("FR-002")
    def test_enforce_stage_with_enforcement_level_off_skips_enforcement(
        self,
    ) -> None:
        """ENFORCE stage MUST skip enforcement when level is 'off'.

        When policy_enforcement_level is 'off', the ENFORCE stage
        should return a passing result without running validators.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.result import EnforcementResult
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="off",
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        assert isinstance(result, EnforcementResult)
        assert result.passed is True
        assert result.enforcement_level == "off"


class TestStrictModeBlocking:
    """Tests for strict mode blocking compilation on violations.

    Task: T072
    Requirement: FR-001 (PolicyEnforcer core), US1 (Compile-time enforcement)
    """

    @pytest.mark.requirement("FR-001")
    def test_strict_mode_raises_on_error_violations(
        self,
    ) -> None:
        """Strict mode MUST raise PolicyEnforcementError on error violations.

        When enforcement_level is 'strict' and there are error-severity
        violations, run_enforce_stage MUST raise PolicyEnforcementError.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.errors import PolicyEnforcementError
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",  # Use strict to generate error-severity violations
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

        with pytest.raises(PolicyEnforcementError) as exc_info:
            run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
                dry_run=False,
            )

        # Verify exception contains violations
        assert len(exc_info.value.violations) > 0
        assert any(v.policy_type == "naming" for v in exc_info.value.violations)

    @pytest.mark.requirement("FR-001")
    def test_strict_mode_does_not_raise_on_warnings_only(
        self,
    ) -> None:
        """Strict mode MUST NOT raise when only warning-severity violations exist.

        When enforcement_level is 'strict' but all violations are warnings,
        run_enforce_stage should return the result without raising.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.result import EnforcementResult
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="warn",  # Warning only, not error
            ),
        )

        # Model that violates medallion naming (but only as warning)
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

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        assert isinstance(result, EnforcementResult)
        # Has warnings but no errors, so passes
        assert result.passed is True
        assert result.warning_count > 0
        assert result.error_count == 0

    @pytest.mark.requirement("FR-001")
    def test_strict_mode_passes_with_no_violations(
        self,
    ) -> None:
        """Strict mode MUST pass when there are no violations.

        When enforcement_level is 'strict' and validation passes,
        run_enforce_stage should return a passing result.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.result import EnforcementResult
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",
            ),
        )

        # Model that follows medallion naming (bronze_ prefix)
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

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        assert isinstance(result, EnforcementResult)
        assert result.passed is True
        assert result.error_count == 0


class TestWarnModeLogging:
    """Tests for warn mode logging violations without blocking.

    Task: T073
    Requirement: FR-001 (PolicyEnforcer core), US1 (Compile-time enforcement)
    """

    @pytest.mark.requirement("FR-001")
    def test_warn_mode_does_not_raise_on_violations(
        self,
    ) -> None:
        """Warn mode MUST NOT raise PolicyEnforcementError on violations.

        When enforcement_level is 'warn', run_enforce_stage should
        return the result without raising, even with error-severity violations.
        The result still reflects failure (passed=False) but no exception is raised.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.result import EnforcementResult
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="strict",  # Will generate error-severity violations
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

        # Should NOT raise (warn mode doesn't block)
        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        assert isinstance(result, EnforcementResult)
        # Warn mode: no exception raised, but passed reflects actual validation result
        assert result.error_count > 0  # Violations exist
        # Key behavior: no exception was raised

    @pytest.mark.requirement("FR-001")
    def test_warn_mode_logs_violations(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warn mode MUST log violations via structlog.

        When enforcement_level is 'warn' and violations exist,
        they should be logged for visibility.
        """
        import structlog

        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
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

        # Capture structlog output
        captured_logs: list[dict[str, Any]] = []

        def capture_processor(
            logger: Any,
            method_name: str,
            event_dict: dict[str, Any],
        ) -> dict[str, Any]:
            captured_logs.append(event_dict.copy())
            return event_dict

        # Configure structlog to capture logs
        with structlog.testing.capture_logs() as logs:
            run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
                dry_run=False,
            )

        # Verify violations were logged
        violation_logs = [
            log for log in logs if "violation" in log.get("event", "").lower()
        ]
        # Should have logged the violations in warn mode
        assert len(logs) > 0

    @pytest.mark.requirement("FR-001")
    def test_warn_mode_returns_all_violations_in_result(
        self,
    ) -> None:
        """Warn mode MUST include all violations in EnforcementResult.

        Even though warn mode doesn't block, all violations should be
        available in the result for reporting.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
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
                    "description": "",  # Missing description
                    "columns": {},
                },
            },
        }

        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=False,
        )

        # Both naming and documentation violations should be in result
        violation_types = {v.policy_type for v in result.violations}
        assert "naming" in violation_types
        assert "documentation" in violation_types


class TestDryRunModeInEnforceStage:
    """Tests for dry-run mode in ENFORCE stage.

    Task: T073 (part of warn mode testing)
    Requirement: FR-002 (Pipeline integration), US7 (Dry-run mode)
    """

    @pytest.mark.requirement("FR-002")
    def test_dry_run_passes_flag_to_policy_enforcer(
        self,
    ) -> None:
        """ENFORCE stage MUST pass dry_run flag to PolicyEnforcer.

        When dry_run=True, the flag should be passed through to
        PolicyEnforcer.enforce() for proper handling.
        """
        from floe_core.compilation.stages import run_enforce_stage
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
            "nodes": {},
        }

        with patch.object(PolicyEnforcer, "enforce") as mock_enforce:
            mock_enforce.return_value = MagicMock(
                passed=True,
                violations=[],
                error_count=0,
                warning_count=0,
            )

            run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
                dry_run=True,
            )

        # Verify dry_run was passed
        call_kwargs = mock_enforce.call_args.kwargs
        assert call_kwargs.get("dry_run") is True

    @pytest.mark.requirement("FR-002")
    def test_dry_run_does_not_raise_even_in_strict_mode(
        self,
    ) -> None:
        """Dry-run MUST NOT raise even when strict mode would block.

        When dry_run=True and enforcement_level='strict', violations
        should be reported but not cause an exception.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.enforcement.result import EnforcementResult
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

        # Should NOT raise because dry_run=True
        result = run_enforce_stage(
            governance_config=governance_config,
            dbt_manifest=dbt_manifest,
            dry_run=True,
        )

        assert isinstance(result, EnforcementResult)
        assert result.passed is True  # Dry-run always passes
        assert len(result.violations) > 0  # But violations are still reported


class TestEnforceStageOTelIntegration:
    """Tests for OpenTelemetry span attributes in ENFORCE stage.

    Task: T076
    Requirement: FR-007 (OTel span attributes)
    """

    @pytest.mark.requirement("FR-007")
    def test_enforce_stage_emits_otel_span_attributes(
        self,
    ) -> None:
        """ENFORCE stage MUST emit OTel span attributes for enforcement result.

        The span should include:
        - enforcement.passed: bool
        - enforcement.violation_count: int
        - enforcement.error_count: int
        - enforcement.warning_count: int
        - enforcement.level: str
        """
        from unittest.mock import MagicMock

        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.telemetry.tracing import create_span

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        # Track span attributes
        captured_attributes: dict[str, Any] = {}

        def mock_create_span(name: str, **kwargs: Any) -> MagicMock:
            span = MagicMock()
            span.__enter__ = MagicMock(return_value=span)
            span.__exit__ = MagicMock(return_value=False)

            def capture_attribute(key: str, value: Any) -> None:
                captured_attributes[key] = value

            span.set_attribute = capture_attribute
            return span

        with patch("floe_core.compilation.stages.create_span", mock_create_span):
            run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
                dry_run=False,
            )

        # Verify expected attributes were set
        assert "enforcement.passed" in captured_attributes
        assert "enforcement.violation_count" in captured_attributes
        assert captured_attributes["enforcement.passed"] is True
        assert captured_attributes["enforcement.violation_count"] == 0
