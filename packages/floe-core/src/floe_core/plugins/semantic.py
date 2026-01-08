"""SemanticLayerPlugin ABC for semantic layer plugins.

This module defines the abstract base class for semantic layer plugins that
provide business intelligence API functionality. Semantic layer plugins are
responsible for:
- Syncing semantic models from dbt manifests
- Providing security context for data isolation
- Configuring datasources from compute plugins

Example:
    >>> from floe_core.plugins.semantic import SemanticLayerPlugin
    >>> class CubePlugin(SemanticLayerPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "cube"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    from floe_core.plugins.compute import ComputePlugin


class SemanticLayerPlugin(PluginMetadata):
    """Abstract base class for semantic layer plugins.

    SemanticLayerPlugin extends PluginMetadata with semantic-specific
    methods for business intelligence APIs. Implementations include
    Cube and dbt Semantic Layer.

    The semantic layer delegates database connectivity to the active
    ComputePlugin, following the platform's plugin architecture (ADR-0032).

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - sync_from_dbt_manifest() method
        - get_security_context() method
        - get_datasource_config() method

    Example:
        >>> class CubePlugin(SemanticLayerPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "cube"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def sync_from_dbt_manifest(self, manifest_path, output_dir) -> list[Path]:
        ...         # Generate Cube schema files from dbt manifest
        ...         return [output_dir / "schema" / "orders.yml"]

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - ComputePlugin: Provides database connectivity
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @abstractmethod
    def sync_from_dbt_manifest(
        self,
        manifest_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """Generate semantic models from dbt manifest.

        Parses the dbt manifest.json and generates semantic layer
        schema files (Cube YAML, dbt Semantic Layer definitions, etc.).

        Args:
            manifest_path: Path to dbt manifest.json file.
            output_dir: Directory to write generated schema files.

        Returns:
            List of paths to generated schema files.

        Raises:
            FileNotFoundError: If manifest doesn't exist.
            ValidationError: If manifest is invalid.

        Example:
            >>> files = plugin.sync_from_dbt_manifest(
            ...     manifest_path=Path("target/manifest.json"),
            ...     output_dir=Path("cube/schema")
            ... )
            >>> files
            [PosixPath('cube/schema/orders.yml'), PosixPath('cube/schema/customers.yml')]
        """
        ...

    @abstractmethod
    def get_security_context(
        self,
        namespace: str,
        roles: list[str],
    ) -> dict[str, Any]:
        """Build security context for data isolation.

        Creates a security context dictionary used for row-level security
        and column-level access control in the semantic layer.

        Args:
            namespace: Data namespace (e.g., "tenant_123", "region_us").
            roles: List of user roles for access control.

        Returns:
            Dictionary with security context configuration.

        Example:
            >>> context = plugin.get_security_context(
            ...     namespace="tenant_acme",
            ...     roles=["analyst", "viewer"]
            ... )
            >>> context
            {
                'tenant_id': 'tenant_acme',
                'allowed_roles': ['analyst', 'viewer'],
                'row_filters': {'orders': "tenant_id = 'tenant_acme'"}
            }
        """
        ...

    @abstractmethod
    def get_datasource_config(
        self,
        compute_plugin: ComputePlugin,
    ) -> dict[str, Any]:
        """Generate datasource configuration from compute plugin.

        The semantic layer delegates database connectivity to the active
        compute plugin, following the platform's plugin architecture.

        Args:
            compute_plugin: Active ComputePlugin instance.

        Returns:
            Datasource configuration dict for the semantic layer.

        Example:
            >>> config = plugin.get_datasource_config(duckdb_plugin)
            >>> config
            {
                'type': 'duckdb',
                'url': '/data/floe.duckdb',
                'catalog': 'ice'
            }

            >>> config = plugin.get_datasource_config(snowflake_plugin)
            >>> config
            {
                'type': 'snowflake',
                'account': 'xxx.us-east-1',
                'warehouse': 'compute_wh'
            }
        """
        ...
