"""Shared factory for GovernanceIntegrator construction in CLI commands.

Provides a single create_governance_integrator() used by audit, report,
and status commands.

Task: Architecture review remediation (M-01, M-02)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from floe_core.governance.integrator import GovernanceIntegrator


def create_governance_integrator(
    manifest_path: Path,
    spec_path: Path,
) -> GovernanceIntegrator:
    """Create GovernanceIntegrator from manifest and spec files.

    Loads the manifest YAML, extracts GovernanceConfig, and creates
    a GovernanceIntegrator. Reads FLOE_TOKEN from the environment
    for RBAC when an identity plugin is available.

    Args:
        manifest_path: Path to manifest.yaml
        spec_path: Path to floe.yaml spec

    Returns:
        Configured GovernanceIntegrator instance.
    """
    import yaml

    from floe_core.governance.integrator import GovernanceIntegrator
    from floe_core.schemas.manifest import GovernanceConfig

    manifest_data = yaml.safe_load(manifest_path.read_text())
    governance_data = manifest_data.get("governance", {})
    governance_config = GovernanceConfig(**governance_data)

    # M-02: Pass identity_plugin=None for now; RBAC token/principal
    # are passed via run_checks() from FLOE_TOKEN / FLOE_PRINCIPAL env vars.
    # When an IdentityPlugin entry-point is available, load it here.
    return GovernanceIntegrator(
        governance_config=governance_config,
        identity_plugin=None,
    )


def get_token_and_principal() -> tuple[str | None, str | None]:
    """Read RBAC token and principal from environment.

    Returns:
        Tuple of (token, principal) from FLOE_TOKEN and FLOE_PRINCIPAL env vars.
    """
    token = os.environ.get("FLOE_TOKEN")
    principal = os.environ.get("FLOE_PRINCIPAL")
    return token, principal
