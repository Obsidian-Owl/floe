"""Validators submodule for policy enforcement.

This module contains individual validators for different policy types:
- NamingValidator: Validates model naming conventions (medallion, kimball, custom)
- CoverageValidator: Validates test coverage thresholds
- DocumentationValidator: Validates model and column descriptions

Task: T002 (part of enforcement module structure)

Example:
    >>> from floe_core.enforcement.validators import (
    ...     NamingValidator, CoverageValidator, DocumentationValidator
    ... )
    >>> validator = NamingValidator()
    >>> violations = validator.validate(dbt_manifest, naming_config)
"""

from __future__ import annotations

# Validators - imported as implemented
from floe_core.enforcement.validators.coverage import CoverageValidator
from floe_core.enforcement.validators.documentation import DocumentationValidator
from floe_core.enforcement.validators.naming import NamingValidator

__all__: list[str] = [
    # T043-T045: NamingValidator
    "NamingValidator",
    # T053-T059: CoverageValidator
    "CoverageValidator",
    # T065-T069: DocumentationValidator
    "DocumentationValidator",
]
