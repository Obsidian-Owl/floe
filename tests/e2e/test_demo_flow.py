"""End-to-end test for demo pipeline workflow.

This test validates that features work together as an integrated system,
not just in isolation. It exercises the full compile → deploy → run cycle.

Requirements Covered:
- E2E-001: Full pipeline workflow validation
- E2E-002: Platform services integration
- E2E-003: Catalog integration

Per testing standards: Tests FAIL when infrastructure is unavailable.
No pytest.skip() - see .claude/rules/testing-standards.md
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase


class TestDemoFlow(IntegrationTestBase):
    """E2E tests for the demo data pipeline.

    These tests validate the complete floe platform workflow:
    1. Compile a floe.yaml specification
    2. Deploy compiled artifacts to orchestrator
    3. Trigger pipeline execution
    4. Validate outputs exist and are correct

    Requires all platform services running:
    - Dagster (orchestrator)
    - Polaris (catalog)
    - LocalStack (S3-compatible storage)
    """

    # Services required for E2E tests
    required_services: ClassVar[list[tuple[str, int]]] = [
        ("dagster", 3000),
        ("polaris", 8181),
        ("localstack", 4566),
    ]

    @pytest.mark.e2e
    @pytest.mark.requirement("E2E-001")
    def test_compile_deploy_run_validates(self, e2e_namespace: str) -> None:
        """Test complete pipeline: compile → deploy → run → validate.

        This is the canonical E2E test that validates the entire floe
        platform works as an integrated system.

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("localstack", 4566)

        # TODO: Epic 13 - Implement E2E pipeline tests
        # When implementing, replace this fail with actual test logic:
        #
        # 1. Compile demo/floe.yaml
        #    artifacts = compile_floe_spec("demo/floe.yaml")
        #
        # 2. Deploy artifacts to Dagster
        #    deploy_to_dagster(artifacts, namespace=e2e_namespace)
        #
        # 3. Trigger pipeline run
        #    run_id = trigger_pipeline("demo_pipeline")
        #
        # 4. Poll for completion
        #    status = poll_for_completion(run_id, timeout=300)
        #
        # 5. Validate outputs exist
        #    assert status == "SUCCESS"
        #    assert output_table_exists(f"{e2e_namespace}.customers")

        pytest.fail(
            "E2E test not yet implemented.\n"
            "Track: Epic 13 - E2E Testing Infrastructure\n"
            "This test validates the full compile → deploy → run cycle."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("E2E-002")
    def test_platform_services_healthy(self) -> None:
        """Test that all platform services are reachable and healthy.

        This is a smoke test to verify E2E infrastructure is working
        before running more complex workflow tests.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("localstack", 4566)

        # TODO: Epic 13 - Implement health check test
        # When implementing, replace this fail with actual test logic:
        #
        # 1. Check Dagster health endpoint
        #    assert dagster_client.health_check()
        #
        # 2. Check Polaris catalog accessible
        #    assert polaris_catalog.ping()
        #
        # 3. Check S3 (LocalStack) accessible
        #    assert s3_client.list_buckets()

        pytest.fail(
            "E2E health check test not yet implemented.\n"
            "Track: Epic 13 - E2E Testing Infrastructure\n"
            "This test validates all platform services are healthy."
        )


class TestCatalogIntegration(IntegrationTestBase):
    """E2E tests for catalog integration across the platform."""

    required_services: ClassVar[list[tuple[str, int]]] = [
        ("dagster", 3000),
        ("polaris", 8181),
        ("localstack", 4566),
    ]

    @pytest.mark.e2e
    @pytest.mark.requirement("E2E-003")
    def test_table_registration_and_discovery(self, e2e_namespace: str) -> None:
        """Test that tables created via dbt are discoverable in catalog.

        Validates the integration between:
        - dbt (creates Iceberg tables)
        - Polaris (catalogs tables)
        - Dagster (orchestrates the workflow)

        Args:
            e2e_namespace: Unique namespace for test isolation.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("polaris", 8181)
        self.check_infrastructure("localstack", 4566)

        # TODO: Epic 13 - Implement catalog integration test
        # When implementing, replace this fail with actual test logic:
        #
        # 1. Run dbt model that creates a table
        # 2. Verify table appears in Polaris catalog
        # 3. Verify table is queryable via Iceberg

        pytest.fail(
            "E2E catalog integration test not yet implemented.\n"
            "Track: Epic 13 - E2E Testing Infrastructure\n"
            f"Namespace: {e2e_namespace}"
        )
