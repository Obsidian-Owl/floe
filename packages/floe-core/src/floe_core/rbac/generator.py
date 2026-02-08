"""RBACManifestGenerator for Kubernetes RBAC manifest generation.

This module provides the RBACManifestGenerator class that transforms floe
configuration into Kubernetes RBAC YAML manifests. It handles aggregation
and deduplication of permissions across data products.

Example:
    >>> from floe_core.rbac.generator import RBACManifestGenerator
    >>> from floe_core.plugin_registry import PluginRegistry
    >>> # Get RBACPlugin via registry (no direct plugin imports)
    >>> registry = PluginRegistry()
    >>> rbac_plugins = list(registry.list("floe.rbac"))
    >>> if rbac_plugins:
    ...     plugin = registry.get("floe.rbac", rbac_plugins[0].name)
    ...     generator = RBACManifestGenerator(plugin=plugin)
    ...     result = generator.generate(security_config, secret_refs)

Task: T043, T044, T045, T046, T047, T065
User Story: US4 - RBAC Manifest Generation
Requirements: FR-002, FR-050, FR-051, FR-052, FR-053
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from opentelemetry import trace

from floe_core.rbac.audit import (
    RBACGenerationAuditEvent,
    log_rbac_event,
)
from floe_core.rbac.result import GenerationResult
from floe_core.schemas.rbac import RoleRule
from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer


def _get_tracer() -> trace.Tracer:
    """Get the tracer, initializing lazily with fallback to NoOp.

    Returns a thread-safe tracer from the factory. Falls back to NoOpTracer
    if OTel is not properly configured or initialization fails.
    """
    return _factory_get_tracer(__name__)


if TYPE_CHECKING:
    from floe_core.plugins.rbac import RBACPlugin
    from floe_core.schemas.rbac import (
        NamespaceConfig,
        RoleBindingConfig,
        RoleConfig,
        ServiceAccountConfig,
    )
    from floe_core.schemas.security import SecurityConfig


# Manifest file names - part of the contract (FR-053)
MANIFEST_FILES: list[str] = [
    "serviceaccounts.yaml",
    "roles.yaml",
    "rolebindings.yaml",
    "namespaces.yaml",
]

# Required K8s manifest fields for validation (FR-051)
REQUIRED_MANIFEST_FIELDS: set[str] = {"apiVersion", "kind", "metadata"}

# Valid K8s kinds for RBAC resources
VALID_RBAC_KINDS: set[str] = {
    "ServiceAccount",
    "Role",
    "RoleBinding",
    "ClusterRole",
    "ClusterRoleBinding",
    "Namespace",
}


class ManifestValidationError(Exception):
    """Raised when a manifest fails validation."""

    pass


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate a single K8s manifest for required fields.

    Checks that the manifest contains required K8s fields and valid values
    to ensure it will pass kubectl apply --dry-run=client.

    Args:
        manifest: Dictionary representing a K8s manifest.

    Returns:
        List of validation error messages. Empty if valid.

    Contract:
        - MUST check for apiVersion, kind, metadata fields (FR-051)
        - MUST validate kind is a recognized RBAC resource
        - MUST validate metadata contains name field
        - MUST return empty list for valid manifests

    Example:
        >>> errors = validate_manifest({"kind": "ServiceAccount"})
        >>> "Missing required field: apiVersion" in errors
        True
    """
    errors: list[str] = []

    # Check required top-level fields
    for required_field in REQUIRED_MANIFEST_FIELDS:
        if required_field not in manifest:
            errors.append(f"Missing required field: {required_field}")

    # Validate kind if present
    kind = manifest.get("kind")
    if kind and kind not in VALID_RBAC_KINDS:
        errors.append(
            f"Unknown kind: {kind}. Expected one of: {sorted(VALID_RBAC_KINDS)}"
        )

    # Validate metadata has name
    metadata = manifest.get("metadata", {})
    if "metadata" in manifest and not isinstance(metadata, dict):
        errors.append("metadata must be a dictionary")
    elif isinstance(metadata, dict) and "name" not in metadata:
        errors.append("metadata.name is required")

    # Validate apiVersion format
    api_version = manifest.get("apiVersion")
    if api_version and not isinstance(api_version, str):
        errors.append("apiVersion must be a string")

    return errors


def validate_all_manifests(
    manifests: dict[str, list[dict[str, Any]]],
) -> tuple[bool, list[str]]:
    """Validate all manifests in a collection.

    Args:
        manifests: Dictionary mapping file names to lists of manifest dicts.

    Returns:
        Tuple of (is_valid, error_messages).

    Contract:
        - MUST validate each manifest in each file
        - MUST return True only if all manifests are valid
        - MUST include file context in error messages

    Example:
        >>> is_valid, errors = validate_all_manifests({"roles.yaml": [...]})
        >>> is_valid
        True
    """
    all_errors: list[str] = []

    for filename, docs in manifests.items():
        for i, doc in enumerate(docs):
            errors = validate_manifest(doc)
            for error in errors:
                all_errors.append(f"{filename}[{i}]: {error}")

    return len(all_errors) == 0, all_errors


def aggregate_permissions(secret_refs: list[str]) -> list[RoleRule]:
    """Aggregate permissions across all secret references.

    Combines multiple secret references into minimal Role rules following
    least-privilege principles. Deduplicates secrets and produces a single
    rule with resourceNames constraint.

    Args:
        secret_refs: List of secret names to grant access to.

    Returns:
        List of RoleRule instances representing aggregated permissions.

    Contract:
        - MUST return empty list for empty secret_refs (FR-052)
        - MUST deduplicate secret references (FR-052)
        - MUST preserve order of first occurrence (FR-052)
        - MUST use only 'get' verb for secrets (FR-024)
        - MUST use resourceNames constraint (FR-021)
        - MUST target core API group (empty string) for secrets

    Example:
        >>> rules = aggregate_permissions(["secret-a", "secret-b"])
        >>> rules[0].verbs
        ['get']
        >>> rules[0].resource_names
        ['secret-a', 'secret-b']
    """
    if not secret_refs:
        return []

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_refs: list[str] = []
    for ref in secret_refs:
        # Strip whitespace for consistency
        clean_ref = ref.strip() if isinstance(ref, str) else ref
        if clean_ref not in seen:
            seen.add(clean_ref)
            unique_refs.append(clean_ref)

    # Create single rule with all resource names
    return [
        RoleRule(
            api_groups=[""],
            resources=["secrets"],
            verbs=["get"],
            resource_names=unique_refs,
        )
    ]


def validate_secret_references(
    secret_references: list[str],
    permitted_secrets: set[str],
) -> tuple[bool, list[str]]:
    """Validate that all secret references have RBAC permissions.

    Ensures every secret reference in the configuration is covered by
    RBAC permissions before generation proceeds. This prevents runtime
    access failures due to missing permissions.

    Args:
        secret_references: List of secret names required by data products.
        permitted_secrets: Set of secret names with RBAC access granted.

    Returns:
        Tuple of (is_valid, error_messages).

    Contract:
        - MUST fail if any secret_ref not in permitted_secrets (FR-073)
        - MUST report ALL missing permissions, not just first
        - MUST handle duplicate references (report once)
        - MUST strip whitespace from secret names

    Example:
        >>> is_valid, errors = validate_secret_references(
        ...     ["secret-a", "secret-b"],
        ...     {"secret-a"}
        ... )
        >>> is_valid
        False
        >>> "secret-b" in errors[0]
        True
    """
    if not secret_references:
        return True, []

    # Deduplicate and clean secret references
    seen: set[str] = set()
    unique_refs: list[str] = []
    for ref in secret_references:
        clean_ref = ref.strip() if isinstance(ref, str) else ref
        if clean_ref not in seen:
            seen.add(clean_ref)
            unique_refs.append(clean_ref)

    # Find missing permissions
    missing: list[str] = []
    for ref in unique_refs:
        if ref not in permitted_secrets:
            missing.append(ref)

    if not missing:
        return True, []

    # Build error messages
    errors = [
        f"Secret '{name}' requires RBAC permission but is not in permitted secrets"
        for name in missing
    ]

    return False, errors


def write_manifests(
    manifests: dict[str, list[dict[str, Any]]],
    output_dir: Path,
) -> list[Path]:
    """Write manifests to output directory.

    Writes each manifest type to its own file using YAML multi-document
    format with document separators.

    Args:
        manifests: Dictionary mapping file names to lists of manifest dicts.
        output_dir: Directory to write manifest files.

    Returns:
        List of paths to generated files.

    Contract:
        - MUST create output_dir if not exists (FR-053)
        - MUST create all manifest files even if empty (FR-053)
        - MUST use YAML document separator between manifests (FR-051)
        - MUST overwrite existing files (FR-053)
        - MUST return list of generated file paths (FR-053)

    Example:
        >>> paths = write_manifests(manifests, Path("target/rbac"))
        >>> len(paths)
        4
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_paths: list[Path] = []

    for filename, docs in manifests.items():
        file_path = output_dir / filename

        if not docs:
            # Write empty file or minimal placeholder
            file_path.write_text("")
        else:
            # Write all documents with separator
            # SECURITY: Use safe_dump_all to prevent arbitrary Python object serialization
            yaml_content = yaml.safe_dump_all(
                docs,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            file_path.write_text(yaml_content)

        generated_paths.append(file_path)

    return generated_paths


@dataclass
class RBACManifestGenerator:
    """Generates RBAC manifests from floe configuration.

    Transforms SecurityConfig and secret references into Kubernetes RBAC
    YAML manifests. Handles aggregation of permissions across data products
    into minimal Role definitions.

    Attributes:
        plugin: The RBACPlugin implementation to use for manifest generation.
        output_dir: Directory to write generated manifests.

    Contract:
        - MUST use provided RBACPlugin for manifest generation (FR-002)
        - MUST write to output_dir (default: target/rbac) (FR-050)
        - MUST produce separate files per resource type (FR-053)
        - MUST aggregate permissions into minimal Roles (FR-052)

    Example:
        >>> generator = RBACManifestGenerator(
        ...     plugin=K8sRBACPlugin(),
        ...     output_dir=Path("target/rbac")
        ... )
        >>> result = generator.generate(security_config, ["snowflake-creds"])
        >>> result.success
        True
    """

    plugin: RBACPlugin
    output_dir: Path = field(default_factory=lambda: Path("target/rbac"))

    # =========================================================================
    # Helper Methods (T023 - Reduce Cyclomatic Complexity via Strategy Pattern)
    # =========================================================================

    def _generate_manifests_for_type(
        self,
        configs: list[Any] | None,
        generator_fn: Any,
        resource_type: str,
        errors: list[str],
    ) -> list[dict[str, Any]]:
        """Generate manifests for a specific resource type.

        Applies the Strategy pattern to consolidate repetitive generation loops.

        Args:
            configs: List of configuration objects (ServiceAccountConfig, etc.)
            generator_fn: Plugin method to generate manifest (e.g., plugin.generate_role)
            resource_type: Name of resource type for error messages
            errors: List to append error messages to

        Returns:
            List of generated manifest dictionaries.
        """
        manifests: list[dict[str, Any]] = []
        if not configs:
            return manifests

        for config in configs:
            try:
                manifest = generator_fn(config)
                manifests.append(manifest)
            except Exception as e:
                config_name = getattr(config, "name", "unknown")
                errors.append(f"Failed to generate {resource_type} {config_name}: {e}")

        return manifests

    def generate(
        self,
        security_config: SecurityConfig,
        secret_references: list[str],
        *,
        service_accounts: list[ServiceAccountConfig] | None = None,
        roles: list[RoleConfig] | None = None,
        role_bindings: list[RoleBindingConfig] | None = None,
        namespaces: list[NamespaceConfig] | None = None,
    ) -> GenerationResult:
        """Generate all RBAC manifests.

        Generates ServiceAccount, Role, RoleBinding, and Namespace manifests
        from the provided configuration and writes them to the output directory.

        Args:
            security_config: Security configuration from manifest.yaml.
            secret_references: List of secret names referenced by data products.
            service_accounts: Optional explicit list of ServiceAccountConfigs.
            roles: Optional explicit list of RoleConfigs.
            role_bindings: Optional explicit list of RoleBindingConfigs.
            namespaces: Optional explicit list of NamespaceConfigs.

        Returns:
            GenerationResult with counts and file paths.

        Contract:
            - MUST generate valid YAML manifests (FR-051)
            - MUST aggregate permissions if not explicitly provided (FR-052)
            - MUST write to output_dir (FR-050)
            - MUST track counts of generated resources

        Example:
            >>> result = generator.generate(config, ["secret-a", "secret-b"])
            >>> result.service_accounts
            1
        """
        with _get_tracer().start_as_current_span(
            "rbac_manifest_generator.generate",
            attributes={
                "rbac.enabled": security_config.rbac.enabled,
                "rbac.secret_refs_count": len(secret_references),
                "rbac.output_dir": str(self.output_dir),
                "rbac.service_accounts_count": len(service_accounts or []),
                "rbac.roles_count": len(roles or []),
                "rbac.role_bindings_count": len(role_bindings or []),
                "rbac.namespaces_count": len(namespaces or []),
            },
        ) as span:
            return self._generate_impl(
                security_config,
                secret_references,
                service_accounts=service_accounts,
                roles=roles,
                role_bindings=role_bindings,
                namespaces=namespaces,
                span=span,
            )

    def _generate_impl(
        self,
        security_config: SecurityConfig,
        secret_references: list[str],
        *,
        service_accounts: list[ServiceAccountConfig] | None = None,
        roles: list[RoleConfig] | None = None,
        role_bindings: list[RoleBindingConfig] | None = None,
        namespaces: list[NamespaceConfig] | None = None,
        span: trace.Span | None = None,
    ) -> GenerationResult:
        """Implementation of generate with span context."""
        # Check if RBAC is enabled
        if not security_config.rbac.enabled:
            # Log disabled audit event (FR-072)
            audit_event = RBACGenerationAuditEvent.create_disabled(
                output_dir=self.output_dir,
            )
            log_rbac_event(audit_event)

            return GenerationResult(
                success=True,
                warnings=["RBAC generation disabled in security_config"],
            )

        errors: list[str] = []
        warnings: list[str] = []

        # Generate manifests using Strategy pattern (T023: Reduced CC from 24 to ~12)
        sa_manifests = self._generate_manifests_for_type(
            service_accounts,
            self.plugin.generate_service_account,
            "ServiceAccount",
            errors,
        )
        role_manifests = self._generate_manifests_for_type(
            roles, self.plugin.generate_role, "Role", errors
        )
        binding_manifests = self._generate_manifests_for_type(
            role_bindings, self.plugin.generate_role_binding, "RoleBinding", errors
        )
        ns_manifests = self._generate_manifests_for_type(
            namespaces, self.plugin.generate_namespace, "Namespace", errors
        )

        # Aggregate permissions from secret references if no explicit roles provided
        if secret_references and not roles:
            aggregated_rules = self.aggregate_permissions(secret_references)
            if aggregated_rules:
                warnings.append(
                    f"Aggregated {len(secret_references)} secret refs into "
                    f"{len(aggregated_rules)} rules"
                )

        # Write manifests to files
        all_manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": sa_manifests,
            "roles.yaml": role_manifests,
            "rolebindings.yaml": binding_manifests,
            "namespaces.yaml": ns_manifests,
        }

        # Validate all manifests before writing (FR-051)
        with _get_tracer().start_as_current_span(
            "rbac_manifest_generator.validate",
            attributes={
                "rbac.manifest_count": sum(len(v) for v in all_manifests.values())
            },
        ):
            is_valid, validation_errors = validate_all_manifests(all_manifests)
        if not is_valid:
            errors.extend(validation_errors)

            # Record validation failure on span
            if span:
                span.set_attribute("rbac.validation_errors", len(validation_errors))
                span.set_attribute("rbac.success", False)

            # Log validation error audit event (FR-072)
            audit_event = RBACGenerationAuditEvent.create_validation_error(
                output_dir=self.output_dir,
                errors=errors,
                warnings=warnings,
            )
            log_rbac_event(audit_event)

            return GenerationResult(
                success=False,
                errors=errors,
                warnings=warnings,
            )

        try:
            with _get_tracer().start_as_current_span(
                "rbac_manifest_generator.write_manifests",
                attributes={
                    "rbac.output_dir": str(self.output_dir),
                    "rbac.manifest_count": sum(len(v) for v in all_manifests.values()),
                },
            ):
                files_generated = write_manifests(all_manifests, self.output_dir)
        except Exception as e:
            errors.append(f"Failed to write manifests: {e}")

            # Record write failure on span
            if span:
                span.record_exception(e)
                span.set_attribute("rbac.success", False)

            # Log write error audit event (FR-072)
            audit_event = RBACGenerationAuditEvent.create_write_error(
                output_dir=self.output_dir,
                errors=errors,
                warnings=warnings,
            )
            log_rbac_event(audit_event)

            return GenerationResult(
                success=False,
                errors=errors,
                warnings=warnings,
            )

        # Record success on span
        if span:
            span.set_attribute("rbac.success", True)
            span.set_attribute("rbac.files_generated", len(files_generated))

        # Log success audit event (FR-072)
        audit_event = RBACGenerationAuditEvent.create_success(
            service_accounts=len(sa_manifests),
            roles=len(role_manifests),
            role_bindings=len(binding_manifests),
            namespaces=len(ns_manifests),
            output_dir=self.output_dir,
            files_generated=files_generated,
            secret_refs_count=len(secret_references),
            warnings=warnings,
        )
        log_rbac_event(audit_event)

        return GenerationResult(
            success=len(errors) == 0,
            files_generated=files_generated,
            service_accounts=len(sa_manifests),
            roles=len(role_manifests),
            role_bindings=len(binding_manifests),
            namespaces=len(ns_manifests),
            warnings=warnings,
            errors=errors,
        )

    def aggregate_permissions(
        self,
        secret_references: list[str],
    ) -> list[RoleRule]:
        """Aggregate permissions across all secret references.

        Args:
            secret_references: List of secret names to grant access to.

        Returns:
            List of RoleRule instances representing aggregated permissions.

        See Also:
            Module-level aggregate_permissions function for implementation.
        """
        return aggregate_permissions(secret_references)

    def write_manifests(
        self,
        manifests: dict[str, list[dict[str, Any]]],
    ) -> list[Path]:
        """Write manifests to output directory.

        Args:
            manifests: Dictionary mapping file names to lists of manifest dicts.

        Returns:
            List of paths to generated files.

        See Also:
            Module-level write_manifests function for implementation.
        """
        return write_manifests(manifests, self.output_dir)

    def validate_secret_references(
        self,
        secret_references: list[str],
        permitted_secrets: set[str],
    ) -> tuple[bool, list[str]]:
        """Validate that all secret references have RBAC permissions.

        Args:
            secret_references: List of secret names required by data products.
            permitted_secrets: Set of secret names with RBAC access granted.

        Returns:
            Tuple of (is_valid, error_messages).

        See Also:
            Module-level validate_secret_references function for implementation.
        """
        return validate_secret_references(secret_references, permitted_secrets)
