"""Tests for launching the Customer 360 demo through Dagster GraphQL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from testing.demo.customer360_runner import (
    Customer360DagsterRunner,
    RunnerError,
    default_graphql_client,
)


class FakeDagsterGraphQL:
    """GraphQL fake that records requests and returns queued responses."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((url, payload))
        if not self.responses:
            raise AssertionError("Unexpected GraphQL request")
        return self.responses.pop(0)


def _write_manifest(path: Path, *, dagster_url: str = "http://dagster.example") -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "validation": {
                    "namespace": "floe-dev",
                    "urls": {"dagster": dagster_url},
                    "dagster": {
                        "job_name": "customer-360",
                        "run_tags": {
                            "floe.demo": "customer-360",
                            "floe.validation": "alpha",
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.requirement("alpha-demo")
def test_customer360_runner_discovers_repository_and_launches_configured_job(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Runner derives URL/job from validation.yaml and discovers Dagster internals."""
    manifest = tmp_path / "validation.yaml"
    _write_manifest(manifest)
    graphql = FakeDagsterGraphQL(
        [
            {
                "data": {
                    "repositoriesOrError": {
                        "__typename": "RepositoryConnection",
                        "nodes": [
                            {
                                "name": "__repository__",
                                "location": {"name": "customer_360"},
                                "pipelines": [{"name": "customer-360"}],
                                "jobs": [{"name": "customer-360"}],
                            }
                        ],
                    }
                }
            },
            {
                "data": {
                    "launchPipelineExecution": {
                        "__typename": "LaunchRunSuccess",
                        "run": {"runId": "run-123"},
                    }
                }
            },
            {
                "data": {
                    "runOrError": {
                        "__typename": "Run",
                        "runId": "run-123",
                        "status": "SUCCESS",
                    }
                }
            },
        ]
    )

    result = Customer360DagsterRunner(graphql_client=graphql, sleep=lambda _: None).run(manifest)

    assert result.status == "PASS"
    assert result.run_id == "run-123"
    assert result.job_name == "customer-360"
    assert capsys.readouterr().out.splitlines() == [
        "status=PASS",
        "dagster.run_id=run-123",
        "dagster.job_name=customer-360",
    ]

    assert [url for url, _payload in graphql.requests] == [
        "http://dagster.example/graphql",
        "http://dagster.example/graphql",
        "http://dagster.example/graphql",
    ]
    launch_payload = graphql.requests[1][1]
    selector = launch_payload["variables"]["executionParams"]["selector"]
    assert selector == {
        "repositoryLocationName": "customer_360",
        "repositoryName": "__repository__",
        "pipelineName": "customer-360",
    }
    assert "tags" not in launch_payload["variables"]["executionParams"]
    assert launch_payload["variables"]["executionParams"]["executionMetadata"]["tags"] == [
        {"key": "floe.demo", "value": "customer-360"},
        {"key": "floe.validation", "value": "alpha"},
    ]


@pytest.mark.requirement("alpha-demo")
def test_customer360_runner_fails_clearly_when_configured_job_is_absent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing Dagster job reports the job, URL, and next diagnostic command."""
    manifest = tmp_path / "validation.yaml"
    _write_manifest(manifest, dagster_url="http://localhost:3100")
    graphql = FakeDagsterGraphQL(
        [
            {
                "data": {
                    "repositoriesOrError": {
                        "__typename": "RepositoryConnection",
                        "nodes": [
                            {
                                "name": "__repository__",
                                "location": {"name": "customer_360"},
                                "pipelines": [{"name": "other-job"}],
                                "jobs": [{"name": "other-job"}],
                            }
                        ],
                    }
                }
            }
        ]
    )

    with pytest.raises(RunnerError, match="Dagster job was not found"):
        Customer360DagsterRunner(graphql_client=graphql, sleep=lambda _: None).run(manifest)

    assert capsys.readouterr().out.splitlines() == [
        "status=FAIL",
        "dagster.url=http://localhost:3100",
        "dagster.job_name=customer-360",
        "diagnostic=kubectl logs -n floe-dev deployment/floe-platform-dagster-webserver",
        "error=Dagster job was not found",
    ]


@pytest.mark.requirement("alpha-demo")
def test_customer360_runner_prints_deterministic_failure_for_graphql_transport_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Transport failures are surfaced as Customer 360 failure evidence, not tracebacks."""
    manifest = tmp_path / "validation.yaml"
    _write_manifest(manifest, dagster_url="http://localhost:3100")

    def broken_graphql(_url: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise RunnerError("Dagster GraphQL request failed: connection refused")

    with pytest.raises(RunnerError, match="connection refused"):
        Customer360DagsterRunner(graphql_client=broken_graphql, sleep=lambda _: None).run(manifest)

    assert capsys.readouterr().out.splitlines() == [
        "status=FAIL",
        "dagster.url=http://localhost:3100",
        "dagster.job_name=customer-360",
        "diagnostic=kubectl logs -n floe-dev deployment/floe-platform-dagster-webserver",
        "error=Dagster GraphQL request failed: connection refused",
    ]


@pytest.mark.requirement("alpha-demo")
def test_default_graphql_client_wraps_http_errors_as_runner_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP failures from Dagster GraphQL are normalized before CLI handling."""
    request = httpx.Request("POST", "http://dagster.example/graphql")
    response = httpx.Response(503, request=request, text="unavailable")

    def post(_url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        del json, timeout
        return response

    monkeypatch.setattr(httpx, "post", post)

    with pytest.raises(RunnerError, match="Dagster GraphQL request failed"):
        default_graphql_client("http://dagster.example/graphql", {"query": "{}"})


@pytest.mark.requirement("alpha-demo")
def test_default_graphql_client_wraps_invalid_json_as_runner_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid Dagster GraphQL JSON responses are normalized before CLI handling."""
    request = httpx.Request("POST", "http://dagster.example/graphql")
    response = httpx.Response(200, request=request, text="not json")

    def post(_url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        del json, timeout
        return response

    monkeypatch.setattr(httpx, "post", post)

    with pytest.raises(RunnerError, match="Dagster GraphQL returned invalid JSON"):
        default_graphql_client("http://dagster.example/graphql", {"query": "{}"})
