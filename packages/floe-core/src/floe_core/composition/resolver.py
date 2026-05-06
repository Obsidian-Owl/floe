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

        for requirement in requirements:
            if requirement.plugin_type != "catalog":
                continue
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

        return CompositionValidationResult(
            valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )

    def _validate_storage_for_catalog(
        self,
        storage: PluginCapabilities,
        catalog: PluginRequirements,
    ) -> list[CompositionIssue]:
        """Validate storage capabilities against catalog requirements."""
        issues: list[CompositionIssue] = []
        storage_protocols = list(storage.capabilities.get("protocols", []))
        required_protocols = list(catalog.requirements.get("protocols", []))
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

        storage_modes = list(storage.capabilities.get("credential_modes", []))
        required_modes = list(catalog.requirements.get("credential_modes", []))
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
