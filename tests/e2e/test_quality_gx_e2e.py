"""E2E tests for Great Expectations validation against real Iceberg data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import QualityCheck, QualitySuite
from floe_quality_gx import GreatExpectationsPlugin

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.polaris import rewrite_table_io_for_host_access


@pytest.mark.e2e
@pytest.mark.requirement("W3-QUALITY-GX")
class TestGreatExpectationsIcebergE2E(IntegrationTestBase):
    """E2E validation for GX checks over Customer 360 Iceberg data."""

    required_services: ClassVar[list[str]] = ["polaris", "minio"]

    def _load_customer_360_dataframe(self, polaris_client: Any) -> Any:
        """Load the Customer 360 mart table from Iceberg as a pandas DataFrame."""
        namespace = "customer_360"
        table_name = "mart_customer_360"
        tables = polaris_client.list_tables(namespace)
        table_names = [table[-1] if isinstance(table, tuple | list) else table for table in tables]
        assert table_name in table_names, (
            f"Expected Iceberg table {namespace}.{table_name} to exist. "
            f"Available tables in {namespace}: {tables}"
        )

        table = polaris_client.load_table(f"{namespace}.{table_name}")
        rewrite_table_io_for_host_access(table)
        dataframe = table.scan().to_arrow().to_pandas()
        assert not dataframe.empty, f"Expected {namespace}.{table_name} to contain rows"
        return dataframe

    @pytest.mark.parametrize("dbt_pipeline_result", ["customer-360"], indirect=True)
    def test_gx_plugin_validates_real_customer_360_iceberg_data(
        self,
        dbt_pipeline_result: tuple[str, Path],
        polaris_client: Any,
    ) -> None:
        """Validate real Customer 360 Iceberg data through Great Expectations."""
        product, _project_dir = dbt_pipeline_result
        assert product == "customer-360"
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        dataframe = self._load_customer_360_dataframe(polaris_client)
        row_count = len(dataframe)
        assert row_count == 500, (
            "Customer 360 mart should have one row per raw customer; "
            f"expected 500 rows, got {row_count}"
        )

        suite = QualitySuite(
            model_name="mart_customer_360",
            timeout_seconds=60,
            checks=[
                QualityCheck(
                    name="customer_id_not_null",
                    type="not_null",
                    column="customer_id",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheck(
                    name="customer_id_unique",
                    type="unique",
                    column="customer_id",
                    dimension=Dimension.CONSISTENCY,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheck(
                    name="segment_values",
                    type="values_in_set",
                    column="segment",
                    dimension=Dimension.VALIDITY,
                    severity=SeverityLevel.WARNING,
                    parameters={
                        "value_set": [
                            "enterprise",
                            "mid_market",
                            "smb",
                            "startup",
                            "unknown",
                        ]
                    },
                ),
                QualityCheck(
                    name="row_count_bounds",
                    type="row_count_between",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                    parameters={"min_value": 500, "max_value": 500},
                ),
            ],
        )

        result = GreatExpectationsPlugin().run_suite(
            suite,
            {"dialect": "pandas", "dataframe": dataframe},
        )

        assert result.suite_name == "mart_customer_360_suite"
        assert result.model_name == "mart_customer_360"
        assert result.passed is True
        assert result.summary["total"] == 4
        assert result.summary["passed"] == 4
        assert result.summary["failed"] == 0

        check_names = {check.check_name for check in result.checks}
        assert check_names == {
            "customer_id_not_null",
            "customer_id_unique",
            "segment_values",
            "row_count_bounds",
        }
        assert all(check.passed for check in result.checks)

        checks_by_name = {check.check_name: check for check in result.checks}
        customer_id_not_null = checks_by_name["customer_id_not_null"]
        assert customer_id_not_null.records_checked == row_count
        assert customer_id_not_null.records_failed == 0
