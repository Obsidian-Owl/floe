"""Manifest schema definitions for the floe data platform.

This module provides Pydantic models for validating and working with
platform manifest files (manifest.yaml). It supports:

- 2-tier mode: Single platform configuration (scope=None)
- 3-tier mode: Enterprise/Domain hierarchy with inheritance (scope=enterprise/domain)

Models:
    PlatformManifest: Root configuration schema
    ManifestMetadata: Name, version, owner metadata
    PluginsConfig: Plugin selection for all 11 categories
    PluginSelection: Individual plugin configuration
    GovernanceConfig: Security and compliance settings
    SecretReference: Placeholder for sensitive values
    InheritanceChain: Resolved configuration lineage (3-tier)

Example:
    >>> from floe_core.schemas import PlatformManifest
    >>> import yaml
    >>> with open("manifest.yaml") as f:
    ...     data = yaml.safe_load(f)
    >>> manifest = PlatformManifest.model_validate(data)
    >>> print(f"Platform: {manifest.metadata.name}")

See Also:
    - specs/001-manifest-schema/spec.md: Feature specification
    - specs/001-manifest-schema/quickstart.md: Usage guide
"""

from __future__ import annotations

# Public exports will be added as models are implemented
__all__: list[str] = []
