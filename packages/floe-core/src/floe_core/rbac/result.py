"""Result types for RBAC manifest generation.

This module defines dataclasses for representing the results of RBAC
manifest generation operations.

Example:
    >>> from floe_core.rbac.result import GenerationResult
    >>> result = GenerationResult(
    ...     success=True,
    ...     service_accounts=2,
    ...     roles=2,
    ...     role_bindings=2,
    ...     namespaces=2
    ... )
    >>> result.success
    True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GenerationResult:
    """Result of RBAC manifest generation.

    Contains information about the generated manifests, including counts of
    each resource type and any warnings or errors encountered.

    Attributes:
        success: Whether generation completed successfully.
        files_generated: List of file paths that were generated.
        service_accounts: Number of ServiceAccount manifests generated.
        roles: Number of Role manifests generated.
        role_bindings: Number of RoleBinding manifests generated.
        namespaces: Number of Namespace manifests generated.
        warnings: Non-fatal warnings encountered during generation.
        errors: Errors that prevented successful generation.

    Example:
        >>> result = GenerationResult(success=True, service_accounts=3)
        >>> result.files_generated
        []
        >>> result.service_accounts
        3
    """

    success: bool
    files_generated: list[Path] = field(default_factory=lambda: list[Path]())
    service_accounts: int = 0
    roles: int = 0
    role_bindings: int = 0
    namespaces: int = 0
    warnings: list[str] = field(default_factory=lambda: list[str]())
    errors: list[str] = field(default_factory=lambda: list[str]())

    def __str__(self) -> str:
        """Return human-readable summary of generation result."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"RBAC Generation: {status}",
            f"  ServiceAccounts: {self.service_accounts}",
            f"  Roles: {self.roles}",
            f"  RoleBindings: {self.role_bindings}",
            f"  Namespaces: {self.namespaces}",
            f"  Files: {len(self.files_generated)}",
        ]
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
        return "\n".join(lines)
