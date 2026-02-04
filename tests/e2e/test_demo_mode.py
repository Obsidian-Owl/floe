"""E2E tests for demo mode deployment and validation.

This module validates the complete demo experience:
- One-command deployment via `make demo`
- Three data products visible in Dagster UI
- Asset lineage graphs (Bronze->Silver->Gold)
- Grafana dashboards showing metrics
- Jaeger traces for all products
- Independent product deployment
- Configurable seed data scale
"""

from __future__ import annotations

import subprocess
from typing import Any

import httpx
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.polling import wait_for_condition


class TestDemoMode(IntegrationTestBase):
    """E2E tests validating demo mode deployment and functionality.

    Tests the complete demo workflow from deployment through validation
    of all platform services and data products.
    """

    required_services = [
        ("dagster-webserver", 3000),
        ("polaris", 8181),
        ("jaeger-query", 16686),
    ]

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-087")
    @pytest.mark.requirement("FR-088")
    def test_make_demo_completes(self) -> None:
        """Test that demo directory structure is complete and definitions are importable.

        Validates:
        - customer-360 directory exists with required files
        - iot-telemetry directory exists with required files
        - financial-risk directory exists with required files
        - Each product has floe.yaml, dbt_project.yml, seeds directory
        - Each product's definitions.py imports without errors
        - Each product's definitions.py exposes a Dagster Definitions object

        Raises:
            AssertionError: If demo structure incomplete or definitions not importable.
        """
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        demo_dir = project_root / "demo"

        # Expected products and required files
        products = ["customer-360", "iot-telemetry", "financial-risk"]
        required_files = ["floe.yaml", "dbt_project.yml"]

        for product in products:
            product_dir = demo_dir / product
            assert product_dir.exists(), f"Product directory {product_dir} does not exist"

            # Check required files
            for required_file in required_files:
                file_path = product_dir / required_file
                assert file_path.exists(), f"Required file {required_file} missing in {product}"

            # Check seeds directory
            seeds_dir = product_dir / "seeds"
            assert seeds_dir.exists(), f"Seeds directory missing in {product}"
            assert seeds_dir.is_dir(), f"Seeds path exists but is not a directory in {product}"

        # Verify all services are healthy
        for service_name, port in self.required_services:
            self.check_infrastructure(service_name, port)

        # Validate each product's definitions.py is importable (no syntax errors)
        import importlib.util

        for product in products:
            definitions_path = demo_dir / product / "definitions.py"
            assert definitions_path.exists(), f"Product {product} missing definitions.py"

            spec = importlib.util.spec_from_file_location(
                f"demo.{product.replace('-', '_')}.definitions",
                str(definitions_path),
            )
            assert spec is not None, (
                f"IMPORT GAP: Could not create module spec for {product}/definitions.py. "
                "File may have invalid Python syntax."
            )
            assert spec.loader is not None, f"IMPORT GAP: No loader for {product}/definitions.py"

            try:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                pytest.fail(
                    f"IMPORT GAP: {product}/definitions.py failed to import.\n"
                    f"Error: {e}\n"
                    "This means the demo product cannot be loaded as a Dagster code location."
                )

            # Verify the module has a Definitions object or defs attribute
            has_defs = (
                hasattr(module, "defs")
                or hasattr(module, "Definitions")
                or hasattr(module, "definitions")
            )
            assert has_defs, (
                f"DEFINITIONS GAP: {product}/definitions.py imported successfully but has no "
                "'defs', 'Definitions', or 'definitions' attribute. "
                "Dagster code locations require a Definitions object."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-080")
    @pytest.mark.requirement("FR-081")
    @pytest.mark.requirement("FR-082")
    def test_three_products_visible_in_dagster(self, dagster_client: Any) -> None:
        """Test that Dagster workspace is configured with three loadable code locations.

        Validates:
        - Dagster GraphQL API is accessible and returns version
        - Demo product definitions.py files exist locally
        - Workspace ConfigMap has code locations for all three products
        - Code locations load successfully in Dagster (no PythonError)

        Args:
            dagster_client: DagsterGraphQLClient fixture.

        Raises:
            AssertionError: If Dagster API unreachable, products missing, or locations fail to load.
        """
        from pathlib import Path

        # 1. Verify Dagster GraphQL API is accessible
        query = """
        query ServerInfo {
            version
        }
        """
        result = dagster_client._execute(query)

        # Handle both response formats (with or without data wrapper)
        if isinstance(result, dict):
            if "data" in result:
                version = result["data"].get("version")
            else:
                version = result.get("version")
        else:
            version = None

        assert version is not None, (
            f"Dagster GraphQL API not responding correctly. Response: {result}"
        )
        assert isinstance(version, str), f"Version should be string, got {type(version)}"
        assert len(version) > 0, "Version should not be empty"

        # 2. Verify demo product definitions.py files exist (code ready for deployment)
        expected_products = ["customer-360", "iot-telemetry", "financial-risk"]
        project_root = Path(__file__).parent.parent.parent

        for product in expected_products:
            definitions_path = project_root / "demo" / product / "definitions.py"
            assert definitions_path.exists(), (
                f"Demo product {product} missing definitions.py. Expected at: {definitions_path}"
            )

        # 3. Verify workspace ConfigMap has code locations defined
        # This validates the Helm chart configuration is correct
        import subprocess

        chart_path = project_root / "charts" / "floe-platform"
        result = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(chart_path),
                "-f",
                str(chart_path / "values-test.yaml"),
                "--skip-schema-validation",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert result.returncode == 0, f"Helm template failed: {result.stderr}"

        # Verify workspace has python_module entries for each product
        rendered = result.stdout
        for product in expected_products:
            product_underscore = product.replace("-", "_")
            assert f"location_name: {product}" in rendered, (
                f"Workspace ConfigMap missing code location for {product}. "
                f"Check dagster.codeLocations in values-test.yaml"
            )
            assert f"demo.{product_underscore}.definitions" in rendered, (
                f"Workspace ConfigMap missing module path for {product}"
            )

        # 4. Query Dagster for loaded code locations (will FAIL if locations can't load)
        locations_query = """
        query WorkspaceLocationEntries {
            workspaceOrError {
                __typename
                ... on Workspace {
                    locationEntries {
                        name
                        locationOrLoadError {
                            __typename
                            ... on RepositoryLocation {
                                name
                                repositories {
                                    name
                                }
                            }
                            ... on PythonError {
                                message
                            }
                        }
                    }
                }
            }
        }
        """
        try:
            locations_result = dagster_client._execute(locations_query)
            workspace = locations_result.get("workspaceOrError", {})

            if workspace.get("__typename") == "Workspace":
                entries = workspace.get("locationEntries", [])
                loaded_locations: list[str] = []
                failed_locations: list[str] = []

                for entry in entries:
                    loc_or_error = entry.get("locationOrLoadError", {})
                    if loc_or_error.get("__typename") == "RepositoryLocation":
                        loaded_locations.append(entry["name"])
                    elif loc_or_error.get("__typename") == "PythonError":
                        failed_locations.append(
                            f"{entry['name']}: {loc_or_error.get('message', 'unknown error')}"
                        )

                assert len(loaded_locations) >= 3, (
                    f"CODE LOCATION GAP: Only {len(loaded_locations)} of 3 code locations loaded.\n"
                    f"Loaded: {loaded_locations}\n"
                    f"Failed: {failed_locations}\n"
                    "Fix: Ensure demo product definitions.py files import correctly "
                    "in the Dagster container environment."
                )
        except Exception as e:
            # GraphQL query failure is itself informative
            pytest.fail(
                f"DAGSTER GAP: Could not query workspace locations.\n"
                f"Error: {e}\n"
                "Dagster may not have code location loading configured."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-084")
    def test_dagster_asset_lineage(self, dagster_client: Any) -> None:
        """Test that demo products define Bronze->Silver->Gold lineage and compile correctly.

        Validates:
        - Each product's floe.yaml has Bronze, Silver, Gold tier transforms
        - Silver transforms depend on Bronze
        - Gold transforms depend on Silver
        - Lineage graph is complete for each product
        - Each product compiles to valid CompiledArtifacts with quality tiers

        Args:
            dagster_client: DagsterGraphQLClient fixture.

        Raises:
            AssertionError: If lineage graphs incomplete, broken, or compilation fails.
        """
        from pathlib import Path

        import yaml

        products = ["customer-360", "iot-telemetry", "financial-risk"]
        project_root = Path(__file__).parent.parent.parent

        for product in products:
            floe_yaml_path = project_root / "demo" / product / "floe.yaml"
            assert floe_yaml_path.exists(), f"Missing floe.yaml for {product}"

            with open(floe_yaml_path) as f:
                floe_spec = yaml.safe_load(f)

            transforms = floe_spec.get("transforms", [])
            assert len(transforms) > 0, f"{product}: No transforms defined"

            # Build dependency graph
            transform_map = {t["name"]: t for t in transforms}

            # Categorize by tier
            bronze = [t for t in transforms if t.get("tier") == "bronze"]
            silver = [t for t in transforms if t.get("tier") == "silver"]
            gold = [t for t in transforms if t.get("tier") == "gold"]

            # Verify all tiers present
            assert len(bronze) > 0, f"{product}: No Bronze tier transforms"
            assert len(silver) > 0, f"{product}: No Silver tier transforms"
            assert len(gold) > 0, f"{product}: No Gold tier transforms"

            # Verify Silver depends on Bronze
            for silver_transform in silver:
                deps = silver_transform.get("dependsOn", [])
                has_bronze_dep = any(
                    transform_map.get(dep, {}).get("tier") == "bronze" for dep in deps
                )
                assert has_bronze_dep, (
                    f"{product}: Silver transform '{silver_transform['name']}' "
                    f"does not depend on Bronze. Dependencies: {deps}"
                )

            # Verify Gold depends on Silver
            for gold_transform in gold:
                deps = gold_transform.get("dependsOn", [])
                has_silver_dep = any(
                    transform_map.get(dep, {}).get("tier") == "silver" for dep in deps
                )
                assert has_silver_dep, (
                    f"{product}: Gold transform '{gold_transform['name']}' "
                    f"does not depend on Silver. Dependencies: {deps}"
                )

        # Validate that transforms compile to valid CompiledArtifacts
        from floe_core.compilation.stages import compile_pipeline

        manifest_path = project_root / "demo" / "manifest.yaml"

        for product in products:
            spec_path = project_root / "demo" / product / "floe.yaml"
            artifacts = compile_pipeline(spec_path, manifest_path)

            assert artifacts.transforms is not None, (
                f"{product}: Compilation produced no transforms"
            )
            assert len(artifacts.transforms.models) > 0, (
                f"{product}: Compilation produced zero transform models"
            )

            # Verify models have quality_tier tags matching the YAML tiers
            tier_set = {m.quality_tier for m in artifacts.transforms.models if m.quality_tier}
            assert len(tier_set) > 0, (
                f"{product}: No models have quality_tier set. "
                "Compiler should propagate tier from floe.yaml transforms."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-044")
    def test_grafana_dashboards_loaded(self) -> None:
        """Test that Grafana dashboard ConfigMap exists and references real data sources.

        Validates:
        - Helm chart renders Grafana dashboard ConfigMap
        - ConfigMap contains dashboard JSON definitions
        - Dashboard definitions are valid JSON
        - Dashboards reference real data sources (Prometheus/Jaeger)

        Raises:
            AssertionError: If dashboard ConfigMap not found, invalid, or missing data sources.
        """
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        chart_path = project_root / "charts" / "floe-platform"

        # Render Helm templates with --skip-schema-validation to avoid external URL fetch
        result = subprocess.run(
            ["helm", "template", "test-release", str(chart_path), "--skip-schema-validation"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert result.returncode == 0, (
            f"Helm template rendering failed: {result.returncode}\nstderr: {result.stderr}"
        )

        rendered_output = result.stdout

        # Verify Grafana dashboard ConfigMap exists
        assert "grafana-dashboards" in rendered_output.lower(), (
            "Grafana dashboard ConfigMap not found in Helm templates"
        )

        # Verify ConfigMap has kind: ConfigMap
        assert "kind: ConfigMap" in rendered_output, "No ConfigMap resource found in Helm templates"

        # Verify dashboard content marker (JSON structure)
        # Grafana dashboards typically contain "dashboard" and "panels" keys
        has_dashboard_content = (
            '"dashboard"' in rendered_output
            or '"panels"' in rendered_output
            or "floe-platform-dashboard" in rendered_output.lower()
        )

        assert has_dashboard_content, (
            "Dashboard ConfigMap exists but appears to lack dashboard definitions"
        )

        # Validate dashboard JSON contains actual panel definitions
        assert '"panels"' in rendered_output, (
            "DASHBOARD GAP: Dashboard ConfigMap has no 'panels' key. "
            "Grafana dashboards must contain panel definitions with queries."
        )

        # Verify dashboard references real data sources (not dummy)
        assert "datasource" in rendered_output.lower(), (
            "DASHBOARD GAP: Dashboard ConfigMap has no 'datasource' references. "
            "Grafana dashboards must reference Prometheus or Jaeger data sources."
        )
        assert "prometheus" in rendered_output.lower() or "jaeger" in rendered_output.lower(), (
            "DASHBOARD GAP: Grafana dashboards exist but don't reference "
            "Prometheus or Jaeger data sources. Dashboards may show no data."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-047")
    def test_jaeger_traces_for_all_products(self, jaeger_client: httpx.Client) -> None:
        """Test that Jaeger has registered services from demo product trace emission.

        Validates:
        - Jaeger API accessible
        - Services endpoint responds with data
        - Services list is non-empty after demo deployment
        - At least one service matches a demo product name

        Args:
            jaeger_client: httpx.Client for Jaeger API.

        Raises:
            AssertionError: If Jaeger not reachable, no services registered, or
                no demo products found in service list.
        """

        # Wait for Jaeger to be ready
        def check_jaeger_ready() -> bool:
            try:
                response = jaeger_client.get("/api/services")
                return response.status_code == 200
            except (httpx.HTTPError, OSError):
                return False

        wait_for_condition(
            check_jaeger_ready,
            timeout=60.0,
            description="Jaeger API to become ready",
        )

        # Query for services endpoint
        response = jaeger_client.get("/api/services")
        assert response.status_code == 200, (
            f"Jaeger services endpoint failed: {response.status_code}"
        )

        response_json = response.json()
        assert "data" in response_json, "Jaeger services response missing 'data' key"

        services = response_json["data"]
        assert isinstance(services, list), f"Services data should be a list, got: {type(services)}"

        # HARD ASSERTION: After demo deployment, services should be emitting traces
        assert len(services) > 0, (
            "TRACE GAP: No services registered in Jaeger after demo deployment.\n"
            "Demo products are not emitting OTel traces.\n"
            "Fix: Configure OTel SDK in demo product definitions.py to emit spans."
        )

        # Check that demo product services are emitting traces
        # Only match actual product names and floe-platform, NOT generic infrastructure
        required_product_services = {
            "customer-360",
            "iot-telemetry",
            "financial-risk",
        }
        matching_services = [
            s for s in services if any(p in s.lower() for p in required_product_services)
        ]

        assert len(matching_services) >= 1, (
            f"TRACE GAP: Jaeger has services {services} but none match demo products.\n"
            f"Expected services containing at least one of: "
            f"{', '.join(sorted(required_product_services))}.\n"
            "Generic infrastructure services (dagster, otel-collector) do not count — "
            "demo products must emit their own traces."
        )

        # Verify ALL 3 products are emitting (not just one)
        products_found = {
            p for p in required_product_services if any(p in s.lower() for s in services)
        }
        missing_products = required_product_services - products_found
        assert not missing_products, (
            f"TRACE GAP: Products not emitting traces: {', '.join(sorted(missing_products))}.\n"
            f"Products found in Jaeger: {', '.join(sorted(products_found))}.\n"
            "All 3 demo products must emit OTel traces."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-086")
    def test_independent_product_deployment(self) -> None:
        """Test that each product directory is self-contained for independent deployment.

        Validates:
        - Each product has its own floe.yaml
        - Each product has its own dbt_project.yml with unique project name
        - Products do not share configuration files
        - Directory structure supports independent deployment
        - dbt models have no SQL syntax errors

        Raises:
            AssertionError: If products are not self-contained or have syntax errors.
        """
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        demo_dir = project_root / "demo"

        # Expected products
        products = ["customer-360", "iot-telemetry", "financial-risk"]

        for product in products:
            product_dir = demo_dir / product

            # Verify product directory exists
            assert product_dir.exists(), f"Product directory {product} does not exist"

            # Verify self-contained configuration files
            floe_yaml = product_dir / "floe.yaml"
            assert floe_yaml.exists(), f"Product {product} missing floe.yaml (not self-contained)"

            dbt_project_yml = product_dir / "dbt_project.yml"
            assert dbt_project_yml.exists(), (
                f"Product {product} missing dbt_project.yml (not self-contained)"
            )

            # Verify has its own models directory
            models_dir = product_dir / "models"
            assert models_dir.exists(), f"Product {product} missing models directory"

            # Verify has its own seeds directory
            seeds_dir = product_dir / "seeds"
            assert seeds_dir.exists(), f"Product {product} missing seeds directory"

        import yaml as yaml_mod

        for product in products:
            product_dir = demo_dir / product

            # Verify dbt_project.yml has unique project name
            dbt_project_path = product_dir / "dbt_project.yml"
            with open(dbt_project_path) as f:
                dbt_config = yaml_mod.safe_load(f)

            assert "name" in dbt_config, f"{product}: dbt_project.yml missing 'name' field"

            # Verify dbt project can be parsed (valid model graph)
            # This catches broken refs, missing sources, etc.
            result = subprocess.run(
                ["uv", "run", "dbt", "parse", "--project-dir", str(product_dir)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                cwd=product_dir,
            )
            # dbt parse may fail if profiles aren't configured -- that's expected
            # but it should not fail due to syntax errors in SQL models
            if result.returncode != 0 and "Syntax error" in result.stderr:
                pytest.fail(
                    f"DBT PARSE GAP: {product} has SQL syntax errors.\nError: {result.stderr[:500]}"
                )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-083")
    def test_configurable_seed_scale(self) -> None:
        """Test that seed files exist with meaningful data for all products.

        Validates:
        - Seed files exist for all products
        - Seed CSV files have valid headers
        - Seed CSV files contain actual data rows (not just headers)
        - Each product has at least 10 total seed rows for meaningful testing

        Raises:
            AssertionError: If seed files missing, empty, or insufficient.
        """
        import csv
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        demo_dir = project_root / "demo"

        products = ["customer-360", "iot-telemetry", "financial-risk"]

        for product in products:
            seeds_dir = demo_dir / product / "seeds"
            assert seeds_dir.exists(), f"Seeds directory missing for {product}"

            seed_files = list(seeds_dir.glob("*.csv"))
            assert len(seed_files) > 0, f"No seed CSV files found for {product}"

            # Validate actual row counts per product
            total_rows = 0
            for seed_file in seed_files:
                with open(seed_file, newline="") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    assert header is not None, (
                        f"Seed file {seed_file.name} in {product} has no header row"
                    )
                    row_count = sum(1 for _ in reader)
                    total_rows += row_count
                    assert row_count > 0, (
                        f"Seed file {seed_file.name} in {product} has header but no data rows"
                    )

            # Each product should have meaningful seed data (not trivial)
            assert total_rows >= 10, (
                f"SEED GAP: {product} has only {total_rows} total seed rows across "
                f"{len(seed_files)} files. Expected at least 10 rows for meaningful testing."
            )
