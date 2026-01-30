"""Platform promote command implementation.

Task ID: T033, T034, T035, T036
Phase: 3 - User Story 1 (Core Promote)
User Story: US1 - Promote Artifact to Next Environment
Requirements: FR-001 through FR-005

This module implements the `floe platform promote` command which:
- Promotes artifacts from one environment to the next
- Validates transition path and gates
- Verifies signatures (if configured)
- Creates environment-specific tags
- Records audit trail

Example:
    $ floe platform promote v1.2.3 --from=dev --to=staging
    $ floe platform promote v1.2.3 --from=staging --to=prod --dry-run
    $ floe platform promote v1.2.3 --from=dev --to=staging --output=json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import structlog

from floe_core.cli.utils import error, info, success, warn

if TYPE_CHECKING:
    from floe_core.schemas.promotion import PromotionRecord

logger = structlog.get_logger(__name__)


def _format_promotion_result(record: PromotionRecord, output_format: str) -> str:
    """Format promotion result for CLI output.

    Args:
        record: PromotionRecord from successful promotion.
        output_format: Output format ("table" or "json").

    Returns:
        Formatted string for display.
    """
    if output_format == "json":
        return record.model_dump_json(indent=2)

    # Table format (human-readable)
    lines = [
        "",
        f"Promotion ID: {record.promotion_id}",
        f"Artifact:     {record.artifact_tag}",
        f"Digest:       {record.artifact_digest[:19]}...",
        f"From:         {record.source_environment}",
        f"To:           {record.target_environment}",
        f"Operator:     {record.operator}",
        f"Promoted At:  {record.promoted_at.isoformat()}",
        f"Dry Run:      {record.dry_run}",
        f"Trace ID:     {record.trace_id}",
        "",
        "Gate Results:",
    ]

    for gate_result in record.gate_results:
        status_icon = "✓" if gate_result.status.value == "passed" else "✗"
        lines.append(f"  {status_icon} {gate_result.gate.value}: {gate_result.status.value}")
        if gate_result.error:
            lines.append(f"      Error: {gate_result.error}")

    lines.append("")
    sig_status = "verified" if record.signature_verified else "not verified"
    lines.append(f"Signature:    {sig_status}")

    if record.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in record.warnings:
            lines.append(f"  ⚠ {warning}")

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
        return int(exc.exit_code)

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
    name="promote",
    help="Promote an artifact from one environment to the next (FR-001).",
    epilog="""
Examples:
    $ floe platform promote v1.2.3 --from=dev --to=staging
    $ floe platform promote v1.2.3 --from=staging --to=prod --dry-run
    $ floe platform promote v1.2.3 --from=dev --to=staging --output=json
    $ floe platform promote v1.2.3 --from=dev --to=staging --manifest=manifest.yaml

Exit Codes:
    0  - Success
    5  - Registry unavailable / circuit breaker open
    6  - Signature verification failed
    8  - Gate validation failed
    9  - Invalid transition (bad environment path)
    10 - Tag already exists with different digest
""",
)
@click.argument("tag")
@click.option(
    "--from",
    "from_env",
    required=True,
    help="Source environment name (e.g., 'dev', 'staging').",
    metavar="ENV",
)
@click.option(
    "--to",
    "to_env",
    required=True,
    help="Target environment name (e.g., 'staging', 'prod').",
    metavar="ENV",
)
@click.option(
    "--manifest",
    "-m",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    help="Path to manifest.yaml with promotion configuration.",
    metavar="PATH",
)
@click.option(
    "--registry",
    "-r",
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
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate without making changes. Shows what would happen.",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force promotion even if tag exists with matching digest (idempotent retry).",
)
def promote_command(
    tag: str,
    from_env: str,
    to_env: str,
    manifest: Path | None,
    registry: str | None,
    operator: str | None,
    dry_run: bool,
    output: str,
    force: bool,
) -> None:
    """Promote an artifact from one environment to the next.

    Validates gates, verifies signatures (if configured), creates environment
    tags, and records the promotion in the audit trail.

    \b
    TAG: Artifact tag to promote (e.g., "v1.2.3").

    Args:
        tag: Artifact tag to promote.
        from_env: Source environment name.
        to_env: Target environment name.
        manifest: Path to manifest.yaml with promotion configuration.
        registry: OCI registry URI override.
        operator: Operator identity for audit trail.
        dry_run: If True, validate without making changes.
        output: Output format (table or json).
        force: If True, allow idempotent retry when digest matches.
    """
    import os

    from floe_core.oci.client import OCIClient
    from floe_core.oci.errors import (
        CircuitBreakerOpenError,
        GateValidationError,
        InvalidTransitionError,
        RegistryUnavailableError,
        SignatureVerificationError,
        TagExistsError,
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

    # Determine operator identity
    effective_operator = operator or os.environ.get("USER", "unknown")

    # Log start (to stderr, not captured by JSON output)
    if output == "table":
        info(f"Promoting {tag} from {from_env} to {to_env}")
        if dry_run:
            info("DRY RUN - No changes will be made")

    try:
        # Load promotion configuration
        if manifest is not None:
            # TODO: T045+ - Load PromotionConfig from manifest.yaml
            info(f"Loading promotion config from: {manifest}")
            promotion_config = PromotionConfig()  # Default for now
        else:
            promotion_config = PromotionConfig()  # Default [dev, staging, prod]

        # Create OCI client
        if registry is not None:
            registry_config = RegistryConfig(
                uri=registry,
                auth=RegistryAuth(type=AuthType.ANONYMOUS),
            )
        else:
            # TODO: T046+ - Load registry from manifest or environment
            error("Missing --registry option. Provide OCI registry URI.")
            sys.exit(2)

        oci_client = OCIClient.from_registry_config(registry_config)

        # Create promotion controller
        controller = PromotionController(
            client=oci_client,
            promotion=promotion_config,
        )

        # Execute promotion
        record = controller.promote(
            tag=tag,
            from_env=from_env,
            to_env=to_env,
            operator=effective_operator,
            dry_run=dry_run,
        )

        # Format and output result
        formatted = _format_promotion_result(record, output)

        if output == "json":
            # JSON goes to stdout (machine-readable)
            click.echo(formatted)
        else:
            # Table format - success message
            click.echo(formatted)

            # Display signature verification status (T074 - FR-021)
            if record.signature_verified:
                success("✓ Signature verified")
            else:
                warn("WARNING: Artifact is unsigned or signature not verified")

            if dry_run:
                success("Dry run complete. No changes were made.")
            else:
                success(f"Successfully promoted {tag} to {to_env}")

        # Warn about any issues
        for warning in record.warnings:
            warn(warning)

        sys.exit(0)

    except InvalidTransitionError as e:
        if output == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": e.exit_code}))
        else:
            error(f"Invalid transition: {e}")
        sys.exit(e.exit_code)

    except GateValidationError as e:
        if output == "json":
            click.echo(
                json.dumps(
                    {"error": str(e), "gate": e.gate, "exit_code": e.exit_code}
                )
            )
        else:
            error(f"Gate validation failed: {e}")
        sys.exit(e.exit_code)

    except SignatureVerificationError as e:
        if output == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": e.exit_code}))
        else:
            error(f"Signature verification failed: {e}")
        sys.exit(e.exit_code)

    except TagExistsError as e:
        if output == "json":
            click.echo(
                json.dumps(
                    {
                        "error": str(e),
                        "tag": e.tag,
                        "existing_digest": e.existing_digest,
                        "exit_code": e.exit_code,
                    }
                )
            )
        else:
            error(f"Tag already exists: {e}")
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
            "promote_command_failed",
            error_type=type(e).__name__,
            error_summary=str(e)[:200] if str(e) else "Unknown error",
        )
        if output == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": exit_code}))
        else:
            error(f"Promotion failed: {e}")
        sys.exit(exit_code)


__all__: list[str] = ["promote_command"]
