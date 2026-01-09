"""Polaris Catalog Plugin for floe.

This package provides the PolarisCatalogPlugin implementation for Apache Iceberg
catalog management via Apache Polaris.

Example:
    >>> from floe_core.plugins import get_plugin
    >>> catalog = get_plugin("catalog", "polaris")
    >>> iceberg_catalog = catalog.connect(config)

Public API:
    - PolarisCatalogPlugin: Main plugin class (implements CatalogPlugin ABC)
    - PolarisCatalogConfig: Configuration model for Polaris connection
    - OAuth2Config: OAuth2 authentication configuration
    - VendedCredentials: Temporary credentials returned by vend_credentials()
    - HealthStatus: Health check result model
"""

from __future__ import annotations

__version__ = "0.1.0"

# Public API exports
from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.errors import (
    PYICEBERG_EXCEPTION_TYPES,
    map_pyiceberg_error,
)
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

__all__ = [
    "__version__",
    "PolarisCatalogPlugin",
    "PolarisCatalogConfig",
    "OAuth2Config",
    "map_pyiceberg_error",
    "PYICEBERG_EXCEPTION_TYPES",
]
