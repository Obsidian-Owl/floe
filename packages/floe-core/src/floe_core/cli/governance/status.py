"""Governance status CLI command.

Task: T045
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

    Searches for manifest.yaml in the current directory and parents,
    parses it, and returns the GovernanceConfig section.

    Returns:
        GovernanceConfig from the current project manifest.

    Raises:
        FileNotFoundError: If no manifest.yaml is found.
    """
    from floe_core.schemas.manifest import GovernanceConfig

    # TODO: Implement manifest discovery (walk up from cwd to find manifest.yaml)
    # For now, return default empty config
    return GovernanceConfig(data_retention_days=None)


def load_last_enforcement_result() -> EnforcementResult | None:
    """Load the most recent enforcement result from cache.

    Looks for the last enforcement result stored in
    ``target/governance-result.json``.

    Returns:
        Last EnforcementResult, or None if no previous result exists.
    """
    # TODO: Load from target/governance-result.json when result caching is implemented
    return None


def _format_check_status(enabled: bool) -> str:
    """Format a boolean check status as enabled/disabled text.

    Args:
        enabled: Whether the check is enabled.

    Returns:
        Formatted status string.
    """
    return "enabled" if enabled else "disabled"


@click.command(name="status", help="Display governance check status and configuration.")
def status_command() -> None:
    """Display governance status including enabled checks and last result.

    Shows which governance checks are enabled (RBAC, secret scanning,
    network policies), the current enforcement level, and violation
    counts from the last audit run.
    """
    config = load_governance_config()
    last_result = load_last_enforcement_result()

    # Display enforcement level
    click.echo(f"Enforcement Level: {config.policy_enforcement_level}")
    click.echo("")

    # Display check statuses
    click.echo("Governance Checks:")

    rbac_enabled = config.rbac is not None and config.rbac.enabled
    click.echo(f"  RBAC: {_format_check_status(rbac_enabled)}")

    secret_enabled = config.secret_scanning is not None and config.secret_scanning.enabled
    click.echo(f"  Secret Scanning: {_format_check_status(secret_enabled)}")

    network_enabled = config.network_policies is not None and config.network_policies.enabled
    click.echo(f"  Network Policies: {_format_check_status(network_enabled)}")

    click.echo("")

    # Display last enforcement result
    if last_result is None:
        click.echo("Last Audit: No previous result available")
    else:
        total_violations = len(last_result.violations)
        status_text = "passed" if last_result.passed else "failed"
        click.echo(f"Last Audit: {status_text}")
        click.echo(f"  Total Violations: {total_violations}")
        click.echo(f"  Errors: {last_result.error_count}")
        click.echo(f"  Warnings: {last_result.warning_count}")
