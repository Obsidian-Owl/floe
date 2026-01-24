"""DBTCorePlugin implementation using dbt-core's dbtRunner.

This module provides the DBTCorePlugin class which implements the DBTPlugin
interface using dbt-core's Python API (dbtRunner). This is the default dbt
execution environment for local development.

Note: dbtRunner is NOT thread-safe. This plugin returns False from
supports_parallel_execution() to prevent concurrent execution issues.

Example:
    >>> from floe_dbt_core import DBTCorePlugin
    >>> plugin = DBTCorePlugin()
    >>> manifest_path = plugin.compile_project(
    ...     project_dir=Path("my_project"),
    ...     profiles_dir=Path("my_project"),
    ...     target="dev"
    ... )
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog
from floe_core.plugins.dbt import DBTPlugin, DBTRunResult, LintResult

from .callbacks import create_event_collector
from .errors import (
    DBTCompilationError,
    DBTConfigurationError,
    DBTExecutionError,
    parse_dbt_error_location,
)
from .tracing import (
    dbt_span,
    get_tracer,
    set_result_attributes,
    set_runtime_attributes,
)

# Lazy import dbtRunner to avoid import errors when dbt not installed
try:
    from dbt.cli.main import dbtRunner
    from dbt.version import get_installed_version

    DBT_AVAILABLE = True
except ImportError:
    DBT_AVAILABLE = False
    dbtRunner = None  # type: ignore[misc, assignment]
    get_installed_version = None  # type: ignore[misc, assignment]


logger = structlog.get_logger(__name__)


class DBTCorePlugin(DBTPlugin):
    """DBT plugin using dbt-core's dbtRunner for local execution.

    This plugin wraps dbt-core's Python API to provide dbt compilation
    and execution capabilities. It is NOT thread-safe due to dbtRunner
    limitations.

    Features:
        - Compile dbt projects (Jinja to SQL)
        - Run dbt models with select/exclude/full_refresh
        - Execute dbt tests
        - SQL linting via SQLFluff (when installed)
        - Retrieve dbt artifacts (manifest, run_results)

    Thread Safety:
        dbtRunner is NOT thread-safe. Multiple concurrent invocations
        can cause undefined behavior. Use DBTFusionPlugin for parallel
        execution requirements.

    Example:
        >>> plugin = DBTCorePlugin()
        >>> result = plugin.run_models(
        ...     project_dir=Path("my_dbt_project"),
        ...     profiles_dir=Path("~/.dbt"),
        ...     target="dev",
        ...     select="tag:daily"
        ... )
        >>> print(f"Ran {result.models_run} models")
    """

    @property
    def name(self) -> str:
        """Return plugin name."""
        return "core"

    @property
    def version(self) -> str:
        """Return plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return compatible floe API version."""
        return "1.0.0"

    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project and return path to manifest.json.

        Invokes `dbt compile` to parse Jinja templates and generate
        compiled SQL without executing against the database.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name (e.g., "dev", "prod").

        Returns:
            Path to compiled manifest.json.

        Raises:
            DBTCompilationError: If dbt compilation fails.
            DBTConfigurationError: If profiles.yml is invalid.
        """
        self._check_dbt_available()

        # Run dbt deps if packages.yml exists (FR-014)
        self._run_deps_if_needed(project_dir, profiles_dir, target)

        log = logger.bind(
            project_dir=str(project_dir),
            target=target,
        )
        log.info("dbt_compile_started")

        tracer = get_tracer()
        with dbt_span(
            tracer,
            "compile",
            project_dir=str(project_dir),
            profiles_dir=str(profiles_dir),
            target=target,
        ) as span:
            # Set runtime info
            metadata = self.get_runtime_metadata()
            set_runtime_attributes(
                span,
                runtime=metadata.get("runtime"),
                dbt_version=metadata.get("dbt_version"),
            )

            start_time = time.monotonic()

            # Build dbt command using helper (CMPLX-001)
            args = self._build_dbt_args(
                "compile",
                project_dir,
                profiles_dir,
                target,
            )

            # Execute dbt compile with event collector for structured errors
            collector = create_event_collector()
            dbt = dbtRunner(callbacks=[collector.callback])
            result = dbt.invoke(args)

            elapsed = time.monotonic() - start_time
            set_result_attributes(span, execution_time=elapsed)

            if not result.success:
                # Use collector's error summary for more structured error info
                error_summary = collector.get_error_summary()
                error_msg = error_summary or (
                    str(result.exception) if result.exception else "Unknown error"
                )
                file_path, line_number = parse_dbt_error_location(error_msg)

                # Log with structured event data
                log.error(
                    "dbt_compile_failed",
                    error=error_msg,
                    elapsed_seconds=elapsed,
                    error_count=len(collector.errors),
                    warning_count=len(collector.warnings),
                )

                raise DBTCompilationError(
                    message=error_msg,
                    file_path=file_path,
                    line_number=line_number,
                    original_message=error_msg,
                )

            manifest_path = project_dir / "target" / "manifest.json"
            log.info(
                "dbt_compile_completed",
                manifest_path=str(manifest_path),
                elapsed_seconds=elapsed,
            )

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
        """Execute dbt models.

        Invokes `dbt run` to execute selected models against the database.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax (e.g., "tag:daily", "stg_*").
            exclude: dbt exclusion syntax.
            full_refresh: If True, rebuild incremental models from scratch.

        Returns:
            DBTRunResult with execution status and artifact paths.

        Raises:
            DBTExecutionError: If dbt run fails.
        """
        self._check_dbt_available()

        log = logger.bind(
            project_dir=str(project_dir),
            target=target,
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
        )
        log.info("dbt_run_started")

        tracer = get_tracer()
        with dbt_span(
            tracer,
            "run",
            project_dir=str(project_dir),
            profiles_dir=str(profiles_dir),
            target=target,
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
        ) as span:
            # Set runtime info
            metadata = self.get_runtime_metadata()
            set_runtime_attributes(
                span,
                runtime=metadata.get("runtime"),
                dbt_version=metadata.get("dbt_version"),
            )

            start_time = time.monotonic()

            # Build dbt command using helper (CMPLX-002)
            args = self._build_dbt_args(
                "run",
                project_dir,
                profiles_dir,
                target,
                select=select,
                exclude=exclude,
                full_refresh=full_refresh,
            )

            # Execute dbt run with event collector for structured errors
            collector = create_event_collector()
            dbt = dbtRunner(callbacks=[collector.callback])
            result = dbt.invoke(args)

            elapsed = time.monotonic() - start_time

            if not result.success:
                # Use collector's error summary for more structured error info
                error_summary = collector.get_error_summary()
                error_msg = error_summary or (
                    str(result.exception) if result.exception else "Unknown error"
                )
                file_path, line_number = parse_dbt_error_location(error_msg)

                # Log with structured event data
                log.error(
                    "dbt_run_failed",
                    error=error_msg,
                    elapsed_seconds=elapsed,
                    error_count=len(collector.errors),
                    warning_count=len(collector.warnings),
                    failed_nodes=collector.get_failed_nodes(),
                )

                raise DBTExecutionError(
                    message=error_msg,
                    file_path=file_path,
                    line_number=line_number,
                    original_message=error_msg,
                )

            # Parse run results for model count
            run_results = self._load_run_results(project_dir)
            models_run = len(run_results.get("results", []))
            failures = sum(1 for r in run_results.get("results", []) if r.get("status") == "error")

            # Set result attributes on span
            set_result_attributes(
                span,
                models_run=models_run,
                failures=failures,
                execution_time=elapsed,
            )

            log.info(
                "dbt_run_completed",
                models_run=models_run,
                failures=failures,
                elapsed_seconds=elapsed,
            )

            return DBTRunResult(
                success=True,
                manifest_path=project_dir / "target" / "manifest.json",
                run_results_path=project_dir / "target" / "run_results.json",
                execution_time_seconds=elapsed,
                models_run=models_run,
                tests_run=0,
                failures=failures,
            )

    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult:
        """Execute dbt tests.

        Invokes `dbt test` to run schema and data tests.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax for tests.

        Returns:
            DBTRunResult with test results.

        Raises:
            DBTExecutionError: If dbt test fails.
        """
        self._check_dbt_available()

        log = logger.bind(
            project_dir=str(project_dir),
            target=target,
            select=select,
        )
        log.info("dbt_test_started")

        tracer = get_tracer()
        with dbt_span(
            tracer,
            "test",
            project_dir=str(project_dir),
            profiles_dir=str(profiles_dir),
            target=target,
            select=select,
        ) as span:
            # Set runtime info
            metadata = self.get_runtime_metadata()
            set_runtime_attributes(
                span,
                runtime=metadata.get("runtime"),
                dbt_version=metadata.get("dbt_version"),
            )

            start_time = time.monotonic()

            # Build dbt command using helper
            args = self._build_dbt_args(
                "test",
                project_dir,
                profiles_dir,
                target,
                select=select,
            )

            # Execute dbt test with event collector for structured errors
            collector = create_event_collector()
            dbt = dbtRunner(callbacks=[collector.callback])
            result = dbt.invoke(args)

            elapsed = time.monotonic() - start_time

            if not result.success:
                # Use collector's error summary for more structured error info
                error_summary = collector.get_error_summary()
                error_msg = error_summary or (
                    str(result.exception) if result.exception else "Unknown error"
                )

                # Log with structured event data
                log.error(
                    "dbt_test_failed",
                    error=error_msg,
                    elapsed_seconds=elapsed,
                    error_count=len(collector.errors),
                    warning_count=len(collector.warnings),
                    failed_nodes=collector.get_failed_nodes(),
                )

                raise DBTExecutionError(
                    message=error_msg,
                    original_message=error_msg,
                )

            # Parse run results for test count
            run_results = self._load_run_results(project_dir)
            tests_run = len(run_results.get("results", []))
            failures = sum(1 for r in run_results.get("results", []) if r.get("status") == "fail")

            # Set result attributes on span
            set_result_attributes(
                span,
                tests_run=tests_run,
                failures=failures,
                execution_time=elapsed,
            )

            log.info(
                "dbt_test_completed",
                tests_run=tests_run,
                failures=failures,
                elapsed_seconds=elapsed,
            )

            return DBTRunResult(
                success=failures == 0,
                manifest_path=project_dir / "target" / "manifest.json",
                run_results_path=project_dir / "target" / "run_results.json",
                execution_time_seconds=elapsed,
                models_run=0,
                tests_run=tests_run,
                failures=failures,
            )

    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> LintResult:
        """Lint SQL files with SQLFluff.

        Uses SQLFluff for dialect-aware SQL linting. The dialect is
        determined from the target's adapter type in profiles.yml.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name (used for dialect detection).
            fix: If True, auto-fix issues.

        Returns:
            LintResult with all detected issues.
        """
        from .linting import (
            get_adapter_from_profiles,
            get_sqlfluff_dialect,
            lint_sql_files,
        )

        tracer = get_tracer()
        with dbt_span(
            tracer,
            "lint",
            project_dir=str(project_dir),
            profiles_dir=str(profiles_dir),
            target=target,
            extra_attributes={"dbt.lint.fix": fix},
        ) as span:
            # Set runtime info
            metadata = self.get_runtime_metadata()
            set_runtime_attributes(
                span,
                runtime=metadata.get("runtime"),
                dbt_version=metadata.get("dbt_version"),
            )

            # Get adapter type from profiles.yml
            profile_name = self._get_profile_name(project_dir)
            adapter = get_adapter_from_profiles(
                profiles_dir=profiles_dir,
                profile_name=profile_name,
                target=target,
            )

            # Map adapter to SQLFluff dialect
            dialect = get_sqlfluff_dialect(adapter or "ansi")

            # Delegate to lint_sql_files
            result = lint_sql_files(
                project_dir=project_dir,
                dialect=dialect,
                fix=fix,
            )

            # Set result attributes
            set_result_attributes(
                span,
                files_checked=result.files_checked,
                files_fixed=result.files_fixed,
                issues_found=len(result.violations),
            )

            return result

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
            raise FileNotFoundError(
                f"manifest.json not found at {manifest_path}. Run 'dbt compile' first."
            )

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
        return self._load_run_results(project_dir)

    def supports_parallel_execution(self) -> bool:
        """Return False - dbtRunner is NOT thread-safe.

        dbt-core's dbtRunner uses global state that is not safe for
        concurrent access. Use DBTFusionPlugin for parallel execution.
        """
        return False

    def supports_sql_linting(self) -> bool:
        """Return True - SQLFluff integration available."""
        return True

    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime-specific metadata.

        Returns:
            Dictionary with runtime info including dbt version.
        """
        metadata: dict[str, Any] = {
            "runtime": "core",
            "thread_safe": False,
        }

        if DBT_AVAILABLE and get_installed_version:
            metadata["dbt_version"] = str(get_installed_version())

        return metadata

    def _check_dbt_available(self) -> None:
        """Check if dbt-core is installed.

        Raises:
            DBTConfigurationError: If dbt-core is not installed.
        """
        if not DBT_AVAILABLE:
            raise DBTConfigurationError(
                "dbt-core is not installed. Install with: pip install dbt-core"
            )

    def _load_run_results(self, project_dir: Path) -> dict[str, Any]:
        """Load run_results.json from target directory.

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Parsed run_results.json as dictionary.

        Raises:
            FileNotFoundError: If run_results doesn't exist.
        """
        run_results_path = project_dir / "target" / "run_results.json"
        if not run_results_path.exists():
            raise FileNotFoundError(
                f"run_results.json not found at {run_results_path}. "
                "Run 'dbt run' or 'dbt test' first."
            )

        return json.loads(run_results_path.read_text())

    def _get_profile_name(self, project_dir: Path) -> str:
        """Get profile name from dbt_project.yml.

        Args:
            project_dir: Path to dbt project directory.

        Returns:
            Profile name from dbt_project.yml, or "default" if not found.
        """
        import yaml

        project_file = project_dir / "dbt_project.yml"
        if not project_file.exists():
            return "default"

        try:
            with project_file.open() as f:
                project_config = yaml.safe_load(f)
            return project_config.get("profile", "default")
        except Exception:
            return "default"

    def _build_dbt_args(
        self,
        command: str,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        *,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> list[str]:
        """Build dbt command arguments.

        Centralizes argument building to reduce code duplication (CMPLX-001).

        Args:
            command: dbt command (compile, run, test).
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.
            select: dbt selection syntax.
            exclude: dbt exclusion syntax.
            full_refresh: If True, rebuild incremental models.

        Returns:
            List of command arguments for dbtRunner.invoke().
        """
        args = [
            command,
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(profiles_dir),
            "--target",
            target,
        ]

        if select:
            args.extend(["--select", select])
        if exclude:
            args.extend(["--exclude", exclude])
        if full_refresh:
            args.append("--full-refresh")

        return args

    def _run_deps_if_needed(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> bool:
        """Run dbt deps if packages.yml exists.

        Automatically installs dbt packages defined in packages.yml
        before compilation. This ensures dependencies are available.

        Args:
            project_dir: Path to dbt project directory.
            profiles_dir: Path to directory containing profiles.yml.
            target: dbt target name.

        Returns:
            True if deps was run, False if packages.yml doesn't exist.

        Raises:
            DBTExecutionError: If dbt deps fails.

        Requirements:
            FR-014: Automatic dbt deps execution
        """
        packages_yml = project_dir / "packages.yml"
        packages_yaml = project_dir / "packages.yaml"

        # Check if packages file exists (either .yml or .yaml)
        if not packages_yml.exists() and not packages_yaml.exists():
            return False

        log = logger.bind(
            project_dir=str(project_dir),
            target=target,
        )
        log.info("dbt_deps_started", reason="packages.yml exists")

        tracer = get_tracer()
        with dbt_span(
            tracer,
            "deps",
            project_dir=str(project_dir),
            profiles_dir=str(profiles_dir),
            target=target,
        ) as span:
            # Set runtime info
            metadata = self.get_runtime_metadata()
            set_runtime_attributes(
                span,
                runtime=metadata.get("runtime"),
                dbt_version=metadata.get("dbt_version"),
            )

            # Build dbt deps command
            args = [
                "deps",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(profiles_dir),
            ]

            # Execute dbt deps with event collector
            collector = create_event_collector()
            dbt = dbtRunner(callbacks=[collector.callback])
            result = dbt.invoke(args)

            if not result.success:
                error_summary = collector.get_error_summary()
                error_msg = error_summary or (
                    str(result.exception) if result.exception else "Unknown error"
                )

                log.error(
                    "dbt_deps_failed",
                    error=error_msg,
                    error_count=len(collector.errors),
                )

                raise DBTExecutionError(
                    message=f"dbt deps failed: {error_msg}",
                    original_message=error_msg,
                )

            log.info("dbt_deps_completed")
            return True
