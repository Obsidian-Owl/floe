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
