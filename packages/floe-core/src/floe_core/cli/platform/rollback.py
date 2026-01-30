"""Platform rollback command implementation.

Task ID: T053
Phase: 3 - User Story 3 (Rollback)
User Story: US3 - Rollback to Previous Version
Requirements: FR-013 through FR-017

This module implements the `floe platform rollback` command which:
- Rolls back an environment to a previously promoted version (FR-013)
- Creates rollback-specific tags with pattern v{X.Y.Z}-{env}-rollback-{N} (FR-014)
- Updates the mutable latest-{env} tag (FR-015)
- Provides impact analysis before rollback (FR-016)
- Records rollback in audit trail (FR-017)

Example:
    $ floe platform rollback v1.0.0 --env=prod --reason="Performance regression"
    $ floe platform rollback v1.0.0 --env=prod --analyze  # Impact analysis only
    $ floe platform rollback v1.0.0 --env=prod --reason="Bug" --output=json
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import click
import structlog

from floe_core.cli.utils import error, info, success, warn

if TYPE_CHECKING:
    from floe_core.schemas.promotion import RollbackImpactAnalysis, RollbackRecord

logger = structlog.get_logger(__name__)


def _format_rollback_result(record: RollbackRecord, output_format: str) -> str:
    """Format rollback result for CLI output.

    Args:
        record: RollbackRecord from successful rollback.
        output_format: Output format ("table" or "json").

    Returns:
        Formatted string for display.
    """
    if output_format == "json":
        return record.model_dump_json(indent=2)

    # Table format (human-readable)
    lines = [
        "",
        f"Rollback ID:      {record.rollback_id}",
        f"Environment:      {record.environment}",
        f"Target Digest:    {record.artifact_digest[:19]}...",
        f"Previous Digest:  {record.previous_digest[:19]}...",
        f"Reason:           {record.reason}",
        f"Operator:         {record.operator}",
        f"Rolled Back At:   {record.rolled_back_at.isoformat()}",
        f"Trace ID:         {record.trace_id}",
        "",
    ]

    return "\n".join(lines)


def _format_impact_analysis(
    analysis: RollbackImpactAnalysis, output_format: str
) -> str:
    """Format impact analysis for CLI output.

    Args:
        analysis: RollbackImpactAnalysis from analyze_rollback_impact.
        output_format: Output format ("table" or "json").

    Returns:
        Formatted string for display.
    """
    if output_format == "json":
        return analysis.model_dump_json(indent=2)

    # Table format (human-readable)
    lines = [
        "",
        "Rollback Impact Analysis",
        "=" * 40,
        "",
    ]

    if analysis.breaking_changes:
        lines.append("Breaking Changes:")
        for change in analysis.breaking_changes:
            lines.append(f"  ⚠ {change}")
        lines.append("")
    else:
        lines.append("Breaking Changes: None detected")
        lines.append("")

    if analysis.affected_products:
        lines.append("Affected Products:")
        for product in analysis.affected_products:
            lines.append(f"  • {product}")
        lines.append("")
    else:
        lines.append("Affected Products: None detected")
        lines.append("")

    if analysis.recommendations:
        lines.append("Recommendations:")
        for rec in analysis.recommendations:
            lines.append(f"  → {rec}")
        lines.append("")

    if hasattr(analysis, "estimated_downtime") and analysis.estimated_downtime:
        lines.append(f"Estimated Downtime: {analysis.estimated_downtime}")
        lines.append("")

    return "\n".join(lines)


def _get_exit_code_from_exception(exc: Exception) -> int:
    """Get CLI exit code from exception type.

    Maps exception types to their defined exit codes.

    Args:
        exc: Exception that was raised.

    Returns:
        Exit code for CLI.
    """
    # Check if exception has exit_code attribute (our custom exceptions)
    if hasattr(exc, "exit_code"):
        return exc.exit_code

    # Fallback mapping for standard exceptions
    exc_type = type(exc).__name__
    exit_code_map = {
        "FileNotFoundError": 3,
        "PermissionError": 4,
        "ConnectionError": 5,
        "TimeoutError": 5,
    }
    return exit_code_map.get(exc_type, 1)


@click.command(
    name="rollback",
    help="Rollback an environment to a previous artifact version (FR-013).",
    epilog="""
Examples:
    $ floe platform rollback v1.0.0 --env=prod --reason="Performance regression"
    $ floe platform rollback v1.0.0 --env=prod --analyze
    $ floe platform rollback v1.0.0 --env=prod --reason="Bug" --output=json

Exit Codes:
    0  - Success
    5  - Registry unavailable / circuit breaker open
    11 - Version not promoted to environment
    12 - Operator not authorized
    13 - Environment locked
""",
)
@click.argument("tag")
@click.option(
    "--env",
    "environment",
    required=True,
    help="Environment to rollback (e.g., 'staging', 'prod').",
    metavar="ENV",
)
@click.option(
    "--reason",
    "-r",
    default=None,
    help="Reason for rollback (required unless --analyze).",
    metavar="TEXT",
)
@click.option(
    "--registry",
    help="OCI registry URI (e.g., 'oci://harbor.example.com/floe').",
    metavar="URI",
)
@click.option(
    "--operator",
    "-o",
    default=None,
    help="Operator identity. Defaults to $USER or 'unknown'.",
    metavar="IDENTITY",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--analyze",
    is_flag=True,
    default=False,
    help="Only show impact analysis, do not execute rollback (FR-016).",
)
def rollback_command(
    tag: str,
    environment: str,
    reason: str | None,
    registry: str | None,
    operator: str | None,
    output: str,
    analyze: bool,
) -> None:
    """Rollback an environment to a previous artifact version.

    Verifies the version was previously promoted to the environment,
    creates a rollback-specific tag, updates the latest tag, and records
    the rollback in the audit trail.

    \b
    TAG: Artifact tag to rollback to (e.g., "v1.0.0").

    Args:
        tag: Artifact tag to rollback to.
        environment: Environment to rollback.
        reason: Reason for rollback (required unless --analyze).
        registry: OCI registry URI override.
        operator: Operator identity for audit trail.
        output: Output format (table or json).
        analyze: If True, only show impact analysis.
    """
    import os

    from floe_core.oci.client import OCIClient
    from floe_core.oci.errors import (
        AuthorizationError,
        CircuitBreakerOpenError,
        EnvironmentLockedError,
        RegistryUnavailableError,
        VersionNotPromotedError,
    )
    from floe_core.oci.promotion import PromotionController, validate_tag_security
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
    from floe_core.schemas.promotion import PromotionConfig

    # Security: Validate tag format early to prevent command injection
    try:
        validate_tag_security(tag)
    except ValueError as e:
        error(f"Invalid tag: {e}")
        sys.exit(2)

    # Validate reason is provided unless analyze mode
    if not analyze and not reason:
        error("--reason is required unless using --analyze")
        sys.exit(2)

    # Determine operator identity
    effective_operator = operator or os.environ.get("USER", "unknown")

    # Log start (to stderr, not captured by JSON output)
    if output == "table":
        if analyze:
            info(f"Analyzing rollback impact for {tag} in {environment}")
        else:
            info(f"Rolling back {environment} to {tag}")

    try:
        # Create OCI client
        if registry is not None:
            registry_config = RegistryConfig(
                uri=registry,
                auth=RegistryAuth(type=AuthType.ANONYMOUS),
            )
        else:
            error("Missing --registry option. Provide OCI registry URI.")
            sys.exit(2)

        oci_client = OCIClient.from_registry_config(registry_config)

        # Create promotion controller with default config
        promotion_config = PromotionConfig()
        controller = PromotionController(
            client=oci_client,
            promotion=promotion_config,
        )

        if analyze:
            # Impact analysis only (FR-016)
            analysis = controller.analyze_rollback_impact(
                tag=tag,
                environment=environment,
            )

            formatted = _format_impact_analysis(analysis, output)
            click.echo(formatted)

            if output == "table":
                success("Impact analysis complete")

            sys.exit(0)

        # Execute rollback (FR-013)
        record = controller.rollback(
            tag=tag,
            environment=environment,
            reason=reason or "",  # Already validated above
            operator=effective_operator,
        )

        # Format and output result
        formatted = _format_rollback_result(record, output)
        click.echo(formatted)

        if output == "table":
            success(f"Successfully rolled back {environment} to {tag}")

        sys.exit(0)

    except VersionNotPromotedError as e:
        if output == "json":
            click.echo(
                json.dumps(
                    {
                        "error": str(e),
                        "tag": e.tag,
                        "environment": e.environment,
                        "exit_code": e.exit_code,
                    }
                )
            )
        else:
            error(f"Version not promoted: {e}")
            warn(f"Tag '{e.tag}' was never promoted to '{e.environment}'")
        sys.exit(e.exit_code)

    except AuthorizationError as e:
        if output == "json":
            click.echo(
                json.dumps(
                    {
                        "error": str(e),
                        "operator": e.operator,
                        "required_groups": e.required_groups,
                        "reason": e.reason,
                        "exit_code": e.exit_code,
                    }
                )
            )
        else:
            error(f"Authorization failed: {e}")
        sys.exit(e.exit_code)

    except EnvironmentLockedError as e:
        if output == "json":
            click.echo(
                json.dumps(
                    {
                        "error": str(e),
                        "environment": e.environment,
                        "exit_code": e.exit_code,
                    }
                )
            )
        else:
            error(f"Environment locked: {e}")
        sys.exit(e.exit_code)

    except (RegistryUnavailableError, CircuitBreakerOpenError) as e:
        if output == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": e.exit_code}))
        else:
            error(f"Registry unavailable: {e}")
        sys.exit(e.exit_code)

    except Exception as e:
        # Catch-all for unexpected errors
        exit_code = _get_exit_code_from_exception(e)
        logger.error(
            "rollback_command_failed",
            error_type=type(e).__name__,
            error_summary=str(e)[:200] if str(e) else "Unknown error",
        )
        if output == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": exit_code}))
        else:
            error(f"Rollback failed: {e}")
        sys.exit(exit_code)


__all__: list[str] = ["rollback_command"]
