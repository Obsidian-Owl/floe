"""Compilation error handling for the floe compilation pipeline.

This module provides structured error models for compilation failures.
Errors include:
- Stage identification (which pipeline stage failed)
- Error codes (for programmatic handling)
- User-friendly messages
- Actionable suggestions (FR-002, SC-002)

Exit Code Mapping:
    1: Validation error (LOAD, VALIDATE stages)
    2: Compilation error (RESOLVE, ENFORCE, COMPILE, GENERATE stages)

See Also:
    - specs/2b-compilation-pipeline/spec.md: Error handling specification
    - CompilationStage: Pipeline stage enumeration
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from floe_core.compilation.stages import CompilationStage


class CompilationError(BaseModel):
    """Structured error from the compilation pipeline.

    Provides actionable error information including the stage where
    the error occurred, an error code, message, and suggestion.

    Attributes:
        stage: Pipeline stage where the error occurred
        code: Error code for programmatic handling (e.g., "E001")
        message: Human-readable error message
        suggestion: Actionable suggestion for fixing the error
        context: Optional additional context (file path, line number, etc.)

    Example:
        >>> error = CompilationError(
        ...     stage=CompilationStage.VALIDATE,
        ...     code="E001",
        ...     message="Invalid product name 'My Product'",
        ...     suggestion="Use DNS-compatible name (lowercase, no spaces): 'my-product'"
        ... )
        >>> error.exit_code
        1
        >>> print(error.format())
        [VALIDATE] E001: Invalid product name 'My Product'
        Suggestion: Use DNS-compatible name (lowercase, no spaces): 'my-product'

    See Also:
        - CompilationStage: Pipeline stage enumeration
        - FR-002: Actionable error messages requirement
        - SC-002: Error message clarity success criterion
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: CompilationStage = Field(
        ...,
        description="Pipeline stage where the error occurred",
    )
    code: str = Field(
        ...,
        min_length=1,
        pattern=r"^E\d{3}$",
        description="Error code (E001-E999)",
        examples=["E001", "E002", "E101"],
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Human-readable error message",
    )
    suggestion: str | None = Field(
        default=None,
        description="Actionable suggestion for fixing the error",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Additional context (file path, line number, etc.)",
    )

    @property
    def exit_code(self) -> int:
        """Get the CLI exit code for this error.

        Returns:
            1 for validation errors, 2 for compilation errors.

        Example:
            >>> error = CompilationError(
            ...     stage=CompilationStage.VALIDATE,
            ...     code="E001",
            ...     message="Invalid name"
            ... )
            >>> error.exit_code
            1
        """
        return self.stage.exit_code

    def format(self, include_suggestion: bool = True) -> str:
        """Format the error for display.

        Args:
            include_suggestion: Whether to include the suggestion line.

        Returns:
            Formatted error string for CLI output.

        Example:
            >>> error = CompilationError(
            ...     stage=CompilationStage.VALIDATE,
            ...     code="E001",
            ...     message="Invalid name",
            ...     suggestion="Use lowercase"
            ... )
            >>> print(error.format())
            [VALIDATE] E001: Invalid name
            Suggestion: Use lowercase
        """
        lines = [f"[{self.stage.value}] {self.code}: {self.message}"]
        if include_suggestion and self.suggestion:
            lines.append(f"Suggestion: {self.suggestion}")
        return "\n".join(lines)


class CompilationException(Exception):
    """Exception raised during compilation with structured error details.

    Wraps a CompilationError to provide both exception behavior and
    structured error data.

    Attributes:
        error: The structured CompilationError with details.

    Example:
        >>> error = CompilationError(
        ...     stage=CompilationStage.LOAD,
        ...     code="E001",
        ...     message="File not found: floe.yaml"
        ... )
        >>> raise CompilationException(error)
        Traceback (most recent call last):
        ...
        CompilationException: [LOAD] E001: File not found: floe.yaml
    """

    def __init__(self, error: CompilationError) -> None:
        """Initialize with a CompilationError.

        Args:
            error: The structured error details.
        """
        self.error = error
        super().__init__(error.format(include_suggestion=False))

    @property
    def exit_code(self) -> int:
        """Get the CLI exit code for this exception.

        Returns:
            Exit code from the underlying error.
        """
        return self.error.exit_code


# Common error codes
# E0xx: LOAD stage errors
# E1xx: VALIDATE stage errors
# E2xx: RESOLVE stage errors
# E3xx: ENFORCE stage errors
# E4xx: COMPILE stage errors
# E5xx: GENERATE stage errors

ERROR_CODES = {
    # LOAD errors
    "E001": "File not found",
    "E002": "Invalid YAML syntax",
    "E003": "Missing required file",
    # VALIDATE errors
    "E101": "Invalid product name (not DNS-compatible)",
    "E102": "Invalid version format (not semver)",
    "E103": "Missing required field",
    "E104": "Environment-specific field in FloeSpec",
    "E105": "Invalid transform name",
    "E106": "Duplicate transform names",
    "E107": "Missing required compute credentials",
    # RESOLVE errors
    "E201": "Plugin not found in platform manifest",
    "E202": "Invalid plugin version",
    "E203": "Manifest inheritance cycle detected",
    "E204": "Compute target not in approved plugins",
    # ENFORCE errors
    "E301": "Governance policy violation",
    "E302": "PII encryption required but not configured",
    "E303": "Audit logging required but not configured",
    # COMPILE errors
    "E401": "dbt model not found",
    "E402": "Circular dependency in transforms",
    "E403": "Invalid dbt profile configuration",
    # GENERATE errors
    "E501": "Failed to write output file",
    "E502": "Output directory does not exist",
}


__all__ = [
    "CompilationError",
    "CompilationException",
    "ERROR_CODES",
]
