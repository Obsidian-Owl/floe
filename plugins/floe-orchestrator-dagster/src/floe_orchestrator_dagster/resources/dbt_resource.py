"""DBTResource - Dagster ConfigurableResource for DBT plugin integration.

This module provides a Dagster-specific resource for DBT operations within
asset materialization. It loads DBTPlugin implementations from the floe
plugin registry and delegates all dbt operations to the plugin.

Example:
    >>> from floe_orchestrator_dagster.resources import DBTResource
    >>>
    >>> @asset
    >>> def my_dbt_models(dbt: DBTResource) -> None:
    ...     result = dbt.run_models(select="tag:daily")
    ...     assert result.success
    >>>
    >>> defs = Definitions(
    ...     assets=[my_dbt_models],
    ...     resources={
    ...         "dbt": DBTResource(
    ...             plugin_name="core",
    ...             project_dir="/path/to/dbt/project",
    ...             profiles_dir="/path/to/profiles",
    ...             target="dev",
    ...         ),
    ...     },
    ... )

Requirements:
    FR-037: DBTResource MUST be a Dagster ConfigurableResource
    FR-030: DBTResource MUST load DBTPlugin from registry
    FR-031: DBTResource MUST delegate to plugin methods
    FR-032: DBTResource MUST pass select/exclude patterns

See Also:
    - specs/5a-dbt-plugin/spec.md
    - packages/floe-core/src/floe_core/plugins/dbt.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from dagster import ConfigurableResource
from pydantic import Field, PrivateAttr

if TYPE_CHECKING:
    from floe_core.plugins.dbt import DBTPlugin, DBTRunResult, LintResult

logger = structlog.get_logger(__name__)


def load_dbt_plugin(plugin_name: str) -> DBTPlugin:
    """Load DBTPlugin from registry by name.

    Uses floe plugin registry to discover and load dbt plugins
    registered via entry points.

    Args:
        plugin_name: Plugin name (e.g., "core", "fusion").

    Returns:
        DBTPlugin instance.

    Raises:
        ValueError: If plugin not found in registry.
    """
    from floe_core.plugin_registry import PluginRegistry
    from floe_core.plugin_types import PluginType

    registry = PluginRegistry()
    plugins = registry.discover_plugins(PluginType.DBT)

    for plugin in plugins:
        if plugin.name == plugin_name:
            return plugin

    available = [p.name for p in plugins]
    msg = f"Unknown plugin: {plugin_name}. Available: {available}"
    raise ValueError(msg)


class DBTResource(ConfigurableResource):
    """Dagster ConfigurableResource for DBT operations.

    Provides a Dagster resource that wraps DBTPlugin for use in asset
    materialization. The resource loads the appropriate plugin at runtime
    based on configuration.

    This resource is Dagster-specific. It enables dependency injection
    of dbt capabilities into Dagster assets while abstracting the
    underlying dbt execution environment (core, fusion, etc.).

    Attributes:
        plugin_name: DBT plugin to use ("core" or "fusion"). Defaults to "core".
        project_dir: Path to dbt project directory.
        profiles_dir: Path to directory containing profiles.yml.
        target: dbt target name (e.g., "dev", "prod"). Defaults to "dev".

    Example:
        >>> @asset
        >>> def staging_models(dbt: DBTResource) -> None:
        ...     result = dbt.run_models(select="staging.*")
        ...     if not result.success:
        ...         raise Exception(f"dbt run failed: {result.failures} failures")

    Requirements:
        FR-037: ConfigurableResource for Dagster integration
        FR-030: Plugin loading from registry
        FR-031: Method delegation to plugin
        FR-032: Select/exclude pattern support
    """

    plugin_name: str = Field(
        default="core",
        description="DBT plugin to use ('core' for dbt-core, 'fusion' for dbt-fusion)",
    )
    project_dir: str = Field(
        default="",
        description="Path to dbt project directory",
    )
    profiles_dir: str = Field(
        default="",
        description="Path to directory containing profiles.yml",
    )
    target: str = Field(
        default="dev",
        description="dbt target name (e.g., 'dev', 'prod')",
    )

    # Private cached plugin instance
    _plugin: DBTPlugin | None = PrivateAttr(default=None)

    def get_plugin(self) -> DBTPlugin:
        """Load and cache DBTPlugin from registry.

        Loads the plugin on first call and caches for subsequent calls.
        Plugin is loaded by name from the floe plugin registry.

        Returns:
            DBTPlugin instance for dbt operations.

        Raises:
            ValueError: If plugin_name not found in registry.

        Requirements:
            FR-030: Load DBTPlugin from registry
        """
        if self._plugin is None:
            log = logger.bind(plugin_name=self.plugin_name)
            log.debug("loading_dbt_plugin")

            self._plugin = load_dbt_plugin(self.plugin_name)

            log.info(
                "dbt_plugin_loaded",
                plugin_version=self._plugin.version,
                parallel_execution=self._plugin.supports_parallel_execution(),
            )

        return self._plugin

    def compile(self) -> Path:
        """Compile dbt project and return manifest path.

        Delegates to plugin.compile_project() with configured paths.

        Returns:
            Path to compiled manifest.json.

        Raises:
            DBTCompilationError: If compilation fails.

        Requirements:
            FR-031: Method delegation to plugin
        """
        plugin = self.get_plugin()

        log = logger.bind(
            plugin=self.plugin_name,
            project_dir=self.project_dir,
            target=self.target,
        )
        log.info("dbt_compile_started")

        result = plugin.compile_project(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
        )

        log.info("dbt_compile_completed", manifest_path=str(result))
        return result

    def run_models(
        self,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTRunResult:
        """Execute dbt models.

        Delegates to plugin.run_models() with configured paths and
        provided selection patterns.

        Args:
            select: dbt selection syntax (e.g., "tag:daily", "staging.*").
            exclude: dbt exclusion syntax.
            full_refresh: Rebuild incremental models from scratch.

        Returns:
            DBTRunResult with execution status.

        Raises:
            DBTExecutionError: If execution fails.

        Requirements:
            FR-031: Method delegation to plugin
            FR-032: Select/exclude pattern support
        """
        plugin = self.get_plugin()

        log = logger.bind(
            plugin=self.plugin_name,
            project_dir=self.project_dir,
            target=self.target,
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
        )
        log.info("dbt_run_started")

        result = plugin.run_models(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
        )

        log.info(
            "dbt_run_completed",
            success=result.success,
            models_run=result.models_run,
            failures=result.failures,
        )
        return result

    def test_models(self, select: str | None = None) -> DBTRunResult:
        """Execute dbt tests.

        Delegates to plugin.test_models() with configured paths.

        Args:
            select: dbt selection syntax for tests.

        Returns:
            DBTRunResult with test results.

        Raises:
            DBTExecutionError: If test execution fails.

        Requirements:
            FR-031: Method delegation to plugin
            FR-032: Select pattern support
        """
        plugin = self.get_plugin()

        log = logger.bind(
            plugin=self.plugin_name,
            project_dir=self.project_dir,
            target=self.target,
            select=select,
        )
        log.info("dbt_test_started")

        result = plugin.test_models(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
            select=select,
        )

        log.info(
            "dbt_test_completed",
            success=result.success,
            tests_run=result.tests_run,
            failures=result.failures,
        )
        return result

    def lint_project(self, fix: bool = False) -> LintResult:
        """Lint SQL files in dbt project.

        Delegates to plugin.lint_project() with configured paths.

        Args:
            fix: Auto-fix issues if linter supports it.

        Returns:
            LintResult with linting issues.

        Requirements:
            FR-031: Method delegation to plugin
        """
        plugin = self.get_plugin()

        log = logger.bind(
            plugin=self.plugin_name,
            project_dir=self.project_dir,
            target=self.target,
            fix=fix,
        )
        log.info("dbt_lint_started")

        result = plugin.lint_project(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
            fix=fix,
        )

        log.info(
            "dbt_lint_completed",
            success=result.success,
            files_checked=result.files_checked,
            issues_found=len(result.issues),
        )
        return result

    def get_manifest(self) -> dict[str, Any]:
        """Retrieve dbt manifest.json.

        Delegates to plugin.get_manifest().

        Returns:
            Parsed manifest.json as dictionary.

        Raises:
            FileNotFoundError: If manifest doesn't exist.

        Requirements:
            FR-031: Method delegation to plugin
        """
        plugin = self.get_plugin()
        return plugin.get_manifest(Path(self.project_dir))

    def get_run_results(self) -> dict[str, Any]:
        """Retrieve dbt run_results.json.

        Delegates to plugin.get_run_results().

        Returns:
            Parsed run_results.json as dictionary.

        Raises:
            FileNotFoundError: If run_results doesn't exist.

        Requirements:
            FR-031: Method delegation to plugin
        """
        plugin = self.get_plugin()
        return plugin.get_run_results(Path(self.project_dir))

    def supports_parallel_execution(self) -> bool:
        """Check if plugin supports parallel execution.

        Returns:
            True if plugin is thread-safe for parallel execution.

        Requirements:
            FR-031: Method delegation to plugin
        """
        plugin = self.get_plugin()
        return plugin.supports_parallel_execution()

    def supports_sql_linting(self) -> bool:
        """Check if plugin supports SQL linting.

        Returns:
            True if lint_project() is implemented.

        Requirements:
            FR-031: Method delegation to plugin
        """
        plugin = self.get_plugin()
        return plugin.supports_sql_linting()

    def get_runtime_metadata(self) -> dict[str, Any]:
        """Get runtime metadata from plugin.

        Returns:
            Dictionary with runtime info (dbt version, etc.).

        Requirements:
            FR-031: Method delegation to plugin
        """
        plugin = self.get_plugin()
        return plugin.get_runtime_metadata()


__all__ = [
    "DBTResource",
    "load_dbt_plugin",
]
