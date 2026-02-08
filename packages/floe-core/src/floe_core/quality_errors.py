"""Quality plugin exception hierarchy for floe-core.

This module defines all custom exceptions used in the quality plugin system.
All exceptions inherit from QualityError, the base exception class.

Exception Hierarchy:
    QualityError (base)
    ├── QualityProviderNotFoundError  # FLOE-DQ001: Invalid/missing provider
    ├── QualityCheckFailedError       # FLOE-DQ102: Runtime check failures
    ├── QualityCoverageError          # FLOE-DQ103: Coverage below minimum
    ├── QualityMissingTestsError      # FLOE-DQ104: Required tests missing
    ├── QualityColumnReferenceError   # FLOE-DQ105: Invalid column reference
    ├── QualityTimeoutError           # FLOE-DQ106: Check timeout exceeded
    └── QualityOverrideError          # FLOE-DQ107: Locked setting override

Error Codes:
    FLOE-DQ001: Missing or invalid quality provider
    FLOE-DQ102: Quality checks failed at runtime
    FLOE-DQ103: Quality gate coverage violations
    FLOE-DQ104: Missing required test types
    FLOE-DQ105: Reference to non-existent column
    FLOE-DQ106: Quality check timeout
    FLOE-DQ107: Override of locked setting attempted
"""

from __future__ import annotations


class QualityError(Exception):
    """Base exception for all quality-related errors.

    All quality exceptions inherit from this class, allowing callers
    to catch all quality errors with a single except clause.

    Attributes:
        error_code: The FLOE-DQ* error code.
        resolution: Suggested resolution for the error.
    """

    error_code: str = "FLOE-DQ000"
    resolution: str = "Check quality configuration"


class QualityProviderNotFoundError(QualityError):
    """FLOE-DQ001: Missing or invalid quality provider.

    Raised when the configured quality provider is not found in the
    plugin registry or is invalid.

    Attributes:
        provider: The provider that was requested.
        available_providers: List of available/valid providers.
    """

    error_code: str = "FLOE-DQ001"

    def __init__(self, provider: str, available_providers: list[str]) -> None:
        self.provider = provider
        self.available_providers = available_providers
        self.resolution = (
            f"Check manifest.yaml plugins.quality.provider; "
            f"valid providers: {', '.join(available_providers)}"
        )
        available_str = ", ".join(available_providers)
        message = (
            f"[{self.error_code}] Invalid quality provider '{provider}'. "
            f"Available providers: [{available_str}]. "
            f"Resolution: {self.resolution}"
        )
        super().__init__(message)


class QualityCheckFailedError(QualityError):
    """FLOE-DQ102: Quality checks failed at runtime.

    Raised when one or more quality checks fail during runtime execution.

    Attributes:
        model_name: The model that failed quality checks.
        failed_checks: Number of failed checks.
        total_checks: Total number of checks executed.
        score: The achieved quality score.
        min_score: The minimum required score.
    """

    error_code: str = "FLOE-DQ102"

    def __init__(
        self,
        model_name: str,
        failed_checks: int,
        total_checks: int,
        score: float,
        min_score: float,
    ) -> None:
        self.model_name = model_name
        self.failed_checks = failed_checks
        self.total_checks = total_checks
        self.score = score
        self.min_score = min_score
        self.resolution = "Review failed checks in run output; fix data issues"
        message = (
            f"[{self.error_code}] Quality checks failed for '{model_name}': "
            f"{failed_checks}/{total_checks} checks failed. "
            f"Score {score:.1f} < minimum {min_score:.1f}. "
            f"Resolution: {self.resolution}"
        )
        super().__init__(message)


class QualityCoverageError(QualityError):
    """FLOE-DQ103: Quality gate coverage violations.

    Raised when test coverage is below the tier minimum.

    Attributes:
        model_name: The model with insufficient coverage.
        tier: The quality tier (bronze, silver, gold).
        actual_coverage: The actual coverage percentage.
        required_coverage: The required coverage percentage.
    """

    error_code: str = "FLOE-DQ103"

    def __init__(
        self,
        model_name: str,
        tier: str,
        actual_coverage: float,
        required_coverage: float,
    ) -> None:
        self.model_name = model_name
        self.tier = tier
        self.actual_coverage = actual_coverage
        self.required_coverage = required_coverage
        self.resolution = (
            f"Add more tests to meet {tier} tier minimum of {required_coverage}%"
        )
        message = (
            f"[{self.error_code}] Coverage violation for '{model_name}' ({tier} tier): "
            f"{actual_coverage:.1f}% < {required_coverage:.1f}% required. "
            f"Resolution: {self.resolution}"
        )
        super().__init__(message)


class QualityMissingTestsError(QualityError):
    """FLOE-DQ104: Missing required test types.

    Raised when required test types for a tier are missing.

    Attributes:
        model_name: The model missing tests.
        tier: The quality tier (bronze, silver, gold).
        missing_tests: List of missing test types.
    """

    error_code: str = "FLOE-DQ104"

    def __init__(
        self,
        model_name: str,
        tier: str,
        missing_tests: list[str],
    ) -> None:
        self.model_name = model_name
        self.tier = tier
        self.missing_tests = missing_tests
        missing_str = ", ".join(missing_tests)
        self.resolution = f"Add required tests: {missing_str}"
        message = (
            f"[{self.error_code}] Missing required tests for '{model_name}' ({tier} tier): "
            f"[{missing_str}]. "
            f"Resolution: {self.resolution}"
        )
        super().__init__(message)


class QualityColumnReferenceError(QualityError):
    """FLOE-DQ105: Reference to non-existent column.

    Raised when a quality check references a column that doesn't exist.

    Attributes:
        model_name: The model being checked.
        check_name: The check with the invalid reference.
        column_name: The referenced column that doesn't exist.
        available_columns: List of available columns (if known).
    """

    error_code: str = "FLOE-DQ105"

    def __init__(
        self,
        model_name: str,
        check_name: str,
        column_name: str,
        available_columns: list[str] | None = None,
    ) -> None:
        self.model_name = model_name
        self.check_name = check_name
        self.column_name = column_name
        self.available_columns = available_columns
        self.resolution = f"Verify column '{column_name}' exists in model schema"
        message = (
            f"[{self.error_code}] Invalid column reference in check '{check_name}' "
            f"for model '{model_name}': column '{column_name}' not found."
        )
        if available_columns:
            message += f" Available columns: [{', '.join(available_columns)}]."
        message += f" Resolution: {self.resolution}"
        super().__init__(message)


class QualityTimeoutError(QualityError):
    """FLOE-DQ106: Quality check timeout exceeded.

    Raised when quality checks exceed the configured timeout.

    Attributes:
        model_name: The model being checked.
        timeout_seconds: The configured timeout.
        pending_checks: List of checks that were still pending.
    """

    error_code: str = "FLOE-DQ106"

    def __init__(
        self,
        model_name: str,
        timeout_seconds: int,
        pending_checks: list[str] | None = None,
    ) -> None:
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.pending_checks = pending_checks or []
        self.resolution = "Increase check_timeout_seconds or optimize checks"
        message = (
            f"[{self.error_code}] Quality check timeout for '{model_name}' "
            f"after {timeout_seconds}s."
        )
        if pending_checks:
            message += f" Pending checks: [{', '.join(pending_checks)}]."
        message += f" Resolution: {self.resolution}"
        super().__init__(message)


class QualityOverrideError(QualityError):
    """FLOE-DQ107: Override of locked setting attempted.

    Raised when a lower level (Domain/Product) attempts to override
    a setting that was locked (overridable: false) at a higher level.

    Attributes:
        setting_name: The setting that was attempted to be overridden.
        locked_by: The level that locked the setting (enterprise, domain).
        attempted_by: The level that attempted the override.
    """

    error_code: str = "FLOE-DQ107"

    def __init__(
        self,
        setting_name: str,
        locked_by: str,
        attempted_by: str,
    ) -> None:
        self.setting_name = setting_name
        self.locked_by = locked_by
        self.attempted_by = attempted_by
        self.resolution = (
            f"Remove '{setting_name}' override from {attempted_by}-level configuration"
        )
        message = (
            f"[{self.error_code}] Cannot override locked setting '{setting_name}': "
            f"locked by {locked_by} level, attempted by {attempted_by} level. "
            f"Resolution: {self.resolution}"
        )
        super().__init__(message)


__all__ = [
    "QualityError",
    "QualityProviderNotFoundError",
    "QualityCheckFailedError",
    "QualityCoverageError",
    "QualityMissingTestsError",
    "QualityColumnReferenceError",
    "QualityTimeoutError",
    "QualityOverrideError",
]
