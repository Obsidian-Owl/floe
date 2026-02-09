"""Governance status CLI command.

Task: T044 (stub), T045 (implementation)
Requirements: FR-024

Displays current governance configuration status and last enforcement results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from floe_core.enforcement.result import EnforcementResult
    from floe_core.schemas.manifest import GovernanceConfig


def load_governance_config() -> GovernanceConfig:
    """Load governance configuration from the project manifest.

    Returns:
        GovernanceConfig from the current project manifest.

    Raises:
        NotImplementedError: Stub — implemented in T045.
    """
    raise NotImplementedError("T045: Implement load_governance_config")


def load_last_enforcement_result() -> EnforcementResult | None:
    """Load the most recent enforcement result from cache.

    Returns:
        Last EnforcementResult, or None if no previous result exists.

    Raises:
        NotImplementedError: Stub — implemented in T045.
    """
    raise NotImplementedError("T045: Implement load_last_enforcement_result")


@click.command(name="status", help="Display governance check status and configuration.")
def status_command() -> None:
    """Display governance status including enabled checks and last result.

    Shows which governance checks are enabled (RBAC, secret scanning,
    network policies), the current enforcement level, and violation
    counts from the last audit run.

    Raises:
        NotImplementedError: Stub — implemented in T045.
    """
    raise NotImplementedError("T045: Implement status command")
