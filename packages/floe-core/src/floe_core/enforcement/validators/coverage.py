"""CoverageValidator for test coverage enforcement.

This module implements the CoverageValidator class that calculates column-level
test coverage and enforces minimum thresholds per layer (bronze, silver, gold).

Coverage Formula: (columns_with_at_least_one_test / total_columns) * 100

Task: T053, T054, T055, T056, T057, T058, T059, T060
Requirements: FR-004 (Coverage Calculation), FR-012 (Layer Thresholds), US4 (Coverage Enforcement)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.enforcement.patterns import DOCUMENTATION_URLS
from floe_core.enforcement.result import Violation

if TYPE_CHECKING:
    from floe_core.schemas.governance import QualityGatesConfig

logger = structlog.get_logger(__name__)

# Medallion layer detection pattern
_LAYER_PATTERN: re.Pattern[str] = re.compile(r"^(bronze|silver|gold)_")

# Coverage documentation URL
COVERAGE_DOC_URL = f"{DOCUMENTATION_URLS.get('base', 'https://floe.dev/docs')}/coverage"


class CoverageValidator:
    """Validates test coverage against configured thresholds.

    CoverageValidator calculates column-level test coverage for dbt models
    and validates against configured thresholds. It supports layer-specific
    thresholds for medallion architecture (bronze, silver, gold).

    Attributes:
        config: The QualityGatesConfig containing coverage thresholds.

    Example:
        >>> from floe_core.enforcement.validators.coverage import CoverageValidator
        >>> from floe_core.schemas.governance import QualityGatesConfig
        >>>
        >>> config = QualityGatesConfig(minimum_test_coverage=80)
        >>> validator = CoverageValidator(config)
        >>> violations = validator.validate(models, tests)
    """

    def __init__(self, config: QualityGatesConfig) -> None:
        """Initialize CoverageValidator with quality gates configuration.

        Args:
            config: The QualityGatesConfig containing coverage thresholds
                and layer-specific overrides.
        """
        self.config = config
        self._log = logger.bind(
            component="CoverageValidator",
            default_threshold=config.minimum_test_coverage,
        )

    def validate(
        self,
        models: list[dict[str, Any]],
        tests: list[dict[str, Any]],
    ) -> list[Violation]:
        """Validate test coverage for all models against configured thresholds.

        Args:
            models: List of model node dictionaries from dbt manifest.
            tests: List of test node dictionaries from dbt manifest.

        Returns:
            List of Violation objects for models that fail coverage thresholds.
        """
        violations: list[Violation] = []

        for model in models:
            model_name = model.get("name", "")
            model_unique_id = model.get("unique_id", "")

            # Extract columns for this model
            columns = self._extract_columns(model)

            # Extract tests for this model
            model_tests = self._extract_tests_for_model(model_unique_id, tests)

            # Map tests to columns
            column_tests = self._map_tests_to_columns(model_tests)

            # Calculate coverage
            coverage = self._calculate_coverage(columns, column_tests)

            # Skip models with N/A coverage (zero columns with report_na behavior)
            if coverage is None:
                self._log.debug(
                    "coverage_skipped_na",
                    model=model_name,
                    reason="zero columns with report_na behavior",
                )
                continue

            # Detect layer for threshold lookup
            layer = self._detect_layer(model_name)
            threshold = self._get_threshold_for_layer(layer)

            # Check if coverage meets threshold
            if coverage < threshold:
                violation = self._create_violation(
                    model_name=model_name,
                    coverage=coverage,
                    threshold=threshold,
                    layer=layer,
                    columns=columns,
                    column_tests=column_tests,
                )
                violations.append(violation)
                self._log.info(
                    "coverage_violation",
                    model=model_name,
                    coverage=coverage,
                    threshold=threshold,
                    layer=layer,
                )

        return violations

    def _extract_columns(self, model: dict[str, Any]) -> dict[str, Any]:
        """Extract column definitions from a model node.

        Args:
            model: Model node dictionary from dbt manifest.

        Returns:
            Dictionary of column name to column definition.
        """
        columns = model.get("columns")
        if columns is None:
            return {}
        return dict(columns)

    def _extract_tests_for_model(
        self,
        model_unique_id: str,
        tests: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract tests that are attached to a specific model.

        Args:
            model_unique_id: The unique_id of the model (e.g., "model.test.bronze_orders").
            tests: List of all test nodes from dbt manifest.

        Returns:
            List of test nodes attached to this model.
        """
        model_tests = []
        for test in tests:
            attached_node = test.get("attached_node")
            if attached_node == model_unique_id:
                model_tests.append(test)
        return model_tests

    def _map_tests_to_columns(
        self,
        tests: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Map tests to their respective columns and count tests per column.

        Model-level tests (no column_name) do not contribute to column coverage.

        Args:
            tests: List of test nodes for a model.

        Returns:
            Dictionary of column name to test count.
        """
        column_tests: dict[str, int] = {}
        for test in tests:
            column_name = test.get("column_name")
            # Model-level tests (column_name is None) don't count toward column coverage
            if column_name is not None:
                column_tests[column_name] = column_tests.get(column_name, 0) + 1
        return column_tests

    def _calculate_coverage(
        self,
        columns: dict[str, Any],
        column_tests: dict[str, int],
    ) -> float | None:
        """Calculate column-level test coverage percentage.

        Coverage Formula: (columns_with_at_least_one_test / total_columns) * 100

        Args:
            columns: Dictionary of column names to definitions.
            column_tests: Dictionary of column names to test counts.

        Returns:
            Coverage percentage (0.0 - 100.0), or None if zero columns
            and zero_column_coverage_behavior is "report_na".
        """
        total_columns = len(columns)

        # Handle zero columns case
        if total_columns == 0:
            if self.config.zero_column_coverage_behavior == "report_100_percent":
                return 100.0
            # report_na behavior
            return None

        # Count columns with at least one test
        columns_with_tests = sum(1 for col in columns if column_tests.get(col, 0) > 0)

        return (columns_with_tests / total_columns) * 100

    def _detect_layer(self, model_name: str) -> str | None:
        """Detect the medallion layer from model name prefix.

        Args:
            model_name: The model name (e.g., "bronze_orders", "dim_customer").

        Returns:
            The layer name ("bronze", "silver", "gold") or None if not medallion.
        """
        match = _LAYER_PATTERN.match(model_name)
        if match:
            return match.group(1)
        return None

    def _get_threshold_for_layer(self, layer: str | None) -> int:
        """Get the coverage threshold for a specific layer.

        If layer_thresholds is configured, uses layer-specific threshold.
        Otherwise, uses the default minimum_test_coverage.

        Args:
            layer: The layer name or None for unknown layers.

        Returns:
            The coverage threshold percentage (0-100).
        """
        # If no layer thresholds configured, use default
        if self.config.layer_thresholds is None:
            return self.config.minimum_test_coverage

        # If layer is unknown, use default
        if layer is None:
            return self.config.minimum_test_coverage

        # Get layer-specific threshold
        if layer == "bronze":
            return self.config.layer_thresholds.bronze
        if layer == "silver":
            return self.config.layer_thresholds.silver
        if layer == "gold":
            return self.config.layer_thresholds.gold

        # Fallback to default for any unrecognized layer
        return self.config.minimum_test_coverage

    def _create_violation(
        self,
        model_name: str,
        coverage: float,
        threshold: int,
        layer: str | None,
        columns: dict[str, Any],
        column_tests: dict[str, int],
    ) -> Violation:
        """Create a coverage violation with actionable details.

        Args:
            model_name: The model name.
            coverage: The actual coverage percentage.
            threshold: The required threshold percentage.
            layer: The layer name or None.
            columns: Dictionary of column names.
            column_tests: Dictionary of column test counts.

        Returns:
            A Violation object with error details and suggestions.
        """
        # Determine error code based on whether layer_thresholds config is used
        # FLOE-E210: Generic coverage violation (using default minimum_test_coverage)
        # FLOE-E211: Layer-specific coverage violation (using layer_thresholds config)
        uses_layer_specific_threshold = (
            layer is not None and self.config.layer_thresholds is not None
        )
        error_code = "FLOE-E211" if uses_layer_specific_threshold else "FLOE-E210"

        # Find uncovered columns for suggestion
        uncovered = [col for col in columns if column_tests.get(col, 0) == 0]

        # Build suggestion message
        if uncovered:
            uncovered_list = ", ".join(uncovered[:5])  # Show up to 5 columns
            if len(uncovered) > 5:
                uncovered_list += f", ... ({len(uncovered) - 5} more)"
            suggestion = (
                f"Add tests for uncovered columns: {uncovered_list}. "
                f"Need {threshold - int(coverage):.0f}% more coverage to meet threshold."
            )
        else:
            suggestion = f"Add more column-level tests to achieve {threshold}% coverage."

        # Build message
        layer_msg = f" ({layer} layer)" if layer else ""
        message = (
            f"Model '{model_name}'{layer_msg} has {coverage:.1f}% test coverage, "
            f"below the required {threshold}% threshold."
        )

        return Violation(
            error_code=error_code,
            severity="error",
            policy_type="coverage",
            model_name=model_name,
            column_name=None,
            message=message,
            expected=f"{threshold}% column-level test coverage",
            actual=(
                f"{coverage:.1f}% "
                f"({len(columns) - len(uncovered)}/{len(columns)} columns tested)"
            ),
            suggestion=suggestion,
            documentation_url=COVERAGE_DOC_URL,
        )


__all__ = ["CoverageValidator"]
