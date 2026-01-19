"""Unit tests for enforcement error types.

Tests for PolicyEnforcementError and related exceptions.
Following TDD: these tests are written FIRST and will FAIL until
the errors are implemented in T028.

Task: T022
Requirements: FR-002 (Pipeline Integration), US1 (Compile-time Enforcement)
"""

from __future__ import annotations

import pytest


class TestPolicyEnforcementError:
    """Tests for PolicyEnforcementError exception (T022).

    PolicyEnforcementError is raised when policy enforcement fails and
    the enforcement level is 'strict'.
    """

    @pytest.mark.requirement("3A-US1-FR002")
    def test_policy_enforcement_error_with_violations(self) -> None:
        """Test PolicyEnforcementError can be created with violations."""
        from floe_core.enforcement.errors import PolicyEnforcementError
        from floe_core.enforcement.result import Violation

        violations = [
            Violation(
                error_code="FLOE-E201",
                severity="error",
                policy_type="naming",
                model_name="stg_payments",
                message="Model name violates medallion convention",
                expected="^(bronze|silver|gold)_.*$",
                actual="stg_payments",
                suggestion="Rename to bronze_payments",
                documentation_url="https://floe.dev/docs/naming#medallion",
            ),
        ]
        error = PolicyEnforcementError(violations)
        assert len(error.violations) == 1
        assert error.violations[0].error_code == "FLOE-E201"

    @pytest.mark.requirement("3A-US1-FR002")
    def test_policy_enforcement_error_message_format(self) -> None:
        """Test PolicyEnforcementError generates readable message."""
        from floe_core.enforcement.errors import PolicyEnforcementError
        from floe_core.enforcement.result import Violation

        violations = [
            Violation(
                error_code="FLOE-E201",
                severity="error",
                policy_type="naming",
                model_name="stg_payments",
                message="Model name violates medallion convention",
                expected="medallion pattern",
                actual="stg_payments",
                suggestion="Rename to bronze_payments",
                documentation_url="https://floe.dev/docs/naming",
            ),
            Violation(
                error_code="FLOE-E210",
                severity="error",
                policy_type="coverage",
                model_name="customers",
                message="Test coverage below threshold",
                expected="80%",
                actual="50%",
                suggestion="Add tests for columns",
                documentation_url="https://floe.dev/docs/coverage",
            ),
        ]
        error = PolicyEnforcementError(violations)
        message = str(error)

        # Message should include violation count
        assert "2" in message or "two" in message.lower()
        # Message should reference key information
        assert "FLOE-E201" in message or "naming" in message.lower()
        assert "FLOE-E210" in message or "coverage" in message.lower()

    @pytest.mark.requirement("3A-US1-FR002")
    def test_policy_enforcement_error_is_exception(self) -> None:
        """Test PolicyEnforcementError is an Exception subclass."""
        from floe_core.enforcement.errors import PolicyEnforcementError
        from floe_core.enforcement.result import Violation

        violations = [
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
        ]
        error = PolicyEnforcementError(violations)
        assert isinstance(error, Exception)

    @pytest.mark.requirement("3A-US1-FR002")
    def test_policy_enforcement_error_can_be_raised(self) -> None:
        """Test PolicyEnforcementError can be raised and caught."""
        from floe_core.enforcement.errors import PolicyEnforcementError
        from floe_core.enforcement.result import Violation

        violations = [
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
        ]
        with pytest.raises(PolicyEnforcementError) as exc_info:
            raise PolicyEnforcementError(violations)

        assert len(exc_info.value.violations) == 1

    @pytest.mark.requirement("3A-US1-FR002")
    def test_policy_enforcement_error_empty_violations(self) -> None:
        """Test PolicyEnforcementError with empty violations list."""
        from floe_core.enforcement.errors import PolicyEnforcementError

        error = PolicyEnforcementError([])
        assert len(error.violations) == 0
        # Should still be a valid exception
        assert isinstance(error, Exception)

    @pytest.mark.requirement("3A-US1-FR002")
    def test_policy_enforcement_error_with_custom_message(self) -> None:
        """Test PolicyEnforcementError with optional custom message."""
        from floe_core.enforcement.errors import PolicyEnforcementError
        from floe_core.enforcement.result import Violation

        violations = [
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
        ]
        custom_msg = "Custom error message for testing"
        error = PolicyEnforcementError(violations, message=custom_msg)
        assert custom_msg in str(error)
