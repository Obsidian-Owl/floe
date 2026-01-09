"""QualityPlugin ABC for data quality validation plugins.

This module defines the abstract base class for quality plugins that
provide data quality validation functionality. Quality plugins are
responsible for:
- Running data quality tests and assertions
- Validating data against expectations
- Generating quality reports

Example:
    >>> from floe_core.plugins.quality import QualityPlugin
    >>> class GreatExpectationsPlugin(QualityPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "great-expectations"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


@dataclass
class QualityCheckResult:
    """Result of a data quality check.

    Attributes:
        check_name: Name of the quality check that was run.
        passed: Whether the check passed.
        details: Additional details about the check result.
        records_checked: Number of records evaluated.
        records_failed: Number of records that failed the check.
    """

    check_name: str
    passed: bool
    details: dict[str, Any]
    records_checked: int = 0
    records_failed: int = 0


@dataclass
class QualitySuiteResult:
    """Result of running a suite of quality checks.

    Attributes:
        suite_name: Name of the quality suite.
        passed: Whether all checks in the suite passed.
        checks: Individual check results.
        summary: Summary statistics.
    """

    suite_name: str
    passed: bool
    checks: list[QualityCheckResult]
    summary: dict[str, Any]


class QualityPlugin(PluginMetadata):
    """Abstract base class for data quality plugins.

    QualityPlugin extends PluginMetadata with quality-specific methods
    for validating data. Implementations include Great Expectations,
    Soda, and dbt-expectations.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - run_checks() method
        - validate_expectations() method
        - list_suites() method

    Example:
        >>> class GreatExpectationsPlugin(QualityPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "great-expectations"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def run_checks(self, suite_name: str, data_source: str) -> QualitySuiteResult:
        ...         return self._run_expectation_suite(suite_name, data_source)

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

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
            options: Optional execution options.

        Returns:
            QualitySuiteResult with individual check results and summary.

        Raises:
            ValueError: If suite_name is not found.
            ConnectionError: If unable to connect to data source.

        Example:
            >>> result = plugin.run_checks(
            ...     suite_name="orders_quality",
            ...     data_source="staging.orders",
            ... )
            >>> result.passed
            True
            >>> len(result.checks)
            5
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
