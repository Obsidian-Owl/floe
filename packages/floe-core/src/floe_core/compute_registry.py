"""ComputeRegistry for managing approved compute targets.

This module provides the ComputeRegistry class for managing the list of approved
compute plugins and tracking the default compute target. It integrates with the
PluginRegistry for plugin discovery and loading.

The ComputeRegistry supports:
- Managing a list of approved compute targets (subset of discovered plugins)
- Tracking the default compute target
- Plugin lookup by name with validation against approved list
- Hierarchical governance (Enterprise -> Domain -> Product)

Example:
    >>> from floe_core import ComputeRegistry, get_registry, PluginType
    >>> registry = ComputeRegistry(
    ...     approved=["duckdb", "spark"],
    ...     default="duckdb"
    ... )
    >>> plugin = registry.get("duckdb")
    >>> plugin.name
    'duckdb'

See Also:
    - floe_core.plugin_registry: Central plugin discovery and management
    - floe_core.plugins.compute: ComputePlugin ABC
    - docs/architecture/plugin-system/: Full architecture documentation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from floe_core.compute_errors import ComputeConfigurationError
from floe_core.plugin_registry import PluginRegistry, get_registry
from floe_core.plugin_types import PluginType

if TYPE_CHECKING:
    from floe_core.plugins import ComputePlugin

logger = structlog.get_logger(__name__)


class ComputeRegistry:
    """Registry for managing approved compute targets.

    ComputeRegistry acts as a governance layer on top of PluginRegistry,
    restricting which compute plugins are available to data engineers based
    on platform configuration (manifest.yaml).

    Key Features:
        - Manages list of approved compute targets
        - Tracks default compute target for fallback
        - Validates compute selections against approved list
        - Supports hierarchical inheritance (Enterprise -> Domain -> Product)

    Attributes:
        approved: List of approved compute plugin names.
        default: Default compute plugin name (must be in approved list).

    Example:
        >>> registry = ComputeRegistry(
        ...     approved=["duckdb", "spark", "snowflake"],
        ...     default="duckdb"
        ... )
        >>> # Get a specific compute plugin
        >>> duckdb = registry.get("duckdb")
        >>> # Get the default plugin
        >>> default = registry.get_default()

    See Also:
        - PluginRegistry: Underlying plugin discovery mechanism
        - ComputePlugin: Abstract base class for compute plugins
    """

    def __init__(
        self,
        approved: list[str],
        default: str,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        """Initialize a ComputeRegistry with approved targets and default.

        Args:
            approved: List of approved compute plugin names. Must be non-empty.
            default: Default compute plugin name. Must be in approved list.
            plugin_registry: Optional PluginRegistry instance. If not provided,
                uses the global singleton from get_registry().

        Raises:
            ComputeConfigurationError: If approved list is empty, default is
                not in approved list, or no approved plugins are discovered.

        Example:
            >>> registry = ComputeRegistry(
            ...     approved=["duckdb", "spark"],
            ...     default="duckdb"
            ... )
        """
        # Validate inputs
        if not approved:
            logger.error("compute_registry.empty_approved")
            raise ComputeConfigurationError(
                "Approved compute list cannot be empty",
                plugin_name="compute.approved",
            )

        if default not in approved:
            logger.error(
                "compute_registry.default_not_approved",
                default=default,
                approved=approved,
            )
            raise ComputeConfigurationError(
                f"Default compute '{default}' must be in approved list: {approved}",
                plugin_name="compute.default",
            )

        self._approved: list[str] = list(approved)
        self._default: str = default
        self._plugin_registry = plugin_registry or get_registry()

        # Validate that approved plugins can be discovered
        self._validate_approved_plugins()

        logger.info(
            "compute_registry.initialized",
            approved=self._approved,
            default=self._default,
        )

    def _validate_approved_plugins(self) -> None:
        """Validate that all approved plugins exist in the plugin registry.

        Raises:
            ComputeConfigurationError: If any approved plugin is not discovered.
        """
        missing: list[str] = []

        for name in self._approved:
            try:
                self._plugin_registry.get(PluginType.COMPUTE, name)
            except Exception:
                missing.append(name)

        if missing:
            logger.error(
                "compute_registry.missing_plugins",
                missing=missing,
                approved=self._approved,
            )
            raise ComputeConfigurationError(
                f"Approved compute plugins not found: {missing}. "
                f"Check that these plugins are installed and discoverable.",
                plugin_name="compute.approved",
            )

    @property
    def approved(self) -> list[str]:
        """List of approved compute plugin names.

        Returns:
            Copy of the approved plugin names list.

        Example:
            >>> registry.approved
            ['duckdb', 'spark', 'snowflake']
        """
        return list(self._approved)

    @property
    def default(self) -> str:
        """Default compute plugin name.

        Returns:
            The default plugin name.

        Example:
            >>> registry.default
            'duckdb'
        """
        return self._default

    def get(self, name: str) -> ComputePlugin:
        """Get a compute plugin by name.

        Validates that the requested plugin is in the approved list before
        returning it. Use this method for compile-time validation of compute
        selections in floe.yaml.

        Args:
            name: Compute plugin name to retrieve.

        Returns:
            The ComputePlugin instance.

        Raises:
            ComputeConfigurationError: If plugin is not in approved list.

        Example:
            >>> plugin = registry.get("duckdb")
            >>> plugin.name
            'duckdb'
            >>> # Trying to get unapproved plugin
            >>> registry.get("bigquery")
            ComputeConfigurationError: Compute 'bigquery' not in approved list
        """
        if name not in self._approved:
            logger.warning(
                "compute_registry.unapproved_compute",
                requested=name,
                approved=self._approved,
            )
            raise ComputeConfigurationError(
                f"Compute '{name}' is not in the approved list. "
                f"Allowed computes: {self._approved}",
                plugin_name=name,
            )

        plugin = self._plugin_registry.get(PluginType.COMPUTE, name)

        # Type narrowing: we know this is a ComputePlugin from the PluginType
        return plugin  # type: ignore[return-value]

    def get_default(self) -> ComputePlugin:
        """Get the default compute plugin.

        Convenience method to retrieve the default plugin without specifying
        the name. Useful when a transform doesn't specify a compute target.

        Returns:
            The default ComputePlugin instance.

        Example:
            >>> plugin = registry.get_default()
            >>> plugin.name
            'duckdb'
        """
        return self.get(self._default)

    def is_approved(self, name: str) -> bool:
        """Check if a compute plugin is in the approved list.

        Use this for validation without loading the plugin.

        Args:
            name: Compute plugin name to check.

        Returns:
            True if plugin is approved, False otherwise.

        Example:
            >>> registry.is_approved("duckdb")
            True
            >>> registry.is_approved("bigquery")
            False
        """
        return name in self._approved

    def list_approved(self) -> list[ComputePlugin]:
        """List all approved compute plugins.

        Loads and returns all approved compute plugins. Each plugin is
        lazy-loaded on first access.

        Returns:
            List of ComputePlugin instances for all approved plugins.

        Example:
            >>> plugins = registry.list_approved()
            >>> [p.name for p in plugins]
            ['duckdb', 'spark', 'snowflake']
        """
        plugins: list[ComputePlugin] = []

        for name in self._approved:
            try:
                plugin = self.get(name)
                plugins.append(plugin)
            except Exception as e:
                # Log but continue with other plugins (graceful degradation)
                logger.warning(
                    "compute_registry.plugin_load_failed",
                    name=name,
                    error=str(e),
                )

        return plugins

    def validate_selection(self, compute: str | None) -> str:
        """Validate and resolve a compute selection.

        Validates that a compute selection is approved, or returns the
        default if not specified. Use this for compile-time validation
        of compute selections in floe.yaml transforms.

        Args:
            compute: Compute plugin name, or None to use default.

        Returns:
            Validated compute plugin name.

        Raises:
            ComputeConfigurationError: If specified compute is not approved.

        Example:
            >>> registry.validate_selection("spark")
            'spark'
            >>> registry.validate_selection(None)  # Returns default
            'duckdb'
            >>> registry.validate_selection("bigquery")
            ComputeConfigurationError: Compute 'bigquery' not approved
        """
        if compute is None:
            logger.debug(
                "compute_registry.using_default",
                default=self._default,
            )
            return self._default

        if compute not in self._approved:
            logger.warning(
                "compute_registry.invalid_selection",
                requested=compute,
                approved=self._approved,
            )
            raise ComputeConfigurationError(
                f"Compute '{compute}' is not in the approved list. "
                f"Allowed computes: {self._approved}",
                plugin_name=compute,
            )

        return compute

    def create_restricted(
        self,
        approved: list[str],
        default: str | None = None,
    ) -> ComputeRegistry:
        """Create a restricted ComputeRegistry for hierarchical governance.

        Creates a child registry with a subset of this registry's approved
        computes. Use this for Domain or Product level restrictions that
        must be a subset of Enterprise level approvals.

        Args:
            approved: Subset of approved compute names. Must be a subset
                of this registry's approved list.
            default: Default compute for child registry. If not specified,
                uses this registry's default if in the new approved list,
                otherwise uses the first approved compute.

        Returns:
            New ComputeRegistry with restricted approved list.

        Raises:
            ComputeConfigurationError: If approved is not a subset of
                this registry's approved list.

        Example:
            >>> # Enterprise allows [duckdb, spark, snowflake]
            >>> enterprise = ComputeRegistry(
            ...     approved=["duckdb", "spark", "snowflake"],
            ...     default="duckdb"
            ... )
            >>> # Domain restricts to [duckdb, spark]
            >>> domain = enterprise.create_restricted(
            ...     approved=["duckdb", "spark"],
            ...     default="duckdb"
            ... )
        """
        # Validate that approved is a subset
        not_allowed = [name for name in approved if name not in self._approved]
        if not_allowed:
            logger.error(
                "compute_registry.governance_violation",
                not_allowed=not_allowed,
                parent_approved=self._approved,
            )
            raise ComputeConfigurationError(
                f"Compute targets {not_allowed} are not in the parent approved list. "
                f"Parent allows: {self._approved}",
                plugin_name="compute.approved",
            )

        # Determine default for child
        if default is None:
            # Use parent default if allowed, otherwise first in approved
            if self._default in approved:
                default = self._default
            else:
                default = approved[0]

        logger.debug(
            "compute_registry.create_restricted",
            parent_approved=self._approved,
            child_approved=approved,
            child_default=default,
        )

        return ComputeRegistry(
            approved=approved,
            default=default,
            plugin_registry=self._plugin_registry,
        )
