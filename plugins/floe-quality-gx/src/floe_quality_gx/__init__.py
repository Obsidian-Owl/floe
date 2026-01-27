"""Great Expectations data quality plugin for the floe data platform.

This plugin implements the QualityPlugin ABC using Great Expectations
for data quality validation, supporting compile-time configuration
validation and runtime quality checks.

Example:
    >>> from floe_core.plugin_registry import get_registry
    >>> from floe_core.plugin_types import PluginType
    >>>
    >>> registry = get_registry()
    >>> gx_plugin = registry.get(PluginType.QUALITY, "great_expectations")
    >>> print(f"Plugin: {gx_plugin.name} v{gx_plugin.version}")
"""

from floe_quality_gx.plugin import GreatExpectationsPlugin

__all__ = ["GreatExpectationsPlugin"]
__version__ = "0.1.0"
