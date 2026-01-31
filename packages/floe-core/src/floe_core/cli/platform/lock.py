"""Platform lock/unlock command implementation.

Task ID: T105, T106
Phase: 10 - User Story 8 (Environment Lock)
User Story: US8 - Environment Lock/Freeze
Requirements: FR-035, FR-037

This module implements the `floe platform lock` and `floe platform unlock` commands:
- Lock an environment to prevent promotions
- Unlock an environment to allow promotions
- Display lock status

Example:
    $ floe platform lock --env=prod --reason="Incident #123"
    $ floe platform unlock --env=prod --reason="Incident resolved"
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import structlog
import yaml

from floe_core.cli.utils import error, info, success

if TYPE_CHECKING:
    from floe_core.schemas.manifest import PlatformManifest

logger = structlog.get_logger(__name__)


def _get_operator() -> str:
    """Get operator identity from environment or default.

    Returns:
        Operator identity string.
    """
    return os.environ.get("USER") or os.environ.get("FLOE_OPERATOR") or "unknown"


def _load_platform_manifest(path: Path) -> PlatformManifest:
    """Load PlatformManifest from YAML file.

    Args:
        path: Path to manifest.yaml file.

    Returns:
        Parsed PlatformManifest object.

    Raises:
        click.ClickException: If file cannot be loaded or parsed.
    """
    from floe_core.schemas.manifest import PlatformManifest

    try:
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f)
        return PlatformManifest.model_validate(data)
    except yaml.YAMLError as e:
        raise click.ClickException(f"Failed to parse YAML: {e}") from e
    except Exception as e:
        raise click.ClickException(f"Failed to load manifest: {e}") from e


@click.command(
    name="lock",
    help="Lock an environment to prevent promotions (FR-035).",
    epilog="""
Examples:
    $ floe platform lock --env=prod --reason="Incident #123"
    $ floe platform lock --env=staging --reason="Maintenance window"
    $ floe platform lock --env=prod --reason="DB migration" --operator=dba@example.com

Exit Codes:
    0  - Success
    1  - General error
    3  - Configuration error (manifest not found)
    5  - Registry unavailable
""",
)
@click.option(
    "--env",
    "-e",
    required=True,
    help="Environment to lock (e.g., 'staging', 'prod').",
    metavar="ENV",
)
@click.option(
    "--reason",
    "-r",
    required=True,
    help="Reason for locking the environment.",
    metavar="REASON",
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
    type=str,
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
def lock_command(
    env: str,
    reason: str,
    manifest: Path | None,
    registry: str | None,
    operator: str | None,
    output: str,
) -> None:
    """Lock an environment to prevent promotions.

    This command locks the specified environment, preventing any promotions
    to it until it is explicitly unlocked.

    Args:
        env: Environment to lock.
        reason: Reason for locking.
        manifest: Path to manifest.yaml.
        registry: OCI registry URI.
        operator: Operator identity.
        output: Output format (table or json).
    """
    from floe_core.oci.client import OCIClient
    from floe_core.oci.promotion import PromotionController
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig

    # Resolve operator
    resolved_operator = operator or _get_operator()

    logger.info(
        "lock_command_started",
        environment=env,
        reason=reason,
        operator=resolved_operator,
    )

    try:
        # Load manifest or use registry directly
        if manifest:
            manifest_config = _load_platform_manifest(manifest)
            if manifest_config.artifacts is None:
                error("Manifest does not contain 'artifacts' configuration")
                sys.exit(3)
            registry_config = manifest_config.artifacts.registry
            promotion_config = manifest_config.artifacts.promotion
        elif registry:
            registry_config = RegistryConfig(
                uri=registry,
                auth=RegistryAuth(type=AuthType.ANONYMOUS),
            )
            # Minimal promotion config - controller will validate environment
            from floe_core.schemas.promotion import (
                EnvironmentConfig,
                PromotionConfig,
                PromotionGate,
            )

            promotion_config = PromotionConfig(
                environments=[
                    EnvironmentConfig(
                        name=env,
                        gates={PromotionGate.POLICY_COMPLIANCE: True},
                    ),
                ],
            )
        else:
            error("Either --manifest or --registry is required")
            sys.exit(3)

        # Validate promotion config exists
        if promotion_config is None:
            error("Manifest does not contain promotion configuration")
            sys.exit(3)

        # Create client and controller
        client = OCIClient.from_registry_config(registry_config)
        controller = PromotionController(
            client=client,
            promotion=promotion_config,
        )

        # Lock the environment
        controller.lock_environment(
            environment=env,
            reason=reason,
            operator=resolved_operator,
        )

        # Get lock status for output
        lock_status = controller.get_lock_status(env)

        # Format output
        if output == "json":
            result = {
                "status": "locked",
                "environment": env,
                "reason": lock_status.reason,
                "locked_by": lock_status.locked_by,
                "locked_at": (lock_status.locked_at.isoformat() if lock_status.locked_at else None),
            }
            click.echo(json.dumps(result, indent=2))
        else:
            success(f"Environment '{env}' locked successfully")
            info(f"  Reason:    {lock_status.reason}")
            info(f"  Locked by: {lock_status.locked_by}")
            if lock_status.locked_at:
                info(f"  Locked at: {lock_status.locked_at.isoformat()}")

        sys.exit(0)

    except ValueError as e:
        error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception("lock_command_failed", error=str(e))
        error(f"Failed to lock environment: {e}")
        exit_code = getattr(e, "exit_code", 1)
        sys.exit(exit_code)


@click.command(
    name="unlock",
    help="Unlock an environment to allow promotions (FR-037).",
    epilog="""
Examples:
    $ floe platform unlock --env=prod --reason="Incident resolved"
    $ floe platform unlock --env=staging --reason="Maintenance complete"

Exit Codes:
    0  - Success
    1  - General error
    3  - Configuration error (manifest not found)
    5  - Registry unavailable
""",
)
@click.option(
    "--env",
    "-e",
    required=True,
    help="Environment to unlock (e.g., 'staging', 'prod').",
    metavar="ENV",
)
@click.option(
    "--reason",
    "-r",
    required=True,
    help="Reason for unlocking the environment.",
    metavar="REASON",
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
    type=str,
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
def unlock_command(
    env: str,
    reason: str,
    manifest: Path | None,
    registry: str | None,
    operator: str | None,
    output: str,
) -> None:
    """Unlock an environment to allow promotions.

    This command unlocks the specified environment, allowing promotions
    to it again.

    Args:
        env: Environment to unlock.
        reason: Reason for unlocking.
        manifest: Path to manifest.yaml.
        registry: OCI registry URI.
        operator: Operator identity.
        output: Output format (table or json).
    """
    from floe_core.oci.client import OCIClient
    from floe_core.oci.promotion import PromotionController
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig

    # Resolve operator
    resolved_operator = operator or _get_operator()

    logger.info(
        "unlock_command_started",
        environment=env,
        reason=reason,
        operator=resolved_operator,
    )

    try:
        # Load manifest or use registry directly
        if manifest:
            manifest_config = _load_platform_manifest(manifest)
            if manifest_config.artifacts is None:
                error("Manifest does not contain 'artifacts' configuration")
                sys.exit(3)
            registry_config = manifest_config.artifacts.registry
            promotion_config = manifest_config.artifacts.promotion
        elif registry:
            registry_config = RegistryConfig(
                uri=registry,
                auth=RegistryAuth(type=AuthType.ANONYMOUS),
            )
            # Minimal promotion config - controller will validate environment
            from floe_core.schemas.promotion import (
                EnvironmentConfig,
                PromotionConfig,
                PromotionGate,
            )

            promotion_config = PromotionConfig(
                environments=[
                    EnvironmentConfig(
                        name=env,
                        gates={PromotionGate.POLICY_COMPLIANCE: True},
                    ),
                ],
            )
        else:
            error("Either --manifest or --registry is required")
            sys.exit(3)

        # Validate promotion config exists
        if promotion_config is None:
            error("Manifest does not contain promotion configuration")
            sys.exit(3)

        # Create client and controller
        client = OCIClient.from_registry_config(registry_config)
        controller = PromotionController(
            client=client,
            promotion=promotion_config,
        )

        # Unlock the environment
        controller.unlock_environment(
            environment=env,
            reason=reason,
            operator=resolved_operator,
        )

        # Format output
        if output == "json":
            result = {
                "status": "unlocked",
                "environment": env,
                "reason": reason,
                "unlocked_by": resolved_operator,
            }
            click.echo(json.dumps(result, indent=2))
        else:
            success(f"Environment '{env}' unlocked successfully")
            info(f"  Reason:      {reason}")
            info(f"  Unlocked by: {resolved_operator}")

        sys.exit(0)

    except ValueError as e:
        error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception("unlock_command_failed", error=str(e))
        error(f"Failed to unlock environment: {e}")
        exit_code = getattr(e, "exit_code", 1)
        sys.exit(exit_code)


__all__: list[str] = ["lock_command", "unlock_command"]
