"""Enforcement error types for PolicyEnforcer.

This module defines exceptions raised during policy enforcement:
- PolicyEnforcementError: Raised when strict mode enforcement fails

Task: T028
Requirements: FR-002 (Pipeline Integration), US1 (Compile-time Enforcement)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from floe_core.enforcement.result import Violation


class PolicyEnforcementError(Exception):
    """Raised when policy enforcement fails in strict mode.

    PolicyEnforcementError is raised by the compilation pipeline when
    PolicyEnforcer.enforce() returns violations and the enforcement
    level is 'strict'. It contains all violations for error reporting.

    Attributes:
        violations: List of policy violations that caused the failure.
        message: Optional custom message (auto-generated if not provided).

    Example:
        >>> try:
        ...     raise PolicyEnforcementError(violations)
        ... except PolicyEnforcementError as e:
        ...     print(f"Policy failed: {len(e.violations)} violations")
        ...     for v in e.violations:
        ...         print(f"  - {v.error_code}: {v.message}")
    """

    def __init__(
        self,
        violations: list[Violation],
        message: str | None = None,
    ) -> None:
        """Initialize PolicyEnforcementError.

        Args:
            violations: List of policy violations.
            message: Optional custom message. If not provided, a default
                message is generated from the violations.
        """
        self.violations = violations

        if message is not None:
            self._custom_message = message
        else:
            self._custom_message = None

        # Generate the exception message
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message from violations.

        Returns:
            Formatted error message string.
        """
        if self._custom_message:
            return self._custom_message

        if not self.violations:
            return "Policy enforcement failed with 0 violations"

        # Count violations by type
        error_count = sum(1 for v in self.violations if v.severity == "error")
        warning_count = len(self.violations) - error_count

        # Build summary
        parts = []
        if error_count > 0:
            parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
        if warning_count > 0:
            parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")

        summary = " and ".join(parts) if parts else "0 violations"
        message = f"Policy enforcement failed with {summary}:"

        # Add first few violations for context
        max_show = 5
        for v in self.violations[:max_show]:
            message += f"\n  [{v.error_code}] {v.policy_type}: {v.message}"
            if v.suggestion:
                message += f" (suggestion: {v.suggestion})"

        if len(self.violations) > max_show:
            remaining = len(self.violations) - max_show
            message += f"\n  ... and {remaining} more violation{'s' if remaining != 1 else ''}"

        return message

    def __str__(self) -> str:
        """Return string representation of the error.

        Returns:
            Formatted error message.
        """
        return self._format_message()

    def __repr__(self) -> str:
        """Return repr of the error.

        Returns:
            Repr string with class name and violation count.
        """
        return f"PolicyEnforcementError(violations={len(self.violations)})"
