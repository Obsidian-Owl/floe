"""NamingValidator for model naming convention enforcement.

Validates model names against configured naming patterns (medallion, kimball, custom)
and generates actionable violation reports with remediation suggestions.

Task: T043, T044, T045
Requirements: FR-003 (Naming Convention Enforcement), US3 (Naming Validation)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.enforcement.patterns import (
    KIMBALL_PATTERN,
    MEDALLION_PATTERN,
    get_documentation_url,
    matches_custom_patterns,
)
from floe_core.enforcement.result import Violation

if TYPE_CHECKING:
    from floe_core.schemas.governance import NamingConfig

logger = structlog.get_logger(__name__)

# Mapping of common prefixes to suggested medallion equivalents
_MEDALLION_SUGGESTIONS: dict[str, str] = {
    "stg_": "bronze_",  # Staging -> Bronze (raw layer)
    "raw_": "bronze_",  # Raw -> Bronze
    "src_": "bronze_",  # Source -> Bronze
    "staging_": "bronze_",  # Staging -> Bronze
    "int_": "silver_",  # Intermediate -> Silver
    "intermediate_": "silver_",  # Intermediate -> Silver
    "clean_": "silver_",  # Clean -> Silver
    "agg_": "gold_",  # Aggregate -> Gold
    "mart_": "gold_",  # Mart -> Gold
    "dim_": "gold_",  # Dimension -> Gold (transformed)
    "fact_": "gold_",  # Fact -> Gold (transformed)
}

# Mapping of common prefixes to suggested kimball equivalents
_KIMBALL_SUGGESTIONS: dict[str, str] = {
    "bronze_": "fact_",  # Raw data often becomes fact tables
    "silver_": "dim_",  # Transformed data often becomes dimensions
    "gold_": "dim_",  # Gold metrics often map to dimensions
    "stg_": "fact_",  # Staging -> Fact (typically)
    "raw_": "fact_",  # Raw -> Fact
    "agg_": "fact_",  # Aggregate -> Fact
    "mart_": "fact_",  # Mart -> Fact
}


class NamingValidator:
    """Validates model names against naming conventions.

    NamingValidator checks model names against the configured pattern
    (medallion, kimball, or custom regex patterns) and generates violations
    with actionable remediation suggestions.

    Attributes:
        config: The NamingConfig specifying pattern and enforcement level.

    Example:
        >>> from floe_core.enforcement.validators.naming import NamingValidator
        >>> from floe_core.schemas.governance import NamingConfig
        >>>
        >>> config = NamingConfig(enforcement="strict", pattern="medallion")
        >>> validator = NamingValidator(config)
        >>>
        >>> models = [{"name": "stg_payments", "resource_type": "model"}]
        >>> violations = validator.validate(models)
        >>> for v in violations:
        ...     print(f"{v.error_code}: {v.message}")
    """

    def __init__(self, config: NamingConfig) -> None:
        """Initialize NamingValidator with configuration.

        Args:
            config: The naming configuration specifying pattern and enforcement.
        """
        self.config = config
        self._log = logger.bind(
            component="NamingValidator",
            pattern=config.pattern,
            enforcement=config.enforcement,
        )

        # Pre-compile the pattern for efficiency
        self._compiled_pattern: re.Pattern[str] | None = None
        if config.pattern == "medallion":
            self._compiled_pattern = re.compile(MEDALLION_PATTERN)
        elif config.pattern == "kimball":
            self._compiled_pattern = re.compile(KIMBALL_PATTERN)
        # Custom patterns are validated at config time, not compiled here

    def validate(self, models: list[dict[str, Any]]) -> list[Violation]:
        """Validate model names against the configured naming convention.

        Args:
            models: List of model dictionaries from dbt manifest.
                Each model should have at least a "name" key.

        Returns:
            List of Violation objects for models with invalid names.
            Returns empty list if enforcement is "off" or all names are valid.
        """
        # Skip if enforcement is off
        if self.config.enforcement == "off":
            self._log.debug("naming_validation_skipped", reason="enforcement=off")
            return []

        violations: list[Violation] = []
        severity = "error" if self.config.enforcement == "strict" else "warning"

        for model in models:
            model_name = model.get("name", "")
            if not model_name:
                continue

            # Check if name matches the pattern
            if not self._matches_pattern(model_name):
                violation = self._create_violation(model_name, severity)
                violations.append(violation)

        if violations:
            self._log.info(
                "naming_violations_found",
                count=len(violations),
                models=[v.model_name for v in violations],
            )
        else:
            self._log.debug("naming_validation_passed", model_count=len(models))

        return violations

    def _matches_pattern(self, model_name: str) -> bool:
        """Check if a model name matches the configured pattern.

        Args:
            model_name: The model name to check.

        Returns:
            True if the name matches the pattern, False otherwise.
        """
        if self.config.pattern == "custom":
            if self.config.custom_patterns:
                return matches_custom_patterns(model_name, self.config.custom_patterns)
            return False  # No patterns defined

        # Use pre-compiled pattern for medallion/kimball
        if self._compiled_pattern is not None:
            return self._compiled_pattern.match(model_name) is not None

        return False

    def _create_violation(self, model_name: str, severity: str) -> Violation:
        """Create a violation for an invalid model name.

        Args:
            model_name: The invalid model name.
            severity: The severity level ("error" or "warning").

        Returns:
            Violation object with actionable details.
        """
        pattern_type = self.config.pattern
        expected = self._get_expected_description()
        suggestion = self._generate_suggestion(model_name)
        documentation_url = get_documentation_url(pattern_type)

        return Violation(
            error_code="FLOE-E201",
            severity=severity,  # type: ignore[arg-type]
            policy_type="naming",
            model_name=model_name,
            message=f"Model name '{model_name}' does not match {pattern_type} naming convention",
            expected=expected,
            actual=model_name,
            suggestion=suggestion,
            documentation_url=documentation_url,
        )

    def _get_expected_description(self) -> str:
        """Get a human-readable description of the expected pattern.

        Returns:
            Description of the expected naming convention.
        """
        if self.config.pattern == "medallion":
            return "^(bronze|silver|gold)_[a-z][a-z0-9_]*$ (medallion architecture)"
        if self.config.pattern == "kimball":
            return "^(dim|fact|bridge|hub|link|sat)_[a-z][a-z0-9_]*$ (kimball dimensional)"
        if self.config.pattern == "custom" and self.config.custom_patterns:
            patterns_preview = ", ".join(self.config.custom_patterns[:3])
            if len(self.config.custom_patterns) > 3:
                patterns_preview += f" (and {len(self.config.custom_patterns) - 3} more)"
            return f"Custom patterns: {patterns_preview}"
        return "configured naming pattern"

    def _generate_suggestion(self, model_name: str) -> str:
        """Generate a remediation suggestion for an invalid model name.

        Analyzes the model name to suggest an appropriate rename based on
        common prefix patterns.

        Args:
            model_name: The invalid model name.

        Returns:
            Actionable suggestion string.
        """
        if self.config.pattern == "medallion":
            return self._suggest_medallion_name(model_name)
        if self.config.pattern == "kimball":
            return self._suggest_kimball_name(model_name)
        if self.config.pattern == "custom":
            return self._suggest_custom_name(model_name)
        return f"Rename model to match the configured naming convention"

    def _suggest_medallion_name(self, model_name: str) -> str:
        """Generate a suggestion for medallion naming convention.

        Args:
            model_name: The invalid model name.

        Returns:
            Suggestion for renaming to medallion convention.
        """
        # Check if we recognize the prefix
        for prefix, suggestion_prefix in _MEDALLION_SUGGESTIONS.items():
            if model_name.startswith(prefix):
                base_name = model_name[len(prefix):]
                return (
                    f"Rename to '{suggestion_prefix}{base_name}'. "
                    f"The '{prefix}' prefix suggests this is a {self._get_layer_description(suggestion_prefix)} layer model."
                )

        # Default suggestion: suggest bronze_ as starting point
        return (
            f"Rename to 'bronze_{model_name}', 'silver_{model_name}', or 'gold_{model_name}'. "
            "Choose the prefix based on the data layer: "
            "bronze (raw), silver (transformed), gold (aggregated)."
        )

    def _suggest_kimball_name(self, model_name: str) -> str:
        """Generate a suggestion for kimball naming convention.

        Args:
            model_name: The invalid model name.

        Returns:
            Suggestion for renaming to kimball convention.
        """
        # Check if we recognize the prefix
        for prefix, suggestion_prefix in _KIMBALL_SUGGESTIONS.items():
            if model_name.startswith(prefix):
                base_name = model_name[len(prefix):]
                return (
                    f"Rename to '{suggestion_prefix}{base_name}' or 'dim_{base_name}'. "
                    f"Choose based on model purpose: dim_ (dimension), fact_ (transactional), bridge_ (many-to-many)."
                )

        # Default suggestion
        return (
            f"Rename to 'dim_{model_name}', 'fact_{model_name}', or 'bridge_{model_name}'. "
            "Choose the prefix based on model type: "
            "dim (dimension/lookup), fact (transactional/metrics), bridge (many-to-many)."
        )

    def _suggest_custom_name(self, model_name: str) -> str:
        """Generate a suggestion for custom naming convention.

        Args:
            model_name: The invalid model name.

        Returns:
            Suggestion for renaming to match custom patterns.
        """
        if self.config.custom_patterns:
            examples = []
            for pattern in self.config.custom_patterns[:3]:
                # Extract prefix if pattern starts with ^prefix
                match = re.match(r"\^([a-zA-Z_]+)", pattern)
                if match:
                    examples.append(f"{match.group(1)}{model_name}")

            if examples:
                return f"Rename to match one of: {', '.join(examples)}"

        return "Rename to match one of the configured custom patterns"

    def _get_layer_description(self, prefix: str) -> str:
        """Get a description for a medallion layer prefix.

        Args:
            prefix: The medallion prefix (bronze_, silver_, gold_).

        Returns:
            Description of the layer.
        """
        descriptions = {
            "bronze_": "raw/landing",
            "silver_": "cleansed/transformed",
            "gold_": "aggregated/presentation",
        }
        return descriptions.get(prefix, "data")


__all__ = ["NamingValidator"]
