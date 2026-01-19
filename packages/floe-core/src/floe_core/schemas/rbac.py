"""RBAC resource configuration schemas for K8s RBAC Plugin System.

This module defines the Pydantic models for Kubernetes RBAC resources including
ServiceAccount, Role, RoleBinding, Namespace, and PodSecurity configurations.

Each model includes a to_k8s_manifest() method that generates valid Kubernetes
YAML manifest dictionaries.

Example:
    >>> from floe_core.schemas.rbac import ServiceAccountConfig
    >>> config = ServiceAccountConfig(
    ...     name="floe-job-runner",
    ...     namespace="floe-jobs"
    ... )
    >>> manifest = config.to_k8s_manifest()
    >>> manifest["kind"]
    'ServiceAccount'

Contract: See specs/7b-k8s-rbac/data-model.md
"""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# =============================================================================
# T006: ServiceAccountConfig
# =============================================================================


class ServiceAccountConfig(BaseModel):
    """Configuration for generating a K8s ServiceAccount.

    Attributes:
        name: ServiceAccount name (must follow pattern floe-{purpose}).
        namespace: Namespace where the ServiceAccount will be created.
        automount_token: Whether to automount the service account token.
            Defaults to False for least-privilege (FR-011, FR-014).
        labels: Kubernetes labels to apply to the ServiceAccount.
        annotations: Kubernetes annotations to apply to the ServiceAccount.

    Example:
        >>> config = ServiceAccountConfig(
        ...     name="floe-job-runner",
        ...     namespace="floe-jobs"
        ... )
        >>> config.automount_token
        False
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        pattern=r"^floe-[a-z0-9-]+$",
        description="ServiceAccount name following floe-{purpose} pattern",
    )
    namespace: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Namespace for the ServiceAccount",
    )
    automount_token: bool = Field(
        default=False,
        description="Whether to automount service account token",
    )
    labels: dict[str, str] = Field(
        default_factory=lambda: {"app.kubernetes.io/managed-by": "floe"},
        description="Kubernetes labels",
    )
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Kubernetes annotations",
    )

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s ServiceAccount manifest dict.

        Returns:
            Dictionary representing a valid K8s ServiceAccount manifest.
        """
        return {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "automountServiceAccountToken": self.automount_token,
        }


# =============================================================================
# T007: RoleRule and RoleConfig
# =============================================================================


class RoleRule(BaseModel):
    """A single RBAC rule within a Role.

    Attributes:
        api_groups: API groups the rule applies to (e.g., [""] for core, ["batch"]).
        resources: Resource types (e.g., ["pods", "secrets"]).
        verbs: Allowed operations (e.g., ["get", "list"]).
        resource_names: Specific resource names to restrict to (least-privilege).

    Example:
        >>> rule = RoleRule(
        ...     api_groups=[""],
        ...     resources=["secrets"],
        ...     verbs=["get"],
        ...     resource_names=["my-secret"]
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    api_groups: list[str] = Field(
        default_factory=lambda: [""],
        description="API groups the rule applies to",
    )
    resources: list[str] = Field(
        ...,
        min_length=1,
        description="Resource types",
    )
    verbs: list[str] = Field(
        ...,
        min_length=1,
        description="Allowed operations",
    )
    resource_names: list[str] | None = Field(
        default=None,
        description="Specific resource names to restrict to",
    )

    @field_validator("api_groups", "resources", "verbs")
    @classmethod
    def no_wildcards(cls, v: list[str]) -> list[str]:
        """Validate that no wildcard permissions are used (FR-070).

        Args:
            v: List of strings to validate.

        Returns:
            The validated list.

        Raises:
            ValueError: If wildcard (*) is found.
        """
        if "*" in v:
            msg = "Wildcard permissions (*) are forbidden per FR-070"
            raise ValueError(msg)
        return v


class RoleConfig(BaseModel):
    """Configuration for generating a K8s Role.

    Attributes:
        name: Role name (must follow pattern floe-{purpose}-role).
        namespace: Namespace where the Role will be created.
        rules: List of RBAC rules defining permissions.
        labels: Kubernetes labels to apply to the Role.

    Example:
        >>> config = RoleConfig(
        ...     name="floe-job-runner-role",
        ...     namespace="floe-jobs",
        ...     rules=[RoleRule(resources=["secrets"], verbs=["get"])]
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        pattern=r"^floe-[a-z0-9-]+-role$",
        description="Role name following floe-{purpose}-role pattern",
    )
    namespace: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Namespace for the Role",
    )
    rules: list[RoleRule] = Field(
        ...,
        min_length=1,
        description="RBAC rules",
    )
    labels: dict[str, str] = Field(
        default_factory=lambda: {"app.kubernetes.io/managed-by": "floe"},
        description="Kubernetes labels",
    )

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s Role manifest dict.

        Returns:
            Dictionary representing a valid K8s Role manifest.
        """
        rules_list: list[dict[str, Any]] = []
        for rule in self.rules:
            rule_dict: dict[str, Any] = {
                "apiGroups": rule.api_groups,
                "resources": rule.resources,
                "verbs": rule.verbs,
            }
            if rule.resource_names:
                rule_dict["resourceNames"] = rule.resource_names
            rules_list.append(rule_dict)

        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "rules": rules_list,
        }


# =============================================================================
# T008: RoleBindingSubject and RoleBindingConfig
# =============================================================================


class RoleBindingSubject(BaseModel):
    """Subject (ServiceAccount) in a RoleBinding.

    Attributes:
        kind: Subject type (always "ServiceAccount").
        name: ServiceAccount name.
        namespace: Namespace of the ServiceAccount (for cross-namespace bindings).

    Example:
        >>> subject = RoleBindingSubject(
        ...     name="floe-job-runner",
        ...     namespace="floe-jobs"
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["ServiceAccount"] = Field(
        default="ServiceAccount",
        description="Subject type",
    )
    name: str = Field(
        ...,
        description="ServiceAccount name",
    )
    namespace: str = Field(
        ...,
        description="Namespace of the ServiceAccount",
    )


class RoleBindingConfig(BaseModel):
    """Configuration for generating a K8s RoleBinding.

    Attributes:
        name: RoleBinding name (must follow pattern floe-{purpose}-binding).
        namespace: Namespace where the RoleBinding will be created.
        subjects: List of ServiceAccount subjects to bind.
        role_name: Name of the Role to bind to.
        labels: Kubernetes labels to apply to the RoleBinding.
        allowed_subject_namespaces: Optional list of allowed namespaces for cross-namespace
            subjects. If set, subjects from other namespaces will be rejected. If None,
            subjects from any namespace are allowed (for backwards compatibility).

    Example:
        >>> config = RoleBindingConfig(
        ...     name="floe-job-runner-binding",
        ...     namespace="floe-jobs",
        ...     subjects=[RoleBindingSubject(name="floe-job-runner", namespace="floe-jobs")],
        ...     role_name="floe-job-runner-role"
        ... )

    Example with cross-namespace validation:
        >>> config = RoleBindingConfig(
        ...     name="floe-dagster-binding",
        ...     namespace="floe-jobs",
        ...     subjects=[RoleBindingSubject(name="floe-dagster", namespace="floe-platform")],
        ...     role_name="floe-job-creator-role",
        ...     allowed_subject_namespaces=["floe-platform", "floe-jobs"]
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        pattern=r"^floe-[a-z0-9-]+-binding$",
        description="RoleBinding name following floe-{purpose}-binding pattern",
    )
    namespace: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Namespace for the RoleBinding",
    )
    subjects: list[RoleBindingSubject] = Field(
        ...,
        min_length=1,
        description="ServiceAccount subjects to bind",
    )
    role_name: str = Field(
        ...,
        description="Name of the Role to bind to",
    )
    labels: dict[str, str] = Field(
        default_factory=lambda: {"app.kubernetes.io/managed-by": "floe"},
        description="Kubernetes labels",
    )
    allowed_subject_namespaces: list[str] | None = Field(
        default=None,
        description="Allowed namespaces for cross-namespace subjects. If None, all namespaces allowed.",
    )

    @model_validator(mode="after")
    def validate_subject_namespaces(self) -> Self:
        """Validate that cross-namespace subjects are from allowed namespaces.

        When allowed_subject_namespaces is set, subjects must be from one of
        those namespaces. This ensures cross-namespace access is only granted
        to explicitly allowed namespaces per FR-023 and US3.

        Returns:
            The validated model.

        Raises:
            ValueError: If a subject's namespace is not in the allowed list.
        """
        if self.allowed_subject_namespaces is None:
            return self

        allowed = set(self.allowed_subject_namespaces)
        for subject in self.subjects:
            if subject.namespace not in allowed:
                msg = (
                    f"Subject '{subject.name}' is from namespace '{subject.namespace}' "
                    f"which is not in allowed namespaces: {sorted(allowed)}"
                )
                raise ValueError(msg)
        return self

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s RoleBinding manifest dict.

        Returns:
            Dictionary representing a valid K8s RoleBinding manifest.
        """
        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "subjects": [
                {
                    "kind": s.kind,
                    "name": s.name,
                    "namespace": s.namespace,
                }
                for s in self.subjects
            ],
            "roleRef": {
                "kind": "Role",
                "name": self.role_name,
                "apiGroup": "rbac.authorization.k8s.io",
            },
        }


# =============================================================================
# T009: NamespaceConfig
# =============================================================================


class NamespaceConfig(BaseModel):
    """Configuration for generating a K8s Namespace with PSS labels.

    Attributes:
        name: Namespace name (must follow pattern floe-{purpose}).
        layer: Architecture layer ("3" for platform, "4" for jobs).
        pss_enforce: Pod Security Standard enforcement level.
        pss_audit: Pod Security Standard audit level.
        pss_warn: Pod Security Standard warning level.
        labels: Additional Kubernetes labels.

    Example:
        >>> config = NamespaceConfig(
        ...     name="floe-jobs",
        ...     layer="4",
        ...     pss_enforce="restricted"
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        pattern=r"^floe-[a-z0-9-]+$",
        description="Namespace name following floe-{purpose} pattern",
    )
    layer: Literal["3", "4"] = Field(
        ...,
        description="Architecture layer (3=platform, 4=jobs)",
    )
    pss_enforce: Literal["privileged", "baseline", "restricted"] = Field(
        default="restricted",
        description="Pod Security Standard enforcement level",
    )
    pss_audit: Literal["privileged", "baseline", "restricted"] = Field(
        default="restricted",
        description="Pod Security Standard audit level",
    )
    pss_warn: Literal["privileged", "baseline", "restricted"] = Field(
        default="restricted",
        description="Pod Security Standard warning level",
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Additional Kubernetes labels",
    )

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s Namespace manifest dict.

        Returns:
            Dictionary representing a valid K8s Namespace manifest with PSS labels.
        """
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": self.name,
                "labels": {
                    "app.kubernetes.io/part-of": "floe",
                    "app.kubernetes.io/managed-by": "floe",
                    "floe.dev/layer": self.layer,
                    "pod-security.kubernetes.io/enforce": self.pss_enforce,
                    "pod-security.kubernetes.io/audit": self.pss_audit,
                    "pod-security.kubernetes.io/warn": self.pss_warn,
                    **self.labels,
                },
            },
        }


# =============================================================================
# T055: WritableVolumeMount
# =============================================================================


class WritableVolumeMount(BaseModel):
    """Configuration for a writable volume mount with readOnlyRootFilesystem.

    When using readOnlyRootFilesystem: true (required for PSS restricted level),
    applications may still need writable directories. This model defines emptyDir
    volumes to be mounted at specific paths to provide writable storage.

    Attributes:
        name: Volume name (must follow K8s naming conventions: lowercase, alphanumeric, hyphens).
        mount_path: Absolute path where the volume will be mounted.
        size_limit: Optional size limit for the emptyDir volume (e.g., "100Mi", "1Gi").
        medium: Storage medium - "" (default disk) or "Memory" (tmpfs).

    Example:
        >>> mount = WritableVolumeMount(
        ...     name="tmp",
        ...     mount_path="/tmp",
        ...     size_limit="100Mi"
        ... )
        >>> mount.medium
        ''
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Volume name following K8s naming conventions",
    )
    mount_path: str = Field(
        ...,
        pattern=r"^/.*$",
        description="Absolute path where the volume will be mounted",
    )
    size_limit: str | None = Field(
        default=None,
        description="Optional size limit for the emptyDir volume (e.g., '100Mi', '1Gi')",
    )
    medium: Literal["", "Memory"] = Field(
        default="",
        description="Storage medium - '' (default disk) or 'Memory' (tmpfs)",
    )


def _default_writable_mounts() -> list[WritableVolumeMount]:
    """Create default writable volume mounts for common application needs.

    Returns:
        List of default writable volume mounts including /tmp.
    """
    return [
        WritableVolumeMount(name="tmp", mount_path="/tmp"),
    ]


# =============================================================================
# T010: PodSecurityConfig
# =============================================================================


class PodSecurityConfig(BaseModel):
    """Configuration for pod/container security context generation.

    Generates security context settings that comply with Pod Security Standards
    at the 'restricted' level.

    Attributes:
        run_as_non_root: Whether the container must run as non-root user.
        run_as_user: UID to run the container as.
        run_as_group: GID to run the container as.
        fs_group: fsGroup for volume permissions.
        read_only_root_filesystem: Whether to use read-only root filesystem.
        allow_privilege_escalation: Whether privilege escalation is allowed.
        seccomp_profile_type: Seccomp profile type.
        writable_volume_mounts: Configurable volume mounts for writable directories
            when using readOnlyRootFilesystem (FR-043).

    Example:
        >>> config = PodSecurityConfig()
        >>> context = config.to_pod_security_context()
        >>> context["runAsNonRoot"]
        True
        >>> len(config.to_volume_mounts()) > 0  # Default includes /tmp
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_as_non_root: bool = Field(
        default=True,
        description="Whether the container must run as non-root user",
    )
    run_as_user: int = Field(
        default=1000,
        ge=1,
        description="UID to run the container as",
    )
    run_as_group: int = Field(
        default=1000,
        ge=1,
        description="GID to run the container as",
    )
    fs_group: int = Field(
        default=1000,
        ge=1,
        description="fsGroup for volume permissions",
    )
    read_only_root_filesystem: bool = Field(
        default=True,
        description="Whether to use read-only root filesystem",
    )
    allow_privilege_escalation: bool = Field(
        default=False,
        description="Whether privilege escalation is allowed",
    )
    seccomp_profile_type: Literal["RuntimeDefault", "Localhost", "Unconfined"] = Field(
        default="RuntimeDefault",
        description="Seccomp profile type",
    )
    writable_volume_mounts: list[WritableVolumeMount] = Field(
        default_factory=_default_writable_mounts,
        description="Configurable volume mounts for writable directories with readOnlyRootFilesystem (FR-043)",
    )

    def to_pod_security_context(self) -> dict[str, Any]:
        """Generate pod-level securityContext.

        Returns:
            Dictionary representing pod securityContext.
        """
        return {
            "runAsNonRoot": self.run_as_non_root,
            "runAsUser": self.run_as_user,
            "runAsGroup": self.run_as_group,
            "fsGroup": self.fs_group,
            "seccompProfile": {
                "type": self.seccomp_profile_type,
            },
        }

    def to_container_security_context(self) -> dict[str, Any]:
        """Generate container-level securityContext.

        Returns:
            Dictionary representing container securityContext.
        """
        return {
            "allowPrivilegeEscalation": self.allow_privilege_escalation,
            "readOnlyRootFilesystem": self.read_only_root_filesystem,
            "capabilities": {
                "drop": ["ALL"],
            },
        }

    def to_volume_mounts(self) -> list[dict[str, Any]]:
        """Generate volume mounts for container spec.

        Creates volumeMount entries for writable directories when using
        readOnlyRootFilesystem: true (FR-043).

        Returns:
            List of volumeMount dictionaries for container spec.

        Example:
            >>> config = PodSecurityConfig()
            >>> mounts = config.to_volume_mounts()
            >>> mounts[0]["mountPath"]
            '/tmp'
        """
        return [
            {
                "name": mount.name,
                "mountPath": mount.mount_path,
            }
            for mount in self.writable_volume_mounts
        ]

    def to_volumes(self) -> list[dict[str, Any]]:
        """Generate emptyDir volumes for pod spec.

        Creates volume entries with emptyDir for writable directories
        when using readOnlyRootFilesystem: true (FR-043).

        Returns:
            List of volume dictionaries for pod spec.

        Example:
            >>> config = PodSecurityConfig()
            >>> volumes = config.to_volumes()
            >>> "emptyDir" in volumes[0]
            True
        """
        volumes: list[dict[str, Any]] = []
        for mount in self.writable_volume_mounts:
            empty_dir: dict[str, Any] = {}

            if mount.medium:
                empty_dir["medium"] = mount.medium

            if mount.size_limit:
                empty_dir["sizeLimit"] = mount.size_limit

            volumes.append({
                "name": mount.name,
                "emptyDir": empty_dir,
            })
        return volumes
