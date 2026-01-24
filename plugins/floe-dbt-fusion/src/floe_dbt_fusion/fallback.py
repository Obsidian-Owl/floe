"""Automatic fallback mechanism for dbt Fusion plugin (FR-021).

This module provides automatic fallback to dbt-core when:
1. Fusion CLI binary is not found
2. Rust adapter is unavailable for the target database

The fallback mechanism allows the plugin to gracefully degrade to
dbt-core while maintaining the same interface.

Functions:
    check_fallback_available: Check if floe-dbt-core is installed.
    create_fallback_plugin: Create a FallbackPlugin if needed.
    get_best_plugin: Get the best available plugin for an adapter.

Classes:
    FallbackPlugin: Wrapper that delegates to DBTCorePlugin.

Example:
    >>> from floe_dbt_fusion.fallback import get_best_plugin
    >>> plugin = get_best_plugin(adapter="bigquery")
    >>> plugin.name
    'core'  # Falls back to dbt-core for unsupported adapters

Requirements:
    FR-021: Automatic fallback when Rust adapters unavailable
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from .detection import check_adapter_available, detect_fusion_binary
from .errors import DBTAdapterUnavailableError, check_fallback_available

if TYPE_CHECKING:
    from floe_core.plugins.dbt import DBTRunResult, LintResult

logger = structlog.get_logger(__name__)


class FallbackPlugin:
    """Wrapper plugin that delegates to DBTCorePlugin.

    FallbackPlugin provides the same interface as DBTFusionPlugin but
    delegates all operations to an underlying DBTCorePlugin instance.
    This is used when Fusion is unavailable or adapter is unsupported.

    Attributes:
        core_plugin: The wrapped DBTCorePlugin instance.

    Example:
        >>> from floe_dbt_core import DBTCorePlugin
        >>> core = DBTCorePlugin()
        >>> fallback = FallbackPlugin(core_plugin=core)
        >>> fallback.name
        'core'
    """

    def __init__(self, core_plugin: Any) -> None:
        """Initialize FallbackPlugin with a core plugin.

        Args:
            core_plugin: DBTCorePlugin instance to delegate to.
        """
        self._core_plugin = core_plugin

    @property
    def name(self) -> str:
        """Plugin identifier (delegated from core).

        Returns:
            The wrapped core plugin's name.
        """
        return self._core_plugin.name

    @property
    def version(self) -> str:
        """Plugin version (delegated from core).

        Returns:
            The wrapped core plugin's version.
        """
        return self._core_plugin.version

    @property
    def floe_api_version(self) -> str:
        """Compatible floe API version.

        Returns:
            The wrapped core plugin's API version.
        """
        return self._core_plugin.floe_api_version

    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project (delegated to core).

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.

        Returns:
            Path to compiled manifest.json.
        """
        return self._core_plugin.compile_project(
            project_dir,
            profiles_dir,
            target,
        )

    def run_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTRunResult:
        """Execute dbt models (delegated to core).

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax.
            exclude: dbt exclusion syntax.
            full_refresh: If True, rebuild incremental models.

        Returns:
            DBTRunResult with execution status.
        """
        return self._core_plugin.run_models(
            project_dir,
            profiles_dir,
            target,
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
        )

    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult:
        """Execute dbt tests (delegated to core).

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax for tests.

        Returns:
            DBTRunResult with test results.
        """
        return self._core_plugin.test_models(
            project_dir,
            profiles_dir,
            target,
            select=select,
        )

    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> LintResult:
        """Lint SQL files (delegated to core).

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            fix: If True, auto-fix issues.

        Returns:
            LintResult with detected issues.
        """
        return self._core_plugin.lint_project(
            project_dir,
            profiles_dir,
            target,
            fix=fix,
        )

    def get_manifest(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt manifest.json (delegated to core).

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Parsed manifest.json as dictionary.
        """
        return self._core_plugin.get_manifest(project_dir)

    def get_run_results(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt run_results.json (delegated to core).

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Parsed run_results.json as dictionary.
        """
        return self._core_plugin.get_run_results(project_dir)

    def supports_parallel_execution(self) -> bool:
        """Indicate if parallel execution is supported.

        dbt-core is NOT thread-safe, so returns False.

        Returns:
            False - dbt-core is not thread-safe.
        """
        return False

    def supports_sql_linting(self) -> bool:
        """Indicate if SQL linting is supported (delegated).

        Returns:
            Whether the core plugin supports linting.
        """
        return self._core_plugin.supports_sql_linting()

    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime metadata with fallback info.

        Returns:
            Dictionary with runtime information including fallback flag.
        """
        metadata = self._core_plugin.get_runtime_metadata()
        metadata["fallback"] = True
        return metadata


def create_fallback_plugin(adapter: str) -> FallbackPlugin | None:
    """Create a FallbackPlugin if Rust adapter is unavailable.

    Checks if the specified adapter is supported by Fusion. If not,
    creates a FallbackPlugin that delegates to dbt-core.

    Args:
        adapter: The adapter/database type (e.g., "bigquery", "duckdb").

    Returns:
        FallbackPlugin if adapter unsupported, None if Fusion can handle it.

    Raises:
        DBTAdapterUnavailableError: If adapter unsupported and no fallback.

    Requirements:
        FR-021: Automatic fallback for unsupported adapters

    Example:
        >>> fallback = create_fallback_plugin("bigquery")
        >>> if fallback:
        ...     fallback.compile_project(...)
    """
    # Check if adapter is supported by Fusion
    if check_adapter_available(adapter):
        logger.debug("adapter_supported_by_fusion", adapter=adapter)
        return None

    logger.info("adapter_not_supported_by_fusion", adapter=adapter)

    # Check if fallback is available
    if not check_fallback_available():
        raise DBTAdapterUnavailableError(
            adapter=adapter,
            fallback_available=False,
        )

    # Import and create core plugin
    try:
        from floe_dbt_core import DBTCorePlugin

        core_plugin = DBTCorePlugin()
        logger.info("fallback_to_dbt_core", adapter=adapter)
        return FallbackPlugin(core_plugin=core_plugin)

    except ImportError as e:
        raise DBTAdapterUnavailableError(
            adapter=adapter,
            fallback_available=False,
            message=f"Failed to import floe-dbt-core: {e}",
        ) from e


def get_best_plugin(adapter: str) -> Any:
    """Get the best available plugin for an adapter.

    Attempts to use DBTFusionPlugin if:
    1. Fusion CLI binary is found
    2. Rust adapter is available for the target

    Otherwise, falls back to DBTCorePlugin if installed.

    Args:
        adapter: The adapter/database type (e.g., "duckdb", "bigquery").

    Returns:
        DBTPlugin instance (either DBTFusionPlugin or FallbackPlugin).

    Raises:
        DBTAdapterUnavailableError: If neither Fusion nor core available.

    Requirements:
        FR-020: Detect Fusion CLI binary
        FR-021: Automatic fallback for unsupported adapters

    Example:
        >>> plugin = get_best_plugin(adapter="duckdb")
        >>> plugin.name
        'fusion'  # Fusion available for DuckDB

        >>> plugin = get_best_plugin(adapter="bigquery")
        >>> plugin.name
        'core'  # Falls back for unsupported adapter
    """
    log = logger.bind(adapter=adapter)

    # Check if Fusion binary is available
    binary_path = detect_fusion_binary()
    if binary_path is None:
        log.info("fusion_binary_not_found")

        # Check fallback
        if not check_fallback_available():
            raise DBTAdapterUnavailableError(
                adapter=adapter,
                fallback_available=False,
                message="Fusion CLI not found and floe-dbt-core not installed",
            )

        # Use core as fallback
        try:
            from floe_dbt_core import DBTCorePlugin

            core_plugin = DBTCorePlugin()
            log.info("using_dbt_core_fallback", reason="fusion_binary_not_found")
            return FallbackPlugin(core_plugin=core_plugin)

        except ImportError as e:
            raise DBTAdapterUnavailableError(
                adapter=adapter,
                fallback_available=False,
                message=f"Failed to import floe-dbt-core: {e}",
            ) from e

    # Check if adapter is supported
    if not check_adapter_available(adapter):
        log.info("adapter_not_supported_by_fusion", adapter=adapter)

        # Check fallback
        if not check_fallback_available():
            raise DBTAdapterUnavailableError(
                adapter=adapter,
                fallback_available=False,
            )

        # Use core as fallback
        try:
            from floe_dbt_core import DBTCorePlugin

            core_plugin = DBTCorePlugin()
            log.info("using_dbt_core_fallback", reason="adapter_not_supported")
            return FallbackPlugin(core_plugin=core_plugin)

        except ImportError as e:
            raise DBTAdapterUnavailableError(
                adapter=adapter,
                fallback_available=False,
                message=f"Failed to import floe-dbt-core: {e}",
            ) from e

    # Use Fusion
    from .plugin import DBTFusionPlugin

    log.info("using_fusion_plugin")
    return DBTFusionPlugin()


__all__ = [
    "FallbackPlugin",
    "create_fallback_plugin",
    "get_best_plugin",
]
