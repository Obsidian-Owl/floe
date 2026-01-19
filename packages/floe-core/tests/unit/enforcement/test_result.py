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
        from floe_core.enforcement.result import Violation

        for severity in ["error", "warning"]:
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
                severity="info",  # Invalid
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
        from floe_core.enforcement.result import Violation

        for policy_type in ["naming", "coverage", "documentation"]:
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
                policy_type="security",  # Invalid
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
        with pytest.raises((AttributeError, ValidationError)):
            violation.error_code = "FLOE-E202"  # type: ignore[misc]


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
        with pytest.raises((AttributeError, ValidationError)):
            summary.total_models = 20  # type: ignore[misc]


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
            summary=EnforcementSummary(
                total_models=10, models_validated=10, naming_violations=1
            ),
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
        from floe_core.enforcement.result import EnforcementResult, EnforcementSummary

        for level in ["off", "warn", "strict"]:
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
                enforcement_level="moderate",  # Invalid
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
        with pytest.raises((AttributeError, ValidationError)):
            result.passed = False  # type: ignore[misc]

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
            summary=EnforcementSummary(
                total_models=10, models_validated=10, naming_violations=1
            ),
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
