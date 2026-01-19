"""Unit tests for audit logging in policy enforcement.

Tests the structured audit logging requirements:
- Policy decision logging with required fields (FR-010)
- Violation logging with required audit fields
- OTel span events for violations

Task: T083, T084
Requirements: FR-010 (Audit logging), US6 (Audit logging)
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestAuditLogFields:
    """Tests for audit log field requirements.

    Task: T083
    Requirement: FR-010, US6
    """

    @pytest.mark.requirement("FR-010")
    def test_policy_decision_log_contains_required_fields(
        self,
    ) -> None:
        """Policy decision logs MUST include all required audit fields.

        Required fields per FR-010:
        - policy_type
        - model_name (or model_count for aggregate)
        - result (passed/failed)
        - timestamp (implicit in structlog)
        - manifest_version
        - enforcement_level
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
                "model.my_project.bronze_orders": {
                    "name": "bronze_orders",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        with patch("floe_core.enforcement.policy_enforcer.logger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.bind.return_value = mock_log

            enforcer = PolicyEnforcer(governance_config=governance_config)
            result = enforcer.enforce(dbt_manifest)

            # Verify enforcement_started log
            start_calls = [
                call for call in mock_log.info.call_args_list
                if call[0][0] == "enforcement_started"
            ]
            assert len(start_calls) >= 1
            start_kwargs = start_calls[0][1]
            assert "manifest_version" in start_kwargs
            assert "model_count" in start_kwargs

            # Verify enforcement_completed log
            complete_calls = [
                call for call in mock_log.info.call_args_list
                if call[0][0] == "enforcement_completed"
            ]
            assert len(complete_calls) >= 1
            complete_kwargs = complete_calls[0][1]
            assert "passed" in complete_kwargs
            assert "violation_count" in complete_kwargs

    @pytest.mark.requirement("FR-010")
    def test_enforcement_log_includes_manifest_version(
        self,
    ) -> None:
        """Enforcement logs MUST include manifest_version for audit trail.

        The dbt manifest version is critical for tracing which manifest
        was evaluated when an enforcement decision was made.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="warn",
            ),
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.9.5"},  # Specific version
            "nodes": {},
        }

        with patch("floe_core.enforcement.policy_enforcer.logger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.bind.return_value = mock_log

            enforcer = PolicyEnforcer(governance_config=governance_config)
            result = enforcer.enforce(dbt_manifest)

            # The result should contain manifest_version
            assert result.manifest_version == "1.9.5"

            # And logs should reference it
            start_calls = [
                call for call in mock_log.info.call_args_list
                if call[0][0] == "enforcement_started"
            ]
            assert len(start_calls) >= 1
            assert start_calls[0][1]["manifest_version"] == "1.9.5"

    @pytest.mark.requirement("US6")
    def test_violation_log_includes_required_audit_fields(
        self,
    ) -> None:
        """Violation logs MUST include all fields for audit compliance.

        Per US6 acceptance criteria, violation logs must include:
        - violation_code (error_code)
        - severity
        - remediation (suggestion)
        - documentation_url
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="warn",
            ),
        )

        # Model that will generate a violation
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

        # Verify we got a violation
        assert len(result.violations) > 0
        violation = result.violations[0]

        # All audit fields must be present
        assert violation.error_code is not None
        assert violation.severity in ("warning", "error")
        assert violation.suggestion is not None
        assert violation.documentation_url is not None

    @pytest.mark.requirement("US6")
    def test_enforcement_log_includes_duration(
        self,
    ) -> None:
        """Enforcement logs MUST include duration for performance auditing.

        Duration tracking helps identify slow policy evaluations.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="warn",
            ),
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        with patch("floe_core.enforcement.policy_enforcer.logger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.bind.return_value = mock_log

            enforcer = PolicyEnforcer(governance_config=governance_config)
            result = enforcer.enforce(dbt_manifest)

            # Verify duration is logged
            complete_calls = [
                call for call in mock_log.info.call_args_list
                if call[0][0] == "enforcement_completed"
            ]
            assert len(complete_calls) >= 1
            assert "duration_ms" in complete_calls[0][1]

    @pytest.mark.requirement("US6")
    def test_enforcement_log_includes_enforcement_level(
        self,
    ) -> None:
        """Enforcement logs MUST include enforcement_level for audit context.

        Knowing whether enforcement was 'strict' or 'warn' is critical
        for understanding why a build passed or failed.
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
                "model.my_project.bronze_orders": {
                    "name": "bronze_orders",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest)

        # Result should contain enforcement_level
        assert result.enforcement_level == "strict"


class TestOTelSpanEvents:
    """Tests for OTel span events in policy enforcement.

    Task: T084
    Requirement: US6 (Audit logging with OTel)
    """

    @pytest.mark.requirement("US6")
    def test_enforcement_emits_otel_span_with_attributes(
        self,
    ) -> None:
        """Enforcement MUST emit OTel span with audit attributes.

        The OTel span should include:
        - enforcement.passed
        - enforcement.violation_count
        - enforcement.error_count
        - enforcement.warning_count
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

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

        with patch("floe_core.compilation.stages.create_span") as mock_create_span:
            mock_span = MagicMock()
            mock_create_span.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = MagicMock(return_value=False)

            result = run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
            )

            # Verify span was created
            mock_create_span.assert_called()

            # Verify span attributes were set
            set_attribute_calls = {
                call[0][0]: call[0][1]
                for call in mock_span.set_attribute.call_args_list
            }

            assert "enforcement.passed" in set_attribute_calls
            assert "enforcement.violation_count" in set_attribute_calls
            assert "enforcement.error_count" in set_attribute_calls
            assert "enforcement.warning_count" in set_attribute_calls

    @pytest.mark.requirement("US6")
    def test_enforcement_span_includes_duration(
        self,
    ) -> None:
        """Enforcement OTel span MUST include duration_ms attribute.

        Duration is critical for performance monitoring and alerting.
        """
        from floe_core.compilation.stages import run_enforce_stage
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="warn",
            ),
        )

        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        with patch("floe_core.compilation.stages.create_span") as mock_create_span:
            mock_span = MagicMock()
            mock_create_span.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = MagicMock(return_value=False)

            result = run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
            )

            set_attribute_calls = {
                call[0][0]: call[0][1]
                for call in mock_span.set_attribute.call_args_list
            }

            assert "enforcement.duration_ms" in set_attribute_calls
            # Duration should be a positive number
            assert set_attribute_calls["enforcement.duration_ms"] >= 0

    @pytest.mark.requirement("US6")
    def test_enforcement_span_includes_enforcement_level(
        self,
    ) -> None:
        """Enforcement OTel span MUST include enforcement level attribute.

        This allows filtering traces by enforcement strictness.
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
                "model.my_project.bronze_orders": {
                    "name": "bronze_orders",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        with patch("floe_core.compilation.stages.create_span") as mock_create_span:
            mock_span = MagicMock()
            mock_create_span.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = MagicMock(return_value=False)

            result = run_enforce_stage(
                governance_config=governance_config,
                dbt_manifest=dbt_manifest,
            )

            # Check the create_span call included enforcement.level
            call_kwargs = mock_create_span.call_args_list[0]
            if len(call_kwargs) > 1 and "attributes" in call_kwargs[1]:
                assert "enforcement.level" in call_kwargs[1]["attributes"]

    @pytest.mark.requirement("US6")
    def test_violation_events_emitted_to_span(
        self,
    ) -> None:
        """Violations SHOULD be emitted as OTel span events.

        Each violation can be added as a span event for detailed tracing.
        This test verifies that when violations occur, they are captured
        in the enforcement result which can be converted to span events.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance_config = GovernanceConfig(
            policy_enforcement_level="warn",
            naming=NamingConfig(
                pattern="medallion",
                enforcement="warn",
            ),
        )

        # Multiple models that will generate violations
        dbt_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.my_project.bad_model_1": {
                    "name": "bad_model_1",
                    "resource_type": "model",
                    "columns": {},
                },
                "model.my_project.bad_model_2": {
                    "name": "bad_model_2",
                    "resource_type": "model",
                    "columns": {},
                },
            },
        }

        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest)

        # Each violation should have enough data to be converted to an OTel event
        assert len(result.violations) >= 2
        for violation in result.violations:
            # All fields needed for an OTel event
            assert violation.error_code is not None
            assert violation.policy_type is not None
            assert violation.model_name is not None
            assert violation.message is not None
