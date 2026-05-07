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
        secrets = next((item for item in capabilities if item.plugin_type == "secrets"), None)
        identity = next((item for item in capabilities if item.plugin_type == "identity"), None)

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
            issues.extend(self._validate_secret_projection(secrets, requirement))
            if self._requires_identity_validation(storage, requirement):
                issues.extend(self._validate_identity(identity, requirement))

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

    def _requires_identity_validation(
        self,
        storage: PluginCapabilities,
        requirement: PluginRequirements,
    ) -> bool:
        """Return whether selected storage/catalog modes require identity validation."""
        storage_modes = set(storage.capabilities.credential_modes)
        required_modes = set(requirement.requirements.credential_modes)
        workload_identity_selected = "workload-identity" in storage_modes.intersection(
            required_modes
        )
        return workload_identity_selected or bool(requirement.requirements.identity_modes)

    def _validate_secret_projection(
        self,
        secrets: PluginCapabilities | None,
        requirement: PluginRequirements,
    ) -> list[CompositionIssue]:
        """Validate required secret projection modes against secrets provider."""
        issues: list[CompositionIssue] = []
        for mode in requirement.requirements.secret_projection_modes:
            if mode in ("kubernetes-secret", "environment"):
                if secrets is None:
                    continue
            if secrets is None:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_SECRET_PROVIDER_MISSING",
                        message=(
                            f"catalog {requirement.plugin_name} requires secret projection "
                            f"mode {mode} but no secrets plugin was selected"
                        ),
                        plugins=[requirement.ref],
                    )
                )
                continue
            provided_modes = list(secrets.capabilities.secret_projection_modes)
            if mode not in provided_modes:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_SECRET_PROJECTION_UNSUPPORTED",
                        message=(
                            f"catalog {requirement.plugin_name} requires secret projection "
                            f"mode {mode}; secrets {secrets.plugin_name} provides {provided_modes}"
                        ),
                        plugins=[secrets.ref, requirement.ref],
                    )
                )
        return issues

    def _validate_identity(
        self,
        identity: PluginCapabilities | None,
        requirement: PluginRequirements,
    ) -> list[CompositionIssue]:
        """Validate required workload identity modes against identity provider."""
        issues: list[CompositionIssue] = []
        requires_workload_identity = (
            "workload-identity" in requirement.requirements.credential_modes
        )
        required_modes = list(requirement.requirements.identity_modes)
        if not requires_workload_identity and not required_modes:
            return issues

        if identity is None:
            mode = required_modes[0] if required_modes else "workload-identity"
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_IDENTITY_PROVIDER_MISSING",
                    message=(
                        f"catalog {requirement.plugin_name} requires identity mode {mode} "
                        "but no identity plugin was selected"
                    ),
                    plugins=[requirement.ref],
                )
            )
            return issues

        provided_modes = list(identity.capabilities.identity_modes)
        for mode in required_modes:
            if mode not in provided_modes:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_IDENTITY_MODE_UNSUPPORTED",
                        message=(
                            f"catalog {requirement.plugin_name} requires identity mode {mode}; "
                            f"identity {identity.plugin_name} provides {provided_modes}"
                        ),
                        plugins=[identity.ref, requirement.ref],
                    )
                )
        return issues
