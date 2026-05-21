"""SemanticLayerPlugin ABC for semantic layer plugins.

This module defines the abstract base class for semantic layer plugins that
provide provider-neutral business intelligence API functionality. Semantic
layer plugins are responsible for:
- Syncing semantic models from dbt manifests
- Providing security context for data isolation
- Declaring semantic composition capabilities and requirements
- Rendering provider runtime configuration from semantic deployment bindings
- Reporting logical API endpoint families

Abstract methods (2 total):
    1. sync_from_dbt_manifest() - Generate semantic models from dbt manifest
    2. get_security_context() - Build security context for data isolation

Example:
    >>> from floe_core.plugins.semantic import SemanticLayerPlugin
    >>> class SemanticPlugin(SemanticLayerPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "semantic-provider"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any

from floe_core.composition.models import (
    CapabilitySet,
    PluginCapabilities,
    PluginRequirements,
    RequirementSet,
)
from floe_core.plugin_metadata import PluginMetadata
from floe_core.schemas.compiled_artifacts import SemanticDeploymentBinding


class SemanticLayerPlugin(PluginMetadata):
    """Abstract base class for semantic layer plugins.

    SemanticLayerPlugin extends PluginMetadata with semantic-specific
    methods for business intelligence APIs. Implementations include
    Cube and dbt Semantic Layer.

    The public contract is provider-neutral: semantic plugins declare their
    composition surface, consume ``SemanticDeploymentBinding`` desired state,
    and expose logical API endpoint families. Concrete providers may translate
    those contracts into provider runtime configuration internally.

    Orchestrator plugins may host semantic publication steps as workflow
    tasks, but they do not own semantic contracts or semantic provider
    lifecycle semantics.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - sync_from_dbt_manifest() method
        - get_security_context() method

    Example:
        >>> class SemanticPlugin(SemanticLayerPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "semantic-provider"
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
        ...         # Generate provider semantic schema files from dbt manifest.
        ...         return [output_dir / "schema" / "orders.yml"]

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - SemanticDeploymentBinding: Provider-neutral deployment desired state
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

    def get_datasource_config(
        self,
        compute_plugin: Any,
    ) -> dict[str, Any]:
        """Compatibility hook for legacy datasource configuration.

        New provider integrations should use ``render_runtime_config()`` with
        ``SemanticDeploymentBinding``. This method remains available so
        existing plugins can continue to load during the migration window.

        Args:
            compute_plugin: Legacy compute plugin object supplied by older
                callers.

        Returns:
            Legacy datasource configuration dict. The default is empty.
        """
        return {}

    def get_api_endpoints(self) -> dict[str, str]:
        """Compatibility hook for legacy endpoint URL maps.

        New provider integrations should report logical endpoint families via
        ``get_api_endpoint_families()`` and put concrete service endpoint
        desired state in ``SemanticDeploymentBinding``.

        Returns:
            Legacy mapping of endpoint names to URL paths. The default is
            empty.
        """
        return {}

    def get_helm_values_override(self) -> dict[str, Any]:
        """Compatibility hook for legacy Helm values overrides.

        New provider integrations should render runtime configuration from
        ``SemanticDeploymentBinding``. This method remains available during the
        migration window for existing deployment code.

        Returns:
            Dictionary of Helm values to merge into a platform chart. The
            default is empty.
        """
        return {}

    def get_composition_capabilities(self) -> PluginCapabilities:
        """Return semantic capabilities for composition validation.

        The default is intentionally empty so existing semantic plugins remain
        discoverable until they adopt semantic composition explicitly.
        """
        return PluginCapabilities(
            plugin_type="semantic",
            plugin_name=self.name,
            capabilities=CapabilitySet(),
        )

    def get_composition_requirements(self) -> PluginRequirements:
        """Return peer plugin requirements for semantic composition.

        The default is intentionally empty. Providers that require specific
        datasource engines, API families, artifact transports, identity modes,
        or secret projection modes should override this method.
        """
        return PluginRequirements(
            plugin_type="semantic",
            plugin_name=self.name,
            requirements=RequirementSet(),
        )

    def render_runtime_config(
        self,
        binding: SemanticDeploymentBinding,
    ) -> dict[str, Any]:
        """Render provider runtime config from semantic deployment desired state.

        Args:
            binding: Provider-neutral, secret-free semantic deployment desired
                state resolved by floe-core.

        Returns:
            Provider runtime configuration derived from the binding.

        Raises:
            NotImplementedError: If the provider has not adopted deployment
                binding rendering yet.
        """
        raise NotImplementedError(
            f"{self.name} does not implement semantic runtime config rendering"
        )

    def get_api_endpoint_families(self) -> list[str]:
        """Return logical semantic API endpoint families supported by provider.

        Families are provider-neutral labels such as query, metadata, or health.
        Concrete URL paths belong in deployment bindings or provider runtime
        configuration, not in the public ABC contract.
        """
        return []
