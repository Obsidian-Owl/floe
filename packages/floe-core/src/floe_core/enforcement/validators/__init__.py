"""Validators submodule for policy enforcement.

This module contains individual validators for different policy types:
- NamingValidator: Validates model naming conventions (medallion, kimball, custom)
- CoverageValidator: Validates test coverage thresholds
- DocumentationValidator: Validates model and column descriptions
- SemanticValidator: Validates model relationships (refs, sources, circular deps)
- CustomRuleValidator: Validates user-defined custom rules (tags, meta, tests)

Task: T002 (part of enforcement module structure), T017-T020, T027-T033

Example:
    >>> from floe_core.enforcement.validators import (
    ...     NamingValidator, CoverageValidator, DocumentationValidator,
    ...     SemanticValidator, CustomRuleValidator
    ... )
    >>> validator = NamingValidator()
    >>> violations = validator.validate(dbt_manifest, naming_config)
"""

from __future__ import annotations

# Validators - imported as implemented
from floe_core.enforcement.validators.coverage import CoverageValidator
from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
from floe_core.enforcement.validators.documentation import DocumentationValidator
from floe_core.enforcement.validators.naming import NamingValidator
from floe_core.enforcement.validators.semantic import SemanticValidator

__all__: list[str] = [
    # T043-T045: NamingValidator
    "NamingValidator",
    # T053-T059: CoverageValidator
    "CoverageValidator",
    # T065-T069: DocumentationValidator
    "DocumentationValidator",
    # T017-T020: SemanticValidator
    "SemanticValidator",
    # T027-T033: CustomRuleValidator
    "CustomRuleValidator",
]
