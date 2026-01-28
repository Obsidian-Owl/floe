"""Lineage backend plugin implementations.

This module contains concrete implementations of LineageBackendPlugin
for various OpenLineage backends (Marquez, Atlan, OpenMetadata, etc.).

Available backends:
    - MarquezLineageBackendPlugin: Self-hosted Marquez backend

Example:
    >>> from floe_core.lineage.backends import MarquezLineageBackendPlugin
    >>> plugin = MarquezLineageBackendPlugin(url="http://marquez:5000")
    >>> config = plugin.get_transport_config()
"""

from __future__ import annotations

from floe_core.lineage.backends.marquez import MarquezLineageBackendPlugin

__all__ = [
    "MarquezLineageBackendPlugin",
]
