"""Validators submodule for policy enforcement.

This module contains individual validators for different policy types:
- NamingValidator: Validates model naming conventions (medallion, kimball, custom)
- CoverageValidator: Validates test coverage thresholds
- DocumentationValidator: Validates model and column descriptions

Task: T002 (part of enforcement module structure)

Example:
    >>> from floe_core.enforcement.validators import NamingValidator
    >>> validator = NamingValidator()
    >>> violations = validator.validate(dbt_manifest, naming_config)
"""

from __future__ import annotations

# Imports will be added as validators are implemented:
# - T043-T045: NamingValidator from naming.py
# - T053-T059: CoverageValidator from coverage.py
# - T065-T069: DocumentationValidator from documentation.py

__all__: list[str] = [
    # Validators (T043, T053, T065)
    # "NamingValidator",
    # "CoverageValidator",
    # "DocumentationValidator",
]
