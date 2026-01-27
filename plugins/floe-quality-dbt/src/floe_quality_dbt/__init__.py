"""dbt-expectations data quality plugin for the floe data platform.

This plugin implements the QualityPlugin ABC using dbt-expectations
for data quality validation, executing checks as dbt tests via the
DBTPlugin interface.

Example:
    >>> from floe_core.plugin_registry import get_registry
    >>> from floe_core.plugin_types import PluginType
    >>>
    >>> registry = get_registry()
    >>> dbt_plugin = registry.get(PluginType.QUALITY, "dbt_expectations")
    >>> print(f"Plugin: {dbt_plugin.name} v{dbt_plugin.version}")
"""

from floe_quality_dbt.plugin import DBTExpectationsPlugin

__all__ = ["DBTExpectationsPlugin"]
__version__ = "0.1.0"
