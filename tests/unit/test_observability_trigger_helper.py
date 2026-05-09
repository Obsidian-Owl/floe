"""Regression tests for E2E observability trigger helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from tests.e2e import conftest as e2e_conftest


def test_trigger_lineage_run_waits_for_marquez_after_launch_timeout() -> None:
    """Dagster launch timeouts may still enqueue a run; wait for lineage proof."""
    marquez_client = MagicMock()
    before_run_ids = {"existing-run"}

    with (
        patch.object(
            e2e_conftest,
            "_discover_repo_for_asset",
            return_value=("repo", "location", ["stg_crm_customers"], "__ASSET_JOB"),
        ),
        patch.object(e2e_conftest.httpx, "post", side_effect=httpx.ReadTimeout("slow")),
        patch.object(
            e2e_conftest,
            "_wait_for_fresh_completed_marquez_run",
            return_value=True,
        ) as wait_for_fresh_run,
    ):
        e2e_conftest._trigger_lineage_run(
            lambda *_args, **_kwargs: None,
            marquez_client,
            expected_namespace="customer-360",
            expected_job_name="customer-360",
            before_run_ids=before_run_ids,
        )

    wait_for_fresh_run.assert_called_once_with(
        marquez_client,
        namespace="customer-360",
        job_name="customer-360",
        before_run_ids=before_run_ids,
        timeout=e2e_conftest._DAGSTER_LAUNCH_TIMEOUT_MARQUEZ_GRACE_SECONDS,
    )
