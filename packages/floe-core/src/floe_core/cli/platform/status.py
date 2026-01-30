"""Platform status command implementation.

Task ID: T063
Phase: 6 - User Story 4 (Status)
User Story: US4 - Query Promotion Status
Requirements: FR-023, FR-024, FR-027

This module implements the `floe platform status` command which:
- Queries artifact promotion status across environments (FR-023)
- Shows environment-specific promotion state
- Displays promotion history with audit fields (FR-027)
- Supports table, JSON, and YAML output formats

Example:
    $ floe platform status v1.0.0 --registry=oci://harbor.example.com/floe
    $ floe platform status v1.0.0 --registry=oci://... --env=prod
    $ floe platform status v1.0.0 --registry=oci://... --history=5
    $ floe platform status v1.0.0 --registry=oci://... --format=json
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import click
import structlog

from floe_core.cli.utils import error, info, success

if TYPE_CHECKING:
    from floe_core.schemas.promotion import PromotionStatusResponse

logger = structlog.get_logger(__name__)


def _format_status_table(response: PromotionStatusResponse) -> str:
    """Format status response as human-readable table.

    Args:
        response: PromotionStatusResponse from get_status().

    Returns:
        Formatted string for display.
    """
    lines = [
        "",
        f"Artifact Status: {response.tag}",
        "=" * 50,
        f"Digest: {response.digest[:19]}...",
        f"Queried: {response.queried_at.isoformat()}",
        "",
        "Environments:",
    ]

    for env_name, env_state in sorted(response.environments.items()):
        status_icon = "✓" if env_state.promoted else "✗"
        latest_marker = " (latest)" if env_state.is_latest else ""

        if env_state.promoted:
            promoted_at = (
                env_state.promoted_at.isoformat()
                if env_state.promoted_at
                else "unknown"
            )
            operator = env_state.operator or "unknown"
            lines.append(
                f"  {status_icon} {env_name}: Promoted{latest_marker}"
            )
            lines.append(f"      at: {promoted_at}")
            lines.append(f"      by: {operator}")
        else:
            lines.append(f"  {status_icon} {env_name}: Not promoted")

    if response.history:
        lines.append("")
        lines.append("Promotion History:")
        for i, entry in enumerate(response.history, 1):
            promoted_at = (
                entry.promoted_at.isoformat()
                if hasattr(entry.promoted_at, "isoformat")
                else str(entry.promoted_at)
            )
            lines.append(
                f"  {i}. {entry.source_environment} → {entry.target_environment}"
            )
            lines.append(f"     at: {promoted_at}")
            lines.append(f"     by: {entry.operator}")

    lines.append("")
    return "\n".join(lines)


def _format_status_json(response: PromotionStatusResponse) -> str:
    """Format status response as JSON.

    Args:
        response: PromotionStatusResponse from get_status().

    Returns:
        JSON string.
    """
    return response.model_dump_json(indent=2)


def _format_status_yaml(response: PromotionStatusResponse) -> str:
    """Format status response as YAML.

    Args:
        response: PromotionStatusResponse from get_status().

    Returns:
        YAML string.
    """
    import yaml

    data = response.model_dump(mode="json")
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)


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
    name="status",
    help="Query artifact promotion status across environments (FR-023).",
    epilog="""
Examples:
    $ floe platform status v1.0.0 --registry=oci://harbor.example.com/floe
    $ floe platform status v1.0.0 --registry=oci://... --env=prod
    $ floe platform status v1.0.0 --registry=oci://... --history=5
    $ floe platform status v1.0.0 --registry=oci://... --format=json

Exit Codes:
    0  - Success
    3  - Artifact not found
    5  - Registry unavailable / circuit breaker open
""",
)
@click.argument("tag")
@click.option(
    "--registry",
    required=True,
    help="OCI registry URI (e.g., 'oci://harbor.example.com/floe').",
    metavar="URI",
)
@click.option(
    "--env",
    "environment",
    default=None,
    help="Filter to single environment (e.g., 'prod').",
    metavar="ENV",
)
@click.option(
    "--history",
    type=int,
    default=None,
    help="Limit promotion history entries (e.g., --history=5).",
    metavar="N",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "yaml"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
def status_command(
    tag: str,
    registry: str,
    environment: str | None,
    history: int | None,
    output_format: str,
) -> None:
    """Query artifact promotion status across environments.

    Shows which environments an artifact is promoted to, when promotions
    occurred, and promotion history with audit trail information.

    \\b
    TAG: Artifact tag to query (e.g., "v1.0.0").

    Args:
        tag: Artifact tag to query status for.
        registry: OCI registry URI.
        environment: Optional environment filter.
        history: Optional limit on history entries.
        output_format: Output format (table, json, yaml).
    """
    from floe_core.oci.client import OCIClient
    from floe_core.oci.errors import (
        ArtifactNotFoundError,
        CircuitBreakerOpenError,
        RegistryUnavailableError,
    )
    from floe_core.oci.promotion import PromotionController
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
    from floe_core.schemas.promotion import PromotionConfig

    # Log start (to stderr, not captured by JSON/YAML output)
    if output_format == "table":
        info(f"Querying status for {tag}")

    try:
        # Create OCI client
        registry_config = RegistryConfig(
            uri=registry,
            auth=RegistryAuth(type=AuthType.ANONYMOUS),
        )
        oci_client = OCIClient.from_registry_config(registry_config)

        # Create promotion controller with default config
        promotion_config = PromotionConfig()
        controller = PromotionController(
            client=oci_client,
            promotion=promotion_config,
        )

        # Query status
        response = controller.get_status(
            tag=tag,
            env=environment,
            history=history,
        )

        # Format output based on requested format
        if output_format == "json":
            formatted = _format_status_json(response)
        elif output_format == "yaml":
            formatted = _format_status_yaml(response)
        else:  # table
            formatted = _format_status_table(response)

        click.echo(formatted)

        if output_format == "table":
            success(f"Status query complete for {tag}")

        sys.exit(0)

    except ArtifactNotFoundError as e:
        if output_format == "json":
            click.echo(
                json.dumps(
                    {
                        "error": str(e),
                        "tag": e.tag,
                        "registry": e.registry,
                        "exit_code": e.exit_code,
                    }
                )
            )
        elif output_format == "yaml":
            import yaml

            click.echo(
                yaml.safe_dump(
                    {
                        "error": str(e),
                        "tag": e.tag,
                        "registry": e.registry,
                        "exit_code": e.exit_code,
                    }
                )
            )
        else:
            error(f"Artifact not found: {e}")
        sys.exit(e.exit_code)

    except (RegistryUnavailableError, CircuitBreakerOpenError) as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": e.exit_code}))
        elif output_format == "yaml":
            import yaml

            click.echo(yaml.safe_dump({"error": str(e), "exit_code": e.exit_code}))
        else:
            error(f"Registry unavailable: {e}")
        sys.exit(e.exit_code)

    except Exception as e:
        # Catch-all for unexpected errors
        exit_code = _get_exit_code_from_exception(e)
        logger.error(
            "status_command_failed",
            error_type=type(e).__name__,
            error_summary=str(e)[:200] if str(e) else "Unknown error",
        )
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": exit_code}))
        elif output_format == "yaml":
            import yaml

            click.echo(yaml.safe_dump({"error": str(e), "exit_code": exit_code}))
        else:
            error(f"Status query failed: {e}")
        sys.exit(exit_code)


__all__: list[str] = ["status_command"]
