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

# Re-export shared types from floe-core (ARCH-001: canonical location)
from floe_core.plugins.dbt import (
    DBTCompilationError,
    DBTError,
    DBTExecutionError,
    LintResult,
    LintViolation,
)

from .callbacks import (
    DBTEvent,
    DBTEventCollector,
    DBTEventLevel,
    create_event_collector,
)

# Plugin-specific errors (extend floe-core base classes)
from .errors import (
    DBTConfigurationError,
    DBTLintError,
    parse_dbt_error_location,
)
from .linting import (
    DEFAULT_DIALECT,
    DIALECT_MAP,
    get_adapter_from_profiles,
    get_sqlfluff_dialect,
    lint_sql_files,
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
    # Error classes (re-exported from floe-core for backwards compatibility)
    "DBTError",
    "DBTCompilationError",
    "DBTExecutionError",
    # Plugin-specific error classes
    "DBTConfigurationError",
    "DBTLintError",
    "parse_dbt_error_location",
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
    # Linting utilities (re-exported from floe-core)
    "LintResult",
    "LintViolation",
    "get_sqlfluff_dialect",
    "lint_sql_files",
    "get_adapter_from_profiles",
    "DIALECT_MAP",
    "DEFAULT_DIALECT",
]
