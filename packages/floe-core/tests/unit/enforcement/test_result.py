"""Unit tests for enforcement result models.

Tests for Violation, EnforcementSummary, and EnforcementResult models.
Following TDD: these tests are written FIRST and will FAIL until
the models are implemented in T025-T027.

Task: T020, T021
Requirements: FR-002 (Pipeline Integration), US1 (Compile-time Enforcement)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


class TestViolation:
    """Tests for Violation model (T021).

    Violation represents a single policy violation found during enforcement.
    See: data-model.md, Error Code Catalog
    """

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_all_fields(self) -> None:
        """Test Violation with all fields populated."""
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="stg_payments",
            column_name=None,
            message="Model name violates medallion convention",
            expected="^(bronze|silver|gold)_.*$",
            actual="stg_payments",
            suggestion="Rename to bronze_payments, silver_payments, or gold_payments",
            documentation_url="https://floe.dev/docs/naming#medallion",
        )
        assert violation.error_code == "FLOE-E201"
        assert violation.severity == "error"
        assert violation.policy_type == "naming"
        assert violation.model_name == "stg_payments"
        assert violation.column_name is None
        assert "medallion" in violation.message

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_with_column(self) -> None:
        """Test Violation with column_name for column-level violations."""
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E221",
            severity="error",
            policy_type="documentation",
            model_name="customers",
            column_name="email",
            message="Missing column description",
            expected="Non-empty description",
            actual="(no description)",
            suggestion="Add description to column 'email' in model 'customers'",
            documentation_url="https://floe.dev/docs/documentation#columns",
        )
        assert violation.column_name == "email"
        assert violation.policy_type == "documentation"

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_severity_values(self) -> None:
        """Test Violation accepts valid severity values."""
        from typing import Literal, get_args

        from floe_core.enforcement.result import Violation

        SeverityType = Literal["error", "warning"]
        for severity in get_args(SeverityType):
            violation = Violation(
                error_code="FLOE-E201",
                severity=severity,
                policy_type="naming",
                model_name="test_model",
                message="Test message",
                expected="expected",
                actual="actual",
                suggestion="Fix it",
                documentation_url="https://floe.dev/docs/test",
            )
            assert violation.severity == severity

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_severity_invalid_rejected(self) -> None:
        """Test Violation rejects invalid severity values."""
        from floe_core.enforcement.result import Violation

        with pytest.raises(ValidationError, match="severity"):
            Violation(
                error_code="FLOE-E201",
                severity="info",  # type: ignore[arg-type]  # Invalid value for testing
                policy_type="naming",
                model_name="test_model",
                message="Test message",
                expected="expected",
                actual="actual",
                suggestion="Fix it",
                documentation_url="https://floe.dev/docs/test",
            )

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_policy_type_values(self) -> None:
        """Test Violation accepts valid policy_type values."""
        from typing import Literal, get_args

        from floe_core.enforcement.result import Violation

        PolicyType = Literal["naming", "coverage", "documentation", "semantic", "custom"]
        for policy_type in get_args(PolicyType):
            violation = Violation(
                error_code="FLOE-E201",
                severity="error",
                policy_type=policy_type,
                model_name="test_model",
                message="Test message",
                expected="expected",
                actual="actual",
                suggestion="Fix it",
                documentation_url="https://floe.dev/docs/test",
            )
            assert violation.policy_type == policy_type

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_policy_type_invalid_rejected(self) -> None:
        """Test Violation rejects invalid policy_type values."""
        from floe_core.enforcement.result import Violation

        with pytest.raises(ValidationError, match="policy_type"):
            Violation(
                error_code="FLOE-E201",
                severity="error",
                policy_type="security",  # type: ignore[arg-type]  # Invalid value for testing
                model_name="test_model",
                message="Test message",
                expected="expected",
                actual="actual",
                suggestion="Fix it",
                documentation_url="https://floe.dev/docs/test",
            )

    @pytest.mark.requirement("3A-US1-FR002")
    def test_violation_frozen(self) -> None:
        """Test Violation is immutable (frozen=True)."""
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="test_model",
            message="Test message",
            expected="expected",
            actual="actual",
            suggestion="Fix it",
            documentation_url="https://floe.dev/docs/test",
        )
        # Verify frozen config is set
        assert violation.model_config.get("frozen") is True


class TestEnforcementSummary:
    """Tests for EnforcementSummary model (T026).

    EnforcementSummary provides statistics about the enforcement run.
    """

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_summary_defaults(self) -> None:
        """Test EnforcementSummary has correct default values."""
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=10,
            models_validated=10,
        )
        assert summary.total_models == 10
        assert summary.models_validated == 10
        assert summary.naming_violations == 0
        assert summary.coverage_violations == 0
        assert summary.documentation_violations == 0
        assert summary.duration_ms == 0.0

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_summary_all_fields(self) -> None:
        """Test EnforcementSummary with all fields populated."""
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=50,
            models_validated=48,
            naming_violations=3,
            coverage_violations=5,
            documentation_violations=2,
            duration_ms=123.45,
        )
        assert summary.total_models == 50
        assert summary.models_validated == 48
        assert summary.naming_violations == 3
        assert summary.coverage_violations == 5
        assert summary.documentation_violations == 2
        assert summary.duration_ms == pytest.approx(123.45)

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_summary_frozen(self) -> None:
        """Test EnforcementSummary is immutable (frozen=True)."""
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(total_models=10, models_validated=10)
        # Verify frozen config is set
        assert summary.model_config.get("frozen") is True


class TestEnforcementResult:
    """Tests for EnforcementResult model (T020).

    EnforcementResult is the top-level result returned by PolicyEnforcer.
    """

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_passed_no_violations(self) -> None:
        """Test EnforcementResult with passed=True and no violations."""
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result.passed is True
        assert len(result.violations) == 0
        assert result.enforcement_level == "strict"

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_failed_with_violations(self) -> None:
        """Test EnforcementResult with passed=False and violations."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        violations = [
            Violation(
                error_code="FLOE-E201",
                severity="error",
                policy_type="naming",
                model_name="stg_payments",
                message="Naming violation",
                expected="medallion",
                actual="staging",
                suggestion="Rename",
                documentation_url="https://floe.dev/docs",
            ),
        ]
        result = EnforcementResult(
            passed=False,
            violations=violations,
            summary=EnforcementSummary(total_models=10, models_validated=10, naming_violations=1),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.summary.naming_violations == 1

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_enforcement_level_values(self) -> None:
        """Test EnforcementResult accepts valid enforcement_level values."""
        from typing import Literal, get_args

        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        EnforcementLevel = Literal["off", "warn", "strict"]
        for level in get_args(EnforcementLevel):
            result = EnforcementResult(
                passed=True,
                violations=[],
                summary=EnforcementSummary(total_models=0, models_validated=0),
                enforcement_level=level,
                manifest_version="1.0.0",
                timestamp=datetime.now(timezone.utc),
            )
            assert result.enforcement_level == level

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_enforcement_level_invalid_rejected(self) -> None:
        """Test EnforcementResult rejects invalid enforcement_level values."""
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        with pytest.raises(ValidationError, match="enforcement_level"):
            EnforcementResult(
                passed=True,
                violations=[],
                summary=EnforcementSummary(total_models=0, models_validated=0),
                enforcement_level="moderate",  # type: ignore[arg-type]  # Invalid value for testing
                manifest_version="1.0.0",
                timestamp=datetime.now(timezone.utc),
            )

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_frozen(self) -> None:
        """Test EnforcementResult is immutable (frozen=True)."""
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=0, models_validated=0),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        # Verify frozen config is set
        assert result.model_config.get("frozen") is True

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_has_errors_property(self) -> None:
        """Test EnforcementResult.has_errors returns True if any error severity."""
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        # No violations = no errors
        result_clean = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result_clean.has_errors is False

        # Warning only = no errors
        result_warning = EnforcementResult(
            passed=True,
            violations=[
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test",
                    message="Placeholder",
                    expected="real",
                    actual="TODO",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(
                total_models=10, models_validated=10, documentation_violations=1
            ),
            enforcement_level="warn",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result_warning.has_errors is False

        # Error severity = has errors
        result_error = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="test",
                    message="Error",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(total_models=10, models_validated=10, naming_violations=1),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result_error.has_errors is True

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_warning_count_property(self) -> None:
        """Test EnforcementResult.warning_count returns count of warnings."""
        from floe_core.enforcement.result import (
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
                    message="Placeholder",
                    expected="real",
                    actual="TODO",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test2",
                    message="Placeholder",
                    expected="real",
                    actual="TBD",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="test3",
                    message="Error",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(
                total_models=10,
                models_validated=10,
                naming_violations=1,
                documentation_violations=2,
            ),
            enforcement_level="warn",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result.warning_count == 2

    @pytest.mark.requirement("3A-US1-FR002")
    def test_enforcement_result_error_count_property(self) -> None:
        """Test EnforcementResult.error_count returns count of errors."""
        from floe_core.enforcement.result import (
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
                    error_code="FLOE-E210",
                    severity="error",
                    policy_type="coverage",
                    model_name="test2",
                    message="Error 2",
                    expected="80",
                    actual="50",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E222",
                    severity="warning",
                    policy_type="documentation",
                    model_name="test3",
                    message="Warning",
                    expected="real",
                    actual="TODO",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(
                total_models=10,
                models_validated=10,
                naming_violations=1,
                coverage_violations=1,
                documentation_violations=1,
            ),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )
        assert result.error_count == 2


# ==============================================================================
# Epic 3B: Extended Violation Model Tests (T013)
# ==============================================================================


class TestViolationEpic3BFields:
    """Tests for Epic 3B context fields added to Violation model.

    New fields: downstream_impact, first_detected, occurrences, override_applied
    Task: T013
    Requirements: FR-018, FR-019
    """

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_with_downstream_impact(self) -> None:
        """Test Violation with downstream_impact field.

        Given a Violation with downstream models affected,
        When creating the Violation,
        Then downstream_impact contains the affected model names.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="stg_customers",
            message="Naming violation",
            expected="^(bronze|silver|gold)_.*$",
            actual="stg_customers",
            suggestion="Rename model",
            documentation_url="https://floe.dev/docs/naming",
            downstream_impact=["dim_customers", "fct_orders", "rpt_sales"],
        )

        assert violation.downstream_impact == [
            "dim_customers",
            "fct_orders",
            "rpt_sales",
        ]

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_downstream_impact_empty_list(self) -> None:
        """Test Violation with empty downstream_impact list.

        Given a Violation with no downstream models,
        When creating the Violation with empty list,
        Then downstream_impact is an empty list.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="leaf_model",
            message="Naming violation",
            expected="pattern",
            actual="actual",
            suggestion="Fix",
            documentation_url="https://floe.dev",
            downstream_impact=[],
        )

        assert violation.downstream_impact == []

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_without_downstream_impact_backward_compat(self) -> None:
        """Test Violation without downstream_impact for backward compatibility.

        Given a Violation created without downstream_impact,
        When creating the Violation,
        Then downstream_impact defaults to None.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="test_model",
            message="Test",
            expected="x",
            actual="y",
            suggestion="Fix",
            documentation_url="https://floe.dev",
        )

        assert violation.downstream_impact is None

    @pytest.mark.requirement("003b-FR-019")
    def test_violation_with_override_applied(self) -> None:
        """Test Violation with override_applied field.

        Given a Violation where a policy override was applied,
        When creating the Violation,
        Then override_applied contains the pattern that matched.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="warning",  # Downgraded from error
            policy_type="naming",
            model_name="legacy_customers",
            message="Naming violation (downgraded)",
            expected="^(bronze|silver|gold)_.*$",
            actual="legacy_customers",
            suggestion="Consider renaming after migration",
            documentation_url="https://floe.dev/docs/naming",
            override_applied="legacy_*",
        )

        assert violation.override_applied == "legacy_*"

    @pytest.mark.requirement("003b-FR-019")
    def test_violation_without_override_backward_compat(self) -> None:
        """Test Violation without override_applied for backward compatibility.

        Given a Violation created without override_applied,
        When creating the Violation,
        Then override_applied defaults to None.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="test_model",
            message="Test",
            expected="x",
            actual="y",
            suggestion="Fix",
            documentation_url="https://floe.dev",
        )

        assert violation.override_applied is None

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_with_first_detected(self) -> None:
        """Test Violation with first_detected timestamp.

        Given a Violation with historical tracking,
        When creating the Violation,
        Then first_detected contains the timestamp.
        """
        from floe_core.enforcement.result import Violation

        detected_time = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="test_model",
            message="Test",
            expected="x",
            actual="y",
            suggestion="Fix",
            documentation_url="https://floe.dev",
            first_detected=detected_time,
        )

        assert violation.first_detected == detected_time

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_with_occurrences(self) -> None:
        """Test Violation with occurrences count.

        Given a Violation detected multiple times,
        When creating the Violation,
        Then occurrences contains the count.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="test_model",
            message="Test",
            expected="x",
            actual="y",
            suggestion="Fix",
            documentation_url="https://floe.dev",
            occurrences=5,
        )

        assert violation.occurrences == 5

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_occurrences_must_be_positive(self) -> None:
        """Test Violation occurrences must be >= 1.

        Given occurrences=0,
        When creating a Violation,
        Then ValidationError is raised.
        """
        from floe_core.enforcement.result import Violation

        with pytest.raises(ValidationError) as exc_info:
            Violation(
                error_code="FLOE-E201",
                severity="error",
                policy_type="naming",
                model_name="test_model",
                message="Test",
                expected="x",
                actual="y",
                suggestion="Fix",
                documentation_url="https://floe.dev",
                occurrences=0,
            )

        assert "occurrences" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_with_all_epic3b_fields(self) -> None:
        """Test Violation with all Epic 3B fields populated.

        Given a Violation with all new optional fields,
        When creating the Violation,
        Then all fields are stored correctly.
        """
        from floe_core.enforcement.result import Violation

        detected_time = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        violation = Violation(
            error_code="FLOE-E201",
            severity="warning",
            policy_type="naming",
            model_name="legacy_customers",
            message="Naming violation (downgraded)",
            expected="^(bronze|silver|gold)_.*$",
            actual="legacy_customers",
            suggestion="Rename after migration",
            documentation_url="https://floe.dev/docs/naming",
            downstream_impact=["dim_customers", "fct_orders"],
            first_detected=detected_time,
            occurrences=3,
            override_applied="legacy_*",
        )

        assert violation.downstream_impact == ["dim_customers", "fct_orders"]
        assert violation.first_detected == detected_time
        assert violation.occurrences == 3
        assert violation.override_applied == "legacy_*"

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_new_policy_types_semantic(self) -> None:
        """Test Violation with policy_type='semantic' (new in Epic 3B).

        Given policy_type='semantic',
        When creating a Violation,
        Then the violation is created successfully.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E301",
            severity="error",
            policy_type="semantic",
            model_name="fct_orders",
            message="Invalid ref: model 'stg_orders' not found",
            expected="Valid model reference",
            actual="ref('stg_orders') - model not in manifest",
            suggestion="Check model name or add missing model",
            documentation_url="https://floe.dev/docs/semantic#refs",
        )

        assert violation.policy_type == "semantic"

    @pytest.mark.requirement("003b-FR-018")
    def test_violation_new_policy_types_custom(self) -> None:
        """Test Violation with policy_type='custom' (new in Epic 3B).

        Given policy_type='custom',
        When creating a Violation,
        Then the violation is created successfully.
        """
        from floe_core.enforcement.result import Violation

        violation = Violation(
            error_code="FLOE-E400",
            severity="error",
            policy_type="custom",
            model_name="gold_customers",
            message="Missing required tag 'tested'",
            expected="Tag 'tested' present",
            actual="Tags: []",
            suggestion="Add 'tested' tag to model config",
            documentation_url="https://floe.dev/docs/custom-rules",
        )

        assert violation.policy_type == "custom"


class TestEnforcementSummaryEpic3BFields:
    """Tests for Epic 3B fields added to EnforcementSummary model.

    New fields: semantic_violations, custom_rule_violations, overrides_applied
    Task: T013 (related to T009)
    """

    @pytest.mark.requirement("003b-FR-018")
    def test_summary_with_semantic_violations(self) -> None:
        """Test EnforcementSummary with semantic_violations count.

        Given a summary with semantic validation failures,
        When creating the summary,
        Then semantic_violations contains the count.
        """
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=50,
            models_validated=48,
            naming_violations=3,
            coverage_violations=5,
            documentation_violations=2,
            semantic_violations=4,
        )

        assert summary.semantic_violations == 4

    @pytest.mark.requirement("003b-FR-018")
    def test_summary_with_custom_rule_violations(self) -> None:
        """Test EnforcementSummary with custom_rule_violations count.

        Given a summary with custom rule failures,
        When creating the summary,
        Then custom_rule_violations contains the count.
        """
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=50,
            models_validated=48,
            custom_rule_violations=7,
        )

        assert summary.custom_rule_violations == 7

    @pytest.mark.requirement("003b-FR-019")
    def test_summary_with_overrides_applied(self) -> None:
        """Test EnforcementSummary with overrides_applied count.

        Given a summary where policy overrides were applied,
        When creating the summary,
        Then overrides_applied contains the count.
        """
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=50,
            models_validated=48,
            overrides_applied=10,
        )

        assert summary.overrides_applied == 10

    @pytest.mark.requirement("003b-FR-018")
    def test_summary_new_fields_default_to_zero(self) -> None:
        """Test EnforcementSummary new fields default to zero.

        Given a summary without new fields,
        When creating the summary,
        Then new fields default to 0.
        """
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=50,
            models_validated=48,
        )

        assert summary.semantic_violations == 0
        assert summary.custom_rule_violations == 0
        assert summary.overrides_applied == 0

    @pytest.mark.requirement("003b-FR-018")
    def test_summary_with_all_epic3b_fields(self) -> None:
        """Test EnforcementSummary with all Epic 3B fields.

        Given a summary with all violation types and overrides,
        When creating the summary,
        Then all fields are stored correctly.
        """
        from floe_core.enforcement.result import EnforcementSummary

        summary = EnforcementSummary(
            total_models=100,
            models_validated=95,
            naming_violations=5,
            coverage_violations=10,
            documentation_violations=3,
            semantic_violations=2,
            custom_rule_violations=4,
            overrides_applied=8,
            duration_ms=456.78,
        )

        assert summary.naming_violations == 5
        assert summary.coverage_violations == 10
        assert summary.documentation_violations == 3
        assert summary.semantic_violations == 2
        assert summary.custom_rule_violations == 4
        assert summary.overrides_applied == 8


class TestEnforcementResultViolationsByModel:
    """Tests for violations_by_model computed property (T010)."""

    @pytest.mark.requirement("003b-FR-018")
    def test_violations_by_model_property(self) -> None:
        """Test violations_by_model groups violations by model name.

        Given an EnforcementResult with violations from multiple models,
        When accessing violations_by_model,
        Then violations are grouped by model_name.
        """
        from floe_core.enforcement.result import (
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
                    model_name="model_a",
                    message="Error 1",
                    expected="x",
                    actual="y",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E210",
                    severity="error",
                    policy_type="coverage",
                    model_name="model_b",
                    message="Error 2",
                    expected="80",
                    actual="50",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
                Violation(
                    error_code="FLOE-E220",
                    severity="warning",
                    policy_type="documentation",
                    model_name="model_a",
                    message="Warning",
                    expected="desc",
                    actual="(none)",
                    suggestion="Fix",
                    documentation_url="https://floe.dev",
                ),
            ],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        by_model = result.violations_by_model
        assert len(by_model) == 2
        assert len(by_model["model_a"]) == 2
        assert len(by_model["model_b"]) == 1

    @pytest.mark.requirement("003b-FR-018")
    def test_violations_by_model_empty(self) -> None:
        """Test violations_by_model with no violations.

        Given an EnforcementResult with no violations,
        When accessing violations_by_model,
        Then an empty dict is returned.
        """
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
        )

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.0.0",
            timestamp=datetime.now(timezone.utc),
        )

        assert result.violations_by_model == {}
