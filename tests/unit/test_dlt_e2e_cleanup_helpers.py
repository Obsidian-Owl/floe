"""Regression tests for dlt E2E namespace cleanup helpers."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "tests.e2e.test_customer360_dlt_ingestion",
        "tests.e2e.test_dlt_ingestion_format_matrix",
    ],
)
def test_dlt_namespace_cleanup_drops_metadata_without_purge(module_name: str) -> None:
    """dlt E2E cleanup must not require Polaris purge to be enabled."""
    module = importlib.import_module(module_name)
    events: list[str] = []

    class Catalog:
        def list_tables(self, namespace: str) -> list[tuple[str, str]]:
            events.append(f"list:{namespace}")
            return [(namespace, "raw_customers")]

        def drop_table(self, identifier: str, purge_requested: bool = False) -> None:
            events.append(f"drop_table:{identifier}:{purge_requested}")

        def purge_table(self, identifier: str) -> None:
            events.append(f"purge_table:{identifier}")
            raise AssertionError("purge_table must not be used")

        def drop_namespace(self, namespace: str) -> None:
            events.append(f"drop_namespace:{namespace}")

    module._purge_namespace(Catalog(), "dlt_test_namespace")

    assert events == [
        "list:dlt_test_namespace",
        "drop_table:dlt_test_namespace.raw_customers:False",
        "drop_namespace:dlt_test_namespace",
    ]


@pytest.mark.parametrize(
    "module_name",
    [
        "tests.e2e.test_customer360_dlt_ingestion",
        "tests.e2e.test_dlt_ingestion_format_matrix",
    ],
)
def test_dlt_namespace_cleanup_supports_catalogs_without_purge_flag(module_name: str) -> None:
    """Cleanup still works with PyIceberg clients that expose drop_table(identifier)."""
    module = importlib.import_module(module_name)
    events: list[str] = []

    class Catalog:
        def list_tables(self, namespace: str) -> list[tuple[str, str]]:
            events.append(f"list:{namespace}")
            return [(namespace, "raw_customers")]

        def drop_table(self, identifier: str) -> None:
            events.append(f"drop_table:{identifier}")

        def drop_namespace(self, namespace: str) -> None:
            events.append(f"drop_namespace:{namespace}")

    module._purge_namespace(Catalog(), "dlt_test_namespace")

    assert events == [
        "list:dlt_test_namespace",
        "drop_table:dlt_test_namespace.raw_customers",
        "drop_namespace:dlt_test_namespace",
    ]
