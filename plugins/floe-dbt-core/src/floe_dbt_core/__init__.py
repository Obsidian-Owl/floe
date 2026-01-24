"""floe-dbt-core: DBT plugin using dbt-core Python API.

This package provides DBTCorePlugin, which wraps dbt-core's dbtRunner
for local development and CI/CD pipelines.

Note: dbtRunner is NOT thread-safe. For parallel execution, use floe-dbt-fusion.

Example:
    >>> from floe_dbt_core import DBTCorePlugin
    >>> plugin = DBTCorePlugin()
    >>> manifest = plugin.compile_project(
    ...     project_dir=Path("my_dbt_project"),
    ...     profiles_dir=Path("~/.dbt"),
    ...     target="dev"
    ... )
"""

from __future__ import annotations

from .errors import (
    DBTCompilationError,
    DBTConfigurationError,
    DBTError,
    DBTExecutionError,
    DBTLintError,
)
from .plugin import DBTCorePlugin
from .tracing import (
    TRACER_NAME,
    dbt_span,
    get_tracer,
    set_result_attributes,
    set_runtime_attributes,
)

__all__ = [
    "DBTCorePlugin",
    "DBTError",
    "DBTCompilationError",
    "DBTExecutionError",
    "DBTConfigurationError",
    "DBTLintError",
    # Tracing utilities
    "TRACER_NAME",
    "get_tracer",
    "dbt_span",
    "set_result_attributes",
    "set_runtime_attributes",
]
