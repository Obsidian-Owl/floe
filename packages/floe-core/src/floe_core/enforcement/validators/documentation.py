"""DocumentationValidator for documentation enforcement.

This module implements the DocumentationValidator class that validates model and
column descriptions against documentation requirements.

Error Codes:
- FLOE-E220: Missing model description
- FLOE-E221: Missing column description
- FLOE-E222: Placeholder description detected (warning)

Task: T065, T066, T067, T068, T069, T070
Requirements: FR-005 (Documentation Enforcement), US5 (Documentation Validation)
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

# Documentation URL for documentation violations
DOCS_DOC_URL = f"{DOCUMENTATION_URLS.get('base', 'https://floe.dev/docs')}/documentation"

# Placeholder patterns to detect (case-insensitive)
# Matches common placeholder text that indicates incomplete documentation:
# - TBD, TODO, FIXME, XXX, HACK (developer markers)
# - Placeholder, Fill in, Add description, Description pending
# - N/A, NA, None (when used as entire description)
# - WIP, Work in progress
_PLACEHOLDER_WORDS: tuple[str, ...] = (
    "TBD",
    "TODO",
    "FIXME",
    "XXX",
    "HACK",
    "WIP",
)

_PLACEHOLDER_PHRASES: tuple[str, ...] = (
    r"fill\s+in",
    r"add\s+description",
    r"description\s+pending",
    r"pending\s+description",
    r"to\s+be\s+completed",
    r"to\s+be\s+documented",
    r"needs?\s+description",
    r"needs?\s+documentation",
    r"placeholder",
    r"work\s+in\s+progress",
    r"coming\s+soon",
    r"update\s+later",
    r"fill\s+later",
    r"describe\s+later",
)

# Compile pattern for single words (with word boundaries)
_PLACEHOLDER_WORDS_PATTERN: re.Pattern[str] = re.compile(
    r"\b(" + "|".join(_PLACEHOLDER_WORDS) + r")\b",
    re.IGNORECASE,
)

# Compile pattern for phrases
_PLACEHOLDER_PHRASES_PATTERN: re.Pattern[str] = re.compile(
    r"(" + "|".join(_PLACEHOLDER_PHRASES) + r")",
    re.IGNORECASE,
)

# Pattern for descriptions that are just "N/A", "NA", "None", "-", or similar
# Note: N/?A matches both "NA" and "N/A" (the ? makes / optional)
_NA_ONLY_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*(N/?A|None|-|\.{2,})\s*$",
    re.IGNORECASE,
)


class DocumentationValidator:
    """Validates documentation requirements for models and columns.

    DocumentationValidator checks that models and columns have proper descriptions
    when required by the governance configuration. It also detects placeholder
    descriptions (TBD, TODO, etc.) and reports them as warnings.

    Attributes:
        config: The QualityGatesConfig containing documentation requirements.

    Example:
        >>> from floe_core.enforcement.validators.documentation import (
        ...     DocumentationValidator,
        ... )
        >>> from floe_core.schemas.governance import QualityGatesConfig
        >>>
        >>> config = QualityGatesConfig(require_descriptions=True)
        >>> validator = DocumentationValidator(config)
        >>> violations = validator.validate(models)
    """

    def __init__(self, config: QualityGatesConfig) -> None:
        """Initialize DocumentationValidator with quality gates configuration.

        Args:
            config: The QualityGatesConfig containing documentation requirements.
        """
        self.config = config
        self._log = logger.bind(
            component="DocumentationValidator",
            require_descriptions=config.require_descriptions,
            require_column_descriptions=config.require_column_descriptions,
        )

    def validate(
        self,
        models: list[dict[str, Any]],
    ) -> list[Violation]:
        """Validate documentation for all models against configured requirements.

        Args:
            models: List of model node dictionaries from dbt manifest.

        Returns:
            List of Violation objects for models/columns that fail requirements.
        """
        violations: list[Violation] = []

        for model in models:
            model_name = model.get("name", "")

            # Check model description if required
            if self.config.require_descriptions:
                model_violations = self._validate_model_description(model, model_name)
                violations.extend(model_violations)

            # Check column descriptions if required
            if self.config.require_column_descriptions:
                column_violations = self._validate_column_descriptions(model, model_name)
                violations.extend(column_violations)

        return violations

    def _validate_model_description(
        self,
        model: dict[str, Any],
        model_name: str,
    ) -> list[Violation]:
        """Validate model description.

        Args:
            model: Model node dictionary.
            model_name: Model name for error messages.

        Returns:
            List of violations (0-1 for missing/placeholder description).
        """
        description = model.get("description")

        # Check for missing description
        if self._is_missing_or_empty(description):
            self._log.info(
                "documentation_violation",
                model=model_name,
                issue="missing_description",
            )
            return [
                self._create_model_violation(
                    model_name=model_name,
                    error_code="FLOE-E220",
                    issue="missing",
                )
            ]

        # Check for placeholder description
        # At this point description is not None (passed _is_missing_or_empty check)
        assert description is not None
        if self._is_placeholder(description):
            self._log.info(
                "documentation_violation",
                model=model_name,
                issue="placeholder_description",
                description=description,
            )
            return [
                self._create_model_placeholder_violation(
                    model_name=model_name,
                    description=description,
                )
            ]

        return []

    def _validate_column_descriptions(
        self,
        model: dict[str, Any],
        model_name: str,
    ) -> list[Violation]:
        """Validate column descriptions for a model.

        Args:
            model: Model node dictionary.
            model_name: Model name for error messages.

        Returns:
            List of violations for columns with missing/placeholder descriptions.
        """
        violations: list[Violation] = []
        columns = model.get("columns", {})

        for column_name, column_def in columns.items():
            description = column_def.get("description")

            # Check for missing description
            if self._is_missing_or_empty(description):
                self._log.info(
                    "documentation_violation",
                    model=model_name,
                    column=column_name,
                    issue="missing_description",
                )
                violations.append(
                    self._create_column_violation(
                        model_name=model_name,
                        column_name=column_name,
                        error_code="FLOE-E221",
                        issue="missing",
                    )
                )
            # Check for placeholder description
            elif self._is_placeholder(description):
                self._log.info(
                    "documentation_violation",
                    model=model_name,
                    column=column_name,
                    issue="placeholder_description",
                    description=description,
                )
                violations.append(
                    self._create_column_placeholder_violation(
                        model_name=model_name,
                        column_name=column_name,
                        description=description,
                    )
                )

        return violations

    def _is_missing_or_empty(self, description: str | None) -> bool:
        """Check if a description is missing or empty.

        Args:
            description: The description string or None.

        Returns:
            True if description is None, empty, or whitespace-only.
        """
        if description is None:
            return True
        if not description.strip():
            return True
        return False

    def _is_placeholder(self, description: str | None) -> bool:
        """Check if a description contains placeholder text.

        Detects common placeholder patterns including:
        - Developer markers: TBD, TODO, FIXME, XXX, HACK, WIP
        - Placeholder phrases: "fill in", "add description", "coming soon", etc.
        - N/A-style descriptions: "N/A", "NA", "None", "-", "..."

        Args:
            description: The description string.

        Returns:
            True if description contains placeholder text.
        """
        if description is None:
            return False

        # Check for N/A-style descriptions (entire description is just a placeholder)
        if _NA_ONLY_PATTERN.match(description):
            return True

        # Check for placeholder words (TBD, TODO, etc.)
        if _PLACEHOLDER_WORDS_PATTERN.search(description):
            return True

        # Check for placeholder phrases
        if _PLACEHOLDER_PHRASES_PATTERN.search(description):
            return True

        return False

    def _create_model_violation(
        self,
        model_name: str,
        error_code: str,
        issue: str,
    ) -> Violation:
        """Create a model documentation violation.

        Args:
            model_name: The model name.
            error_code: The error code (FLOE-E220).
            issue: The issue type ("missing").

        Returns:
            A Violation object.
        """
        return Violation(
            error_code=error_code,
            severity="error",
            policy_type="documentation",
            model_name=model_name,
            column_name=None,
            message=f"Model '{model_name}' is missing a description.",
            expected="Non-empty model description",
            actual=f"Description is {issue}",
            suggestion=(
                f"Add a description to model '{model_name}' in schema.yml. "
                "Describe the model's purpose, data source, and business context."
            ),
            documentation_url=DOCS_DOC_URL,
        )

    def _create_model_placeholder_violation(
        self,
        model_name: str,
        description: str,
    ) -> Violation:
        """Create a placeholder description violation for a model.

        Args:
            model_name: The model name.
            description: The placeholder description.

        Returns:
            A Violation object with warning severity.
        """
        return Violation(
            error_code="FLOE-E222",
            severity="warning",
            policy_type="documentation",
            model_name=model_name,
            column_name=None,
            message=f"Model '{model_name}' has a placeholder description.",
            expected="Complete model description",
            actual=f"Placeholder description: '{description}'",
            suggestion=(
                f"Replace the placeholder in model '{model_name}' description "
                "with meaningful documentation."
            ),
            documentation_url=DOCS_DOC_URL,
        )

    def _create_column_violation(
        self,
        model_name: str,
        column_name: str,
        error_code: str,
        issue: str,
    ) -> Violation:
        """Create a column documentation violation.

        Args:
            model_name: The model name.
            column_name: The column name.
            error_code: The error code (FLOE-E221).
            issue: The issue type ("missing").

        Returns:
            A Violation object.
        """
        return Violation(
            error_code=error_code,
            severity="error",
            policy_type="documentation",
            model_name=model_name,
            column_name=column_name,
            message=f"Column '{column_name}' in model '{model_name}' is missing a description.",
            expected="Non-empty column description",
            actual=f"Description is {issue}",
            suggestion=(
                f"Add a description for column '{column_name}' in model '{model_name}'. "
                "Describe the column's meaning, data type, and valid values."
            ),
            documentation_url=DOCS_DOC_URL,
        )

    def _create_column_placeholder_violation(
        self,
        model_name: str,
        column_name: str,
        description: str,
    ) -> Violation:
        """Create a placeholder description violation for a column.

        Args:
            model_name: The model name.
            column_name: The column name.
            description: The placeholder description.

        Returns:
            A Violation object with warning severity.
        """
        return Violation(
            error_code="FLOE-E222",
            severity="warning",
            policy_type="documentation",
            model_name=model_name,
            column_name=column_name,
            message=(
                f"Column '{column_name}' in model '{model_name}' has a placeholder description."
            ),
            expected="Complete column description",
            actual=f"Placeholder description: '{description}'",
            suggestion=(
                f"Replace the placeholder in column '{column_name}' description "
                "with meaningful documentation."
            ),
            documentation_url=DOCS_DOC_URL,
        )


__all__ = ["DocumentationValidator"]
