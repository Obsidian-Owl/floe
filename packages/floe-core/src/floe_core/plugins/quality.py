"""QualityPlugin ABC for data quality validation plugins.

This module defines the abstract base class for quality plugins that
provide data quality validation functionality. Quality plugins are
responsible for:
- Compile-time configuration validation
- Runtime quality check execution
- Quality scoring calculation
- OpenLineage event emission

Contract Version: 0.4.0

Example:
    >>> from floe_core.plugins.quality import QualityPlugin
    >>> class GreatExpectationsPlugin(QualityPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "great-expectations"
    ...     # ... implement other abstract methods

See Also:
    - specs/5b-dataquality-plugin/spec.md: Feature specification
    - ADR-0044: Unified Data Quality Plugin
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from floe_core.plugin_metadata import PluginMetadata
from floe_core.schemas.quality_config import QualityConfig, QualityGates
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualityScore,
    QualitySuite,
    QualitySuiteResult,
)
from floe_core.schemas.quality_validation import GateResult, ValidationResult

if TYPE_CHECKING:
    from collections.abc import Sequence


@runtime_checkable
class OpenLineageEmitter(Protocol):
    """Protocol for OpenLineage event emission.

    Quality plugins that support lineage tracking should return an
    implementation of this protocol from get_lineage_emitter().
    """

    def emit_fail_event(
        self,
        job_name: str,
        dataset_name: str,
        check_results: Sequence[QualityCheckResult],
    ) -> None:
        """Emit an OpenLineage FAIL event for quality check failures.

        Args:
            job_name: Name of the job that failed.
            dataset_name: Name of the dataset being validated.
            check_results: List of failed check results.
        """
        ...


class QualityPlugin(PluginMetadata):
    """Abstract base class for data quality plugins.

    QualityPlugin extends PluginMetadata with quality-specific methods
    for compile-time validation, runtime execution, quality scoring,
    and observability integration.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - Compile-time: validate_config(), validate_quality_gates()
        - Runtime: run_checks(), validate_expectations()
        - Scoring: calculate_quality_score()
        - Metadata: list_suites(), supports_dialect()
        - Observability: get_lineage_emitter() (optional, returns None if not supported)

    Example:
        >>> class GreatExpectationsPlugin(QualityPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "great_expectations"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def validate_config(self, config: QualityConfig) -> ValidationResult:
        ...         return ValidationResult(success=True)

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    # =========================================================================
    # Compile-Time Methods (FR-002, FR-003)
    # =========================================================================

    @abstractmethod
    def validate_config(self, config: QualityConfig) -> ValidationResult:
        """Validate quality configuration at compile-time.

        Called by the compiler to verify that the quality configuration
        is valid for this plugin. Should validate provider-specific settings.

        Args:
            config: The quality configuration to validate.

        Returns:
            ValidationResult indicating success/failure with errors/warnings.

        Raises:
            ValueError: If config is fundamentally invalid.

        Example:
            >>> result = plugin.validate_config(config)
            >>> if not result.success:
            ...     for error in result.errors:
            ...         print(f"Error: {error}")
        """
        ...

    @abstractmethod
    def validate_quality_gates(
        self,
        models: list[dict[str, Any]],
        gates: QualityGates,
    ) -> GateResult:
        """Validate models against quality gate requirements.

        Called by the compiler to enforce coverage thresholds and
        required test types for the specified tier.

        Args:
            models: List of model definitions with their quality checks.
            gates: Quality gate configuration (bronze/silver/gold).

        Returns:
            GateResult indicating pass/fail with coverage metrics and violations.

        Example:
            >>> result = plugin.validate_quality_gates(models, gates)
            >>> if not result.passed:
            ...     print(f"Coverage: {result.coverage_actual}% < {result.coverage_required}%")
            ...     for missing in result.missing_tests:
            ...         print(f"Missing test type: {missing}")
        """
        ...

    # =========================================================================
    # Runtime Methods (FR-004, existing methods enhanced)
    # =========================================================================

    @abstractmethod
    def run_checks(
        self,
        suite_name: str,
        data_source: str,
        options: dict[str, Any] | None = None,
    ) -> QualitySuiteResult:
        """Run a quality check suite against a data source.

        Executes all checks defined in the specified suite against
        the given data source and returns aggregated results.

        Args:
            suite_name: Name of the quality suite to run.
            data_source: Data source identifier (table name, file path, etc.).
            options: Optional execution options (timeout, fail_fast, etc.).

        Returns:
            QualitySuiteResult with individual check results and summary.

        Raises:
            ValueError: If suite_name is not found.
            ConnectionError: If unable to connect to data source.
            TimeoutError: If check execution exceeds timeout (FLOE-DQ106).

        Example:
            >>> result = plugin.run_checks(
            ...     suite_name="orders_quality",
            ...     data_source="staging.orders",
            ...     options={"timeout_seconds": 300},
            ... )
            >>> result.passed
            True
            >>> len(result.checks)
            5
        """
        ...

    @abstractmethod
    def run_suite(
        self,
        suite: QualitySuite,
        connection_config: dict[str, Any],
    ) -> QualitySuiteResult:
        """Run a quality suite with explicit configuration.

        Alternative to run_checks() that accepts a QualitySuite object
        and connection configuration directly, for runtime execution.

        Args:
            suite: Quality suite with checks to execute.
            connection_config: Database connection configuration from ComputePlugin.

        Returns:
            QualitySuiteResult with individual check results and summary.

        Raises:
            ConnectionError: If unable to connect using connection_config.
            TimeoutError: If check execution exceeds suite.timeout_seconds.
        """
        ...

    @abstractmethod
    def validate_expectations(
        self,
        data_source: str,
        expectations: list[dict[str, Any]],
    ) -> list[QualityCheckResult]:
        """Validate data against a list of expectations.

        Runs ad-hoc quality checks without requiring a pre-defined suite.

        Args:
            data_source: Data source identifier.
            expectations: List of expectation definitions.

        Returns:
            List of QualityCheckResult for each expectation.

        Raises:
            ValueError: If expectations format is invalid.
            ConnectionError: If unable to connect to data source.

        Example:
            >>> results = plugin.validate_expectations(
            ...     data_source="staging.orders",
            ...     expectations=[
            ...         {"type": "not_null", "column": "order_id"},
            ...         {"type": "unique", "column": "order_id"},
            ...     ],
            ... )
            >>> all(r.passed for r in results)
            True
        """
        ...

    # =========================================================================
    # Scoring Methods (FR-005)
    # =========================================================================

    @abstractmethod
    def calculate_quality_score(
        self,
        results: QualitySuiteResult,
        config: QualityConfig,
    ) -> QualityScore:
        """Calculate unified quality score from check results.

        Applies the three-layer scoring model:
        1. Dimension weights (completeness, accuracy, validity, consistency, timeliness)
        2. Check-level severity (critical, warning, info)
        3. Calculation parameters (baseline, influence caps)

        Args:
            results: Quality suite execution results.
            config: Quality configuration with scoring parameters.

        Returns:
            QualityScore with overall score and per-dimension breakdown.

        Example:
            >>> score = plugin.calculate_quality_score(results, config)
            >>> print(f"Overall: {score.overall}")
            >>> for dim, value in score.dimension_scores.items():
            ...     print(f"  {dim.value}: {value}")
        """
        ...

    # =========================================================================
    # Metadata Methods (FR-007)
    # =========================================================================

    @abstractmethod
    def list_suites(self) -> list[str]:
        """List available quality suites.

        Returns:
            List of suite names available for execution.

        Example:
            >>> plugin.list_suites()
            ['orders_quality', 'customers_quality', 'products_quality']
        """
        ...

    @abstractmethod
    def supports_dialect(self, dialect: str) -> bool:
        """Check if the plugin supports a SQL dialect.

        Args:
            dialect: SQL dialect name (e.g., "duckdb", "postgresql", "snowflake").

        Returns:
            True if the dialect is supported, False otherwise.

        Example:
            >>> plugin.supports_dialect("duckdb")
            True
            >>> plugin.supports_dialect("oracle")
            False
        """
        ...

    # =========================================================================
    # Observability Methods (FR-006)
    # =========================================================================

    def get_lineage_emitter(self) -> OpenLineageEmitter | None:
        """Get the OpenLineage event emitter for this plugin.

        Returns an emitter for sending OpenLineage FAIL events when
        quality checks fail. Returns None if lineage is not configured.

        Returns:
            OpenLineageEmitter instance, or None if not available.

        Example:
            >>> emitter = plugin.get_lineage_emitter()
            >>> if emitter is not None:
            ...     emitter.emit_fail_event(job_name, dataset, failed_checks)
        """
        return None

    # =========================================================================
    # Check Mapping (Helper for implementations)
    # =========================================================================

    def map_check_to_expectation(self, check: QualityCheck) -> dict[str, Any]:
        """Map a floe QualityCheck to plugin-native expectation format.

        Subclasses should override this to convert QualityCheck
        definitions to their native format (GX Expectation, dbt test, etc.).
        """
        return {
            "name": check.name,
            "type": check.type,
            "column": check.column,
            "parameters": check.parameters,
        }


__all__ = [
    "QualityPlugin",
    "OpenLineageEmitter",
    "QualityCheck",
    "QualityCheckResult",
    "QualityScore",
    "QualitySuite",
    "QualitySuiteResult",
    "GateResult",
    "ValidationResult",
]
