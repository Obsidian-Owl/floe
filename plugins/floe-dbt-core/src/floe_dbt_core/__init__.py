"""floe-dbt-core: DBT plugin using dbt-core Python API.

This package provides DBTCorePlugin, which wraps dbt-core's dbtRunner
for local development and CI/CD pipelines.

Note: dbtRunner is NOT thread-safe. For parallel execution, use floe-dbt-fusion.
"""

from __future__ import annotations

__all__: list[str] = []
