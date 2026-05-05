"""Unit tests for DataFrame-backed Great Expectations validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import QualityCheck, QualitySuite

if TYPE_CHECKING:
    from floe_quality_gx import GreatExpectationsPlugin


def test_create_dataframe_from_connection_accepts_pandas_dataframe() -> None:
    """DataFrame connection configs return equivalent data as a defensive copy."""
    from floe_quality_gx.executor import create_dataframe_from_connection

    source_df = pd.DataFrame(
        {
            "customer_id": [1, 2, 3],
            "status": ["active", "pending", "active"],
        }
    )

    result = create_dataframe_from_connection(
        {"dialect": "pandas", "dataframe": source_df},
        table_name="customers",
    )

    pd.testing.assert_frame_equal(result, source_df)
    assert result is not source_df

    result.loc[0, "status"] = "inactive"
    assert source_df.loc[0, "status"] == "active"


@pytest.mark.parametrize(
    "connection_config",
    [
        {"dialect": "pandas", "dataframe": [{"customer_id": 1}]},
        {"dialect": "dataframe", "dataframe": "not a dataframe"},
        {"dataframe": None},
    ],
)
def test_create_dataframe_from_connection_rejects_non_dataframe_values(
    connection_config: dict[str, Any],
) -> None:
    """DataFrame connection configs require a pandas DataFrame value."""
    from floe_quality_gx.executor import create_dataframe_from_connection

    with pytest.raises(
        TypeError,
        match=r"connection_config\['dataframe'\] must be a pandas DataFrame",
    ):
        create_dataframe_from_connection(connection_config, table_name="customers")


def test_run_suite_validates_supplied_dataframe(
    gx_plugin: GreatExpectationsPlugin,
) -> None:
    """run_suite validates a pandas DataFrame supplied in connection_config."""
    source_df = pd.DataFrame(
        {
            "customer_id": [1, 2, 3],
            "email": ["a@example.com", "b@example.com", "c@example.com"],
            "status": ["active", "pending", "active"],
        }
    )
    suite = QualitySuite(
        model_name="customers",
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
                name="status_values_in_set",
                type="values_in_set",
                column="status",
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.WARNING,
                parameters={"value_set": ["active", "pending"]},
            ),
            QualityCheck(
                name="row_count_between",
                type="row_count_between",
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
                parameters={"min_value": 3, "max_value": 3},
            ),
        ],
    )

    result = gx_plugin.run_suite(
        suite,
        {"dialect": "pandas", "dataframe": source_df},
    )

    assert result.suite_name == "customers_suite"
    assert result.model_name == "customers"
    assert result.summary["total"] == 4
    assert result.summary["passed"] == 4
    assert result.summary["failed"] == 0
    assert [check.check_name for check in result.checks] == [
        "customer_id_not_null",
        "customer_id_unique",
        "status_values_in_set",
        "row_count_between",
    ]
    assert all(check.passed for check in result.checks)
    assert result.checks[0].records_checked == 3
