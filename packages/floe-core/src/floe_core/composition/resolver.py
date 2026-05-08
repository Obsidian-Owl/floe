"""Composition resolver for validating selected plugin compatibility."""

from __future__ import annotations

from floe_core.composition.error_codes import (
    COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED,
    COMPOSITION_IDENTITY_MODE_UNSUPPORTED,
    COMPOSITION_IDENTITY_PROVIDER_MISSING,
    COMPOSITION_IDENTITY_PROVIDER_UNSUPPORTED,
    COMPOSITION_PROTOCOL_UNSUPPORTED,
    COMPOSITION_SECRET_PROJECTION_UNSUPPORTED,
    COMPOSITION_SECRET_PROVIDER_MISSING,
    COMPOSITION_SECRET_PROVIDER_UNSUPPORTED,
    COMPOSITION_STORAGE_MISSING,
)
from floe_core.composition.models import (
    CompositionIssue,
    CompositionValidationResult,
    PluginCapabilities,
    PluginRequirements,
)


class CompositionResolver:
    """Validate that selected plugin capabilities satisfy peer requirements."""

    def validate(
        self,
        capabilities: list[PluginCapabilities],
        requirements: list[PluginRequirements],
    ) -> CompositionValidationResult:
        """Return compatibility issues for the selected plugin graph."""
        issues: list[CompositionIssue] = []
        storage = next((item for item in capabilities if item.plugin_type == "storage"), None)
        catalog = next((item for item in capabilities if item.plugin_type == "catalog"), None)
        secrets = next((item for item in capabilities if item.plugin_type == "secrets"), None)
        identity = next((item for item in capabilities if item.plugin_type == "identity"), None)

        for requirement in requirements:
            if requirement.plugin_type == "ingestion":
                issues.extend(self._validate_ingestion(requirement, storage, catalog))
                continue
            if requirement.plugin_type != "catalog":
                continue

            if storage is None:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code=COMPOSITION_STORAGE_MISSING,
                        message=(
                            f"catalog {requirement.plugin_name} requires storage "
                            "capabilities but no storage plugin was selected"
                        ),
                        plugins=[requirement.ref],
                    )
                )
                continue
            issues.extend(self._validate_storage_for_catalog(storage, requirement))
            compatible_credential_modes = self._compatible_credential_modes(storage, requirement)
            issues.extend(self._validate_secret_projection(secrets, storage, requirement))
            if self._requires_identity_validation(storage, requirement):
                issues.extend(
                    self._validate_identity(
                        identity,
                        storage,
                        requirement,
                        compatible_credential_modes,
                    )
                )

        return CompositionValidationResult(
            valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )

    def _validate_ingestion(
        self,
        ingestion: PluginRequirements,
        storage: PluginCapabilities | None,
        catalog: PluginCapabilities | None,
    ) -> list[CompositionIssue]:
        """Validate ingestion requirements against selected storage and catalog."""
        issues: list[CompositionIssue] = []
        if storage is None:
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_STORAGE_MISSING,
                    message=(
                        f"ingestion {ingestion.plugin_name} requires storage "
                        "capabilities but no storage plugin was selected"
                    ),
                    plugins=[ingestion.ref],
                )
            )
        else:
            issues.extend(self._validate_storage_for_catalog(storage, ingestion))

        required_catalogs = list(ingestion.requirements.catalog_providers)
        if required_catalogs and catalog is None:
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_CATALOG_MISSING",
                    message=(
                        f"ingestion {ingestion.plugin_name} requires one of catalog providers "
                        f"{required_catalogs}; no catalog plugin was selected"
                    ),
                    plugins=[ingestion.ref],
                )
            )
        elif required_catalogs and catalog is not None:
            provided_catalogs = list(catalog.capabilities.catalog_providers)
            if not set(provided_catalogs).intersection(required_catalogs):
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_CATALOG_UNSUPPORTED",
                        message=(
                            f"ingestion {ingestion.plugin_name} requires one of catalog providers "
                            f"{required_catalogs}; catalog {catalog.plugin_name} provides "
                            f"{provided_catalogs}"
                        ),
                        plugins=[catalog.ref, ingestion.ref],
                    )
                )

        required_table_formats = list(ingestion.requirements.table_formats)
        if required_table_formats and catalog is None:
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_TABLE_FORMAT_UNSUPPORTED",
                    message=(
                        f"ingestion {ingestion.plugin_name} requires one of table formats "
                        f"{required_table_formats}; no catalog plugin was selected"
                    ),
                    plugins=[ingestion.ref],
                )
            )
        elif required_table_formats and catalog is not None:
            provided_table_formats = list(catalog.capabilities.table_formats)
            if not set(provided_table_formats).intersection(required_table_formats):
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_TABLE_FORMAT_UNSUPPORTED",
                        message=(
                            f"ingestion {ingestion.plugin_name} requires one of table formats "
                            f"{required_table_formats}; catalog {catalog.plugin_name} provides "
                            f"{provided_table_formats}"
                        ),
                        plugins=[catalog.ref, ingestion.ref],
                    )
                )

        return issues

    def _validate_storage_for_catalog(
        self,
        storage: PluginCapabilities,
        catalog: PluginRequirements,
    ) -> list[CompositionIssue]:
        """Validate storage capabilities against catalog requirements."""
        issues: list[CompositionIssue] = []
        storage_protocols = list(storage.capabilities.protocols)
        required_protocols = list(catalog.requirements.protocols)
        requester = f"{catalog.plugin_type} {catalog.plugin_name}"
        if required_protocols and not set(storage_protocols).intersection(required_protocols):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_PROTOCOL_UNSUPPORTED,
                    message=(
                        f"{requester} requires one of protocols "
                        f"{required_protocols}; storage {storage.plugin_name} "
                        f"provides {storage_protocols}"
                    ),
                    plugins=[storage.ref, catalog.ref],
                )
            )

        storage_modes = list(storage.capabilities.credential_modes)
        required_modes = list(catalog.requirements.credential_modes)
        if required_modes and not set(storage_modes).intersection(required_modes):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED,
                    message=(
                        f"{requester} requires one of credential modes "
                        f"{required_modes}; storage {storage.plugin_name} provides {storage_modes}"
                    ),
                    plugins=[storage.ref, catalog.ref],
                )
            )

        return issues

    def _compatible_credential_modes(
        self,
        storage: PluginCapabilities,
        requirement: PluginRequirements,
    ) -> list[str]:
        """Return credential modes accepted by both storage and catalog."""
        storage_modes = list(storage.capabilities.credential_modes)
        required_modes = set(requirement.requirements.credential_modes)
        return [mode for mode in storage_modes if mode in required_modes]

    def _requires_identity_validation(
        self,
        storage: PluginCapabilities,
        requirement: PluginRequirements,
    ) -> bool:
        """Return whether selected storage/catalog modes require identity validation."""
        compatible_modes = self._compatible_credential_modes(storage, requirement)
        non_identity_modes = [mode for mode in compatible_modes if mode != "workload-identity"]
        if non_identity_modes:
            return False
        return "workload-identity" in compatible_modes or bool(
            requirement.requirements.identity_modes
        )

    def _validate_secret_projection(
        self,
        secrets: PluginCapabilities | None,
        storage: PluginCapabilities,
        requirement: PluginRequirements,
    ) -> list[CompositionIssue]:
        """Validate required secret projection modes against secrets provider."""
        issues: list[CompositionIssue] = []
        storage_modes = list(storage.capabilities.secret_projection_modes)
        required_modes = list(requirement.requirements.secret_projection_modes)
        compatible_modes = self._compatible_secret_projection_modes(storage, requirement)
        if required_modes and not compatible_modes:
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_SECRET_PROJECTION_UNSUPPORTED,
                    message=(
                        f"catalog {requirement.plugin_name} requires one of secret "
                        f"projection modes {required_modes}; storage {storage.plugin_name} "
                        f"provides {storage_modes}"
                    ),
                    plugins=[storage.ref, requirement.ref],
                )
            )
            return issues

        if not compatible_modes:
            return issues

        required_providers = list(requirement.requirements.providers)
        if (
            secrets is None
            and any(mode in ("kubernetes-secret", "environment") for mode in compatible_modes)
            and not required_providers
        ):
            return issues

        mode = compatible_modes[0]
        if secrets is None:
            message = (
                f"catalog {requirement.plugin_name} requires secret projection "
                f"mode {mode} but no secrets plugin was selected"
            )
            if required_providers:
                message = (
                    f"catalog {requirement.plugin_name} requires one of secret "
                    f"providers {required_providers} for secret projection mode {mode} "
                    "but no secrets plugin was selected"
                )
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_SECRET_PROVIDER_MISSING,
                    message=message,
                    plugins=[requirement.ref],
                )
            )
            return issues

        provided_modes = list(secrets.capabilities.secret_projection_modes)
        if not set(provided_modes).intersection(compatible_modes):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_SECRET_PROJECTION_UNSUPPORTED,
                    message=(
                        f"catalog {requirement.plugin_name} requires secret projection "
                        f"mode {mode}; secrets {secrets.plugin_name} provides {provided_modes}"
                    ),
                    plugins=[secrets.ref, requirement.ref],
                )
            )
            return issues

        provided_providers = list(secrets.capabilities.providers)
        if required_providers and not set(required_providers).intersection(provided_providers):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_SECRET_PROVIDER_UNSUPPORTED,
                    message=(
                        f"catalog {requirement.plugin_name} requires one of secret "
                        f"providers {required_providers}; secrets {secrets.plugin_name} "
                        f"provides {provided_providers}"
                    ),
                    plugins=[secrets.ref, requirement.ref],
                )
            )
        return issues

    def _compatible_secret_projection_modes(
        self,
        storage: PluginCapabilities,
        requirement: PluginRequirements,
    ) -> list[str]:
        """Return secret projection modes accepted by storage and catalog."""
        storage_modes = list(storage.capabilities.secret_projection_modes)
        required_modes = set(requirement.requirements.secret_projection_modes)
        return [mode for mode in storage_modes if mode in required_modes]

    def _validate_identity(
        self,
        identity: PluginCapabilities | None,
        storage: PluginCapabilities,
        requirement: PluginRequirements,
        compatible_credential_modes: list[str],
    ) -> list[CompositionIssue]:
        """Validate required workload identity modes against identity provider."""
        issues: list[CompositionIssue] = []
        required_modes = list(requirement.requirements.identity_modes)
        if "workload-identity" not in compatible_credential_modes and not required_modes:
            return issues

        if identity is None:
            mode = required_modes[0] if required_modes else "workload-identity"
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_IDENTITY_PROVIDER_MISSING,
                    message=(
                        f"catalog {requirement.plugin_name} requires identity mode {mode} "
                        "but no identity plugin was selected"
                    ),
                    plugins=[requirement.ref],
                )
            )
            return issues

        storage_modes = list(storage.capabilities.identity_modes)
        provided_modes = list(identity.capabilities.identity_modes)
        if "workload-identity" in compatible_credential_modes and not required_modes:
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_IDENTITY_MODE_UNSUPPORTED,
                    message=(
                        f"catalog {requirement.plugin_name} requires workload identity "
                        "but does not declare concrete identity modes; storage "
                        f"{storage.plugin_name} provides {storage_modes}; identity "
                        f"{identity.plugin_name} provides {provided_modes}"
                    ),
                    plugins=[storage.ref, identity.ref, requirement.ref],
                )
            )
            return issues

        compatible_modes = [mode for mode in storage_modes if mode in set(required_modes)]
        if (
            required_modes
            and compatible_modes
            and set(provided_modes).intersection(compatible_modes)
        ):
            required_providers = list(requirement.requirements.providers)
            provided_providers = list(identity.capabilities.providers)
            if required_providers and not set(required_providers).intersection(provided_providers):
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code=COMPOSITION_IDENTITY_PROVIDER_UNSUPPORTED,
                        message=(
                            f"catalog {requirement.plugin_name} requires one of identity "
                            f"providers {required_providers}; identity "
                            f"{identity.plugin_name} provides {provided_providers}"
                        ),
                        plugins=[identity.ref, requirement.ref],
                    )
                )
            return issues

        if required_modes and len(required_modes) == 1 and compatible_modes:
            mode = required_modes[0]
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_IDENTITY_MODE_UNSUPPORTED,
                    message=(
                        f"catalog {requirement.plugin_name} requires identity mode {mode}; "
                        f"identity {identity.plugin_name} provides {provided_modes}"
                    ),
                    plugins=[identity.ref, requirement.ref],
                )
            )
            return issues

        if required_modes:
            issues.append(
                CompositionIssue(
                    severity="error",
                    code=COMPOSITION_IDENTITY_MODE_UNSUPPORTED,
                    message=(
                        f"catalog {requirement.plugin_name} requires one of identity "
                        f"modes {required_modes}; storage {storage.plugin_name} "
                        f"provides {storage_modes}; identity {identity.plugin_name} "
                        f"provides {provided_modes}"
                    ),
                    plugins=[storage.ref, identity.ref, requirement.ref],
                )
            )
        return issues
