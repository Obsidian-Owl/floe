"""DBTFusionPlugin - High-performance dbt plugin using Fusion CLI.

This module provides DBTFusionPlugin, which implements the DBTPlugin interface
using the dbt Fusion CLI (dbt-sa-cli). Fusion is a Rust-based dbt runtime that
provides ~30x faster parsing and thread-safe execution.

Features:
- Thread-safe (Rust memory safety) - supports_parallel_execution() returns True
- ~30x faster parsing than dbt-core for large projects
- Built-in static analysis for SQL linting
- Automatic fallback to dbt-core when Rust adapters unavailable

Supported Adapters:
- DuckDB (duckdb-rs)
- Snowflake (snowflake-connector-rust)

Requirements:
    FR-017: Use subprocess to invoke dbt Fusion CLI
    FR-018: supports_parallel_execution() returns True
    FR-019: Built-in static analysis for linting

Example:
    >>> from floe_dbt_fusion import DBTFusionPlugin
    >>> plugin = DBTFusionPlugin()
    >>> manifest = plugin.compile_project(
    ...     project_dir=Path("my_dbt_project"),
    ...     profiles_dir=Path("~/.dbt"),
    ...     target="dev"
    ... )

See Also:
    - floe_core.plugins.dbt.DBTPlugin: Base class interface
    - floe_dbt_core.DBTCorePlugin: dbt-core implementation
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import structlog

# Import from floe-core ABCs only (ARCH-001: avoid plugin cross-imports)
from floe_core.plugins.dbt import (
    DBTCompilationError,
    DBTExecutionError,
    DBTPlugin,
    DBTRunResult,
    LintResult,
    LintViolation,
)

from .detection import detect_fusion, detect_fusion_binary
from .errors import DBTFusionNotFoundError

logger = structlog.get_logger(__name__)

# Plugin version
PLUGIN_VERSION = "0.1.0"

# floe API version this plugin is compatible with
FLOE_API_VERSION = "1.0.0"


class DBTFusionPlugin(DBTPlugin):
    """High-performance dbt plugin using Fusion CLI.

    DBTFusionPlugin implements the DBTPlugin interface using the Rust-based
    dbt Fusion CLI for high-performance dbt execution. The plugin invokes
    the Fusion CLI via subprocess.

    Key Characteristics:
    - Thread-safe: Rust memory safety allows parallel execution
    - Fast: ~30x faster parsing than dbt-core for large projects
    - Built-in linting: Static analysis without SQLFluff dependency

    Attributes:
        name: Plugin identifier ("fusion")
        version: Plugin version (e.g., "0.1.0")
        floe_api_version: Compatible floe API version

    Example:
        >>> plugin = DBTFusionPlugin()
        >>> if plugin.supports_parallel_execution():
        ...     # Safe to use in ThreadPoolExecutor
        ...     with ThreadPoolExecutor() as executor:
        ...         futures = [executor.submit(plugin.run_models, ...) for ...]

    Requirements:
        FR-017: subprocess invocation
        FR-018: Thread-safe parallel execution
        FR-019: Built-in static analysis
    """

    @property
    def name(self) -> str:
        """Plugin identifier.

        Returns:
            "fusion" - identifies this as the Fusion-based plugin.
        """
        return "fusion"

    @property
    def version(self) -> str:
        """Plugin version.

        Returns:
            Plugin version string (e.g., "0.1.0").
        """
        return PLUGIN_VERSION

    @property
    def floe_api_version(self) -> str:
        """Compatible floe API version.

        Returns:
            The floe API version this plugin is compatible with.
        """
        return FLOE_API_VERSION

    def _get_binary_path(self) -> Path:
        """Get path to Fusion CLI binary.

        Returns:
            Path to dbt-sa-cli binary.

        Raises:
            DBTFusionNotFoundError: If binary not found.
        """
        binary_path = detect_fusion_binary()
        if binary_path is None:
            raise DBTFusionNotFoundError(
                searched_paths=["/usr/local/bin", "~/.local/bin", "PATH"],
            )
        return binary_path

    def _run_fusion_command(
        self,
        command: str,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        *,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Run a Fusion CLI command.

        Args:
            command: dbt command (compile, run, test, etc.)
            project_dir: Path to dbt project.
            profiles_dir: Path to profiles directory.
            target: dbt target name.
            select: Optional select pattern.
            exclude: Optional exclude pattern.
            full_refresh: Whether to use --full-refresh.

        Returns:
            CompletedProcess with command result.

        Raises:
            DBTFusionNotFoundError: If Fusion CLI not found.
        """
        binary_path = self._get_binary_path()

        cmd = [
            str(binary_path),
            command,
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(profiles_dir),
            "--target",
            target,
        ]

        if select:
            cmd.extend(["--select", select])
        if exclude:
            cmd.extend(["--exclude", exclude])
        if full_refresh:
            cmd.append("--full-refresh")

        log = logger.bind(
            command=command,
            project_dir=str(project_dir),
            target=target,
        )
        log.debug("fusion_command_started", cmd=cmd)

        # PERF-001: Add timeout to prevent hanging subprocess (5 min default)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,  # 5 minute timeout for dbt commands
            )
        except subprocess.TimeoutExpired as err:
            log.error("fusion_command_timeout", command=command, timeout=300)
            raise DBTExecutionError(
                message=f"Fusion {command} command timed out after 300 seconds",
            ) from err

        log.debug(
            "fusion_command_completed",
            returncode=result.returncode,
        )

        return result

    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project using Fusion CLI.

        Invokes `dbt-sa-cli compile` via subprocess to compile the
        dbt project and generate manifest.json.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name (e.g., "dev", "prod").

        Returns:
            Path to compiled manifest.json.

        Raises:
            DBTFusionNotFoundError: If Fusion CLI not found.
            DBTCompilationError: If compilation fails.

        Requirements:
            FR-017: subprocess invocation
        """
        result = self._run_fusion_command(
            "compile",
            project_dir,
            profiles_dir,
            target,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise DBTCompilationError(
                message=f"Fusion compile failed: {error_msg}",
                original_message=result.stderr,
            )

        manifest_path = project_dir / "target" / "manifest.json"
        return manifest_path

    def run_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTRunResult:
        """Execute dbt models using Fusion CLI.

        Invokes `dbt-sa-cli run` via subprocess to execute models.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax.
            exclude: dbt exclusion syntax.
            full_refresh: If True, rebuild incremental models.

        Returns:
            DBTRunResult with execution status.

        Raises:
            DBTFusionNotFoundError: If Fusion CLI not found.
            DBTExecutionError: If execution fails.

        Requirements:
            FR-017: subprocess invocation
        """
        result = self._run_fusion_command(
            "run",
            project_dir,
            profiles_dir,
            target,
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise DBTExecutionError(
                message=f"Fusion run failed: {error_msg}",
                original_message=result.stderr,
            )

        # Parse run_results.json for result details
        run_results_path = project_dir / "target" / "run_results.json"
        manifest_path = project_dir / "target" / "manifest.json"

        models_run = 0
        failures = 0
        execution_time = 0.0

        if run_results_path.exists():
            run_results = json.loads(run_results_path.read_text())
            results = run_results.get("results", [])
            models_run = len(results)
            failures = sum(1 for r in results if r.get("status") not in ("success", "pass"))
            execution_time = run_results.get("elapsed_time", 0.0)

        return DBTRunResult(
            success=True,
            manifest_path=manifest_path,
            run_results_path=run_results_path,
            models_run=models_run,
            failures=failures,
            execution_time_seconds=execution_time,
        )

    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult:
        """Execute dbt tests using Fusion CLI.

        Invokes `dbt-sa-cli test` via subprocess.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax for tests.

        Returns:
            DBTRunResult with test results.

        Raises:
            DBTFusionNotFoundError: If Fusion CLI not found.
            DBTExecutionError: If test execution fails.

        Requirements:
            FR-017: subprocess invocation
        """
        result = self._run_fusion_command(
            "test",
            project_dir,
            profiles_dir,
            target,
            select=select,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise DBTExecutionError(
                message=f"Fusion test failed: {error_msg}",
                original_message=result.stderr,
            )

        # Parse run_results.json for test details
        run_results_path = project_dir / "target" / "run_results.json"
        manifest_path = project_dir / "target" / "manifest.json"

        tests_run = 0
        failures = 0
        execution_time = 0.0

        if run_results_path.exists():
            run_results = json.loads(run_results_path.read_text())
            results = run_results.get("results", [])
            tests_run = len(results)
            failures = sum(1 for r in results if r.get("status") not in ("success", "pass"))
            execution_time = run_results.get("elapsed_time", 0.0)

        return DBTRunResult(
            success=failures == 0,
            manifest_path=manifest_path,
            run_results_path=run_results_path,
            tests_run=tests_run,
            failures=failures,
            execution_time_seconds=execution_time,
        )

    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> LintResult:
        """Lint SQL files using Fusion's static analysis.

        Fusion includes built-in static analysis for SQL linting,
        eliminating the need for external tools like SQLFluff.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            fix: If True, auto-fix issues (if supported).

        Returns:
            LintResult with detected issues.

        Requirements:
            FR-019: Built-in static analysis
        """
        # Fusion static analysis command
        cmd_args = ["lint", "--format", "json"]
        if fix:
            cmd_args.append("--fix")

        binary_path = self._get_binary_path()

        cmd = [
            str(binary_path),
            *cmd_args,
            "--project-dir",
            str(project_dir),
        ]

        # PERF-002: Add timeout to prevent hanging subprocess (2 min for linting)
        log = logger.bind(project_dir=str(project_dir), fix=fix)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,  # 2 minute timeout for linting
            )
        except subprocess.TimeoutExpired:
            log.error("fusion_lint_timeout", timeout=120)
            # Return empty result on timeout rather than raising
            return LintResult(
                success=False,
                violations=[],
                files_checked=0,
                files_fixed=0,
            )

        violations: list[LintViolation] = []
        files_checked = 0
        files_fixed = 0

        if result.returncode == 0 and result.stdout:
            try:
                output = json.loads(result.stdout)
                raw_violations = output.get("violations", [])
                files_checked = output.get("files_analyzed", 0)
                files_fixed = output.get("files_fixed", 0) if fix else 0

                # Convert raw violations to LintViolation models
                for v in raw_violations:
                    violations.append(
                        LintViolation(
                            file_path=v.get("file", ""),
                            line=max(1, v.get("line", 1)),
                            column=v.get("column", 0),
                            code=v.get("rule", "UNKNOWN"),
                            message=v.get("message", ""),
                            severity=v.get("severity", "warning"),
                        )
                    )
            except json.JSONDecodeError:
                pass

        return LintResult(
            success=len(violations) == 0,
            violations=violations,
            files_checked=files_checked,
            files_fixed=files_fixed,
        )

    def get_manifest(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt manifest.json.

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Parsed manifest.json as dictionary.

        Raises:
            FileNotFoundError: If manifest doesn't exist.
        """
        manifest_path = project_dir / "target" / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        return json.loads(manifest_path.read_text())

    def get_run_results(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt run_results.json.

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Parsed run_results.json as dictionary.

        Raises:
            FileNotFoundError: If run_results doesn't exist.
        """
        run_results_path = project_dir / "target" / "run_results.json"
        if not run_results_path.exists():
            raise FileNotFoundError(f"Run results not found: {run_results_path}")
        return json.loads(run_results_path.read_text())

    def supports_parallel_execution(self) -> bool:
        """Indicate Fusion supports parallel model execution.

        Fusion is Rust-based and thread-safe, supporting parallel
        execution in ThreadPoolExecutor or similar contexts.

        Returns:
            True - Fusion is thread-safe.

        Requirements:
            FR-018: Thread-safe execution
        """
        return True

    def supports_sql_linting(self) -> bool:
        """Indicate Fusion provides SQL linting.

        Fusion includes built-in static analysis for SQL linting.

        Returns:
            True - lint_project() is implemented.

        Requirements:
            FR-019: Built-in static analysis
        """
        return True

    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime metadata for observability.

        Returns:
            Dictionary with Fusion runtime information.
        """
        info = detect_fusion()

        return {
            "runtime": "fusion",
            "thread_safe": True,
            "fusion_version": info.version,
            "adapters_available": info.adapters_available,
        }


__all__ = ["DBTFusionPlugin"]
