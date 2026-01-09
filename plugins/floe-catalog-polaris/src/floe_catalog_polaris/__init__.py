"""Polaris Catalog Plugin for floe.

This package provides the PolarisCatalogPlugin implementation for Apache Iceberg
catalog management via Apache Polaris.

Example:
    >>> from floe_core.plugins import get_plugin
    >>> catalog = get_plugin("catalog", "polaris")
    >>> iceberg_catalog = catalog.connect(config)
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "__version__",
]
