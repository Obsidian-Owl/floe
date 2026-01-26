"""Result types for NetworkPolicy generation operations.

This module provides Pydantic models for tracking NetworkPolicy generation
outcomes including generated policies, warnings, and summary statistics.

Task: T017
Epic: 7C - Network and Pod Security
Requirements: FR-070

Example:
    >>> from floe_core.network.result import NetworkPolicyGenerationResult
    >>> result = NetworkPolicyGenerationResult(
    ...     generated_policies=[{"kind": "NetworkPolicy", ...}],
    ...     warnings=["Deprecated egress rule format"],
    ...     policies_count=5,
    ...     namespaces_count=2,
    ... )
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NetworkPolicyGenerationResult(BaseModel):
    """Result of NetworkPolicy generation operation.

    Captures the output of generating Kubernetes NetworkPolicy manifests
    from floe security configuration, including any warnings encountered
    during generation.

    Attributes:
        generated_policies: List of generated K8s NetworkPolicy manifest dicts.
        warnings: List of non-fatal issues encountered during generation.
        policies_count: Total number of NetworkPolicy manifests generated.
        namespaces_count: Number of unique namespaces with policies.
        default_deny_count: Number of default-deny policies generated.
        egress_rules_count: Total egress rules across all policies.
        ingress_rules_count: Total ingress rules across all policies.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_policies: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of generated K8s NetworkPolicy manifests",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues encountered during generation",
    )

    policies_count: int = Field(
        default=0,
        ge=0,
        description="Total number of NetworkPolicy manifests generated",
    )

    namespaces_count: int = Field(
        default=0,
        ge=0,
        description="Number of unique namespaces with policies",
    )

    default_deny_count: int = Field(
        default=0,
        ge=0,
        description="Number of default-deny policies generated",
    )

    egress_rules_count: int = Field(
        default=0,
        ge=0,
        description="Total egress rules across all policies",
    )

    ingress_rules_count: int = Field(
        default=0,
        ge=0,
        description="Total ingress rules across all policies",
    )

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were generated."""
        return len(self.warnings) > 0

    @property
    def is_empty(self) -> bool:
        """Check if no policies were generated."""
        return self.policies_count == 0

    def summary(self) -> dict[str, Any]:
        """Generate a summary dictionary for logging/reporting.

        Returns:
            Dictionary with generation statistics.
        """
        return {
            "policies_count": self.policies_count,
            "namespaces_count": self.namespaces_count,
            "default_deny_count": self.default_deny_count,
            "egress_rules_count": self.egress_rules_count,
            "ingress_rules_count": self.ingress_rules_count,
            "warnings_count": len(self.warnings),
        }
