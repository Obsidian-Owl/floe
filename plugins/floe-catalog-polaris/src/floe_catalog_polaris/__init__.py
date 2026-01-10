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
from floe_catalog_polaris.config import (
    OAuth2Config,
    PolarisCatalogConfig,
    export_json_schema,
    get_json_schema,
)
from floe_catalog_polaris.credentials import (
    credentials_are_valid,
    extract_credentials_from_io_properties,
    get_expiration_datetime,
    is_expired,
    parse_expiration,
    validate_credential_structure,
)
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
    "export_json_schema",
    "get_json_schema",
    "map_pyiceberg_error",
    "PYICEBERG_EXCEPTION_TYPES",
    # Credential vending helpers
    "extract_credentials_from_io_properties",
    "parse_expiration",
    "validate_credential_structure",
    "credentials_are_valid",
    "is_expired",
    "get_expiration_datetime",
]
