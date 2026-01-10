"""DuckDB compute plugin for floe data platform.

This package provides the DuckDB compute plugin implementation that enables
DuckDB as a compute target for dbt transforms. DuckDB is a self-hosted,
in-process analytical database that runs within K8s job pods.

Key Features:
    - In-process: Runs alongside dbt in the same pod
    - Self-hosted: Managed by floe K8s infrastructure
    - Iceberg support: Direct catalog attachment via iceberg extension
    - Low overhead: No separate database server required

Example:
    >>> from floe_compute_duckdb import DuckDBComputePlugin
    >>> plugin = DuckDBComputePlugin()
    >>> plugin.name
    'duckdb'
    >>> plugin.is_self_hosted
    True

Entry Point:
    This plugin is registered via entry point `floe.computes = duckdb`
    and discovered automatically by the floe plugin registry.
"""

from __future__ import annotations

from floe_compute_duckdb.plugin import DuckDBComputePlugin

__all__ = ["DuckDBComputePlugin"]

__version__ = "0.1.0"
