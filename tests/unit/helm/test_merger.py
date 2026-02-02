"""Unit tests for Helm values merger.

Tests the deep_merge, merge_all, flatten_dict, and unflatten_dict utilities.

Requirements tested:
- 9b-FR-061: Deep merge Helm values with nested structure support
"""

from __future__ import annotations

import pytest
from floe_core.helm.merger import (
    deep_merge,
    flatten_dict,
    merge_all,
    unflatten_dict,
)


class TestDeepMerge:
    """Tests for deep_merge function."""

    @pytest.mark.requirement("9b-FR-061")
    def test_merge_disjoint_dicts(self) -> None:
        """Test merging dictionaries with no overlapping keys."""
        base = {"a": 1, "b": 2}
        override = {"c": 3, "d": 4}
        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    @pytest.mark.requirement("9b-FR-061")
    def test_override_takes_precedence(self) -> None:
        """Test that override values replace base values."""
        base = {"a": 1, "b": 2}
        override = {"a": 10, "c": 3}
        result = deep_merge(base, override)

        assert result == {"a": 10, "b": 2, "c": 3}

    @pytest.mark.requirement("9b-FR-061")
    def test_nested_dict_merge(self) -> None:
        """Test recursive merging of nested dictionaries."""
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 20, "c": 3}}
        result = deep_merge(base, override)

        assert result == {"outer": {"a": 1, "b": 20, "c": 3}}

    @pytest.mark.requirement("9b-FR-061")
    def test_deeply_nested_merge(self) -> None:
        """Test merging deeply nested structures."""
        base = {"l1": {"l2": {"l3": {"a": 1}}}}
        override = {"l1": {"l2": {"l3": {"b": 2}}}}
        result = deep_merge(base, override)

        assert result == {"l1": {"l2": {"l3": {"a": 1, "b": 2}}}}

    @pytest.mark.requirement("9b-FR-061")
    def test_list_replace_default(self) -> None:
        """Test that lists are replaced by default."""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = deep_merge(base, override)

        assert result == {"items": [4, 5]}

    @pytest.mark.requirement("9b-FR-061")
    def test_list_append_strategy(self) -> None:
        """Test list append merge strategy."""
        base = {"items": [1, 2]}
        override = {"items": [3, 4]}
        result = deep_merge(base, override, list_strategy="append")

        assert result == {"items": [1, 2, 3, 4]}

    @pytest.mark.requirement("9b-FR-061")
    def test_list_prepend_strategy(self) -> None:
        """Test list prepend merge strategy."""
        base = {"items": [1, 2]}
        override = {"items": [3, 4]}
        result = deep_merge(base, override, list_strategy="prepend")

        assert result == {"items": [3, 4, 1, 2]}

    @pytest.mark.requirement("9b-FR-061")
    def test_does_not_mutate_inputs(self) -> None:
        """Test that merge does not modify input dictionaries."""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        base_copy = {"a": {"b": 1}}
        override_copy = {"a": {"c": 2}}

        deep_merge(base, override)

        assert base == base_copy
        assert override == override_copy

    @pytest.mark.requirement("9b-FR-061")
    def test_type_mismatch_override_wins(self) -> None:
        """Test that override wins when types don't match."""
        base = {"a": {"b": 1}}
        override = {"a": "string"}
        result = deep_merge(base, override)

        assert result == {"a": "string"}

    @pytest.mark.requirement("9b-FR-061")
    def test_helm_values_merge(self) -> None:
        """Test realistic Helm values merge scenario."""
        defaults = {
            "dagster": {
                "enabled": True,
                "replicas": 1,
                "resources": {"requests": {"cpu": "100m", "memory": "256Mi"}},
            }
        }
        env_override = {
            "dagster": {
                "replicas": 3,
                "resources": {"requests": {"cpu": "500m"}},
            }
        }
        result = deep_merge(defaults, env_override)

        assert result["dagster"]["enabled"] is True
        assert result["dagster"]["replicas"] == 3
        assert result["dagster"]["resources"]["requests"]["cpu"] == "500m"
        assert result["dagster"]["resources"]["requests"]["memory"] == "256Mi"


class TestMergeAll:
    """Tests for merge_all function."""

    @pytest.mark.requirement("9b-FR-061")
    def test_merge_multiple_dicts(self) -> None:
        """Test merging multiple dictionaries in order."""
        d1 = {"a": 1, "b": 1}
        d2 = {"b": 2, "c": 2}
        d3 = {"c": 3, "d": 3}
        result = merge_all(d1, d2, d3)

        assert result == {"a": 1, "b": 2, "c": 3, "d": 3}

    @pytest.mark.requirement("9b-FR-061")
    def test_merge_empty_list(self) -> None:
        """Test merging empty list returns empty dict."""
        result = merge_all()
        assert result == {}

    @pytest.mark.requirement("9b-FR-061")
    def test_merge_single_dict(self) -> None:
        """Test merging single dict returns copy."""
        d = {"a": 1}
        result = merge_all(d)

        assert result == {"a": 1}
        assert result is not d  # Should be a copy


class TestFlattenDict:
    """Tests for flatten_dict function."""

    @pytest.mark.requirement("9b-FR-061")
    def test_flatten_simple(self) -> None:
        """Test flattening simple nested dict."""
        nested = {"a": {"b": 1}}
        result = flatten_dict(nested)

        assert result == {"a.b": 1}

    @pytest.mark.requirement("9b-FR-061")
    def test_flatten_deep(self) -> None:
        """Test flattening deeply nested dict."""
        nested = {"dagster": {"webserver": {"replicas": 2}}}
        result = flatten_dict(nested)

        assert result == {"dagster.webserver.replicas": 2}

    @pytest.mark.requirement("9b-FR-061")
    def test_flatten_with_list(self) -> None:
        """Test flattening dict with list values."""
        nested = {"items": [1, 2, 3]}
        result = flatten_dict(nested)

        assert result == {"items[0]": 1, "items[1]": 2, "items[2]": 3}

    @pytest.mark.requirement("9b-FR-061")
    def test_flatten_mixed(self) -> None:
        """Test flattening mixed structure."""
        nested = {"a": 1, "b": {"c": 2}, "d": [3, 4]}
        result = flatten_dict(nested)

        assert result == {"a": 1, "b.c": 2, "d[0]": 3, "d[1]": 4}


class TestUnflattenDict:
    """Tests for unflatten_dict function."""

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_simple(self) -> None:
        """Test unflattening simple dot-notation."""
        flat = {"a.b": 1}
        result = unflatten_dict(flat)

        assert result == {"a": {"b": 1}}

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_deep(self) -> None:
        """Test unflattening deep dot-notation."""
        flat = {"dagster.webserver.replicas": 2}
        result = unflatten_dict(flat)

        assert result == {"dagster": {"webserver": {"replicas": 2}}}

    @pytest.mark.requirement("9b-FR-061")
    def test_roundtrip(self) -> None:
        """Test that flatten and unflatten are inverses."""
        original = {"dagster": {"webserver": {"replicas": 2, "memory": "1Gi"}}}
        flat = flatten_dict(original)
        result = unflatten_dict(flat)

        assert result == original

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_with_list_indices(self) -> None:
        """Test unflattening with list index notation."""
        flat = {"items[0]": "first", "items[1]": "second", "items[2]": "third"}
        result = unflatten_dict(flat)

        assert result == {"items": ["first", "second", "third"]}

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_nested_list_with_dict(self) -> None:
        """Test unflattening nested structure with lists containing dicts."""
        flat = {
            "servers[0].host": "server1",
            "servers[0].port": 8080,
            "servers[1].host": "server2",
            "servers[1].port": 9090,
        }
        result = unflatten_dict(flat)

        assert result == {
            "servers": [
                {"host": "server1", "port": 8080},
                {"host": "server2", "port": 9090},
            ]
        }

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_mixed_structure(self) -> None:
        """Test unflattening complex mixed structure."""
        flat = {
            "config.name": "test",
            "config.items[0]": 1,
            "config.items[1]": 2,
            "nested.deep.value": "deep",
        }
        result = unflatten_dict(flat)

        assert result == {
            "config": {"name": "test", "items": [1, 2]},
            "nested": {"deep": {"value": "deep"}},
        }

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_custom_separator(self) -> None:
        """Test unflattening with custom separator."""
        flat = {"a/b/c": 1}
        result = unflatten_dict(flat, sep="/")

        assert result == {"a": {"b": {"c": 1}}}

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_extend_list_with_gaps(self) -> None:
        """Test unflattening extends list when indices have gaps."""
        flat = {"items[0]": "first", "items[3]": "fourth"}
        result = unflatten_dict(flat)

        # Should create None entries for gaps
        assert result["items"][0] == "first"
        assert result["items"][1] is None
        assert result["items"][2] is None
        assert result["items"][3] == "fourth"

    @pytest.mark.requirement("9b-FR-061")
    def test_flatten_with_nested_list_dicts(self) -> None:
        """Test flattening list containing dictionaries."""
        nested = {"items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}
        result = flatten_dict(nested)

        assert result == {
            "items[0].name": "a",
            "items[0].value": 1,
            "items[1].name": "b",
            "items[1].value": 2,
        }

    @pytest.mark.requirement("9b-FR-061")
    def test_flatten_custom_separator(self) -> None:
        """Test flattening with custom separator."""
        nested = {"a": {"b": {"c": 1}}}
        result = flatten_dict(nested, sep="/")

        assert result == {"a/b/c": 1}

    @pytest.mark.requirement("9b-FR-061")
    def test_flatten_empty_dict(self) -> None:
        """Test flattening empty dictionary."""
        result = flatten_dict({})
        assert result == {}

    @pytest.mark.requirement("9b-FR-061")
    def test_unflatten_empty_dict(self) -> None:
        """Test unflattening empty dictionary."""
        result = unflatten_dict({})
        assert result == {}
