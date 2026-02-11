"""Shared parsing utilities for Helm CLI commands.

Provides ``parse_set_values`` and ``parse_value`` used by both
``floe helm generate`` and ``floe platform deploy`` to interpret
``--set key=value`` arguments into nested dictionaries.

Example:
    >>> from floe_core.helm.parsing import parse_set_values
    >>> parse_set_values(("dagster.replicas=3", "global.env=prod"))
    {'dagster': {'replicas': 3}, 'global': {'env': 'prod'}}
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from floe_core.helm.merger import unflatten_dict


def parse_set_values(
    set_values: tuple[str, ...],
    *,
    warn_fn: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Parse --set key=value arguments into nested dict.

    Args:
        set_values: Tuple of "key=value" strings.
        warn_fn: Optional callback for invalid entries. If *None*,
            invalid items are silently skipped.

    Returns:
        Nested dictionary with parsed values.

    Example:
        >>> parse_set_values(("dagster.replicas=3", "global.env=prod"))
        {'dagster': {'replicas': 3}, 'global': {'env': 'prod'}}
    """
    if not set_values:
        return {}

    flat: dict[str, Any] = {}
    for item in set_values:
        if "=" not in item:
            if warn_fn is not None:
                warn_fn(f"Ignoring invalid --set value (missing '='): {item}")
            continue
        key, _, value = item.partition("=")
        flat[key] = parse_value(value)

    return unflatten_dict(flat)


def parse_value(value: str) -> str | int | float | bool | None:
    """Parse a string value into appropriate Python type.

    Follows Helm ``--set`` semantics: null, booleans, integers, floats,
    then falls back to string.

    Args:
        value: String value from --set argument.

    Returns:
        Parsed value as int, float, bool, None, or original string.
    """
    # Handle null
    if value.lower() == "null":
        return None

    # Handle booleans
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Return as string
    return value


__all__: list[str] = [
    "parse_set_values",
    "parse_value",
]
