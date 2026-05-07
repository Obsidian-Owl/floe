"""Composition resolver for validating selected plugin compatibility."""

from __future__ import annotations

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

        for requirement in requirements:
            if requirement.plugin_type == "catalog":
                if storage is None:
                    issues.append(
                        CompositionIssue(
                            severity="error",
                            code="COMPOSITION_STORAGE_MISSING",
                            message=(
                                f"catalog {requirement.plugin_name} requires storage "
                                "capabilities but no storage plugin was selected"
                            ),
                            plugins=[requirement.ref],
                        )
                    )
                    continue
                issues.extend(self._validate_storage_for_catalog(storage, requirement))
                continue

            if requirement.plugin_type == "ingestion":
                issues.extend(self._validate_ingestion(requirement, storage, catalog))

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
                    code="COMPOSITION_STORAGE_MISSING",
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
        if required_protocols and not set(storage_protocols).intersection(required_protocols):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_PROTOCOL_UNSUPPORTED",
                    message=(
                        f"catalog {catalog.plugin_name} requires one of protocols "
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
                    code="COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
                    message=(
                        f"catalog {catalog.plugin_name} requires one of credential modes "
                        f"{required_modes}; storage {storage.plugin_name} provides {storage_modes}"
                    ),
                    plugins=[storage.ref, catalog.ref],
                )
            )

        return issues
