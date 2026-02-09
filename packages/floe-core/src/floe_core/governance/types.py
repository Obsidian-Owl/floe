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
        severity: Severity level of the finding (error or warning)
        match_context: Redacted context around the match for verification
        confidence: Confidence level of the detection (high, medium, or low)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(..., description="Relative path to file")
    line_number: int = Field(..., ge=1, description="Line number")
    pattern_name: str = Field(..., description="Pattern that matched")
    severity: Literal["error", "warning"] = Field(default="error")
    match_context: str = Field(default="", description="Redacted context")
    confidence: Literal["high", "medium", "low"] = Field(default="high")


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

    check_type: str = Field(
        ..., description="Type: rbac, secrets, policies, network"
    )
    violations: list[Violation] = Field(default_factory=list)
    duration_ms: float = Field(..., ge=0, description="Check execution time")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Check-specific metadata"
    )
