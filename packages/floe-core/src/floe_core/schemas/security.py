"""Security configuration schemas for K8s RBAC Plugin System.

This module defines the Pydantic models for the security section of manifest.yaml,
including RBAC configuration and Pod Security Standards settings.

Example:
    >>> from floe_core.schemas.security import SecurityConfig
    >>> config = SecurityConfig(
    ...     rbac=RBACConfig(enabled=True, job_service_account="auto"),
    ...     pod_security=PodSecurityLevelConfig(jobs_level="restricted"),
    ...     namespace_isolation="strict"
    ... )

Contract: See specs/7b-k8s-rbac/contracts/security-config-schema.md
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RBACConfig(BaseModel):
    """RBAC configuration from manifest.yaml security section.

    Attributes:
        enabled: Whether RBAC manifest generation is enabled.
        job_service_account: Service account creation mode - 'auto' generates
            ServiceAccounts automatically, 'manual' expects pre-existing ones.
        cluster_scope: Whether to generate ClusterRole/ClusterRoleBinding
            resources. Defaults to False for least-privilege.

    Example:
        >>> config = RBACConfig(enabled=True, job_service_account="auto")
        >>> config.enabled
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable RBAC manifest generation",
    )
    job_service_account: Literal["auto", "manual"] = Field(
        default="auto",
        description="Service account creation mode",
    )
    cluster_scope: bool = Field(
        default=False,
        description="Enable ClusterRole/ClusterRoleBinding generation",
    )


class PodSecurityLevelConfig(BaseModel):
    """Pod Security Standard configuration for namespaces.

    Defines the PSS enforcement levels for different namespace types.
    See: https://kubernetes.io/docs/concepts/security/pod-security-standards/

    Attributes:
        jobs_level: PSS level for floe-jobs namespace (default: restricted).
        platform_level: PSS level for floe-platform namespace (default: baseline).

    Example:
        >>> config = PodSecurityLevelConfig(jobs_level="restricted")
        >>> config.platform_level
        'baseline'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    jobs_level: Literal["privileged", "baseline", "restricted"] = Field(
        default="restricted",
        description="PSS level for floe-jobs namespace",
    )
    platform_level: Literal["privileged", "baseline", "restricted"] = Field(
        default="baseline",
        description="PSS level for floe-platform namespace",
    )


class SecurityConfig(BaseModel):
    """Security section of manifest.yaml.

    This is the top-level configuration for security settings including
    RBAC, Pod Security Standards, and namespace isolation.

    Attributes:
        rbac: RBAC configuration settings.
        pod_security: Pod Security Standard configuration.
        namespace_isolation: Namespace isolation mode - 'strict' enforces
            full isolation, 'permissive' allows some cross-namespace access.

    Example:
        >>> config = SecurityConfig()
        >>> config.rbac.enabled
        True
        >>> config.namespace_isolation
        'strict'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rbac: RBACConfig = Field(
        default_factory=RBACConfig,
        description="RBAC configuration",
    )
    pod_security: PodSecurityLevelConfig = Field(
        default_factory=PodSecurityLevelConfig,
        description="Pod Security Standard configuration",
    )
    namespace_isolation: Literal["strict", "permissive"] = Field(
        default="strict",
        description="Namespace isolation mode",
    )
