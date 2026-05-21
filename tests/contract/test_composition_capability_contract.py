"""Contract tests for plugin composition capability models."""

from __future__ import annotations

import pytest
from floe_core.composition.models import (
    CapabilitySet,
    PluginCapabilities,
    PluginRequirements,
    RequirementSet,
)
from floe_core.composition.resolver import CompositionResolver


@pytest.mark.requirement("AC-4")
def test_capability_set_exposes_security_composition_fields() -> None:
    """CapabilitySet is a public plugin contract for security composition."""
    capabilities = CapabilitySet(
        protocols=["s3-compatible"],
        credential_modes=["kubernetes-secret", "workload-identity"],
        secret_projection_modes=["kubernetes-secret"],
        identity_modes=["oidc-federation"],
        providers=["kubernetes"],
        semantic_api_families=["metadata"],
        semantic_datasource_engines=["duckdb"],
        semantic_artifact_transports=["filesystem"],
        path_style_access=True,
        sts=False,
    )

    assert capabilities.protocols == ["s3-compatible"]
    assert capabilities.credential_modes == ["kubernetes-secret", "workload-identity"]
    assert capabilities.secret_projection_modes == ["kubernetes-secret"]
    assert capabilities.identity_modes == ["oidc-federation"]
    assert capabilities.providers == ["kubernetes"]
    assert capabilities.semantic_api_families == ["metadata"]
    assert capabilities.semantic_datasource_engines == ["duckdb"]
    assert capabilities.semantic_artifact_transports == ["filesystem"]
    assert capabilities.path_style_access is True
    assert capabilities.sts is False


@pytest.mark.requirement("AC-4")
def test_requirement_set_exposes_security_composition_fields() -> None:
    """RequirementSet is a public plugin contract for security composition."""
    requirements = RequirementSet(
        protocols=["s3-compatible"],
        credential_modes=["kubernetes-secret"],
        secret_projection_modes=["kubernetes-secret", "external-secret-sync"],
        identity_modes=["aws-irsa"],
        providers=["infisical"],
        semantic_api_families=["metadata"],
        semantic_datasource_engines=["duckdb"],
        semantic_artifact_transports=["filesystem"],
        requires_server_side_storage_access=True,
        supports_no_sts=True,
        supports_path_style_access=True,
    )

    assert requirements.protocols == ["s3-compatible"]
    assert requirements.credential_modes == ["kubernetes-secret"]
    assert requirements.secret_projection_modes == [
        "kubernetes-secret",
        "external-secret-sync",
    ]
    assert requirements.identity_modes == ["aws-irsa"]
    assert requirements.providers == ["infisical"]
    assert requirements.semantic_api_families == ["metadata"]
    assert requirements.semantic_datasource_engines == ["duckdb"]
    assert requirements.semantic_artifact_transports == ["filesystem"]
    assert requirements.requires_server_side_storage_access is True
    assert requirements.supports_no_sts is True
    assert requirements.supports_path_style_access is True


@pytest.mark.requirement("semantic-composition")
def test_semantic_requirements_pass_when_storage_and_catalog_are_compatible() -> None:
    """Semantic requirements are satisfied by compatible storage and catalog peers."""
    resolver = CompositionResolver()

    result = resolver.validate(
        capabilities=[
            PluginCapabilities(
                plugin_type="storage",
                plugin_name="object-store",
                capabilities=CapabilitySet(protocols=["s3-compatible"]),
            ),
            PluginCapabilities(
                plugin_type="catalog",
                plugin_name="metadata-catalog",
                capabilities=CapabilitySet(
                    catalog_providers=["iceberg-rest"],
                    table_formats=["iceberg"],
                ),
            ),
        ],
        requirements=[
            PluginRequirements(
                plugin_type="semantic",
                plugin_name="cube",
                requirements=RequirementSet(
                    protocols=["s3-compatible"],
                    catalog_providers=["iceberg-rest"],
                    table_formats=["iceberg"],
                    semantic_api_families=["metadata", "query", "sql_http"],
                    semantic_datasource_engines=["duckdb"],
                ),
            )
        ],
    )

    assert result.valid is True
    assert result.issues == []


@pytest.mark.requirement("semantic-composition")
def test_semantic_requirements_fail_when_catalog_table_format_is_incompatible() -> None:
    """Semantic requirements report incompatible catalog table formats."""
    resolver = CompositionResolver()

    result = resolver.validate(
        capabilities=[
            PluginCapabilities(
                plugin_type="storage",
                plugin_name="object-store",
                capabilities=CapabilitySet(protocols=["s3-compatible"]),
            ),
            PluginCapabilities(
                plugin_type="catalog",
                plugin_name="metadata-catalog",
                capabilities=CapabilitySet(
                    catalog_providers=["iceberg-rest"],
                    table_formats=["delta"],
                ),
            ),
        ],
        requirements=[
            PluginRequirements(
                plugin_type="semantic",
                plugin_name="cube",
                requirements=RequirementSet(
                    protocols=["s3-compatible"],
                    catalog_providers=["iceberg-rest"],
                    table_formats=["iceberg"],
                    semantic_api_families=["metadata", "query", "sql_http"],
                    semantic_datasource_engines=["duckdb"],
                ),
            )
        ],
    )

    assert result.valid is False
    assert [issue.code for issue in result.issues] == [
        "COMPOSITION_SEMANTIC_TABLE_FORMAT_UNSUPPORTED"
    ]


@pytest.mark.requirement("semantic-composition")
@pytest.mark.parametrize(
    ("capabilities", "expected_code"),
    [
        (
            [],
            "COMPOSITION_SEMANTIC_STORAGE_MISSING",
        ),
        (
            [
                PluginCapabilities(
                    plugin_type="storage",
                    plugin_name="object-store",
                    capabilities=CapabilitySet(protocols=["s3-compatible"]),
                )
            ],
            "COMPOSITION_SEMANTIC_CATALOG_MISSING",
        ),
        (
            [
                PluginCapabilities(
                    plugin_type="storage",
                    plugin_name="object-store",
                    capabilities=CapabilitySet(protocols=["abfs"]),
                ),
                PluginCapabilities(
                    plugin_type="catalog",
                    plugin_name="metadata-catalog",
                    capabilities=CapabilitySet(
                        catalog_providers=["iceberg-rest"],
                        table_formats=["iceberg"],
                    ),
                ),
            ],
            "COMPOSITION_SEMANTIC_PROTOCOL_UNSUPPORTED",
        ),
        (
            [
                PluginCapabilities(
                    plugin_type="storage",
                    plugin_name="object-store",
                    capabilities=CapabilitySet(protocols=["s3-compatible"]),
                ),
                PluginCapabilities(
                    plugin_type="catalog",
                    plugin_name="metadata-catalog",
                    capabilities=CapabilitySet(
                        catalog_providers=["glue"],
                        table_formats=["iceberg"],
                    ),
                ),
            ],
            "COMPOSITION_SEMANTIC_CATALOG_UNSUPPORTED",
        ),
    ],
)
def test_semantic_requirements_report_peer_compatibility_failures(
    capabilities: list[PluginCapabilities],
    expected_code: str,
) -> None:
    """Semantic requirements report storage, catalog, and protocol failures."""
    resolver = CompositionResolver()

    result = resolver.validate(
        capabilities=capabilities,
        requirements=[
            PluginRequirements(
                plugin_type="semantic",
                plugin_name="cube",
                requirements=RequirementSet(
                    protocols=["s3-compatible"],
                    catalog_providers=["iceberg-rest"],
                    table_formats=["iceberg"],
                    semantic_api_families=["metadata", "query", "sql_http"],
                    semantic_datasource_engines=["duckdb"],
                ),
            )
        ],
    )

    assert result.valid is False
    assert expected_code in [issue.code for issue in result.issues]
