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

from .callbacks import (
    DBTEvent,
    DBTEventCollector,
    DBTEventLevel,
    create_event_collector,
)
from .errors import (
    DBTCompilationError,
    DBTConfigurationError,
    DBTError,
    DBTExecutionError,
    DBTLintError,
)
from .plugin import DBTCorePlugin
from .linting import (
    DEFAULT_DIALECT,
    DIALECT_MAP,
    LintResult,
    LintViolation,
    get_adapter_from_profiles,
    get_sqlfluff_dialect,
    lint_sql_files,
)
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
    # Callback utilities
    "DBTEvent",
    "DBTEventLevel",
    "DBTEventCollector",
    "create_event_collector",
    # Tracing utilities
    "TRACER_NAME",
    "get_tracer",
    "dbt_span",
    "set_result_attributes",
    "set_runtime_attributes",
    # Linting utilities
    "LintResult",
    "LintViolation",
    "get_sqlfluff_dialect",
    "lint_sql_files",
    "get_adapter_from_profiles",
    "DIALECT_MAP",
    "DEFAULT_DIALECT",
]
