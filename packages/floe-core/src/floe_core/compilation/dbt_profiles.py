"""dbt profile generation for floe compilation pipeline.

This module provides functions to generate dbt profiles.yml configuration
from resolved plugins and platform manifest. It integrates with the
ComputePlugin system to generate adapter-specific configurations.

The generated profiles use dbt's `{{ env_var('X') }}` syntax for credential
placeholders, ensuring environment-agnostic compilation (FR-014).

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - floe_core.plugins.compute: ComputePlugin ABC
    - https://docs.getdbt.com/docs/core/connect-data-platform/profiles.yml
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from floe_core.compilation.errors import CompilationError, CompilationException
from floe_core.compilation.stages import CompilationStage
from floe_core.compute_config import ComputeConfig
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

if TYPE_CHECKING:
    from floe_core.plugins.compute import ComputePlugin
    from floe_core.schemas.compiled_artifacts import ResolvedPlugins

logger = structlog.get_logger(__name__)

# Default environments for dbt profiles
DEFAULT_ENVIRONMENTS = ["dev"]


def format_env_var_placeholder(
    var_name: str,
    default: str | None = None,
) -> str:
    """Format a dbt env_var placeholder string.

    Creates a Jinja2 template string compatible with dbt's env_var function.
    This allows credentials to be resolved at runtime from environment
    variables rather than being hardcoded in compiled artifacts (FR-014).

    Args:
        var_name: Environment variable name (e.g., "DB_PASSWORD").
        default: Optional default value if env var is not set.

    Returns:
        Formatted env_var placeholder string.

    Examples:
        >>> format_env_var_placeholder("DB_PASSWORD")
        "{{ env_var('DB_PASSWORD') }}"

        >>> format_env_var_placeholder("FLOE_ENV", default="dev")
        "{{ env_var('FLOE_ENV', 'dev') }}"
    """
    if default is not None:
        return f"{{{{ env_var('{var_name}', '{default}') }}}}"
    return f"{{{{ env_var('{var_name}') }}}}"


def get_compute_plugin(plugin_type: str) -> ComputePlugin:
    """Get a compute plugin instance by type name.

    Loads the compute plugin from the registry. Plugins are discovered
    via entry points and instantiated on first access.

    Args:
        plugin_type: Compute plugin type name (e.g., "duckdb", "snowflake").

    Returns:
        ComputePlugin instance for the specified type.

    Raises:
        CompilationException: If plugin not found or fails to load.

    Example:
        >>> plugin = get_compute_plugin("duckdb")
        >>> plugin.name
        'duckdb'
    """
    try:
        registry = get_registry()
        plugin = registry.get(PluginType.COMPUTE, plugin_type)
        return plugin  # type: ignore[return-value]
    except Exception as e:
        logger.error(
            "dbt_profiles.plugin_not_found",
            plugin_type=plugin_type,
            error=str(e),
        )
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code="E301",
                message=f"Compute plugin '{plugin_type}' not found",
                suggestion=(
                    f"Ensure the '{plugin_type}' compute plugin is installed. "
                    f"Check that floe-compute-{plugin_type} package is in your environment."
                ),
                context={"plugin_type": plugin_type, "error": str(e)},
            )
        ) from e


def _build_compute_config(
    plugin_type: str,
    plugin_config: dict[str, Any] | None,
) -> ComputeConfig:
    """Build ComputeConfig from plugin configuration.

    Args:
        plugin_type: Compute plugin type name.
        plugin_config: Optional configuration dict from PluginRef.

    Returns:
        ComputeConfig instance ready for plugin.generate_dbt_profile().
    """
    config_dict: dict[str, Any] = plugin_config or {}

    # Extract known fields, put rest in connection
    threads = config_dict.pop("threads", 4)
    timeout_seconds = config_dict.pop("timeout_seconds", 3600)

    return ComputeConfig(
        plugin=plugin_type,
        threads=threads,
        timeout_seconds=timeout_seconds,
        connection=config_dict,
    )


def generate_dbt_profiles(
    plugins: ResolvedPlugins,
    product_name: str,
    environments: list[str] | None = None,
) -> dict[str, Any]:
    """Generate dbt profiles.yml configuration from resolved plugins.

    Creates a complete profiles.yml structure suitable for dbt. The profile
    uses the ComputePlugin.generate_dbt_profile() method to generate
    adapter-specific configuration.

    Args:
        plugins: ResolvedPlugins with compute plugin configuration.
        product_name: Data product name (used as profile name in dbt).
        environments: List of environment names to generate (default: ["dev"]).

    Returns:
        Dictionary matching dbt profiles.yml structure:
        {
            "<product_name>": {
                "target": "dev",  # or env_var placeholder
                "outputs": {
                    "dev": { ... adapter config ... },
                    "prod": { ... adapter config ... }
                }
            }
        }

    Raises:
        CompilationException: If compute plugin not found or configuration invalid.

    Example:
        >>> profiles = generate_dbt_profiles(
        ...     plugins=resolved_plugins,
        ...     product_name="analytics",
        ...     environments=["dev", "prod"]
        ... )
        >>> profiles["analytics"]["outputs"]["dev"]["type"]
        'duckdb'
    """
    if environments is None:
        environments = DEFAULT_ENVIRONMENTS

    # compute is required in ResolvedPlugins, but we validate type
    compute_type = plugins.compute.type
    compute_config_dict = plugins.compute.config

    logger.info(
        "dbt_profiles.generating",
        product_name=product_name,
        compute_type=compute_type,
        environments=environments,
    )

    # Get the compute plugin
    plugin = get_compute_plugin(compute_type)

    # Build ComputeConfig from plugin configuration
    compute_config = _build_compute_config(compute_type, compute_config_dict)

    # Generate profile for each environment
    outputs: dict[str, Any] = {}
    for env in environments:
        try:
            profile_output = plugin.generate_dbt_profile(compute_config)
            outputs[env] = profile_output
        except Exception as e:
            logger.error(
                "dbt_profiles.generation_failed",
                environment=env,
                compute_type=compute_type,
                error=str(e),
            )
            raise CompilationException(
                CompilationError(
                    stage=CompilationStage.RESOLVE,
                    code="E303",
                    message=f"Failed to generate dbt profile for '{compute_type}'",
                    suggestion=(f"Check compute plugin configuration. Error: {e}"),
                    context={
                        "compute_type": compute_type,
                        "environment": env,
                        "error": str(e),
                    },
                )
            ) from e

    # Build final profile structure
    profile: dict[str, Any] = {
        product_name: {
            "target": "dev",  # Default target
            "outputs": outputs,
        }
    }

    logger.info(
        "dbt_profiles.generated",
        product_name=product_name,
        environments=list(outputs.keys()),
    )

    return profile


__all__ = [
    "format_env_var_placeholder",
    "generate_dbt_profiles",
    "get_compute_plugin",
]
