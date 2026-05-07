"""Unit tests for storage/catalog plugin composition resolution."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.composition.models import (
    CapabilitySet,
    CompositionIssue,
    PluginCapabilities,
    PluginRequirements,
    RequirementSet,
)
from floe_core.composition.resolver import CompositionResolver

pytestmark = pytest.mark.requirement("AC-4")


def test_resolver_accepts_satisfied_requirements() -> None:
    """Resolver must accept storage capabilities that satisfy catalog needs."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            path_style_access=True,
            sts=False,
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="polaris",
        requirements=RequirementSet(
            protocols=["s3-compatible", "s3"],
            credential_modes=["kubernetes-secret", "workload-identity"],
            requires_server_side_storage_access=True,
            supports_no_sts=True,
            supports_path_style_access=True,
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is True
    assert result.issues == []


def test_resolver_rejects_incompatible_protocol() -> None:
    """Resolver must reject catalog protocol needs the storage plugin lacks."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["kubernetes-secret"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_PROTOCOL_UNSUPPORTED",
            message=(
                "catalog glue requires one of protocols ['s3']; "
                "storage minio provides ['s3-compatible']"
            ),
            plugins=["storage:minio", "catalog:glue"],
        )
    ]


def test_resolver_rejects_incompatible_credential_mode() -> None:
    """Resolver must reject credential modes unsupported by the storage plugin."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3-compatible"],
            credential_modes=["workload-identity"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
            message=(
                "catalog glue requires one of credential modes ['workload-identity']; "
                "storage minio provides ['kubernetes-secret']"
            ),
            plugins=["storage:minio", "catalog:glue"],
        )
    ]


def test_resolver_rejects_missing_storage_for_catalog_requirements() -> None:
    """Resolver must fail catalog requirements when no storage plugin is selected."""
    resolver = CompositionResolver()
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="polaris",
        requirements=RequirementSet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )

    result = resolver.validate([], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_STORAGE_MISSING",
            message=(
                "catalog polaris requires storage capabilities but no storage plugin was selected"
            ),
            plugins=["catalog:polaris"],
        )
    ]


def test_resolver_rejects_malformed_capability_payload() -> None:
    """Composition payloads must be typed instead of arbitrary dictionaries."""
    with pytest.raises(ValidationError):
        PluginCapabilities(
            plugin_type="storage",
            plugin_name="minio",
            capabilities={"protocols": "s3-compatible"},  # type: ignore[arg-type]
        )


def test_capability_set_accepts_security_composition_modes() -> None:
    """CapabilitySet should carry secret projection and identity capabilities."""
    capabilities = CapabilitySet(
        credential_modes=["kubernetes-secret", "workload-identity"],
        secret_projection_modes=["kubernetes-secret", "external-secret-sync"],
        identity_modes=["aws-irsa", "oidc-federation"],
        providers=["kubernetes", "aws", "oidc"],
    )

    assert capabilities.secret_projection_modes == [
        "kubernetes-secret",
        "external-secret-sync",
    ]
    assert capabilities.identity_modes == ["aws-irsa", "oidc-federation"]
    assert capabilities.providers == ["kubernetes", "aws", "oidc"]


def test_requirement_set_accepts_security_composition_modes() -> None:
    """RequirementSet should describe required secret and identity modes."""
    requirements = RequirementSet(
        credential_modes=["external-secret-sync"],
        secret_projection_modes=["external-secret-sync"],
        identity_modes=["gcp-workload-identity"],
        providers=["gcp"],
    )

    assert requirements.credential_modes == ["external-secret-sync"]
    assert requirements.secret_projection_modes == ["external-secret-sync"]
    assert requirements.identity_modes == ["gcp-workload-identity"]
    assert requirements.providers == ["gcp"]


def test_resolver_accepts_kubernetes_secret_with_implicit_baseline() -> None:
    """Existing MinIO and Polaris path must stay valid without secrets plugin."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            secret_projection_modes=["kubernetes-secret"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="polaris",
        requirements=RequirementSet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            secret_projection_modes=["kubernetes-secret"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is True
    assert result.issues == []


def test_resolver_rejects_external_secret_sync_without_secrets_plugin() -> None:
    """External secret sync requires an explicit secrets provider."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_SECRET_PROVIDER_MISSING",
            message=(
                "catalog glue requires secret projection mode external-secret-sync "
                "but no secrets plugin was selected"
            ),
            plugins=["catalog:glue"],
        )
    ]


def test_resolver_accepts_external_secret_sync_with_matching_secrets_plugin() -> None:
    """External secret sync succeeds when selected secrets plugin supports it."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )
    secrets = PluginCapabilities(
        plugin_type="secrets",
        plugin_name="infisical",
        capabilities=CapabilitySet(
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
            providers=["infisical"],
        ),
    )

    result = resolver.validate([storage, secrets], [catalog])

    assert result.valid is True
    assert result.issues == []


def test_resolver_rejects_unsupported_secret_projection_mode() -> None:
    """Selected secrets provider must support the requested projection mode."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="azure-blob",
        capabilities=CapabilitySet(
            protocols=["azure-blob"],
            credential_modes=["csi-secret-volume"],
            secret_projection_modes=["csi-secret-volume"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="rest",
        requirements=RequirementSet(
            protocols=["azure-blob"],
            credential_modes=["csi-secret-volume"],
            secret_projection_modes=["csi-secret-volume"],
        ),
    )
    secrets = PluginCapabilities(
        plugin_type="secrets",
        plugin_name="infisical",
        capabilities=CapabilitySet(
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
            providers=["infisical"],
        ),
    )

    result = resolver.validate([storage, secrets], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_SECRET_PROJECTION_UNSUPPORTED",
            message=(
                "catalog rest requires secret projection mode csi-secret-volume; "
                "secrets infisical provides ['external-secret-sync']"
            ),
            plugins=["secrets:infisical", "catalog:rest"],
        )
    ]


def test_resolver_rejects_identity_mode_without_identity_plugin() -> None:
    """Workload identity requires an explicit identity provider."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_IDENTITY_PROVIDER_MISSING",
            message=(
                "catalog glue requires identity mode aws-irsa but no identity plugin was selected"
            ),
            plugins=["catalog:glue"],
        )
    ]


def test_resolver_rejects_unsupported_identity_mode() -> None:
    """Selected identity provider must support the requested identity mode."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )
    identity = PluginCapabilities(
        plugin_type="identity",
        plugin_name="keycloak",
        capabilities=CapabilitySet(
            credential_modes=["workload-identity"],
            identity_modes=["oidc-federation"],
            providers=["oidc"],
        ),
    )

    result = resolver.validate([storage, identity], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_IDENTITY_MODE_UNSUPPORTED",
            message=(
                "catalog glue requires identity mode aws-irsa; "
                "identity keycloak provides ['oidc-federation']"
            ),
            plugins=["identity:keycloak", "catalog:glue"],
        )
    ]


def test_resolver_treats_security_modes_as_alternatives_for_kubernetes_secret_path() -> None:
    """Kubernetes Secret path should satisfy mixed-mode requirements without identity."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret", "workload-identity"],
            secret_projection_modes=["kubernetes-secret", "external-secret-sync"],
            identity_modes=["oidc-federation"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="polaris",
        requirements=RequirementSet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret", "workload-identity"],
            secret_projection_modes=["kubernetes-secret", "external-secret-sync"],
            identity_modes=["oidc-federation"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is True
    assert result.issues == []


def test_resolver_accepts_one_matching_identity_mode_from_alternatives() -> None:
    """One matching identity mode should satisfy an alternative mode list."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa", "aws-pod-identity"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa", "aws-pod-identity"],
        ),
    )
    identity = PluginCapabilities(
        plugin_type="identity",
        plugin_name="aws",
        capabilities=CapabilitySet(
            credential_modes=["workload-identity"],
            identity_modes=["aws-pod-identity"],
            providers=["aws"],
        ),
    )

    result = resolver.validate([storage, identity], [catalog])

    assert result.valid is True
    assert result.issues == []
