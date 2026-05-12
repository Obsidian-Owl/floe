"""Unit coverage for Dagster launch retry classification."""

from __future__ import annotations

from typing import Any

import pytest

import testing.fixtures.dagster_retry as dagster_retry

pytestmark = pytest.mark.requirement("LIVE-VALIDATION")


def test_launch_retry_classifies_dagster_postgres_connection_reset() -> None:
    """Dagster launch HTTP 500 caused by PostgreSQL connection loss is infra-transient."""
    assert dagster_retry.is_transient_dagster_storage_launch_error(
        500,
        {
            "data": {
                "launchRun": {
                    "__typename": "PythonError",
                    "message": (
                        "sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) "
                        "server closed the connection unexpectedly"
                    ),
                }
            }
        },
    )


def test_launch_retry_rejects_non_postgres_python_errors() -> None:
    """Product Python errors must not be retried as infrastructure failures."""
    assert not dagster_retry.is_transient_dagster_storage_launch_error(
        500,
        {
            "data": {
                "launchRun": {
                    "__typename": "PythonError",
                    "message": "dbt failed to compile model stg_crm_customers",
                }
            }
        },
    )


def test_launch_retry_rejects_non_500_responses() -> None:
    """Only Dagster launch HTTP 500 metadata-store failures are retryable."""
    assert not dagster_retry.is_transient_dagster_storage_launch_error(
        400,
        {
            "data": {
                "launchRun": {
                    "__typename": "PythonError",
                    "message": "server closed the connection unexpectedly",
                }
            }
        },
    )


def test_launch_retry_attempts_once_after_transient_storage_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launch helper retries once after the narrow Dagster/PostgreSQL failure."""
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def json(self) -> dict[str, Any]:
            return self._payload

    responses = iter(
        [
            FakeResponse(
                500,
                {
                    "data": {
                        "launchRun": {
                            "__typename": "PythonError",
                            "message": (
                                "psycopg2.OperationalError: server closed the connection "
                                "unexpectedly"
                            ),
                        }
                    }
                },
            ),
            FakeResponse(
                200,
                {
                    "data": {
                        "launchRun": {
                            "__typename": "LaunchRunSuccess",
                            "run": {"runId": "run-123", "status": "STARTING"},
                        }
                    }
                },
            ),
        ]
    )

    def fake_post(*_args: Any, **kwargs: Any) -> FakeResponse:
        calls.append(kwargs)
        return next(responses)

    waits: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_wait_for_delay(*args: Any, **kwargs: Any) -> None:
        waits.append((args, kwargs))

    monkeypatch.setattr(dagster_retry.httpx, "post", fake_post)
    monkeypatch.setattr(dagster_retry, "wait_for_delay", fake_wait_for_delay)

    response = dagster_retry.launch_dagster_run_with_storage_retry(
        "http://dagster",
        "mutation",
        {"executionParams": {}},
    )

    assert response.status_code == 200
    assert len(calls) == 2
    assert waits == [
        (
            (dagster_retry.DAGSTER_STORAGE_RETRY_DELAY_SECONDS,),
            {"description": "Dagster metadata storage retry backoff"},
        )
    ]
