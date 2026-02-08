"""Deep merge utility for Helm values.

This module provides utilities for merging multiple Helm values dictionaries
with proper handling of nested structures, lists, and special merge directives.

The deep_merge function is used by HelmValuesGenerator to combine:
1. Chart default values
2. Plugin-specific values (from get_helm_values())
3. Environment-specific overrides
4. User-provided values

Example:
    >>> from floe_core.helm.merger import deep_merge
    >>> base = {"dagster": {"replicas": 1, "resources": {"cpu": "100m"}}}
    >>> override = {"dagster": {"resources": {"memory": "256Mi"}}}
    >>> result = deep_merge(base, override)
    >>> result["dagster"]["replicas"]
    1
    >>> result["dagster"]["resources"]["memory"]
    '256Mi'
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    *,
    list_strategy: str = "replace",
) -> dict[str, Any]:  # noqa: C901
    """Recursively merge two dictionaries with nested structure support.

    The override dictionary takes precedence over base for conflicting keys.
    Nested dictionaries are merged recursively. Lists can be replaced or
    appended based on the list_strategy parameter.

    Args:
        base: Base dictionary (lower priority)
        override: Override dictionary (higher priority)
        list_strategy: How to handle list values:
            - "replace": Override list replaces base list (default)
            - "append": Override list items are appended to base list
            - "prepend": Override list items are prepended to base list

    Returns:
        New dictionary with merged values (does not modify inputs)

    Examples:
        Basic merge:
        >>> base = {"a": 1, "b": {"c": 2}}
        >>> override = {"b": {"d": 3}}
        >>> deep_merge(base, override)
        {'a': 1, 'b': {'c': 2, 'd': 3}}

        Override takes precedence:
        >>> base = {"a": 1}
        >>> override = {"a": 2}
        >>> deep_merge(base, override)
        {'a': 2}

        List replacement (default):
        >>> base = {"items": [1, 2]}
        >>> override = {"items": [3, 4]}
        >>> deep_merge(base, override)
        {'items': [3, 4]}

        List append:
        >>> deep_merge(base, override, list_strategy="append")
        {'items': [1, 2, 3, 4]}
    """
    # Start with a deep copy of base to avoid mutation
    result = deepcopy(base)

    for key, override_value in override.items():
        if key not in result:
            # Key only in override - add it
            result[key] = deepcopy(override_value)
        elif isinstance(result[key], dict) and isinstance(override_value, dict):
            # Both are dicts - recurse
            base_dict: dict[str, Any] = result[key]
            override_dict: dict[str, Any] = override_value
            result[key] = deep_merge(
                base_dict, override_dict, list_strategy=list_strategy
            )
        elif isinstance(result[key], list) and isinstance(override_value, list):
            # Both are lists - apply list strategy
            base_list: list[Any] = result[key]
            override_list: list[Any] = override_value
            result[key] = _merge_lists(base_list, override_list, list_strategy)
        else:
            # Override wins for scalar values or type mismatches
            result[key] = deepcopy(override_value)

    return result


def _merge_lists(
    base_list: list[Any],
    override_list: list[Any],
    strategy: str,
) -> list[Any]:
    """Merge two lists according to the specified strategy.

    Args:
        base_list: Base list
        override_list: Override list
        strategy: Merge strategy (replace, append, prepend)

    Returns:
        Merged list
    """
    if strategy == "append":
        return deepcopy(base_list) + deepcopy(override_list)
    elif strategy == "prepend":
        return deepcopy(override_list) + deepcopy(base_list)
    else:  # replace (default)
        return deepcopy(override_list)


def merge_all(
    *dicts: dict[str, Any],
    list_strategy: str = "replace",
) -> dict[str, Any]:
    """Merge multiple dictionaries in order.

    Later dictionaries override earlier ones. This is a convenience
    function for merging more than two dictionaries.

    Args:
        *dicts: Variable number of dictionaries to merge
        list_strategy: How to handle list values

    Returns:
        Merged dictionary

    Example:
        >>> defaults = {"a": 1, "b": 2}
        >>> env = {"b": 3, "c": 4}
        >>> user = {"c": 5}
        >>> merge_all(defaults, env, user)
        {'a': 1, 'b': 3, 'c': 5}
    """
    if not dicts:
        return {}

    result = deepcopy(dicts[0])
    for d in dicts[1:]:
        result = deep_merge(result, d, list_strategy=list_strategy)

    return result


def flatten_dict(
    d: dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """Flatten a nested dictionary to dot-notation keys.

    Useful for generating Helm --set arguments from nested values.

    Args:
        d: Dictionary to flatten
        parent_key: Prefix for keys (used in recursion)
        sep: Separator for nested keys (default: ".")

    Returns:
        Flattened dictionary with dot-notation keys

    Example:
        >>> nested = {"dagster": {"webserver": {"replicas": 2}}}
        >>> flatten_dict(nested)
        {'dagster.webserver.replicas': 2}
    """
    items: list[tuple[str, Any]] = []

    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key

        if isinstance(value, dict):
            nested_dict: dict[str, Any] = value
            items.extend(flatten_dict(nested_dict, new_key, sep).items())
        elif isinstance(value, list):
            # Handle lists by indexing
            list_value: list[Any] = value
            for idx, item in enumerate(list_value):
                if isinstance(item, dict):
                    item_dict: dict[str, Any] = item
                    items.extend(
                        flatten_dict(item_dict, f"{new_key}[{idx}]", sep).items()
                    )
                else:
                    items.append((f"{new_key}[{idx}]", item))
        else:
            items.append((new_key, value))

    return dict(items)


def unflatten_dict(
    d: dict[str, Any],
    sep: str = ".",
) -> dict[str, Any]:
    """Convert a flattened dictionary back to nested structure.

    Args:
        d: Flattened dictionary with dot-notation keys
        sep: Separator used in keys

    Returns:
        Nested dictionary

    Example:
        >>> flat = {"dagster.webserver.replicas": 2}
        >>> unflatten_dict(flat)
        {'dagster': {'webserver': {'replicas': 2}}}
    """
    result: dict[str, Any] = {}

    for key, value in d.items():
        parts = key.split(sep)
        current = result

        for part in parts[:-1]:
            # Handle list indices like "items[0]"
            if "[" in part:
                dict_key, index_str = part.rstrip("]").split("[")
                index = int(index_str)

                if dict_key not in current:
                    current[dict_key] = []

                # Extend list if needed
                while len(current[dict_key]) <= index:
                    current[dict_key].append({})

                current = current[dict_key][index]
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

        # Set the final value
        final_key = parts[-1]
        if "[" in final_key:
            dict_key, index_str = final_key.rstrip("]").split("[")
            index = int(index_str)

            if dict_key not in current:
                current[dict_key] = []

            while len(current[dict_key]) <= index:
                current[dict_key].append(None)

            current[dict_key][index] = value
        else:
            current[final_key] = value

    return result


__all__: list[str] = [
    "deep_merge",
    "flatten_dict",
    "merge_all",
    "unflatten_dict",
]
