"""Dagster resources for floe orchestration.

This module provides ConfigurableResource implementations for:
- DBTResource: DBT plugin integration for asset materialization

Example:
    >>> from floe_orchestrator_dagster.resources import DBTResource
    >>> from dagster import asset, Definitions
    >>>
    >>> @asset
    >>> def my_models(dbt: DBTResource) -> None:
    ...     dbt.run_models(select="staging.*")
    >>>
    >>> defs = Definitions(
    ...     assets=[my_models],
    ...     resources={"dbt": DBTResource(project_dir="/path/to/dbt")},
    ... )
"""

from __future__ import annotations

from .dbt_resource import DBTResource, load_dbt_plugin

__all__: list[str] = [
    "DBTResource",
    "load_dbt_plugin",
]
