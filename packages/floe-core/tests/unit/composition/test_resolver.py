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


def test_resolver_rejects_ingestion_unsupported_catalog_provider() -> None:
    """Resolver must reject ingestion catalog provider needs the catalog lacks."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )
    catalog = PluginCapabilities(
        plugin_type="catalog",
        plugin_name="glue",
        capabilities=CapabilitySet(catalog_providers=["glue"]),
    )
    ingestion = PluginRequirements(
        plugin_type="ingestion",
        plugin_name="dlt",
        requirements=RequirementSet(catalog_providers=["iceberg-rest"]),
    )

    result = resolver.validate([storage, catalog], [ingestion])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_CATALOG_UNSUPPORTED",
            message=(
                "ingestion dlt requires one of catalog providers ['iceberg-rest']; "
                "catalog glue provides ['glue']"
            ),
            plugins=["catalog:glue", "ingestion:dlt"],
        )
    ]


def test_resolver_rejects_ingestion_unsupported_table_format() -> None:
    """Resolver must reject ingestion table formats the catalog lacks."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )
    catalog = PluginCapabilities(
        plugin_type="catalog",
        plugin_name="polaris",
        capabilities=CapabilitySet(
            catalog_providers=["iceberg-rest"],
            table_formats=["delta"],
        ),
    )
    ingestion = PluginRequirements(
        plugin_type="ingestion",
        plugin_name="dlt",
        requirements=RequirementSet(table_formats=["iceberg"]),
    )

    result = resolver.validate([storage, catalog], [ingestion])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_TABLE_FORMAT_UNSUPPORTED",
            message=(
                "ingestion dlt requires one of table formats ['iceberg']; "
                "catalog polaris provides ['delta']"
            ),
            plugins=["catalog:polaris", "ingestion:dlt"],
        )
    ]


def test_resolver_ingestion_protocol_error_names_ingestion_plugin() -> None:
    """Ingestion storage protocol diagnostics must identify ingestion as requester."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )
    ingestion = PluginRequirements(
        plugin_type="ingestion",
        plugin_name="dlt",
        requirements=RequirementSet(protocols=["s3"]),
    )

    result = resolver.validate([storage], [ingestion])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_PROTOCOL_UNSUPPORTED",
            message=(
                "ingestion dlt requires one of protocols ['s3']; "
                "storage minio provides ['s3-compatible']"
            ),
            plugins=["storage:minio", "ingestion:dlt"],
        )
    ]


def test_resolver_ingestion_credential_error_names_ingestion_plugin() -> None:
    """Ingestion storage credential diagnostics must identify ingestion as requester."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )
    ingestion = PluginRequirements(
        plugin_type="ingestion",
        plugin_name="dlt",
        requirements=RequirementSet(credential_modes=["workload-identity"]),
    )

    result = resolver.validate([storage], [ingestion])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
            message=(
                "ingestion dlt requires one of credential modes ['workload-identity']; "
                "storage minio provides ['kubernetes-secret']"
            ),
            plugins=["storage:minio", "ingestion:dlt"],
        )
    ]
