"""Governance check types and models.

This module defines data structures for governance validation results,
including secret detection findings and general governance check results.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from floe_core.enforcement.result import Violation


class SecretFinding(BaseModel):
    """A single secret detection finding.

    Represents a potential secret detected in source code or configuration files.
    Includes file location, pattern matched, severity, and confidence level.

    Attributes:
        file_path: Relative path to file containing potential secret
        line_number: Line number where secret was detected (1-indexed)
        pattern_name: Name of the detection pattern that matched
        error_code: Error code for the violation (E601-E699)
        matched_content: Redacted or truncated matched content
        severity: Severity level of the finding (error or warning)
        match_context: Redacted context around the match for verification
        confidence: Confidence level of the detection (high, medium, or low)
        allow_secrets: Whether secrets are allowed (downgrades to warning)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(..., description="Relative path to file")
    line_number: int = Field(..., ge=1, description="Line number")
    pattern_name: str = Field(..., description="Pattern that matched")
    error_code: str = Field(..., description="Error code (E601-E699)")
    matched_content: str = Field(..., description="Matched content (redacted)")
    severity: Literal["error", "warning"] = Field(default="error")
    match_context: str = Field(default="", description="Redacted context")
    confidence: Literal["high", "medium", "low"] = Field(default="high")
    allow_secrets: bool = Field(default=False, description="Allow secrets flag")


class SecretPattern(BaseModel):
    """A custom secret detection pattern for the scanner.

    Defines a regex pattern for detecting custom secrets beyond the
    built-in patterns. Used by BuiltinSecretScanner's custom_patterns
    parameter.

    Attributes:
        name: Pattern name (e.g., 'floe_token')
        regex: Regular expression pattern to match
        description: Human-readable description
        error_code: Error code for violations (E6XX format)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Pattern name")
    regex: str = Field(..., description="Regex pattern")
    description: str = Field(..., description="Pattern description")
    error_code: str = Field(..., pattern=r"^E6\d{2}$", description="Error code")


class GovernanceCheckResult(BaseModel):
    """Result from a single governance check.

    Encapsulates the outcome of running a governance validation check,
    including any violations found, execution duration, and check-specific metadata.

    Attributes:
        check_type: Type of check performed (rbac, secrets, policies, network)
        violations: List of violations found during the check
        duration_ms: Time taken to execute the check in milliseconds
        metadata: Check-specific metadata and additional context
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_type: str = Field(..., description="Type: rbac, secrets, policies, network")
    violations: list[Violation] = Field(default_factory=list)
    duration_ms: float = Field(..., ge=0, description="Check execution time")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Check-specific metadata")
