"""Built-in regex patterns and pattern validation for naming conventions.

This module defines the standard naming patterns (medallion, kimball) and provides
utilities for validating custom patterns including ReDoS protection.

Task: T040, T041, T042
Requirements: FR-003 (Naming Convention Enforcement), US3 (Naming Validation)
"""

from __future__ import annotations

import re
from typing import Final

# Maximum pattern length to prevent DoS via extremely long patterns
MAX_PATTERN_LENGTH: Final[int] = 500

# Documentation URLs for naming conventions
DOCUMENTATION_URLS: Final[dict[str, str | dict[str, str]]] = {
    "base": "https://floe.dev/docs",
    "naming": {
        "medallion": "https://floe.dev/docs/naming#medallion",
        "kimball": "https://floe.dev/docs/naming#kimball",
        "custom": "https://floe.dev/docs/naming#custom",
    },
}

# Medallion architecture naming pattern (T040)
# Matches: bronze_*, silver_*, gold_* with lowercase alphanumeric and underscores
# Pattern: ^(bronze|silver|gold)_[a-z][a-z0-9_]*$
MEDALLION_PATTERN: Final[str] = r"^(bronze|silver|gold)_[a-z][a-z0-9_]*$"
"""Regex pattern for medallion architecture naming convention.

Valid examples:
    - bronze_orders
    - silver_customers
    - gold_revenue

Invalid examples:
    - stg_payments (wrong prefix)
    - bronze_ (missing name)
    - Bronze_orders (uppercase)
"""

# Kimball dimensional modeling naming pattern (T041)
# Matches: dim_*, fact_*, bridge_*, hub_*, link_*, sat_* (Data Vault extension)
# Pattern: ^(dim|fact|bridge|hub|link|sat)_[a-z][a-z0-9_]*$
KIMBALL_PATTERN: Final[str] = r"^(dim|fact|bridge|hub|link|sat)_[a-z][a-z0-9_]*$"
"""Regex pattern for Kimball dimensional modeling naming convention.

Includes Data Vault extensions (hub_, link_, sat_) for compatibility.

Valid examples:
    - dim_customer
    - fact_orders
    - bridge_order_product
    - hub_customer
    - link_order_customer
    - sat_product_details

Invalid examples:
    - bronze_orders (medallion prefix)
    - stg_data (staging prefix)
"""

# Known ReDoS-vulnerable patterns to block
_REDOS_PATTERNS: Final[list[str]] = [
    r"\(([^)]*\+)+",  # Nested quantifiers like (a+)+
    r"\(([^)]*\*)+",  # Nested quantifiers like (a*)*
    r"\([^)]*\|[^)]*\)\+",  # Alternation with quantifier (a|a)+
    r"\([^)]*\)\{[0-9]+,\}",  # Large repetition bounds
]

# Pre-compile ReDoS detection patterns
_REDOS_DETECTORS: Final[list[re.Pattern[str]]] = [
    re.compile(pattern) for pattern in _REDOS_PATTERNS
]


class InvalidPatternError(Exception):
    """Raised when a custom regex pattern is invalid or unsafe.

    Attributes:
        pattern: The invalid pattern string.
        reason: Description of why the pattern is invalid.

    Example:
        >>> try:
        ...     validate_custom_patterns(["(a+)+$"])
        ... except InvalidPatternError as e:
        ...     print(f"Invalid pattern: {e.pattern} - {e.reason}")
    """

    def __init__(self, pattern: str, reason: str) -> None:
        """Initialize InvalidPatternError.

        Args:
            pattern: The invalid pattern string.
            reason: Description of why the pattern is invalid.
        """
        self.pattern = pattern
        self.reason = reason
        super().__init__(f"Invalid regex pattern '{pattern}': {reason}")


def validate_custom_patterns(patterns: list[str]) -> None:
    """Validate a list of custom regex patterns for correctness and safety.

    Performs the following checks:
    1. List is not empty (at least one pattern required)
    2. Each pattern is valid regex syntax
    3. Each pattern passes ReDoS safety checks
    4. Each pattern is within length limits

    Args:
        patterns: List of regex pattern strings to validate.

    Raises:
        InvalidPatternError: If any pattern is invalid, unsafe, or too long.

    Example:
        >>> validate_custom_patterns(["^raw_.*$", "^clean_.*$"])  # OK
        >>> validate_custom_patterns(["(a+)+$"])  # Raises InvalidPatternError
    """
    if not patterns:
        raise InvalidPatternError(
            pattern="<empty list>",
            reason="Custom patterns must contain at least one pattern",
        )

    for pattern in patterns:
        # Check length limit
        if len(pattern) > MAX_PATTERN_LENGTH:
            raise InvalidPatternError(
                pattern=pattern[:50] + "...",
                reason=f"Pattern too long ({len(pattern)} chars, max {MAX_PATTERN_LENGTH}). "
                "Reduce complexity to avoid performance issues.",
            )

        # Check syntax validity
        try:
            re.compile(pattern)
        except re.error as e:
            raise InvalidPatternError(
                pattern=pattern,
                reason=f"Invalid regex syntax: {e}",
            ) from e

        # Check for ReDoS vulnerabilities
        _check_redos_safety(pattern)


def _check_redos_safety(pattern: str) -> None:
    """Check if a regex pattern is safe from ReDoS attacks.

    ReDoS (Regular Expression Denial of Service) occurs when certain regex
    patterns cause exponential or polynomial time complexity on specific inputs.

    Common dangerous patterns:
    - (a+)+ - Nested quantifiers
    - (a|a)+ - Alternation with quantifier
    - (.*a){n} where n is large - Polynomial backtracking

    Args:
        pattern: The regex pattern to check.

    Raises:
        InvalidPatternError: If the pattern appears to be ReDoS-vulnerable.
    """
    # Check against known ReDoS patterns
    for detector in _REDOS_DETECTORS:
        if detector.search(pattern):
            raise InvalidPatternError(
                pattern=pattern,
                reason="Pattern contains potentially unsafe nested quantifiers (ReDoS vulnerability). "
                "Avoid patterns like (a+)+, (a|a)+, or nested repetitions.",
            )

    # Additional heuristic checks
    # Count nested groups with quantifiers
    nested_quantifier_count = len(re.findall(r"\([^)]*[+*]\)[+*]", pattern))
    if nested_quantifier_count > 0:
        raise InvalidPatternError(
            pattern=pattern,
            reason="Pattern contains nested quantifiers which may cause catastrophic backtracking. "
            "Use atomic groups or possessive quantifiers if available.",
        )


def matches_custom_patterns(model_name: str, patterns: list[str]) -> bool:
    """Check if a model name matches ANY of the custom patterns.

    Uses OR logic - returns True if at least one pattern matches.

    Args:
        model_name: The model name to check.
        patterns: List of regex patterns (assumed to be pre-validated).

    Returns:
        True if model_name matches at least one pattern, False otherwise.

    Example:
        >>> patterns = ["^raw_.*$", "^clean_.*$"]
        >>> matches_custom_patterns("raw_orders", patterns)
        True
        >>> matches_custom_patterns("stg_data", patterns)
        False
    """
    for pattern in patterns:
        if re.match(pattern, model_name):
            return True
    return False


def get_pattern_for_type(pattern_type: str) -> str:
    """Get the regex pattern for a built-in pattern type.

    Args:
        pattern_type: One of "medallion", "kimball".

    Returns:
        The regex pattern string.

    Raises:
        ValueError: If pattern_type is not recognized.
    """
    if pattern_type == "medallion":
        return MEDALLION_PATTERN
    if pattern_type == "kimball":
        return KIMBALL_PATTERN
    msg = f"Unknown pattern type: {pattern_type}. Use 'medallion', 'kimball', or 'custom'."
    raise ValueError(msg)


def get_documentation_url(pattern_type: str) -> str:
    """Get the documentation URL for a pattern type.

    Args:
        pattern_type: One of "medallion", "kimball", "custom".

    Returns:
        The documentation URL string.
    """
    naming_urls = DOCUMENTATION_URLS.get("naming", {})
    if isinstance(naming_urls, dict):
        url = naming_urls.get(pattern_type)
        if url:
            return url
    base = DOCUMENTATION_URLS.get("base", "https://floe.dev/docs")
    if isinstance(base, str):
        return f"{base}/naming#{pattern_type}"
    return f"https://floe.dev/docs/naming#{pattern_type}"


__all__ = [
    "MEDALLION_PATTERN",
    "KIMBALL_PATTERN",
    "DOCUMENTATION_URLS",
    "MAX_PATTERN_LENGTH",
    "InvalidPatternError",
    "validate_custom_patterns",
    "matches_custom_patterns",
    "get_pattern_for_type",
    "get_documentation_url",
]
