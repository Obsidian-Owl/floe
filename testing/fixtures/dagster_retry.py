"""Dagster GraphQL retry helpers for validation tests."""

from __future__ import annotations

import os
from typing import Any

import httpx

from testing.fixtures.polling import wait_for_delay

DAGSTER_STORAGE_RETRY_DELAY_SECONDS = float(
    os.environ.get("FLOE_E2E_DAGSTER_STORAGE_RETRY_DELAY_SECONDS", "10")
)
DAGSTER_STORAGE_ERROR_MARKERS = (
    "psycopg2.operationalerror",
    "sqlalchemy.exc.operationalerror",
)


def is_transient_dagster_storage_launch_error(
    status_code: int,
    payload: dict[str, Any],
) -> bool:
    """Identify Dagster launch failures caused by transient metadata DB loss."""
    if status_code != 500:
        return False

    launch_result = payload.get("data", {}).get("launchRun", {})
    if launch_result.get("__typename") != "PythonError":
        return False

    message = str(launch_result.get("message", "")).lower()
    return "server closed the connection unexpectedly" in message and any(
        marker in message for marker in DAGSTER_STORAGE_ERROR_MARKERS
    )


def launch_dagster_run_with_storage_retry(
    dagster_url: str,
    mutation: str,
    variables: dict[str, Any],
    *,
    attempts: int = 2,
) -> httpx.Response:
    """Launch a Dagster run, retrying only the known metadata-store transient."""
    response: httpx.Response | None = None
    for attempt in range(attempts):
        response = httpx.post(
            f"{dagster_url}/graphql",
            json={"query": mutation, "variables": variables},
            timeout=30.0,
        )
        try:
            payload = response.json()
        except ValueError:
            return response
        if not is_transient_dagster_storage_launch_error(response.status_code, payload):
            return response
        if attempt < attempts - 1:
            wait_for_delay(
                DAGSTER_STORAGE_RETRY_DELAY_SECONDS,
                description="Dagster metadata storage retry backoff",
            )

    assert response is not None
    return response
