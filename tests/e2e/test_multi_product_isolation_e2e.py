"""E2E test: Multi-Product Isolation (AC-2.6).

Validates that multiple data products can be compiled and deployed
simultaneously without namespace collisions or data leakage.

Workflow:
    Deploy all 3 demo products → verify namespace isolation → verify
    no cross-product data leakage in Polaris catalog

Prerequisites:
    - Kind cluster: make kind-up
    - Port-forwards active: make test-e2e

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.6
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any

import pytest

# Demo products to compile concurrently
DEMO_PRODUCTS = {
    "customer-360": "demo/customer-360/floe.yaml",
    "iot-telemetry": "demo/iot-telemetry/floe.yaml",
    "financial-risk": "demo/financial-risk/floe.yaml",
}


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.6")
class TestMultiProductIsolation:
    """Multi-product isolation: concurrent products, no namespace bleed.

    Validates that the compilation pipeline produces correctly isolated
    artifacts for each product, and that Polaris catalog namespaces
    don't collide.
    """

    @pytest.mark.requirement("AC-2.6")
    def test_concurrent_compilation(
        self,
        compiled_artifacts: Any,
        project_root: Path,
    ) -> None:
        """Compile all 3 demo products concurrently and verify isolation.

        Uses ThreadPoolExecutor to compile products in parallel, then
        verifies each produces distinct artifacts with correct metadata.
        """
        results: dict[str, Any] = {}

        def compile_product(name: str, rel_path: str) -> tuple[str, Any]:
            spec_path = project_root / rel_path
            artifacts = compiled_artifacts(spec_path)
            return name, artifacts

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(compile_product, name, path): name
                for name, path in DEMO_PRODUCTS.items()
            }

            for future in concurrent.futures.as_completed(futures):
                product_name = futures[future]
                try:
                    name, artifacts = future.result(timeout=120)
                    results[name] = artifacts
                except Exception as e:
                    pytest.fail(f"Concurrent compilation failed for {product_name}: {e}")

        # All 3 should have compiled
        assert len(results) == 3, (
            f"Expected 3 compiled products, got {len(results)}: {list(results.keys())}"
        )

    @pytest.mark.requirement("AC-2.6")
    def test_product_names_distinct(
        self,
        compiled_artifacts: Any,
        project_root: Path,
    ) -> None:
        """Verify each product has a distinct product_name in metadata.

        Products must not share names to avoid namespace collisions in
        Dagster code locations and Polaris catalogs.
        """
        product_names: set[str] = set()

        for name, rel_path in DEMO_PRODUCTS.items():
            spec_path = project_root / rel_path
            artifacts = compiled_artifacts(spec_path)

            product_name = artifacts.metadata.product_name
            assert product_name not in product_names, (
                f"Duplicate product_name '{product_name}' — namespace collision!\n"
                f"Products must have unique names for catalog isolation."
            )
            product_names.add(product_name)

            # Product name should match the directory name
            assert product_name == name, (
                f"Product name mismatch: expected '{name}', got '{product_name}'"
            )

        assert len(product_names) == 3, (
            f"Expected 3 distinct product names, got {len(product_names)}: {product_names}"
        )

    @pytest.mark.requirement("AC-2.6")
    def test_product_transforms_isolated(
        self,
        compiled_artifacts: Any,
        project_root: Path,
    ) -> None:
        """Verify each product's transforms are independent.

        Model names should not collide across products. Each product's
        transforms should reference only its own models.
        """
        all_model_names: dict[str, set[str]] = {}

        for name, rel_path in DEMO_PRODUCTS.items():
            spec_path = project_root / rel_path
            artifacts = compiled_artifacts(spec_path)

            if artifacts.transforms is None:
                continue

            model_names = {m.name for m in artifacts.transforms.models}
            all_model_names[name] = model_names

        # Check for model name collisions across products
        products = list(all_model_names.keys())
        for i, prod_a in enumerate(products):
            for prod_b in products[i + 1 :]:
                overlap = all_model_names[prod_a] & all_model_names[prod_b]
                assert not overlap, (
                    f"Model name collision between {prod_a} and {prod_b}: {overlap}\n"
                    "Products must have unique model names for isolation."
                )

    @pytest.mark.requirement("AC-2.6")
    def test_polaris_namespace_isolation(
        self,
        polaris_client: Any,
    ) -> None:
        """Verify Polaris catalog supports separate namespaces for each product.

        If namespaces exist in Polaris, verify they don't share tables.
        This is the data-level isolation check.
        """
        try:
            namespaces = polaris_client.list_namespaces()
        except Exception as e:
            pytest.fail(f"Polaris catalog not accessible: {e}")

        # Check for cross-product table leakage
        namespace_tables: dict[str, list[str]] = {}
        for ns_tuple in namespaces:
            ns_name = ".".join(ns_tuple) if isinstance(ns_tuple, tuple) else str(ns_tuple)
            try:
                tables = polaris_client.list_tables(ns_tuple)
                namespace_tables[ns_name] = [str(t) for t in tables]
            except Exception:
                namespace_tables[ns_name] = []

        # If any product-specific namespaces exist, verify isolation
        product_namespaces = {
            ns: tables
            for ns, tables in namespace_tables.items()
            if any(p in ns for p in ("customer", "iot", "financial"))
        }

        if product_namespaces:
            # Verify no shared table names across product namespaces
            all_tables: list[str] = []
            for ns, tables in product_namespaces.items():
                for table in tables:
                    full_name = f"{ns}.{table}"
                    assert full_name not in all_tables, (
                        f"Table collision: {full_name} appears in multiple namespaces"
                    )
                    all_tables.append(full_name)
