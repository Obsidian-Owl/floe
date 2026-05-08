"""Contract tests for plugin composition capability models."""

from __future__ import annotations

import pytest
from floe_core.composition.models import CapabilitySet, RequirementSet


@pytest.mark.requirement("AC-4")
def test_capability_set_exposes_security_composition_fields() -> None:
    """CapabilitySet is a public plugin contract for security composition."""
    capabilities = CapabilitySet(
        protocols=["s3-compatible"],
        credential_modes=["kubernetes-secret", "workload-identity"],
        secret_projection_modes=["kubernetes-secret"],
        identity_modes=["oidc-federation"],
        providers=["kubernetes"],
        path_style_access=True,
        sts=False,
    )

    assert capabilities.protocols == ["s3-compatible"]
    assert capabilities.credential_modes == ["kubernetes-secret", "workload-identity"]
    assert capabilities.secret_projection_modes == ["kubernetes-secret"]
    assert capabilities.identity_modes == ["oidc-federation"]
    assert capabilities.providers == ["kubernetes"]
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
    assert requirements.requires_server_side_storage_access is True
    assert requirements.supports_no_sts is True
    assert requirements.supports_path_style_access is True
