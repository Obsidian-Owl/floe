"""Compiler for resolving transform compute targets.

This module provides compile-time validation and resolution of compute targets
for transforms. It integrates TransformConfig with ComputeRegistry to:
- Resolve compute inheritance from platform default
- Validate compute selections against approved list
- Enforce environment parity (same compute across dev/staging/prod)

Example:
    >>> from floe_core.compiler import resolve_transform_compute, validate_environment_parity
    >>> from floe_core.plugins.orchestrator import TransformConfig
    >>> from floe_core.compute_registry import ComputeRegistry
    >>>
    >>> # Resolve compute for a transform
    >>> transform = TransformConfig(name="stg_customers")
    >>> compute = resolve_transform_compute(transform, compute_registry)
    >>> compute
    'duckdb'  # Platform default
    >>>
    >>> # Validate environment parity
    >>> env_transforms = {
    ...     "dev": [TransformConfig(name="model", compute="duckdb")],
    ...     "prod": [TransformConfig(name="model", compute="duckdb")],
    ... }
    >>> validate_environment_parity(env_transforms, compute_registry)

See Also:
    - FR-012: Per-transform compute selection in floe.yaml
    - FR-013: Compile-time validation
    - FR-014: Environment parity enforcement
    - ComputeRegistry: Approved compute management
    - TransformConfig: Transform configuration with compute field
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from floe_core.compute_errors import ComputeConfigurationError

if TYPE_CHECKING:
    from floe_core.compute_registry import ComputeRegistry
    from floe_core.plugins.orchestrator import TransformConfig

logger = structlog.get_logger(__name__)


class EnvironmentParityError(ComputeConfigurationError):
    """Error raised when environment parity is violated.

    Environment parity requires each transform to use the SAME compute
    across all environments (dev, staging, prod). This prevents issues
    where a transform works in dev but fails in prod due to compute
    differences.

    Attributes:
        transform_name: Name of the transform with parity violation.
        env_computes: Mapping of environment to compute selection.

    Example:
        >>> raise EnvironmentParityError(
        ...     transform_name="stg_customers",
        ...     env_computes={"dev": "duckdb", "staging": "spark", "prod": "spark"}
        ... )
        EnvironmentParityError: Environment parity violation for transform
        'stg_customers': compute differs across environments (dev=duckdb,
        staging=spark, prod=spark). Each transform must use the same compute
        in all environments.
    """

    def __init__(
        self,
        transform_name: str,
        env_computes: dict[str, str],
    ) -> None:
        """Initialize EnvironmentParityError.

        Args:
            transform_name: Name of the transform with parity violation.
            env_computes: Mapping of environment name to compute selection.
        """
        self.transform_name = transform_name
        self.env_computes = env_computes

        mismatch_details = ", ".join(
            f"{env}={compute}" for env, compute in sorted(env_computes.items())
        )
        message = (
            f"Environment parity violation for transform '{transform_name}': "
            f"compute differs across environments ({mismatch_details}). "
            f"Each transform must use the same compute in all environments."
        )

        super().__init__(message, plugin_name=transform_name)


def resolve_transform_compute(
    transform: TransformConfig,
    compute_registry: ComputeRegistry,
) -> str:
    """Resolve the compute target for a transform.

    If the transform specifies an explicit compute, validates it against
    the approved list. If not specified (None), returns the platform default.

    This function is called at compile time (floe compile) to validate
    compute selections before any jobs are scheduled.

    Args:
        transform: Transform configuration with optional compute field.
        compute_registry: Registry of approved compute targets.

    Returns:
        Resolved compute target name.

    Raises:
        ComputeConfigurationError: If specified compute is not in approved list.

    Example:
        >>> transform = TransformConfig(name="model", compute="spark")
        >>> compute = resolve_transform_compute(transform, registry)
        >>> compute
        'spark'

        >>> transform_default = TransformConfig(name="model")  # No compute
        >>> compute = resolve_transform_compute(transform_default, registry)
        >>> compute
        'duckdb'  # Platform default

    See Also:
        - FR-012: Per-transform compute selection
        - FR-013: Compile-time validation
    """
    resolved = compute_registry.validate_selection(transform.compute)

    if transform.compute is None:
        logger.debug(
            "compiler.transform_inherits_default",
            transform=transform.name,
            resolved_compute=resolved,
        )
    else:
        logger.debug(
            "compiler.transform_explicit_compute",
            transform=transform.name,
            compute=transform.compute,
        )

    return resolved


def resolve_transforms_compute(
    transforms: list[TransformConfig],
    compute_registry: ComputeRegistry,
) -> dict[str, str]:
    """Resolve compute targets for a list of transforms.

    Convenience function to resolve compute for multiple transforms at once.
    Returns a mapping from transform name to resolved compute.

    Args:
        transforms: List of transform configurations.
        compute_registry: Registry of approved compute targets.

    Returns:
        Dictionary mapping transform name to resolved compute target.

    Raises:
        ComputeConfigurationError: If any specified compute is not in approved list.

    Example:
        >>> transforms = [
        ...     TransformConfig(name="model_a", compute=None),  # Uses default
        ...     TransformConfig(name="model_b", compute="spark"),  # Explicit
        ... ]
        >>> resolved = resolve_transforms_compute(transforms, registry)
        >>> resolved
        {'model_a': 'duckdb', 'model_b': 'spark'}
    """
    return {
        transform.name: resolve_transform_compute(transform, compute_registry)
        for transform in transforms
    }


def check_environment_parity(
    env_transforms: dict[str, list[TransformConfig]],
    compute_registry: ComputeRegistry,
) -> list[EnvironmentParityError]:
    """Check environment parity for transforms across environments.

    Validates that each transform uses the same compute target across all
    environments (dev, staging, prod). Returns a list of parity violations
    rather than raising immediately, allowing all violations to be reported.

    Args:
        env_transforms: Mapping from environment name to list of transforms.
            Example: {"dev": [transforms...], "staging": [transforms...]}
        compute_registry: Registry for resolving compute defaults.

    Returns:
        List of EnvironmentParityError for each transform with violations.
        Empty list if all transforms pass parity check.

    Example:
        >>> env_transforms = {
        ...     "dev": [TransformConfig(name="model", compute="duckdb")],
        ...     "prod": [TransformConfig(name="model", compute="spark")],
        ... }
        >>> errors = check_environment_parity(env_transforms, registry)
        >>> len(errors)
        1
        >>> errors[0].transform_name
        'model'

    See Also:
        - FR-014: Environment parity enforcement
    """
    # Build mapping: transform_name -> {env -> resolved_compute}
    transform_env_computes: dict[str, dict[str, str]] = {}

    for env, transforms in env_transforms.items():
        for transform in transforms:
            resolved = resolve_transform_compute(transform, compute_registry)

            if transform.name not in transform_env_computes:
                transform_env_computes[transform.name] = {}

            transform_env_computes[transform.name][env] = resolved

    # Check for parity violations
    errors: list[EnvironmentParityError] = []

    for transform_name, env_computes in transform_env_computes.items():
        unique_computes = set(env_computes.values())

        if len(unique_computes) > 1:
            logger.warning(
                "compiler.environment_parity_violation",
                transform=transform_name,
                env_computes=env_computes,
            )
            errors.append(
                EnvironmentParityError(
                    transform_name=transform_name,
                    env_computes=env_computes,
                )
            )

    return errors


def validate_environment_parity(
    env_transforms: dict[str, list[TransformConfig]],
    compute_registry: ComputeRegistry,
) -> None:
    """Validate environment parity, raising on first violation.

    Validates that each transform uses the same compute across all environments.
    Raises immediately if any parity violation is detected.

    Args:
        env_transforms: Mapping from environment name to list of transforms.
        compute_registry: Registry for resolving compute defaults.

    Raises:
        EnvironmentParityError: If any transform has different computes
            across environments.

    Example:
        >>> # This will raise because dev uses duckdb, prod uses spark
        >>> validate_environment_parity(
        ...     {"dev": [TransformConfig(name="model", compute="duckdb")],
        ...      "prod": [TransformConfig(name="model", compute="spark")]},
        ...     registry
        ... )
        EnvironmentParityError: Environment parity violation...

    See Also:
        - FR-014: Environment parity enforcement
        - check_environment_parity: Non-raising version that returns all errors
    """
    errors = check_environment_parity(env_transforms, compute_registry)

    if errors:
        # Raise first error (or could aggregate - design choice)
        raise errors[0]


def compile_transforms(
    transforms: list[TransformConfig],
    compute_registry: ComputeRegistry,
) -> list[TransformConfig]:
    """Compile transforms with resolved compute targets.

    Creates new TransformConfig instances with compute field resolved to
    actual compute target names. Transforms with None compute get the
    platform default filled in.

    Args:
        transforms: List of transform configurations (possibly with None compute).
        compute_registry: Registry of approved compute targets.

    Returns:
        List of TransformConfig with compute field resolved (never None).

    Raises:
        ComputeConfigurationError: If any specified compute is not in approved list.

    Example:
        >>> transforms = [
        ...     TransformConfig(name="a", compute=None),
        ...     TransformConfig(name="b", compute="spark"),
        ... ]
        >>> compiled = compile_transforms(transforms, registry)
        >>> compiled[0].compute
        'duckdb'  # Resolved from default
        >>> compiled[1].compute
        'spark'  # Kept explicit value
    """
    from dataclasses import replace

    compiled: list[TransformConfig] = []

    for transform in transforms:
        resolved_compute = resolve_transform_compute(transform, compute_registry)

        # Create new TransformConfig with resolved compute
        compiled_transform = replace(transform, compute=resolved_compute)
        compiled.append(compiled_transform)

    logger.info(
        "compiler.transforms_compiled",
        count=len(compiled),
        computes=list({t.compute for t in compiled}),
    )

    return compiled
